import os 
import sys
import math
import datetime as dt
import pandas as pd
import netCDF4 as nc4
import numpy as np
import xarray as xr
import cartopy.crs as ccrs
import geopandas as gpd
import fiona
import regionmask
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator
import string
from dateutil import relativedelta
import cartopy
import cartopy.feature as feature
import cartopy.io.shapereader as shapereader


EARTHRADIUS = 6371  # earth radius [km]
def calculate_gridarea(lats_centr, res, nlon):

    lats1 = (lats_centr + (res / 2)) * np.pi / 180  # np.sin requires radians
    lats2 = (lats_centr - (res / 2)) * np.pi / 180
    areas = (
        (np.pi / 180) * (EARTHRADIUS ** 2) * np.abs(np.sin(lats1) - np.sin(lats2)) * res
    )

    ## overwrite any areas of 0 (at the poles) with np.NaN to prevent problems
    areas[np.where(areas == 0.0)] = np.nan
    # return array of dimension nlat x nlon
    area_2d = np.swapaxes(np.tile(areas, (nlon, 1)), 0, 1)
    return area_2d


ref_syyyy = 1991
ref_eyyyy = 2020
yyyy_start= 2005
yyyy_end  = 2026
indicator = "SPEI"
window    = 12
yyyy      = 2025
mm        = "09"
dataset   = "era5t"
stream    = "moda"
distribut = "genlogistic"
# new versions
ipath     = f"/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/"#%{yyyy}{mm}01/hr"
#ipath_era5t= f"/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/"#{yyyy}{mm}01/hr"
lpath     = "/ec/vol/centaur/nejk/drought_monitor"
cwd       = "/home/nejk/code/drought-on-demand"

dates = pd.date_range(start=f"{yyyy_start}-01-01",end=f"{yyyy_end}-01-01", freq='ME')
pdate_seq = [dt.datetime.strptime(str(i)[0:10], "%Y-%m-%d") for i in dates]#[window:]
print(dates)
print(dates.size)
# !!!! ATTN, below we go to pdate_seq[:-3] to exclude last 3 entries, but everything else is read from ERA5 or ERA5T if ERA5 not available

# binary land mask
lfile      = f"{lpath}/landmask_era5_global.nc"
lmask      = xr.open_dataset(lfile)['lsm']
lmask      = lmask.where( lmask.values == 1 ) # set 0s to nan
# land fraction
lffile     = f"{lpath}/landmask_era5_global_frac.nc"
lmask_frac = xr.open_dataset(lffile)['var172']
# barren area mask: 1 - do NOT use, 0 - use!
vfile = "/home/nejk/code/dryfall_oper/helpers_oper/barren_mask.nc"
bmask = xr.open_dataset(vfile)


# use external shapefile to incl contended territories?
shpfile = gpd.read_file("./regions/IPCC-WGI-reference-regions-v4.shp")
print(shpfile.head())
#shpfile.plot()
shpfile=shpfile.to_crs('epsg:4326')
extent = (shpfile[shpfile["Name"] == "Mediterranean"]).bounds
lon1   = extent.minx.values[0]
lon2   = extent.maxx.values[0]
lat1   = extent.miny.values[0]
lat2   = extent.maxy.values[0]


### MEDITERRANEAN
# from Joey: the "Name" you want is "Mediterranean" and then we have subregions within that WMED (10 > lon), and EMED (10 < lon)
print(shpfile[shpfile["Name"] == "Mediterranean"])
medmask = regionmask.mask_geopandas((shpfile[shpfile["Name"] == "Mediterranean"]), lmask.lon, lmask.lat)
medmask = xr.where(medmask >= 1, 1, np.nan)
medmask = xr.where( (bmask['barren_mask'][0,:,:] == 1) , np.nan, medmask)
medmask_cut = medmask.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
plt.figure()
#medmask.plot()
# and manual subreguions
# WMED
wmedmask = medmask
wmedmask = xr.where(wmedmask.lon < 10, wmedmask, np.nan)
wmedmask = xr.where( (bmask['barren_mask'][0,:,:] == 1) , np.nan, wmedmask)
wmedmask_cut = wmedmask.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
#plt.figure(); wmedmask.plot()
# EMED
emedmask = medmask
emedmask = xr.where(emedmask.lon >= 10, emedmask, np.nan)
emedmask = xr.where( (bmask['barren_mask'][0,:,:] == 1) , np.nan, emedmask)
emedmask_cut = emedmask.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
#plt.figure(); emedmask.plot()

