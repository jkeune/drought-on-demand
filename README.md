# drought-on-demand

Ready-to-use scripts to create drought plots using ERA5-Drought data (Keune et al., 2025).

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
pixi run python map_drought.py SPEI 12 2026 8 global
pixi run python map_drought.py SPEI 6 2026 7 C3S_Europe
pixi run python map_drought.py SPI 6 2026 7 C3S_Europe
```

Sample outputs can be found in 'figures', for example, [figures/SPEI12_202608_global.png](figures/SPEI12_202608_global.png), [figures/SPEI6_202607_C3S_Europe.png](figures/SPEI6_202607_C3S_Europe.png) and [figures/SPI6_202607_C3S_Europe.png](figures/SPI6_202607_C3S_Europe.png).


### timeseries_area_in_drought.py
To create timeseries of the area in drought over a selected region, run
```
pixi run python timeseries_area_in_drought.py INDEX ACCUMULATION_WINDOW REGION
```
where `REGION` can be a Natural Earth country, continent, or C3S region such as `C3S_Central_Europe`. The default period is 1980-01 through the previous month; set `--start YYYY-MM` and `--end YYYY-MM` to change it.

In all cases, the script prefers consolidated data and adds intermediate data only for the final three (hardcoded) months when needed. If the CDS returns an overlapping month in both products, the consolidated ERA5 value takes precedence over the intermediate ERA5T value. Outputs are written to `data` and `figures`; thresholds and colors are optional settings at the top of the script.

Examples:
```
pixi run python timeseries_area_in_drought.py SPEI 6 C3S_Central_Europe
pixi run python timeseries_area_in_drought.py SPEI 12 C3S_Central_Europe
```

Sample figures: [figures/SPEI6_198001_202608_C3S_Europe_area_in_drought.png](figures/SPEI6_198001_202608_C3S_Central_Europe_area_in_drought.png) and [figures/SPEI12_198001_202608_C3S_Central_Europe_area_in_drought.png](figures/SPEI12_198001_202608_C3S_Central_Europe_area_in_drought.png).

### drought_stripes.py
To create monthly drought stripes for a selected region, run
```
pixi run python drought_stripes.py INDEX ACCUMULATION_WINDOW REGION
```
where `INDEX` is `SPI` or `SPEI`, `ACCUMULATION_WINDOW` is the number of months, and `REGION` accepts the same countries, continents, C3S regions, and shapefile options as `timeseries_area_in_drought.py`.

The script downloads monthly ERA5 precipitation and, for SPEI, potential evaporation (monthly averages). It first calculates an area-weighted regional precipitation or water-balance series and then fits the drought index separately for each calendar month. The default reference period is 1991–2020, and the default stripe period is 1940-01 through the previous month. Use `--start`, `--end`, `--reference-start`, and `--reference-end` to change these periods. The regional values and calculated index are written to `data`, while PNG and PDF stripes are written to `figures`.

By default, each stripe represents one monthly index value. Use `--plot_timesteps annual` to plot one stripe per year and `--plot_month` to select that year's calendar month (default: December):
```
pixi run python drought_stripes.py SPEI 12 Slovakia --plot_timesteps monthly
pixi run python drought_stripes.py SPEI 12 Slovakia --plot_timesteps annual --plot_month 12
```

For example, to create SPEI-12 stripes for Slovakia:
```
pixi run python drought_stripes.py SPEI 12 Slovakia
```

Sample figure: [figures/SPEI12_198001_202512_Slovakia_drought_stripes_annual_month12.png](figures/SPEI12_198001_202512_Slovakia_drought_stripes_annual_month12.png)


## Other settings and notes

### Masks
#### Shapefile region
Instead of a named region, use `--shapefile PATH --id FIELD=VALUE` to plot or calculate only the selected polygon feature. Outside the selected geometry, map values are transparent. For example:
```
pixi run python map_drought.py SPEI 3 2026 7 --shapefile regions/med_v2/three_agb_biomes.shp --id biome_id=1
pixi run python timeseries_area_in_drought.py SPEI 3 --shapefile regions/med_v2/three_agb_biomes.shp --id biome_id=1
```
#### Land
ERA5-Drought is only defined over land and masked accordingly. ERA5 data used by `drought_stripes.py` is masked using the ERA5 land-sea mask included in its download.
#### Barren areas
`map_drought.py` and `timeseries_area_in_drought.py` exclude barren land by default, using `masks/ERA5_barren_w_precip.nc`. Set `--barren_area_masking False` to retain it; time-series percentages then include barren pixels.
#### Significance masking
Use `--significance_masking True` to exclude grid cells where the monthly normality test fails. The consolidated monthly mask is applied by calendar month, including to intermediate data.
#### Zero-precipitation probability
For SPI only, use `--pzero_masking True` to exclude cells with a monthly zero-precipitation probability of 0.9 or greater. To change the threshold, manually modify it at the top of each script.

### Drought severity thresholds
By default, the following thresholds are used to define drought severity categories:
extreme (index <= -2), severe (-2 < index <= -1.5), moderate (-1.5 < index <= -1). These are set at the beginning of each script and can be modified manually.

### Regions and continents
Regions are continents are masked using the [regionmask](https://regionmask.readthedocs.io/en/stable/) library, which contains Giorgi and SREX regions (e.g., `WNA` for Western North America, etc), AR6 and PRUDENCE regions, but also states and countries from NaturalEarth. 



## References
- Keune, J., Di Giuseppe, F., Barnard, C. et al. ERA5–Drought: Global drought indices based on ECMWF reanalysis. Scientific Data 12, 616 (2025). [https://doi.org/10.1038/s41597-025-04896-y](https://doi.org/10.1038/s41597-025-04896-y).
- DroughtWatch: [https://sites.ecmwf.int/nejk/drought-watch-live/](https://sites.ecmwf.int/nejk/drought-watch-live/)
