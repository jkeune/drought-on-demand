"""Download and plot monthly drought area for a continent, country, or shapefile feature.

Run with:
    pixi run python timeseries_area_in_drought.py INDEX ACCUMULATION_WINDOW REGION
    pixi run python timeseries_area_in_drought.py INDEX ACCUMULATION_WINDOW \
        --shapefile regions/example.shp --id biome_id=1
"""

import argparse
import os
from pathlib import Path
import re
import zipfile

import cdsapi
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, YearLocator
import numpy as np
import pandas as pd
import regionmask
from shapely.geometry import box
from shapely.ops import unary_union
import xarray as xr


START_DATE = "1980-01-01"
# A hardcoded three-month buffer avoids requesting consolidated data that is not available yet, filled with intermediate!
CONSOLIDATED_LAG_MONTHS = 3
DATA_DIR = Path("data")
OUTPUT_DIR = Path("figures")
BARREN_MASK_FILE = Path("masks/barren_mask.nc")

colors = {"moderate": "#b29980", "severe": "#8c6640", "extreme": "#663300"}
severities = ["extreme", "severe", "moderate"]
drought_thresholds = {
    "moderate": (-1.5, -1.0),
    "severe": (-2.0, -1.5),
    "extreme": (-np.inf, -2.0),
}

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


def download_dataset(index, accumulation, dates, geometry, dataset_type, destination):
    """Download one CDS product period and combine all returned NetCDF files."""
    if not dates:
        return None
    west, south, east, north = geometry.bounds
    variable_names = {
        "spi": "standardised_precipitation_index",
        "spei": "standardised_precipitation_evapotranspiration_index",
    }
    zip_path = destination.with_suffix(".zip")
    request = {
        "variable": [variable_names[index]],
        "accumulation_period": [str(accumulation)],
        "version": ["1_0"],
        "product_type": ["reanalysis"],
        "dataset_type": [dataset_type],
        "year": sorted({f"{date.year:04d}" for date in dates}),
        "month": sorted({f"{date.month:02d}" for date in dates}),
        "area": [north, west, south, east],
    }
    print(f"Downloading {dataset_type}: {dates[0]:%Y-%m} to {dates[-1]:%Y-%m}")
    cdsapi.Client().retrieve("derived-drought-historical-monthly", request).download(str(zip_path))
    with zipfile.ZipFile(zip_path) as archive:
        netcdf_names = [name for name in archive.namelist() if name.endswith(".nc")]
        if not netcdf_names:
            raise ValueError(f"No NetCDF files found in CDS download: {zip_path}")
        extracted_paths = []
        for number, netcdf_name in enumerate(netcdf_names):
            extracted_path = destination.parent / f"{destination.stem}_{number}.nc"
            with archive.open(netcdf_name) as source, open(extracted_path, "wb") as target:
                target.write(source.read())
            extracted_paths.append(extracted_path)
    datasets = [xr.open_dataset(path) for path in extracted_paths]
    combined = xr.combine_by_coords(datasets, combine_attrs="override")
    combined.to_netcdf(destination)
    combined.close()
    for dataset in datasets:
        dataset.close()
    for extracted_path in extracted_paths:
        extracted_path.unlink()
    zip_path.unlink()
    return destination

#
parser = argparse.ArgumentParser(description="Create a monthly stacked drought-area time series from ERA5-Drought.")
parser.add_argument("index", type=str.lower, choices=["spi", "spei"], help="Drought index: SPI or SPEI.")
parser.add_argument("accumulation_window", type=int, help="Accumulation window in months.")
parser.add_argument("region", nargs="?", help="Natural Earth country, continent, or name of hardcoded regions (e.g., C3S_Central_Europe).")
parser.add_argument("--shapefile", type=Path, help="Polygon shapefile to use instead of REGION.")
parser.add_argument("--id", dest="feature_id", help="Shapefile selection in FIELD=VALUE form.")
parser.add_argument("--start", type=pd.Timestamp, default=pd.Timestamp(START_DATE), help="First month, YYYY-MM (default: 1980-01).")
parser.add_argument("--end", type=pd.Timestamp, help="Last month, YYYY-MM (default: previous month).")
parser.add_argument("--barren_area_masking", choices=["True", "False"], default="True", help="Exclude barren land (default: True).")
arguments = parser.parse_args()
if bool(arguments.region) == bool(arguments.shapefile):
    parser.error("Provide exactly one REGION or --shapefile PATH.")
if arguments.accumulation_window < 1:
    parser.error("ACCUMULATION_WINDOW must be at least 1.")

# define region based on command line inputs
try:
    geometry, region_label = get_region(arguments.region, arguments.shapefile, arguments.feature_id)
except ValueError as error:
    parser.error(str(error))
region_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", region_label)