filedate_seq = [dt.datetime.strftime(i, "%Y%m01") for i in pdate_seq[window:]]
filelist = []
for idate in filedate_seq[:-3]:
    # /ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/
    ifile = f"{ipath}/era5/{idate}/hr/{indicator}{window}_{distribut}_global_era5_{stream}_ref{ref_syyyy}to{ref_eyyyy}_{str(idate)[:6]}.nc"
    if os.path.exists(ifile):
        filelist.append(ifile)
    else:
        ifile = f"{ipath}/era5t/{idate}/hr/{indicator}{window}_{distribut}_global_era5t_{stream}_ref{ref_syyyy}to{ref_eyyyy}_{str(idate)[:6]}.nc"
        filelist.append(ifile)
#print(filelist[:-8])

drought_index = {}
drought_index[window] = xr.open_mfdataset(filelist).sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
#print(drought_index[window])

masked_drought_index = drought_index[window] * medmask_cut
masked_drought_index = xr.where(masked_drought_index == -9999, np.nan, masked_drought_index)
#masked_drought_index.isel(time=-1)[f'{indicator}{window}'].plot()

area_2d = calculate_gridarea(masked_drought_index.lat, res=abs(masked_drought_index.lat[1]-masked_drought_index.lat[0]), nlon=len(masked_drought_index.lon))*lmask.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))[0,:,:]
area_2d = xr.DataArray(area_2d, coords={'lat': masked_drought_index.lat,'lon': masked_drought_index.lon}, dims=["lat", "lon"])
area_2d_adj = area_2d * lmask_frac.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
area_2d_adj = area_2d_adj.where( area_2d_adj.values != 0 ) # set 0s to nan


# calculate area in drought
area_3d_adj = area_2d_adj.reindex_like(masked_drought_index, method="nearest")
aid = {}

swindow=f"w{window}"
aid[swindow] = {}

for severity in ['moderate','severe','extreme','any']:

    if severity == "mild":
        thresh_min = -1
        thresh_max = 0
    if severity == "moderate":
        thresh_min = -1.5
        thresh_max = -1
    if severity == "severe":
        thresh_min = -2
        thresh_max = -1.5
    if severity == "extreme":
        thresh_min = -999
        thresh_max = -2
    if severity == "any":
        thresh_min = -999
        thresh_max = -1

    rdi = masked_drought_index[f'{indicator}{window}']
    dmask  = xr.where((rdi > thresh_min) & (rdi <= thresh_max) & (rdi != -9999), 1, np.nan)
    tmp    = 100 * (dmask*area_3d_adj).sum(dim=["lat", "lon"]) / (medmask_cut*area_3d_adj).sum(dim=["lat", "lon"])
    aid[swindow][severity] = tmp.to_pandas()

    del(tmp, dmask)


mylevels     = [-10000,-1000,-2,-1.5,-1,1,1.5,2,1000]
mycollisthex = ['#bebebe','#663300','#8c6640','#b29980','#ffffff','#99b280','#668c40','#336600']


fig, ax1 = plt.subplots(1,1, figsize=(12,4))
#title1 = r"$\bf{" + f"{string.ascii_lowercase[0]}" + "}$"
title1 = r"$\bf{" + f"Mediterranean" + "}$"
fig.suptitle(f"{title1} | Area in drought ({indicator}-{window})", fontsize=22)
#fig.suptitle(f"Area of {country} in long-term drought ({indicator}-{window})", fontsize=22)
fig.tight_layout(pad=3.75)
fig.subplots_adjust(top=0.875)
font = {'family' : 'sans-serif',
        'weight' : 'normal',
        'size'   : 20}
plt.rc('font', **font)

severities = ['extreme','severe','moderate']
pidata2 = aid[f'w{window}']['extreme']#[f'{indicator}{window}']
pidata3 = aid[f'w{window}']['severe']#[f'{indicator}{window}']
pidata4 = aid[f'w{window}']['moderate']#[f'{indicator}{window}']
apidata = pd.concat([pidata2, pidata3, pidata4], axis=1)
#apidata.index = apidata.index.shift(-(window-1), freq="MS") # shift datetimeindex to get start date
bottom = np.zeros(len(apidata.index))
for i in range(len(apidata.columns)):
    p = ax1.bar(apidata.index, apidata.iloc[:,i], facecolor=mycollisthex[i+1],
                alpha=1,
                width=relativedelta.relativedelta(months=1),
                label=severities[i],
                bottom=bottom,
                align='edge')
    bottom += apidata.iloc[:,i]
