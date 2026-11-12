"""Calculate and plot regional drought stripes from monthly ERA5 data.

Run with:
    pixi run python drought_stripes.py INDEX ACCUMULATION_WINDOW REGION
    pixi run python drought_stripes.py INDEX ACCUMULATION_WINDOW \
        --shapefile regions/example.shp --id biome_id=1
"""

import argparse
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from zipfile import is_zipfile, ZipFile

import cdsapi
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
import pandas as pd
import regionmask
from scipy import stats
from shapely.geometry import box
from shapely.ops import unary_union
import xarray as xr


ERA5_START = pd.Timestamp("1940-01-01")
REFERENCE_START = pd.Timestamp("1991-01-01")
REFERENCE_END = pd.Timestamp("2020-12-01")
DATA_DIR = Path("data")
OUTPUT_DIR = Path("figures")

STRIPE_COLORS = [
    "#663300",
    "#8c6640",
    "#b29980",
    "#d9ccbf",
    "#ffffff",
    "#ccd9bf",
    "#99b280",
    "#668c40",
    "#336600",
]
STRIPE_LEVELS = [-10, -2, -1.5, -1, -0.1, 0.1, 1, 1.5, 2, 10]


def get_continent_country_mapping():
    return {
        "Europe": ["Albania", "Andorra", "Austria", "Belarus", "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Kosovo", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta", "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia", "Norway", "Poland", "Portugal", "Romania", "San Marino", "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Ukraine", "United Kingdom", "Vatican"],
        "Africa": ["Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi", "Cameroon", "Cape Verde", "Central African Republic", "Chad", "Comoros", "Congo", "Democratic Republic of the Congo", "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia", "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Ivory Coast", "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius", "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria", "Rwanda", "Sao Tome and Principe", "Senegal", "Seychelles", "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan", "Tanzania", "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe"],
        "Asia": ["Afghanistan", "Armenia", "Azerbaijan", "Bahrain", "Bangladesh", "Bhutan", "Brunei", "Cambodia", "China", "Georgia", "India", "Indonesia", "Iran", "Iraq", "Israel", "Japan", "Jordan", "Kazakhstan", "Kuwait", "Kyrgyzstan", "Laos", "Lebanon", "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal", "North Korea", "Oman", "Pakistan", "Palestine", "Philippines", "Qatar", "Saudi Arabia", "Singapore", "South Korea", "Sri Lanka", "Syria", "Tajikistan", "Thailand", "Timor-Leste", "Turkey", "Turkmenistan", "United Arab Emirates", "Uzbekistan", "Vietnam", "Yemen"],
        "North America": ["Antigua and Barbuda", "Bahamas", "Barbados", "Belize", "Canada", "Costa Rica", "Cuba", "Dominica", "Dominican Republic", "El Salvador", "Grenada", "Guatemala", "Haiti", "Honduras", "Jamaica", "Mexico", "Nicaragua", "Panama", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Trinidad and Tobago", "United States of America"],
        "South America": ["Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador", "Guyana", "Paraguay", "Peru", "Suriname", "Uruguay", "Venezuela"],
        "Oceania": ["Australia", "Fiji", "Kiribati", "Marshall Islands", "Micronesia", "Nauru", "New Zealand", "Palau", "Papua New Guinea", "Samoa", "Solomon Islands", "Tonga", "Tuvalu", "Vanuatu"],
        "Antarctica": ["Antarctica"],
    }


def get_region(region_name, shapefile, feature_id):
    """Return a WGS84 geometry and descriptive label from one supported input mode."""
    if shapefile:
        if not feature_id or "=" not in feature_id:
            raise ValueError("Shapefile input requires --id FIELD=VALUE.")
        field, value = feature_id.split("=", 1)
        features = gpd.read_file(shapefile).to_crs("EPSG:4326")
        if field not in features:
            raise ValueError(f"Field '{field}' is not in {shapefile}. Available fields: {', '.join(features.columns)}")
        selected = features[features[field].astype(str) == value]
        if selected.empty:
            raise ValueError(f"No feature in {shapefile} has {field}={value!r}.")
        return unary_union(selected.geometry), f"{Path(shapefile).stem}_{field}_{value}"

    countries = regionmask.defined_regions.natural_earth_v5_1_2.countries_110
    custom_regions = {
        "global": [-180, 180, -90, 90],
        "C3S_Europe": [-25, 40, 34, 72],
        "C3S_Southwestern_Europe": [-25, 15, 34, 45],
        "C3S_Northwestern_Europe": [-25, 15, 45, 72],
        "C3S_Southeastern_Europe": [15, 40, 34, 45],
        "C3S_Northeastern_Europe": [15, 40, 45, 72],
        "C3S_Central_Europe": [2, 24, 45, 55],
    }
    mapping = get_continent_country_mapping()
    if region_name in custom_regions:
        west, east, south, north = custom_regions[region_name]
        return box(west, south, east, north), region_name
    requested_countries = mapping.get(region_name, [region_name])
    missing = [name for name in requested_countries if name not in countries.names]
    if missing:
        raise ValueError(f"Unknown region '{region_name}'. Use a Natural Earth country, a continent, a C3S region, or --shapefile.")
    geometries = [countries.regions[countries.names.index(name)].polygon for name in requested_countries]
    return unary_union(geometries), region_name


def download_era5(dates, geometry, destination, include_pet):
    """Download ERA5 monthly means of daily precipitation, PET, and land fraction."""
    west, south, east, north = geometry.bounds
    variables = ["total_precipitation", "land_sea_mask"]
    if include_pet:
        variables.append("potential_evaporation")
    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": variables,
        "year": sorted({f"{date.year:04d}" for date in dates}),
        "month": sorted({f"{date.month:02d}" for date in dates}),
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [north, west, south, east],
    }
    print(f"Downloading ERA5 monthly data: {dates[0]:%Y-%m} to {dates[-1]:%Y-%m}")
    cdsapi.Client().retrieve("reanalysis-era5-single-levels-monthly-means", request).download(str(destination))


def collapse_expver(dataset):
    """Combine ERA5 and ERA5T values when CDS returns a split expver dimension."""
    if "expver" not in dataset.dims:
        return dataset
    combined = dataset.isel(expver=0, drop=True)
    for index in range(1, dataset.sizes["expver"]):
        combined = combined.combine_first(dataset.isel(expver=index, drop=True))
    return combined


def get_variable(dataset, *names):
    for name in names:
        if name in dataset:
            return dataset[name]
    raise ValueError(f"ERA5 response is missing {names[0]!r}. Available variables: {', '.join(dataset.data_vars)}")


def open_era5_response(path):
    """Load a direct NetCDF response or merge NetCDF members from a CDS ZIP."""
    if not is_zipfile(path):
        with xr.open_dataset(path) as dataset:
            return dataset.load()

    with TemporaryDirectory(prefix="drought_stripes_") as temporary_directory:
        temporary_path = Path(temporary_directory)
        datasets = []
        with ZipFile(path) as archive:
            netcdf_members = [member for member in archive.infolist() if member.filename.endswith(".nc")]
            if not netcdf_members:
                raise ValueError(f"No NetCDF files found in CDS download: {path}")
            for number, member in enumerate(netcdf_members):
                extracted_path = temporary_path / f"era5_{number}.nc"
                with archive.open(member) as source, extracted_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
                with xr.open_dataset(extracted_path) as dataset:
                    loaded = dataset.load()
                time_name = "valid_time" if "valid_time" in loaded.coords else "time"
                monthly_time = pd.to_datetime(loaded[time_name].values).to_period("M").to_timestamp()
                datasets.append(loaded.assign_coords({time_name: monthly_time}))
        return xr.merge(datasets, compat="no_conflicts", join="exact", combine_attrs="override")


def prepare_regional_series(path, geometry, include_pet):
    """Return regional monthly precipitation or water balance in millimetres."""
    data = collapse_expver(open_era5_response(path))
    coordinate_names = {
        name: replacement
        for name, replacement in {
            "latitude": "lat",
            "longitude": "lon",
            "valid_time": "time",
        }.items()
        if name in data.coords
    }
    data = data.rename(coordinate_names).sortby("time")
    data = data.assign_coords(time=pd.to_datetime(data.time.values).to_period("M").to_timestamp())
    precipitation = get_variable(data, "total_precipitation", "tp").clip(min=0)
    land_fraction = get_variable(data, "land_sea_mask", "lsm")
    region = regionmask.Regions([geometry]).mask(data.lon, data.lat).notnull()
    valid = region & (land_fraction >= 0.5)
    weights = np.cos(np.deg2rad(data.lat)).broadcast_like(precipitation).where(valid, 0)

    days = xr.DataArray(
        pd.DatetimeIndex(data.time.values).days_in_month,
        coords={"time": data.time},
        dims="time",
    )
    precipitation = 1000 * days * precipitation
    regional_precipitation = precipitation.weighted(weights).mean(("lat", "lon"))
    if not include_pet:
        return regional_precipitation.to_pandas().rename("precipitation_mm")

    potential_evaporation = (-get_variable(data, "potential_evaporation", "pev")).clip(min=0)
    potential_evaporation = 1000 * days * potential_evaporation
    regional_pet = potential_evaporation.weighted(weights).mean(("lat", "lon"))
    return (regional_precipitation - regional_pet).to_pandas().rename("water_balance_mm")


def calculate_standardized_index(series, index, window, reference_start, reference_end):
    """Fit a distribution per calendar month and return the standardized index."""
    accumulated = series.rolling(window=window, min_periods=window).sum()
    standardized = pd.Series(np.nan, index=accumulated.index, name=f"{index}{window}")
    reference = accumulated.loc[reference_start:reference_end]

    for month in range(1, 13):
        month_values = accumulated[accumulated.index.month == month]
        reference_values = reference[reference.index.month == month].dropna()
        if len(reference_values) < 5:
            raise ValueError(f"Reference period contains fewer than five valid values for month {month}.")

        if index == "spei":
            shape, location, scale = stats.genlogistic.fit(reference_values.to_numpy())
            probabilities = stats.genlogistic.cdf(month_values, shape, loc=location, scale=scale)
        else:
            positive_reference = reference_values[reference_values > 0]
            if len(positive_reference) < 5:
                raise ValueError(f"Reference period contains fewer than five positive precipitation values for month {month}.")
            zero_probability = 1 - len(positive_reference) / len(reference_values)
            shape, location, scale = stats.gamma.fit(positive_reference.to_numpy(), floc=0)
            probabilities = zero_probability + (1 - zero_probability) * stats.gamma.cdf(
                month_values,
                shape,
                loc=location,
                scale=scale,
            )
            probabilities = np.where(month_values == 0, zero_probability / 2, probabilities)

        probabilities = np.clip(probabilities, np.finfo(float).eps, 1 - np.finfo(float).eps)
        standardized.loc[month_values.index] = stats.norm.ppf(probabilities)

    return standardized


def plot_stripes(index_values, title, destination):
    """Plot one full-height colored stripe for each selected index value."""
    colormap = ListedColormap(STRIPE_COLORS)
    colormap.set_bad("#d9d9d9")
    normalization = BoundaryNorm(STRIPE_LEVELS, colormap.N)
    figure, axis = plt.subplots(figsize=(24, 4))
    axis.imshow(
        np.ma.masked_invalid(index_values.to_numpy()[np.newaxis, :]),
        aspect="auto",
        cmap=colormap,
        norm=normalization,
        interpolation="nearest",
    )
    axis.set_title(title)
    axis.set_axis_off()
    figure.savefig(destination.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0)
    figure.savefig(destination.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0)
    plt.close(figure)


parser = argparse.ArgumentParser(description="Calculate and plot regional drought stripes from monthly ERA5 data.")
parser.add_argument("index", type=str.lower, choices=["spi", "spei"], help="Drought index: SPI or SPEI.")
parser.add_argument("accumulation_window", type=int, help="Accumulation window in months.")
parser.add_argument("region", nargs="?", help="Natural Earth country, continent, or hardcoded C3S region.")
parser.add_argument("--shapefile", type=Path, help="Polygon shapefile to use instead of REGION.")
parser.add_argument("--id", dest="feature_id", help="Shapefile selection in FIELD=VALUE form.")
parser.add_argument("--start", type=pd.Timestamp, default=ERA5_START, help="First stripe month, YYYY-MM (default: 1940-01).")
parser.add_argument("--end", type=pd.Timestamp, help="Last stripe month, YYYY-MM (default: previous month).")
parser.add_argument("--reference-start", type=pd.Timestamp, default=REFERENCE_START, help="Reference-period start, YYYY-MM (default: 1991-01).")
parser.add_argument("--reference-end", type=pd.Timestamp, default=REFERENCE_END, help="Reference-period end, YYYY-MM (default: 2020-12).")
parser.add_argument("--plot_timesteps", choices=["monthly", "annual"], default="monthly", help="Plot every month or one selected month per year (default: monthly).")
parser.add_argument("--plot_month", type=int, choices=range(1, 13), default=12, help="Calendar month used with --plot_timesteps annual (default: 12).")
arguments = parser.parse_args()

if bool(arguments.region) == bool(arguments.shapefile):
    parser.error("Provide exactly one REGION or --shapefile PATH.")
if arguments.accumulation_window < 1:
    parser.error("ACCUMULATION_WINDOW must be at least 1.")

try:
    geometry, region_label = get_region(arguments.region, arguments.shapefile, arguments.feature_id)
except ValueError as error:
    parser.error(str(error))
region_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", region_label)

start = arguments.start.to_period("M").to_timestamp()
previous_month = pd.Timestamp.today().to_period("M").to_timestamp() - pd.DateOffset(months=1)
end = arguments.end.to_period("M").to_timestamp() if arguments.end else previous_month
reference_start = arguments.reference_start.to_period("M").to_timestamp()
reference_end = arguments.reference_end.to_period("M").to_timestamp()
if start < ERA5_START:
    parser.error(f"--start must not be before {ERA5_START:%Y-%m}.")
if start > end:
    parser.error("--start must not be after --end.")
if end > previous_month:
    parser.error("--end must not be after the previous month.")
if reference_start > reference_end:
    parser.error("--reference-start must not be after --reference-end.")
if reference_start < ERA5_START or reference_end > previous_month:
    parser.error(f"The reference period must be within {ERA5_START:%Y-%m} and {previous_month:%Y-%m}.")

first_required = min(start, reference_start) - pd.DateOffset(months=arguments.accumulation_window - 1)
first_required = max(first_required, ERA5_START)
last_required = max(end, reference_end)
dates = list(pd.date_range(first_required, last_required, freq="MS"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
prefix = f"{arguments.index.upper()}{arguments.accumulation_window}_{start:%Y%m}_{end:%Y%m}_{region_label}"
era5_path = DATA_DIR / f"ERA5_{first_required:%Y%m}_{last_required:%Y%m}_{region_label}_{arguments.index}.nc"
if era5_path.exists():
    print(f"Using existing download: {era5_path}")
else:
    download_era5(dates, geometry, era5_path, arguments.index == "spei")

regional_series = prepare_regional_series(era5_path, geometry, arguments.index == "spei")
missing_months = pd.date_range(first_required, last_required, freq="MS").difference(regional_series.index)
if len(missing_months):
    raise ValueError(f"ERA5 response is missing {len(missing_months)} requested month(s), starting with {missing_months[0]:%Y-%m}.")
index_values = calculate_standardized_index(
    regional_series,
    arguments.index,
    arguments.accumulation_window,
    reference_start,
    reference_end,
)

output = pd.concat([regional_series, index_values], axis=1).loc[start:end]
output.index.name = "date"
csv_path = DATA_DIR / f"{prefix}_drought_stripes.csv"
output.to_csv(csv_path, float_format="%.6f")
if arguments.plot_timesteps == "annual":
    plot_values = output.loc[output.index.month == arguments.plot_month, index_values.name]
    if plot_values.empty:
        raise ValueError(
            f"The output period contains no month {arguments.plot_month} values for annual stripes."
        )
    plot_label = f"annual_month{arguments.plot_month:02d}"
    timestep_title = pd.Timestamp(2000, arguments.plot_month, 1).strftime("%B values")
else:
    plot_values = output[index_values.name]
    plot_label = "monthly"
    timestep_title = "Monthly values"

figure_path = OUTPUT_DIR / f"{prefix}_drought_stripes_{plot_label}"
plot_stripes(
    plot_values,
    f"{arguments.index.upper()}-{arguments.accumulation_window} over {region_label} | {timestep_title}",
    figure_path,
)

print(f"Wrote regional drought-index data: {csv_path}")
print(f"Saved drought stripes: {figure_path.with_suffix('.png')}")
print(f"Saved drought stripes: {figure_path.with_suffix('.pdf')}")
