"""Create monthly SPEI-3 and drought-area time series for Mediterranean biomes.

Set PMPET_FILE to the downloaded ERA5 precipitation-minus-potential-evaporation
NetCDF file before running. It must contain a monthly variable named PMPET_VARIABLE
on time, lat, lon coordinates, in mm day-1, from at least 1991-01 through today.

Run with: pixi run python med_biome_timeseries.py [--calculate both|area|spei] [--plot True]
"""

import argparse
from pathlib import Path
import zipfile

import cdsapi
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import regionmask
import xarray as xr

from spidi.spidi.helpers import convert_mmperday_to_mmpermonth
from spidi.spidi.spidi import calculate_si


REFERENCE_START = 1991
REFERENCE_END = 2020
SERIES_START = "2003-01-01"
SERIES_END = "2025-12-31"
WINDOW = 3
PMET_START = (
    pd.Timestamp(f"{REFERENCE_START}-01-01") - pd.DateOffset(months=WINDOW - 1)
).strftime("%Y-%m-%d")
SHAPEFILE = Path("regions/med_v2/three_agb_biomes.shp")
BIOME_IDS = [1, 2, 3]
pmet_file = Path("archive/helpers/era5_data/data_retrieval_regional/wb_all_regional.nc")
PMPET_VARIABLE = "wb"
GRID_DATA_DIR = Path("data/med_biome_spei3")
OUTPUT_DIR = Path("archive/csv/med_biomes")
FIGURE_DIR = Path("figures/med_biomes")

parser = argparse.ArgumentParser()
parser.add_argument(
    "--calculate",
    choices=["both", "area", "spei"],
    default="both",
    help="Calculate both outputs (default), drought area only, or regional SPEI only.",
)
parser.add_argument(
    "--plot",
    choices=["True", "False"],
    default="False",
    help="Write one figure per biome after calculation (default: False).",
)
arguments = parser.parse_args()
calculate_area = arguments.calculate in ["both", "area"]
calculate_spei = arguments.calculate in ["both", "spei"]
make_plot = arguments.plot == "True"


def calculate_gridarea(latitudes, resolution, number_of_longitudes):
    earth_radius = 6371
    latitudes_north = (latitudes + resolution / 2) * np.pi / 180
    latitudes_south = (latitudes - resolution / 2) * np.pi / 180
    areas = (
        (np.pi / 180)
        * earth_radius**2
        * np.abs(np.sin(latitudes_north) - np.sin(latitudes_south))
        * resolution
    )
    areas = np.asarray(areas, dtype=float)
    areas[areas == 0] = np.nan
    return np.swapaxes(np.tile(areas, (number_of_longitudes, 1)), 0, 1)


def download_grid_spei(years, months, west, east, south, north, spei_file):
    """Download the full gridded SPEI-3 series from the consolidated CDS dataset."""
    if spei_file.exists():
        return

    zip_path = spei_file.with_suffix(".zip")
    request = {
        "variable": ["standardised_precipitation_evapotranspiration_index"],
        "accumulation_period": [str(WINDOW)],
        "version": ["1_0"],
        "product_type": ["reanalysis"],
        "dataset_type": ["consolidated_dataset"],
        "year": years,
        "month": months,
        "area": [north, west, south, east],
    }
    client = cdsapi.Client()
    client.retrieve("derived-drought-historical-monthly", request).download(str(zip_path))
    with zipfile.ZipFile(zip_path) as archive:
        netcdf_names = [name for name in archive.namelist() if name.endswith(".nc")]
        if not netcdf_names:
            raise ValueError(f"No NetCDF files found in {zip_path}")
        extracted_files = []
        for netcdf_name in netcdf_names:
            extracted_file = GRID_DATA_DIR / Path(netcdf_name).name
            with archive.open(netcdf_name) as source, open(extracted_file, "wb") as target:
                target.write(source.read())
            extracted_files.append(extracted_file)
    extracted_datasets = [xr.open_dataset(extracted_file) for extracted_file in extracted_files]
    combined_dataset = xr.combine_by_coords(extracted_datasets, combine_attrs="override")
    combined_dataset.to_netcdf(spei_file)
    combined_dataset.close()
    for extracted_dataset in extracted_datasets:
        extracted_dataset.close()
    for extracted_file in extracted_files:
        extracted_file.unlink()
    zip_path.unlink()