ax1.set_ylabel("Area in drought [%]", size=18)
ax1.legend(ncol=3, loc='upper center', fancybox=False, shadow=False, reverse=True, fontsize=12)
ax1.margins(x=0)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['left'].set_visible(False)
ax1.tick_params(axis='y', colors='dimgray')
ax1.tick_params(axis='x', colors='dimgray')
ax1.xaxis.label.set_color('None')
ax1.yaxis.label.set_color('None')
ax1.minorticks_on()
ax1.xaxis.set_minor_locator(AutoMinorLocator(10))
# Major ticks every 20, minor ticks every 5
#https://stackoverflow.com/questions/24943991/change-grid-interval-and-specify-tick-labels
major_ticks = np.arange(0, 150, 50)
minor_ticks = np.arange(0, 150, 10)
ax1.set_yticks(major_ticks)
ax1.set_yticks(minor_ticks, minor=True)
ax1.yaxis.tick_right()
# And a corresponding grid
#ax1.grid(which='minor')
# Or if you want different settings for the grids:
#ax1.grid(which='minor', alpha=0.2)
#ax1.grid(which='major', alpha=0.5)
ax1.tick_params(which='minor', length=4)
ax1.tick_params(which='major', length=12)
#ax1.grid(True)
ax1.set_axisbelow(True)
ax1.yaxis.grid(which='major', alpha=0.5, color='gray', linestyle='solid', zorder=3) #dashed
ax1.yaxis.grid(which='minor', alpha=0.2, color='lightgray', linestyle='solid', zorder=3) #dashed
ax1.set_ylim([0,105])
for tick in ax1.get_xticklabels():
    tick.set_rotation(45)

plt.savefig(f"figures/Mediterranean_{indicator}{window}_AID_timeseries_monthly.png", dpi=300, format=None, metadata=None,
            bbox_inches=None, pad_inches=0.1,
            facecolor='auto', edgecolor='auto',
            backend=None)
#plt.show()




aid_subregions = {}

for subregion in ["WMED", "EMED"]:

    if subregion == "WMED":
        subregionmask = wmedmask_cut
    if subregion == "EMED":
        subregionmask = emedmask_cut

    aid_subregions[subregion] = {}

    # MASK
    masked_drought_index = drought_index[window] * subregionmask
    masked_drought_index = xr.where(masked_drought_index == -9999, np.nan, masked_drought_index)

    # debugging
    plt.figure()
    masked_drought_index.isel(time=-1)[f'{indicator}{window}'].plot()

    area_2d = calculate_gridarea(masked_drought_index.lat, res=abs(masked_drought_index.lat[1]-masked_drought_index.lat[0]), nlon=len(masked_drought_index.lon))*lmask.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))[0,:,:]
    area_2d = xr.DataArray(area_2d, coords={'lat': masked_drought_index.lat,'lon': masked_drought_index.lon}, dims=["lat", "lon"])
    area_2d_adj = area_2d * lmask_frac.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
    area_2d_adj = area_2d_adj.where( area_2d_adj.values != 0 ) # set 0s to nan

    # Calculate area in drought
    area_3d_adj = area_2d_adj.reindex_like(masked_drought_index, method="nearest")

    swindow=f"w{window}"
    aid_subregions[subregion][swindow] = {}

    for severity in ['moderate','severe','extreme','any']:

        if severity == "mild":
            thresh_min = -1
            thresh_max = 0
        if severity == "moderate":
            thresh_min = -1.5
            thresh_max = -1
        if severity == "severe":
            thresh_min = -2
            thresh_max = -1.5
        if severity == "extreme":
            thresh_min = -999
            thresh_max = -2
        if severity == "any":
            thresh_min = -999
            thresh_max = -1

        rdi = masked_drought_index[f'{indicator}{window}']
        dmask  = xr.where((rdi > thresh_min) & (rdi <= thresh_max) & (rdi != -9999), 1, np.nan)
        tmp    = 100 * (dmask*area_3d_adj).sum(dim=["lat", "lon"]) / (subregionmask*area_3d_adj).sum(dim=["lat", "lon"])
        print(tmp)
        aid_subregions[subregion][swindow][severity] = tmp.to_pandas()

        del(tmp, dmask)


