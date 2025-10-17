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
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import matplotlib.dates as mdates
from matplotlib.dates import YearLocator, DateFormatter
from matplotlib.patches import Rectangle
        
yyyy      = 2025
mm        = "09"
minus     = 12-int(mm)

dataset   = "era5t"
stream    = "moda"
ref_syyyy = 1991
ref_eyyyy = 2020
yyyy_start= 1976
yyyy_end  = yyyy+1

for region in ["Global", "Europe"]:

    for indicator in ["SPI","SPEI"]:

        for window in [1,3,6,12,24,36,48]:
    
            if indicator == "SPEI":
                distribut = "genlogistic"
            if indicator == "SPI":
                distribut = "gamma"
            ipath     = f"/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/"
            lpath     = "/ec/vol/centaur/nejk/drought_monitor"
            cwd       = "/home/nejk/code/drought-on-demand"
            
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
            
            dates = pd.date_range(start=f"{yyyy_start}-01-01",end=f"{yyyy_end}-01-01", freq='ME')
            pdate_seq = [dt.datetime.strptime(str(i)[0:10], "%Y-%m-%d") for i in dates]#[window:]
            print(dates)
            
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
            
            #regionmask.defined_regions.natural_earth_v5_0_0.countries_110.plot()
            mask = regionmask.defined_regions.natural_earth_v5_0_0.countries_110.mask(lmask.lon, lmask.lat)
            mask = xr.where(mask >= 1, 1, np.nan)
            mask = xr.where( (bmask['barren_mask'][0,:,:] == 1) , np.nan, mask)

            # Adjust mask to regions
            if region == "Global":
                mask = mask
            if region == "Europe":
                # ESTOC region: -sellonlatbox,-25,40,34,72 # lon1, lon2, lat1, lat2
                mask = xr.where(mask.lon < -25, np.nan, mask) # lon1
                mask = xr.where(mask.lon > 40, np.nan, mask)  # lon2
                mask = xr.where(mask.lat < 34, np.nan, mask) # lat1
                mask = xr.where(mask.lat > 72, np.nan, mask)  # lat2

            
            filedate_seq = [dt.datetime.strftime(i, "%Y%m01") for i in pdate_seq[window:]]
            filelist = []
            for idate in filedate_seq[:-minus]:
                # /ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/
                ifile = f"{ipath}/era5/{idate}/hr/{indicator}{window}_{distribut}_global_era5_{stream}_ref{ref_syyyy}to{ref_eyyyy}_{str(idate)[:6]}.nc"
                if os.path.exists(ifile):
                    filelist.append(ifile)
                else:
                    ifile = f"{ipath}/era5t/{idate}/hr/{indicator}{window}_{distribut}_global_era5t_{stream}_ref{ref_syyyy}to{ref_eyyyy}_{str(idate)[:6]}.nc"
                    filelist.append(ifile)
            
            drought_index = {}
            drought_index[window] = xr.open_mfdataset(filelist)#.sel(lon=slice(lon1, lon2), lat=slice(lat2, lat1))
            
            masked_drought_index = drought_index[window] * mask
            masked_drought_index = xr.where(masked_drought_index == -9999, np.nan, masked_drought_index)
            
            area_2d = calculate_gridarea(masked_drought_index.lat, res=abs(masked_drought_index.lat[1]-masked_drought_index.lat[0]), nlon=len(masked_drought_index.lon))*lmask[0,:,:]
            area_2d = xr.DataArray(area_2d, coords={'lat': masked_drought_index.lat,'lon': masked_drought_index.lon}, dims=["lat", "lon"])
            area_2d_adj = area_2d * lmask_frac * mask
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
                tmp    = 100 * (dmask*area_3d_adj).sum(dim=["lat", "lon"]) / (mask*area_3d_adj).sum(dim=["lat", "lon"])
                aid[swindow][severity] = tmp.to_pandas()
            
                del(tmp, dmask)
            
            
            mylevels     = [-10000,-1000,-2,-1.5,-1,1,1.5,2,1000]
            mycollisthex = ['#bebebe','#663300','#8c6640','#b29980','#ffffff','#99b280','#668c40','#336600']
            
            
            def plot_area_in_drought_twopanels(aid, window, indicator, region="Global", figname="figures/test.png"):
                """
                Plots stacked area of drought by severity over time.
                Shows full (1980–today) and zoomed (2005–today) panels.
                """
            
                # --- Setup ---
                severities = ['extreme', 'severe', 'moderate']
                mycollisthex = ['#663300', '#8c6640', '#b29980']  # dark→light
                grey_color = 'dimgray'
            
                # --- Prepare Data ---
                pidata2 = aid[f'w{window}']['extreme']
                pidata3 = aid[f'w{window}']['severe']
                pidata4 = aid[f'w{window}']['moderate']
                apidata = pd.concat([pidata2, pidata3, pidata4], axis=1)
                apidata.columns = severities
                apidata = apidata.sort_index()
                x_num = mdates.date2num(apidata.index.to_pydatetime())
            
                # --- Time limits ---
                start_full = mdates.date2num(pd.Timestamp("1980-01-01"))
                start_zoom = mdates.date2num(pd.Timestamp("2005-01-01"))
                end_all = x_num[-1]
            
                # --- Figure ---
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharey=True)
                fig.suptitle(f"Area in drought ({region}) | {indicator}-{window}",
                             fontsize=16, weight='bold')
                fig.subplots_adjust(hspace=0.25, top=0.88)
            
                # --- 1. Full Record ---
                ax1.stackplot(x_num, [apidata[s] for s in severities],
                              labels=severities, colors=mycollisthex)
                ax1.set_xlim(start_full, end_all)
                ax1.set_ylim(0, 100)
                ax1.set_ylabel("Area in drought [%]", fontsize=10, labelpad=6)
                ax1.tick_params(axis='y', labelsize=9)
                ax1.yaxis.set_major_locator(plt.MultipleLocator(20))
                ax1.yaxis.set_minor_locator(plt.MultipleLocator(5))
                ax1.yaxis.grid(which='major', linestyle='-', color='gray', alpha=0.5)
                ax1.yaxis.grid(which='minor', linestyle=':', color='lightgray', alpha=0.3)
                for side in ['top', 'right', 'left']:
                    ax1.spines[side].set_visible(False)
                ax1.legend(ncol=1, loc='upper left', fontsize=9)
            
                ax1.xaxis.set_major_locator(YearLocator(10))
                ax1.xaxis.set_major_formatter(DateFormatter('%Y'))
                ax1.tick_params(axis='x', which='major', labelrotation=45, labelsize=9)
                ax1.spines['bottom'].set_visible(True)
                ax1.tick_params(bottom=True, labelbottom=True)
                ax1.xaxis_date()
            
                # --- Zoom box on top plot (lighter grey) ---
                ax1.axvspan(start_zoom, end_all, facecolor='none',
                            alpha=1, edgecolor=grey_color, linestyle='solid',
                            linewidth=2, zorder=1)
            
                # --- Subtitle for top plot ---
                ax1.text(0.01, 1.03, "1980–today", transform=ax1.transAxes,
                         fontsize=10, color=grey_color, weight='normal', va='bottom')
            
                # --- 2. Zoomed-In ---
                zoom_mask = apidata.index >= pd.Timestamp("2005-01-01")
                x_zoom = mdates.date2num(apidata.index[zoom_mask].to_pydatetime())
                ax2.stackplot(x_zoom, [apidata.loc[zoom_mask, s] for s in severities],
                              colors=mycollisthex)
                ax2.set_xlim(start_zoom, end_all)
                ax2.set_ylim(0, 100)
                ax2.set_ylabel("Area in drought [%]", fontsize=10, labelpad=6)
                ax2.tick_params(axis='y', labelsize=9)
                ax2.yaxis.set_major_locator(plt.MultipleLocator(20))
                ax2.yaxis.set_minor_locator(plt.MultipleLocator(5))
                ax2.yaxis.grid(which='major', linestyle='-', color='gray', alpha=0.5)
                ax2.yaxis.grid(which='minor', linestyle=':', color='lightgray', alpha=0.3)
                for side in ['top', 'right', 'left']:
                    ax2.spines[side].set_visible(False)
            
                ax2.set_xlabel("Year", fontsize=10, labelpad=6)
                ax2.xaxis.set_major_locator(YearLocator(2))
                ax2.xaxis.set_major_formatter(DateFormatter('%Y'))
                ax2.tick_params(axis='x', which='major', labelrotation=45, labelsize=9)
                ax2.spines['bottom'].set_visible(True)
                ax2.tick_params(bottom=True, labelbottom=True)
                ax2.xaxis_date()
            
                # --- Dark gray outline box around the second subplot ---
                ylim = ax2.get_ylim()
                rect = Rectangle((start_zoom, ylim[0]),
                                 end_all - start_zoom,
                                 ylim[1] - ylim[0],
                                 linewidth=2, edgecolor=grey_color,
                                 facecolor='none', zorder=6)
                ax2.add_patch(rect)
                rect.set_clip_on(False)
            
                # --- Subtitle for bottom plot ---
                ax2.text(0.01, 1.03, "2005–today", transform=ax2.transAxes,
                         fontsize=10, color=grey_color, weight='normal', va='bottom')
            
                # --- Last entry values annotation ---
                last_values = apidata.loc[apidata.index[-1], severities]
                total = last_values.sum()
                textstr = f"{yyyy}-{int(mm):02d}\n$\\bf{{Total\\ area\\ in\\ drought: {total:5.1f}\\%}}$\nModerate drought: {last_values['moderate']:5.1f}%\nSevere drought: {last_values['severe']:5.1f}%\nExtreme drought: {last_values['extreme']:5.1f}%"
                ax2.annotate(textstr,
                             xy=(x_zoom[-1], total), xycoords='data',
                             xytext=(x_zoom[-1] - 35, 55), textcoords='data',
                             arrowprops=dict(facecolor=grey_color, arrowstyle="->"),
                             fontsize=10, color='black', weight='normal',
                             va='bottom', ha='right')
                plt.savefig(
                    figname,
                    dpi=300,
                    bbox_inches="tight",
                    pad_inches=0.1,
                ) 
                plt.show()
            
            plot_area_in_drought_twopanels(aid, window, indicator, region=region,
                    figname = f"figures/{indicator}{window}_{region}_timeseries.png",)
