# Script to download and plot a snapshot of a drought index from ERA5-Drought
#
# Usage: pixi run python map_drought.py INDEX ACCUMULATION YEAR MONTH REGION
# with 
#   INDEX: drought index to download (e.g., SPI, SPEI)
#   ACCUMULATION: accumulation period (e.g., 1, 3, 6 months)
#   YEAR: year of the snapshot
#   MONTH: month of the snapshot
#   REGION: region to plot (continent, country, or custom region)
# REGION can be, e.g., "Europe" but also "C3S_Europe" or "C3S_Central_Europe" etc. 
# Example usage:
# pixi run python map_drought.py SPI 3 2023 7 C3S_Europe


import argparse
import os
import sys
import xarray as xr
import regionmask
import cdsapi
import geopandas as gpd
from pathlib import Path
import re
from shapely.ops import unary_union
import zipfile
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D


BARREN_MASK_FILE = Path("masks/ERA5_barren_w_precip.nc")
PZERO_THRESHOLD = 0.9

def get_continent_country_mapping():
    """
    Returns a dictionary mapping continent names to lists of country names.
    Country names match those in regionmask.defined_regions.natural_earth.
    """
    return {
        'Europe': [
            'Albania', 'Andorra', 'Austria', 'Belarus', 'Belgium', 'Bosnia and Herzegovina',
            'Bulgaria', 'Croatia', 'Cyprus', 'Czechia', 'Denmark', 'Estonia', 'Finland',
            'France', 'Germany', 'Greece', 'Hungary', 'Iceland', 'Ireland', 'Italy',
            'Kosovo', 'Latvia', 'Liechtenstein', 'Lithuania', 'Luxembourg', 'Malta',
            'Moldova', 'Monaco', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway',
            'Poland', 'Portugal', 'Romania', 'San Marino', 'Serbia', 'Slovakia', 'Slovenia',
            'Spain', 'Sweden', 'Switzerland', 'Ukraine', 'United Kingdom', 'Vatican'
        ],
        'Africa': [
            'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi', 'Cameroon',
            'Cape Verde', 'Central African Republic', 'Chad', 'Comoros', 'Congo', 
            'Democratic Republic of the Congo', 'Djibouti', 'Egypt', 'Equatorial Guinea',
            'Eritrea', 'Eswatini', 'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea',
            'Guinea-Bissau', 'Ivory Coast', 'Kenya', 'Lesotho', 'Liberia', 'Libya',
            'Madagascar', 'Malawi', 'Mali', 'Mauritania', 'Mauritius', 'Morocco',
            'Mozambique', 'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Sao Tome and Principe',
            'Senegal', 'Seychelles', 'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan',
            'Sudan', 'Tanzania', 'Togo', 'Tunisia', 'Uganda', 'Zambia', 'Zimbabwe'
        ],
        'Asia': [
            'Afghanistan', 'Armenia', 'Azerbaijan', 'Bahrain', 'Bangladesh', 'Bhutan',
            'Brunei', 'Cambodia', 'China', 'Georgia', 'India', 'Indonesia', 'Iran',
            'Iraq', 'Israel', 'Japan', 'Jordan', 'Kazakhstan', 'Kuwait', 'Kyrgyzstan',
            'Laos', 'Lebanon', 'Malaysia', 'Maldives', 'Mongolia', 'Myanmar', 'Nepal',
            'North Korea', 'Oman', 'Pakistan', 'Palestine', 'Philippines', 'Qatar',
            'Saudi Arabia', 'Singapore', 'South Korea', 'Sri Lanka', 'Syria', 'Tajikistan',
            'Thailand', 'Timor-Leste', 'Turkey', 'Turkmenistan', 'United Arab Emirates',
            'Uzbekistan', 'Vietnam', 'Yemen'
        ],
        'North America': [
            'Antigua and Barbuda', 'Bahamas', 'Barbados', 'Belize', 'Canada', 'Costa Rica',
            'Cuba', 'Dominica', 'Dominican Republic', 'El Salvador', 'Grenada', 'Guatemala',
            'Haiti', 'Honduras', 'Jamaica', 'Mexico', 'Nicaragua', 'Panama',
            'Saint Kitts and Nevis', 'Saint Lucia', 'Saint Vincent and the Grenadines',
            'Trinidad and Tobago', 'United States of America'
        ],
        'South America': [
            'Argentina', 'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Ecuador', 'Guyana',
            'Paraguay', 'Peru', 'Suriname', 'Uruguay', 'Venezuela'
        ],
        'Oceania': [
            'Australia', 'Fiji', 'Kiribati', 'Marshall Islands', 'Micronesia', 'Nauru',
            'New Zealand', 'Palau', 'Papua New Guinea', 'Samoa', 'Solomon Islands',
            'Tonga', 'Tuvalu', 'Vanuatu'
        ],
        'Antarctica': ['Antarctica']
    }