def plot_timeseries(output, biome_name, biome_label):
    has_spei = "spei3_region_average" in output
    has_area = "area_any_drought_pct" in output
    number_of_panels = int(has_spei) + int(has_area)
    figure, axes = plt.subplots(number_of_panels, 1, figsize=(12, 3.5 * number_of_panels), sharex=True)
    if number_of_panels == 1:
        axes = [axes]

    panel_number = 0
    if has_spei:
        axis = axes[panel_number]
        axis.plot(output.index, output["spei3_region_average"], color="black", linewidth=1)
        axis.axhline(0, color="dimgray", linewidth=0.8)
        axis.axhline(-1, color="#b29980", linewidth=0.8, linestyle="--")
        axis.axhline(-1.5, color="#8c6640", linewidth=0.8, linestyle="--")
        axis.axhline(-2, color="#663300", linewidth=0.8, linestyle="--")
        axis.set_ylabel("Regional SPEI-3")
        axis.set_title(f"{biome_name} | SPEI-3")
        panel_number += 1

    if has_area:
        axis = axes[panel_number]
        bottom = np.zeros(len(output))
        for column, label, color in [
            ("area_extreme_drought_pct", "extreme", "#663300"),
            ("area_severe_drought_pct", "severe", "#8c6640"),
            ("area_moderate_drought_pct", "moderate", "#b29980"),
        ]:
            axis.bar(output.index, output[column], bottom=bottom, width=31, label=label, color=color)
            bottom += output[column].fillna(0).to_numpy()
        axis.set_ylabel("Area in drought [%]")
        axis.set_ylim(0, 100)
        axis.set_title(f"{biome_name} | Area in drought (SPEI-3)")
        axis.legend(ncol=3, loc="upper center")

    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
        axis.margins(x=0)
    figure.tight_layout()
    figure.savefig(FIGURE_DIR / f"{biome_label}_spei3_timeseries.png", dpi=300)
    plt.close(figure)


def plot_biomes(biomes):
    colors = ["#d95f02", "#1b9e77", "#7570b3"]
    figure, axis = plt.subplots(figsize=(9, 6))
    biomes.plot(ax=axis, color=colors, edgecolor="black", linewidth=0.4)
    for _, biome in biomes.iterrows():
        point = biome.geometry.representative_point()
        axis.text(point.x, point.y, str(biome["biome_id"]), ha="center", va="center", fontsize=10, fontweight="bold")
    legend_handles = [
        plt.Line2D([0], [0], marker="s", color="none", markerfacecolor=color, markersize=10, label=name)
        for color, name in zip(colors, biomes["biome_name"])
    ]
    axis.legend(handles=legend_handles, loc="lower left", frameon=False)
    axis.set_xlabel("Longitude")
    axis.set_ylabel("Latitude")
    axis.set_title("Mediterranean biomes")
    axis.set_aspect("equal")
    figure.tight_layout()
    figure.savefig(FIGURE_DIR / "med_biomes_map.png", dpi=300)
    plt.close(figure)


