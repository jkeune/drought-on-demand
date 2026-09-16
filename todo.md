## Easy checks... 
- add output/data path variable to download and store outputs elsewhere (global timeseries > 4GB)
- check if the global option works for timeseries, e.g. `pixi run python timeseries_area_in_drought.py SPEI 12 global` 
- note: timeseries_area_in_drought.py with option global applies the barren mask by default and excludes all ERA5-Drought NULL values (-9999, I think), but is not using a landmask
- check if the global option for timeseries uses land and masking correctly when calculating percentages (and masking barren and/or significance is accounted for correctely)

## More development (but using existing tools)
### timeseries_region.py
A script to (calculate and) plot drought indices averaged over individual regions is under construction, but requires the download of ERA5 data and the re-calculation of drought indices over the region. 
### drought_stripes.py
A script to (calculate and) plot drought stripes is under construction (examples see `archive/drought_stripes` for examples for individual regions), but requires the download of ERA5 data and the re-calculation of drought indices over the region. 