# system arguements
# pixi run python map_drought.py INDEX ACCUMULATION YEAR MONTH REGION
parser = argparse.ArgumentParser(description="Download and plot an ERA5-Drought snapshot.")
parser.add_argument("index", help="Drought index to download, e.g. SPI or SPEI.")
parser.add_argument("accumulation", help="Accumulation period in months.")
parser.add_argument("year", help="Snapshot year.")
parser.add_argument("month", help="Snapshot month.")
parser.add_argument("region", nargs="*", help="Continent or C3S region to plot.")
parser.add_argument("--shapefile", type=Path, help="Polygon shapefile to mask instead of REGION.")
parser.add_argument("--id", dest="feature_id", help="Shapefile selection in FIELD=VALUE form.")
parser.add_argument("--barren_area_masking", choices=["True", "False"], default="True", help="Exclude barren land (default: True).")
parser.add_argument("--significance_masking", choices=["True", "False"], default="False", help="Exclude non-normal index fits (default: False).")
parser.add_argument("--pzero_masking", choices=["True", "False"], default="False", help="For SPI only, exclude high zero-precipitation probability pixels (default: False).")
arguments = parser.parse_args()
index = arguments.index
accumulation = arguments.accumulation
year = arguments.year
month = str(arguments.month).zfill(2)
region = arguments.region
barren_area_masking = arguments.barren_area_masking == "True"
significance_masking = arguments.significance_masking == "True"
pzero_masking = arguments.pzero_masking == "True"
if bool(region) == bool(arguments.shapefile):
    parser.error("Provide at least one REGION or --shapefile PATH, but not both.")
if pzero_masking and index.lower() != "spi":
    parser.error("--pzero_masking is available only for SPI.")

print(f"Running map_drought.py with arguments: INDEX={index}, ACCUMULATION={accumulation}, REGION={region}, YEAR={year}, MONTH={month}")

#%%
# Define region using regionmask (countries or continents)
regions_to_check = region
continent_mapping = get_continent_country_mapping()
custom_regions = {
    "C3S_Europe": [-25, 40, 34, 72],  # west, east, south, north
    "C3S_Southwestern_Europe": [-25, 15, 34, 45],
    "C3S_Northwestern_Europe": [-25, 15, 45, 72],
    "C3S_Southeastern_Europe": [15, 40, 34, 45],
    "C3S_Northeastern_Europe": [15, 40, 45, 72],
    "C3S_Central_Europe": [2, 24, 45, 55],
}
for fixed_region in custom_regions:
    continent_mapping[fixed_region] = continent_mapping["Europe"]

if arguments.shapefile:
    if not arguments.feature_id or "=" not in arguments.feature_id:
        parser.error("Shapefile input requires --id FIELD=VALUE.")
    field, value = arguments.feature_id.split("=", 1)
    features = gpd.read_file(arguments.shapefile).to_crs("EPSG:4326")
    if field not in features:
        parser.error(f"Field '{field}' is not in {arguments.shapefile}. Available fields: {', '.join(features.columns)}")
    selected = features[features[field].astype(str) == value]
    if selected.empty:
        parser.error(f"No feature in {arguments.shapefile} has {field}={value!r}.")
    mask_geometry = unary_union(selected.geometry)
    lon1, lat1, lon2, lat2 = mask_geometry.bounds
    region_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{arguments.shapefile.stem}_{field}_{value}")
else:
    # Use only natural_earth_v5_1_2 for region names
    countries = regionmask.defined_regions.natural_earth_v5_1_2.countries_110
    countries_in_continent = []
    for region_name in regions_to_check:
        if region_name in continent_mapping:
            countries_in_continent.extend(continent_mapping[region_name])
            print(f"Expanding continent '{region_name}' to {len(continent_mapping[region_name])} countries")
        else:
            print(f"Error: '{region_name}' is not a valid continent name")
            print(f"Valid continents: {', '.join(continent_mapping.keys())}")
            sys.exit(1)
    region = countries_in_continent
    all_lons = []
    all_lats = []
    for country_name in region:
        if country_name in countries.names:
            idx = countries.names.index(country_name)
            bounds = countries.regions[idx].bounds
            all_lons.extend([bounds[0], bounds[2]])
            all_lats.extend([bounds[1], bounds[3]])
    if not all_lons or not all_lats:
        print("Error: No valid regions found")
        sys.exit(1)
    lon1, lon2 = min(all_lons), max(all_lons)
    lat1, lat2 = min(all_lats), max(all_lats)
    if len(regions_to_check) == 1 and regions_to_check[0] in custom_regions:
        lon1, lon2, lat1, lat2 = custom_regions[regions_to_check[0]]
        print(f"Using fixed bounds for {regions_to_check[0]}: lat=[{lat1}, {lat2}], lon=[{lon1}, {lon2}]")
    mask_geometry = None
    region_label = "_".join(regions_to_check)