for subregion in ["WMED", "EMED"]:

    # plot
    fig, ax1 = plt.subplots(1,1, figsize=(12,4))
    #title1 = r"$\bf{" + f"{string.ascii_lowercase[0]}" + "}$"
    title1 = r"$\bf{" + f"{subregion}" + "}$"
    fig.suptitle(f"{title1} | Area in drought ({indicator}-{window})", fontsize=22)
    #fig.suptitle(f"Area of {country} in long-term drought ({indicator}-{window})", fontsize=22)
    fig.tight_layout(pad=3.75)
    fig.subplots_adjust(top=0.875)
    font = {'family' : 'sans-serif',
            'weight' : 'normal',
            'size'   : 20}
    plt.rc('font', **font)

    severities = ['extreme','severe','moderate']
    pidata2 = aid_subregions[subregion][f'w{window}']['extreme']#[f'{indicator}{window}']
    pidata3 = aid_subregions[subregion][f'w{window}']['severe']#[f'{indicator}{window}']
    pidata4 = aid_subregions[subregion][f'w{window}']['moderate']#[f'{indicator}{window}']
    apidata = pd.concat([pidata2, pidata3, pidata4], axis=1)
    #apidata.index = apidata.index.shift(-(window-1), freq="MS") # shift datetimeindex to get start date
    bottom = np.zeros(len(apidata.index))
    for i in range(len(apidata.columns)):
        p = ax1.bar(apidata.index, apidata.iloc[:,i], facecolor=mycollisthex[i+1],
                    alpha=1,
                    width=relativedelta.relativedelta(months=1),
                    label=severities[i],
                    bottom=bottom,
                    align='edge')
        bottom += apidata.iloc[:,i]
    ax1.set_ylabel("Area in drought [%]", size=18)
    ax1.legend(ncol=3, loc='upper center', fancybox=False, shadow=False, reverse=True, fontsize=12)
    ax1.margins(x=0)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    ax1.tick_params(axis='y', colors='dimgray')
    ax1.tick_params(axis='x', colors='dimgray')
    ax1.xaxis.label.set_color('None')
    ax1.yaxis.label.set_color('None')
    ax1.minorticks_on()
    ax1.xaxis.set_minor_locator(AutoMinorLocator(10))
    # Major ticks every 20, minor ticks every 5
    #https://stackoverflow.com/questions/24943991/change-grid-interval-and-specify-tick-labels
    major_ticks = np.arange(0, 150, 50)
    minor_ticks = np.arange(0, 150, 10)
    ax1.set_yticks(major_ticks)
    ax1.set_yticks(minor_ticks, minor=True)
    ax1.yaxis.tick_right()
    # And a corresponding grid
    #ax1.grid(which='minor')
    # Or if you want different settings for the grids:
    #ax1.grid(which='minor', alpha=0.2)
    #ax1.grid(which='major', alpha=0.5)
    ax1.tick_params(which='minor', length=4)
    ax1.tick_params(which='major', length=12)
    #ax1.grid(True)
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(which='major', alpha=0.5, color='gray', linestyle='solid', zorder=3) #dashed
    ax1.yaxis.grid(which='minor', alpha=0.2, color='lightgray', linestyle='solid', zorder=3) #dashed
    ax1.set_ylim([0,105])
    for tick in ax1.get_xticklabels():
        tick.set_rotation(45)

    plt.savefig(f"figures/{subregion}_{indicator}{window}_AID_timeseries_monthly.png", dpi=300, format=None, metadata=None,
                bbox_inches=None, pad_inches=0.1,
                facecolor='auto', edgecolor='auto',
                backend=None)
    #plt.show()



# create one final dataframe for regions MED (from aid df), and subregions EMED, WMED (from aid_subregions df)
myindex = aid[f"w{window}"]["moderate"].index.strftime("%Y-%m")
region  = "MED"
aid_mod = aid[f"w{window}"]["moderate"].values
aid_sev = aid[f"w{window}"]["severe"].values
aid_ext = aid[f"w{window}"]["extreme"].values
aid_all = aid_mod + aid_sev + aid_ext
mypd = pd.DataFrame({'date' : myindex, 'drought_index': f"{indicator}{window}", 'region': region, 'AID': aid_all, 'AID_mod': aid_mod, 'AID_sev': aid_sev, 'AID_ext': aid_ext})

for sub in ["WMED", "EMED"]:

    myindex = aid_subregions[sub][f"w{window}"]["moderate"].index.strftime("%Y-%m")
    region  = sub #* len(myindex)
    aid_mod = aid_subregions[sub][f"w{window}"]["moderate"].values
    aid_sev = aid_subregions[sub][f"w{window}"]["severe"].values
    aid_ext = aid_subregions[sub][f"w{window}"]["extreme"].values
    aid_all = aid_mod + aid_sev + aid_ext

    dummy = pd.DataFrame({'date' : myindex, 'drought_index': f"{indicator}{window}", 'region': region, 'AID': aid_all, 'AID_mod': aid_mod, 'AID_sev': aid_sev, 'AID_ext': aid_ext})
    print(dummy)
    mypd = pd.concat([mypd, dummy])
    print(mypd)

mypd.to_csv(f"csv/MEDS_area_in_drought_{indicator}{window}.csv", decimal='.', float_format='%.2f', index=False)