if calculate_spei and not pmet_file.exists():
    raise FileNotFoundError(
        f"Set pmet_file to the downloaded raw P-PET NetCDF file; not found: {pmet_file}"
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GRID_DATA_DIR.mkdir(parents=True, exist_ok=True)
if make_plot:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
biomes = gpd.read_file(SHAPEFILE).to_crs("EPSG:4326")
biomes = biomes[biomes["biome_id"].isin(BIOME_IDS)].copy()
if set(biomes["biome_id"]) != set(BIOME_IDS):
    raise ValueError(f"Expected biome IDs {BIOME_IDS}; found {biomes['biome_id'].tolist()}")

if make_plot:
    plot_biomes(biomes)

west, south, east, north = biomes.total_bounds
if calculate_area:
    series_dates = pd.date_range(SERIES_START, SERIES_END, freq="MS")
    spei_file = GRID_DATA_DIR / f"spei{WINDOW}_{series_dates[0]:%Y%m}_{series_dates[-1]:%Y%m}_med_biomes.nc"
    download_grid_spei(
        [str(year) for year in sorted(series_dates.year.unique())],
        [f"{month:02d}" for month in sorted(series_dates.month.unique())],
        west,
        east,
        south,
        north,
        spei_file,
    )
    grid_spei_dataset = xr.open_dataset(spei_file)
    grid_variable = next(iter(grid_spei_dataset.data_vars))
    grid_spei_all = grid_spei_dataset[grid_variable].sel(time=slice(SERIES_START, SERIES_END))
    grid_coordinate_names = {
        coordinate: new_name
        for coordinate, new_name in {"latitude": "lat", "longitude": "lon"}.items()
        if coordinate in grid_spei_all.dims or coordinate in grid_spei_all.coords
    }
    if grid_coordinate_names:
        grid_spei_all = grid_spei_all.rename(grid_coordinate_names)

if calculate_spei:
    pmpet_dataset = xr.open_dataset(pmet_file)
    pmpet = pmpet_dataset[PMPET_VARIABLE]
    pmpet_coordinate_names = {
        coordinate: new_name
        for coordinate, new_name in {"latitude": "lat", "longitude": "lon"}.items()
        if coordinate in pmpet.dims or coordinate in pmpet.coords
    }
    if pmpet_coordinate_names:
        pmpet = pmpet.rename(pmpet_coordinate_names)
    if not {"time", "lat", "lon"}.issubset(pmpet.dims):
        raise ValueError("The P-PET variable must have time, lat, lon dimensions.")
    pmpet = pmpet.sel(time=slice(PMET_START, SERIES_END))

for _, biome in biomes.iterrows():
    biome_id = int(biome["biome_id"])
    biome_name = biome["biome_name"]
    biome_label = f"biome_{biome_id}"
    geometry = gpd.GeoDataFrame([biome], crs=biomes.crs)

    output = pd.DataFrame()
    if calculate_spei:
        regional_mask = regionmask.mask_geopandas(geometry, pmpet.lon, pmpet.lat)
        regional_mask = xr.where(regional_mask.notnull(), 1, np.nan)
        regional_pmpet = pmpet.where(regional_mask == 1)
        latitude_weights = np.cos(np.deg2rad(regional_pmpet.lat))
        regional_pmpet = regional_pmpet.weighted(latitude_weights).mean(dim=("lat", "lon"))
        regional_pmpet = regional_pmpet.to_series().rename("pmpet")
        regional_pmpet.index = pd.to_datetime(regional_pmpet.index)
        regional_pmpet = convert_mmperday_to_mmpermonth(
            regional_pmpet.to_frame(), ["pmpet"]
        )
        reference_pmpet = regional_pmpet.loc[
            (regional_pmpet.index.year >= REFERENCE_START)
            & (regional_pmpet.index.year <= REFERENCE_END)
        ]
        output["spei3_region_average"] = calculate_si(
            regional_pmpet,
            dfdata_ref=reference_pmpet,
            window=WINDOW,
            distribution="genlogistic",
            integration_frequency_string="%m-%d",
            n_events_min=5,
            max_zeros=0.99,
            remove_zeros=False,
            pzero_replace=False,
            pzero_center_mass=False,
        ).iloc[:, 0]

    if calculate_area:
        grid_mask = regionmask.mask_geopandas(geometry, grid_spei_all.lon, grid_spei_all.lat)
        grid_mask = xr.where(grid_mask.notnull(), 1, np.nan)
        grid_spei = grid_spei_all.where(grid_mask == 1).where(grid_spei_all != -9999)
        polygon_grid_cells = int(grid_mask.notnull().sum())
        valid_grid_cells = int(grid_spei.isel(time=0).notnull().sum())
        print(
            f"{biome_name}: {polygon_grid_cells} grid cells in polygon, "
            f"{valid_grid_cells} cells with valid SPEI in "
            f"{pd.Timestamp(grid_spei.time.values[0]):%Y-%m}"
        )
        resolution = float(abs(grid_spei.lat[1] - grid_spei.lat[0]))
        grid_area = calculate_gridarea(grid_spei.lat, resolution, grid_spei.sizes["lon"])
        grid_area = xr.DataArray(
            grid_area,
            coords={"lat": grid_spei.lat, "lon": grid_spei.lon},
            dims=("lat", "lon"),
        ).where(grid_mask == 1)
        valid_area = grid_area.where(grid_spei.notnull())
        total_area = valid_area.sum(dim=("lat", "lon"))
        for severity, lower_limit, upper_limit in [
            ("moderate", -1.5, -1.0),
            ("severe", -2.0, -1.5),
            ("extreme", -np.inf, -2.0),
            ("any", -np.inf, -1.0),
        ]:
            drought_cells = (grid_spei > lower_limit) & (grid_spei <= upper_limit)
            output[f"area_{severity}_drought_pct"] = (
                100 * grid_area.where(drought_cells).sum(dim=("lat", "lon")) / total_area
            ).to_pandas()

    output.index.name = "date"
    output = output.loc[SERIES_START:SERIES_END]
    if make_plot:
        plot_timeseries(output, biome_name, biome_label)
    output.index = output.index.strftime("%Y-%m")
    output.to_csv(OUTPUT_DIR / f"{biome_label}_spei3_timeseries.csv", float_format="%.6f")
    print(f"Wrote {biome_name}: {OUTPUT_DIR / f'{biome_label}_spei3_timeseries.csv'}")

if calculate_spei:
    pmpet_dataset.close()
if calculate_area:
    grid_spei_dataset.close()