#%% Define dataset to download
# 1 - drought indices 
drought_indices = {
    "spi": {
        "print_name": "SPI",
        "long_name": "Standardized Precipitation Index",
        "variable_name": "standardized_precipitation_index"
    },
    "spei": {
        "print_name": "SPEI",
        "long_name": "Standardized Precipitation Evapotranspiration Index",
        "variable_name": "standardized_precipitation_evapotranspiration_index"
    }
}
# 2 - product type (only reanalysis here)
product_types = ["reanalysis"]

# 3 - dataset type (consolidated, intermediate), use consolidated if available, otherwise use intermediate
dataset_types = ["consolidated_dataset", "intermediate_dataset"]

#%%
# Download ERA5-Drought data from CDS using cdsapi 

def unzip_cds_data(zipfile_path):
    # Unzip data downloaded from CDS and rename to .nc extension.
    zipfile_path = Path(zipfile_path)
    
    with zipfile.ZipFile(zipfile_path, 'r') as zip_ref:
        names = zip_ref.namelist()
        zip_ref.extractall(zipfile_path.parent)
        
        for name in names:
            if name.split(".")[-1] == "nc":
                # Rename the extracted file to match the zip filename
                nc_path = zipfile_path.with_suffix('.nc')
                os.rename(zipfile_path.parent / name, nc_path)
                print(f"  Extracted: {nc_path.name}")
            else:
                # Remove non-NetCDF files
                os.remove(zipfile_path.parent / name)
    
    # Remove the zip file after extraction
    os.remove(zipfile_path)
    print(f"  Removed: {zipfile_path.name}")

zfile = Path("data") / f"{index}{accumulation}_{year}{month}_{region_label}.zip"
ncfile = zfile.with_suffix('.nc')

print(zfile)
print(ncfile)

#
dataset_types = ["consolidated_dataset", "intermediate_dataset"]

def download_era5drought(index, accumulation, year, month, dataset_type, zfile, lon1, lon2, lat1, lat2):

    # Define dataset 
    dataset = "derived-drought-historical-monthly"
    drought_indices = {
        "spi": {
            "print_name": "SPI",
            "long_name": "Standardised Precipitation Index",
            "variable_name": "standardised_precipitation_index"
        },
        "spei": {
            "print_name": "SPEI",
            "long_name": "Standardised Precipitation Evapotranspiration Index",
            "variable_name": "standardised_precipitation_evapotranspiration_index"
        }
    }
    product_type = "reanalysis" # only allowing reanalysis here
    request = {
        "variable": [drought_indices[index.lower()]["variable_name"]],
        "accumulation_period": [accumulation],
        "version": "1_0",
        "product_type": [product_type],
        "dataset_type": [dataset_type],
        "year": [year],
        "month": [month],
        "area": [lat2, lon1, lat1, lon2] # North, West, South, East 
    }

    client = cdsapi.Client()
    client.retrieve(dataset, request).download(str(zfile))
    unzip_cds_data(zfile)


def download_static_masks(index, accumulation, month, zfile, lon1, lon2, lat1, lat2, significance_masking, pzero_masking):
    variables = []
    if significance_masking:
        variables.append(f"test_for_normality_{index.lower()}")
    if pzero_masking:
        variables.append("probability_of_zero_precipitation_spi")
    if not variables:
        return None
    request = {
        "variable": variables,
        "accumulation_period": [accumulation],
        "version": "1_0",
        "product_type": ["reanalysis"],
        "dataset_type": ["consolidated_dataset"],
        "month": [month],
        "area": [lat2, lon1, lat1, lon2],
    }
    zip_path = zfile.with_suffix(".zip")
    print(f"Downloading consolidated static masks for month {month}")
    cdsapi.Client().retrieve("derived-drought-historical-monthly", request).download(str(zip_path))
    with zipfile.ZipFile(zip_path) as archive:
        netcdf_names = [name for name in archive.namelist() if name.endswith(".nc")]
        if not netcdf_names:
            raise ValueError(f"No NetCDF files found in CDS download: {zip_path}")
        extracted_paths = []
        for number, netcdf_name in enumerate(netcdf_names):
            extracted_path = zfile.parent / f"{zfile.stem}_{number}.nc"
            with archive.open(netcdf_name) as source, open(extracted_path, "wb") as target:
                target.write(source.read())
            extracted_paths.append(extracted_path)
    datasets = [xr.open_dataset(path) for path in extracted_paths]
    static_data = xr.merge(datasets, compat="override")
    static_data.to_netcdf(zfile)
    static_data.close()
    for dataset in datasets:
        dataset.close()
    for extracted_path in extracted_paths:
        extracted_path.unlink()
    zip_path.unlink()
    return zfile