# define start and end dates (also consolidated and intermediate)
start = arguments.start.to_period("M").to_timestamp()
previous_month = pd.Timestamp.today().to_period("M").to_timestamp() - pd.DateOffset(months=1)
end = arguments.end.to_period("M").to_timestamp() if arguments.end else previous_month
if start > end:
    parser.error("--start must not be after --end.")
if end > previous_month:
    parser.error("--end must not be after the previous month.")
dates = list(pd.date_range(start, end, freq="MS"))
consolidated_end = end - pd.DateOffset(months=CONSOLIDATED_LAG_MONTHS)
consolidated_dates = [date for date in dates if date <= consolidated_end]
intermediate_dates = [date for date in dates if date > consolidated_end]

# download data 
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
prefix = f"{arguments.index.upper()}{arguments.accumulation_window}_{start:%Y%m}_{end:%Y%m}_{region_label}"
files = []
for dataset_type, requested_dates, suffix in [
    ("consolidated_dataset", consolidated_dates, "consolidated"),
    ("intermediate_dataset", intermediate_dates, "intermediate"),
]:
    destination = DATA_DIR / f"{prefix}_{suffix}.nc"
    if requested_dates:
        files.append(destination if destination.exists() else download_dataset(arguments.index, arguments.accumulation_window, requested_dates, geometry, dataset_type, destination))

# read ERA5-Drought data in download folder
datasets = [xr.open_dataset(path) for path in files]
data = xr.combine_by_coords(datasets, combine_attrs="override")

# minor modifications (coordinate names etc)
variable = data[next(iter(data.data_vars))]
coordinate_names = {name: replacement for name, replacement in {"latitude": "lat", "longitude": "lon"}.items() if name in variable.coords}
variable = variable.rename(coordinate_names).sel(time=slice(start, end)).where(variable != -9999)

# mask to region of interest
mask = regionmask.Regions([geometry]).mask(variable.lon, variable.lat).notnull()
if arguments.barren_area_masking == "True":
    if not BARREN_MASK_FILE.exists():
        raise FileNotFoundError(f"Barren mask not found: {BARREN_MASK_FILE}")
    barren_dataset = xr.open_dataset(BARREN_MASK_FILE)
    barren_mask = barren_dataset["barren_mask"].isel(time=0).reindex_like(mask, method="nearest").load()
    barren_dataset.close()
    mask = mask.where(barren_mask != 1)
variable = variable.where(mask)

# calcululate area of each grid cell for proper area weighting
lat_resolution = float(abs(variable.lat[1] - variable.lat[0]))
lon_resolution = float(abs(variable.lon[1] - variable.lon[0]))
earth_radius_km = 6371.0
cell_area = (earth_radius_km ** 2 * np.deg2rad(lon_resolution) * np.abs(np.sin(np.deg2rad(variable.lat + lat_resolution / 2)) - np.sin(np.deg2rad(variable.lat - lat_resolution / 2))))
valid_area = cell_area.where(variable.notnull()).sum(dim=("lat", "lon"))
# calculate area in drought per severity class
output = pd.DataFrame(index=pd.to_datetime(variable.time.values))
for severity, (lower, upper) in drought_thresholds.items():
    drought_area = cell_area.where((variable > lower) & (variable <= upper)).sum(dim=("lat", "lon"))
    output[f"area_{severity}_drought_pct"] = (100 * drought_area / valid_area).to_pandas()
output.index.name = "date"

# write data to csv
output_path = DATA_DIR / f"{prefix}_area_in_drought.csv"
output.to_csv(output_path, float_format="%.6f")

# create figure
figure, axis = plt.subplots(figsize=(12, 4))
bottom = np.zeros(len(output))
for severity in severities:
    values = output[f"area_{severity}_drought_pct"].fillna(0).to_numpy()
    axis.bar(output.index, values, bottom=bottom, width=31, color=colors[severity], label=severity)
    bottom += values
axis.set_title(f"{region_label} area in drought | {arguments.index.upper()}-{arguments.accumulation_window}")
axis.set_ylabel("Area in drought [%]")
axis.set_ylim(0, 100)
axis.xaxis.set_major_locator(YearLocator(5))
axis.xaxis.set_major_formatter(DateFormatter("%Y"))
axis.yaxis.grid(color="lightgray", linewidth=0.6)
axis.set_axisbelow(True)
axis.spines[["top", "right"]].set_visible(False)
axis.legend(ncol=3, loc="upper center")
axis.margins(x=0)
figure.tight_layout()
figure_path = OUTPUT_DIR / f"{prefix}_area_in_drought.png"
figure.savefig(figure_path, dpi=300)
plt.close(figure)
for dataset in datasets:
    dataset.close()

print(f"Wrote drought-area data: {output_path}")
print(f"Saved drought-area plot: {figure_path}")