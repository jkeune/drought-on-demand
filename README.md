# drought-on-demand

Scripts to create drought plots using ERA5-Drought data (Keune et al., 2025).

## Content
This repository contains 
- several on-demand jupyter notebooks for individual events in `archive` (e.g., `Iceland2024.ipynb`, `Morocco.ipynb`)
- scripts used to create a mini-webpage with the latest snapshots from ERA5-Drought in `drought-watch-live` ([**DroughtWatch**](https://sites.ecmwf.int/nejk/drought-watch-live/), including `update_timeseries.py` and `update_maps.py`
- tools to plot **drought stripes** (`drought_stripes`) on demand (attention, needs download of ERA5 data and calculation of drought indices over area of interest). 

## Get started
Install pixi and all required modules with
```
pixi init --import environment.yml
```
and make sure you have your CDS API key stored and accessible. That's it!


## Scripts
### map_drought.py
To create maps of drought indices for YYYY-MM over a selected continent, run
```
pixi run python map_drought.py INDEX ACCUMULATION_WINDOW REGION YYYY-MM
```
where INDEX and ACCUMULATION_WINDOW define the drought index (e.g., SPEI and 1 for SPEI-1), REGION defines the region, and YYYY-MM defines the month and year of the data to be plotted. 

The script download data from the CDS for REGION, saves it to `data` and plots it following default settings (see below). 


Examples:
```
pixi run python map_drought.py SPEI 12 global
pixi run python map_drought.py SPEI 12 Europe
pixi run python map_drought.py SPI 36 Spain
```

Sample outputs can be found in figures/maps_drought.


### timeseries_area_in_drought.py
To create timeseries of the area in drought over a selected region, run
```
pixi run python timeseries_area_in_drought.py INDEX ACCUMULATION_WINDOW REGION 
```
where INDEX and ACCUMULATION_WINDOW define the drought index (e.g., SPEI and 1 for SPEI-1), REGION defines the region considered.


The script download data from the CDS for REGION, saves it to `data` and plots it following default settings (see below). 


Examples:
```
pixi run python timeseries_area_in_drought.py SPEI 12 global
pixi run python timeseries_area_in_drought.py SPEI 12 Europe
pixi run python timeseries_area_in_drought.py SPI 36 Spain
```


Sample outputs can be found in figures/timeseries_area_on_drought.


## Under construction
### timeseries_region.py
A script to (calculate and) plot drought indices averaged over individual regions is under construction, but requires the download of ERA5 data and the re-calculation of drought indices over the region. 
### drought_stripes.py
A script to (calculate and) plot drought stripes is under construction (examples see `archive/drought_stripes` for examples for individual regions), but requires the download of ERA5 data and the re-calculation of drought indices over the region. 




## Other settings and notes

### Masks
#### Land
ERA5-Drought is only defined over land and masked accordingly. ERA5 data as used in timeseries_region.py and drought_stripes.py is masked using the ERA5 land mask.
#### Barren areas
By default, barren areas are masked. To switch that off, use `--barren_area_masking False`. The barren area mask from `masks/` is used. 
#### Significance masking
By default, non-significant values are __not__ masked. To switch that on, use `--significance_masking True`. Data for masking is downloaded from the CDS.

### Drought severity thresholds
By default, the following thresholds are used to define drought severity categories:
extreme (index <= -2), severe (-2 < index <= -1.5), moderate (-1.5 < index <= -1)

### Regions and continents
Regions are continents are masked using the [regionmask](https://regionmask.readthedocs.io/en/stable/) library, which contains Giorgi and SREX regions (e.g., `WNA` for Western North America, etc), AR6 and PRUDENCE regions, but also states and countries from NaturalEarth. 



## References
- Keune, J., Di Giuseppe, F., Barnard, C. et al. ERA5–Drought: Global drought indices based on ECMWF reanalysis. Scientific Data 12, 616 (2025). [https://doi.org/10.1038/s41597-025-04896-y](https://doi.org/10.1038/s41597-025-04896-y).
- DroughtWatch: [https://sites.ecmwf.int/nejk/drought-watch-live/](https://sites.ecmwf.int/nejk/drought-watch-live/)