# Try downloading the consolidated dataset first; a CDS failure falls back to intermediate.
if ncfile.exists():
    print(f"Using existing download: {ncfile}")
else:
    try:
        download_era5drought(index, accumulation, year, month, "consolidated_dataset", zfile, lon1, lon2, lat1, lat2)
    except Exception as error:
        print(f"Consolidated dataset unavailable for {year}-{month}: {error}")
        print("Trying intermediate dataset...")
        download_era5drought(index, accumulation, year, month, "intermediate_dataset", zfile, lon1, lon2, lat1, lat2)

#%%
# Read and plot a map of the downloaded drought index
def plot_drought_snapshot(data, index, accumulation, year, month, region_label, lon1, lon2, lat1, lat2, mask_geometry, barren_area_masking, significance_masking, pzero_masking):
    levels = [-10000, -1000, -2, -1.5, -1, 1, 1.5, 2, 1000]
    colors = ["#bebebe", "#663300", "#8c6640", "#b29980", "#ffffff", "#99b280", "#668c40", "#336600"]
    labels = ["masked", "extremely dry", "severely dry", "moderately dry", "near normal", "moderately wet", "severely wet", "extremely wet"]
    snapshot = data.squeeze(drop=True).where(data.squeeze(drop=True) != -9999)
    if mask_geometry is not None:
        shapefile_mask = regionmask.Regions([mask_geometry]).mask(snapshot.lon, snapshot.lat).notnull()
        snapshot = snapshot.where(shapefile_mask)
    if barren_area_masking:
        if not BARREN_MASK_FILE.exists():
            raise FileNotFoundError(f"Barren mask not found: {BARREN_MASK_FILE}")
        barren_dataset = xr.open_dataset(BARREN_MASK_FILE)
        barren_mask = barren_dataset["barren_mask"].reindex_like(snapshot, method="nearest").load()
        barren_dataset.close()
        snapshot = snapshot.where(barren_mask == 1)
    if significance_masking or pzero_masking:
        static_mask_label = "significance_pzero" if significance_masking and pzero_masking else "significance" if significance_masking else "pzero"
        static_file = Path("data") / f"{index}{accumulation}_{month}_{region_label}_{static_mask_label}_masks.nc"
        if not static_file.exists():
            download_static_masks(index, accumulation, month, static_file, lon1, lon2, lat1, lat2, significance_masking, pzero_masking)
        static_dataset = xr.open_dataset(static_file)
        if significance_masking:
            normality_mask = static_dataset[f"significance"].isel(time=0, drop=True).reindex_like(snapshot, method="nearest")
            snapshot = snapshot.where(normality_mask != 0)
        if pzero_masking and index.lower() == "spi":
            pzero_mask = static_dataset["pzero"].isel(time=0, drop=True).reindex_like(snapshot, method="nearest")
            snapshot = snapshot.where(pzero_mask < PZERO_THRESHOLD)
        static_dataset.close()
    output_file = Path("figures") / f"{index.upper()}{accumulation}_{year}{month}_{region_label}.png"

    figure = plt.figure(figsize=(9, 6))
    axis = plt.axes(projection=ccrs.PlateCarree())
    snapshot.plot(
        ax=axis,
        transform=ccrs.PlateCarree(),
        add_colorbar=False,
        cmap=ListedColormap(colors),
        levels=levels,
    )
    axis.coastlines(color="black", linewidth=0.5)
    axis.add_feature(cfeature.BORDERS, color="black", linewidth=0.3)
    if mask_geometry is not None:
        axis.add_geometries(
            [mask_geometry],
            crs=ccrs.PlateCarree(),
            facecolor="none",
            edgecolor="black",
            linewidth=1.5,
            linestyle="--",
        )
    axis.set_extent([lon1, lon2, lat1, lat2], crs=ccrs.PlateCarree())
    axis.set_title(f"{index.upper()}-{accumulation} | {year}-{month}")
    axis.legend(
        handles=[
            Line2D([0], [0], marker="s", color="w", label=label, markerfacecolor=color, markersize=8)
            for label, color in zip(labels, colors)
        ],
        fontsize=8,
        loc="lower left",
    )
    figure.savefig(output_file, dpi=300, bbox_inches="tight", pad_inches=0.1)
    plt.close(figure)
    print(f"Saved drought snapshot: {output_file}")

downloaded_data = xr.open_dataset(ncfile)
variable_name = next(iter(downloaded_data.data_vars))
plot_drought_snapshot(
    downloaded_data[variable_name], index, accumulation, year, month, region_label,
    lon1, lon2, lat1, lat2, mask_geometry, barren_area_masking, significance_masking, pzero_masking,
)
downloaded_data.close()