import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.colors import BoundaryNorm
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator)
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter
from mpl_toolkits.basemap import Basemap
from mpl_toolkits.basemap import shiftgrid
import numpy as np
import os
import datetime as dt
import pandas as pd
import geopandas as gpd
import shapely
import sys
import calendar
import netCDF4 as nc4
import xarray as xr
#xr.set_options(display_expand_attrs=False)
from dateutil import relativedelta
from datetime import timedelta
import fiona
from shapely.geometry import shape
import pprint
import regionmask

from helpers.geodata import calculate_gridarea

## Settings
syyyy = 1991
eyyyy = 2023
severity_list = ['moderate','severe','extreme','any']
ipath_ecmwf = "/ec/vol/centaur/nejk/drought_monitor"

# read landmasks
varname       = "var172"
# binary mask (0/1)
ifile_name    = "landmask_era5_global.nc"
ifile         = os.path.join("/home/nejk/code/drought_on_demand/masks", ifile_name)
landmask_ecm = xr.open_dataset(ifile)[varname]
landmask_ecm = landmask_ecm.where( landmask_ecm.values == 1 )
landmask_ecm.plot()
# fraction mask (0-1)
ifile_name     = "landmask_era5_global_frac.nc"
ifile          = os.path.join("/home/nejk/code/drought_on_demand/masks", ifile_name)
landmaskfr_ecm = xr.open_dataset(ifile)[varname]
landmaskfr_ecm = landmaskfr_ecm.where( landmaskfr_ecm.values >= 0 )
landmaskfr_ecm.plot()

# grid area
area_2d_ecm = calculate_gridarea(landmask_ecm.lat, res=abs(landmask_ecm.lat[1]-landmask_ecm.lat[0]), nlon=len(landmask_ecm.lon))*landmask_ecm[0,:,:]
area_2d_ecm = xr.DataArray(area_2d_ecm, coords={'lat': landmask_ecm.lat,'lon': landmask_ecm.lon}, dims=["lat", "lon"])
#area_2d_ecm.plot()

# adjust using land fraction
area_2d_adj_ecm = area_2d_ecm * landmaskfr_ecm
area_2d_adj_ecm.plot()
#(area_2d_ecm - area_2d_adj_ecm).plot()
print(area_2d_adj_ecm.shape)

#### Read ADMIN shp and get all ADMIN IDs
shppath="/ec/vol/centaur/wfs_data/0_FEWSNET_ADMIN/ColdCases"
adminshp=f"{shppath}/MZ_Admin1_2021.shp"
# Open the shapefile with gpd
shapefile=gpd.read_file(adminshp)
#print(shapefile)
print(shapefile['ADMIN1'])
print(shapefile['FNID'])
fnids = shapefile['FNID']

for ifnid in fnids:

    print(ifnid)
    fnshp = shapefile.loc[ (shapefile.FNID.isin([ifnid])), 'geometry' ]
    fnshp = fnshp.to_crs('epsg:4326')
    #plt.figure()
    #fnshp.plot()

    #print(fnshp.index.values)
    adminmask = regionmask.mask_geopandas(fnshp, landmask_ecm.lon, landmask_ecm.lat)
    adminmask = xr.where(adminmask == fnshp.index.values, 1, np.nan) # otherwise this increases and the mask has values 0-len(fnids)
    #print(adminmask.shape)
    #plt.figure()
    #adminmask.plot()

    # calculate area in drought
    indicator="SPI"
    aid_spi_ecm = {}
    for window in [1,3,6,12,24,36,48]:
    #for window in [1, 3]:

        print(f"Processing SPI-{window}")
        swindow=f"w{window}"
        aid_spi_ecm = {}
        #aid_spi_ecm[swindow] = {}

        for severity in severity_list:
            ivar = f"{indicator}{window}_{severity}"
            aid_spi_ecm[ivar] = pd.Series()

        date_list_ecm = []
        for iyyyy in range(syyyy, eyyyy+1):
            for imonth in range(1,13):

                idate = f"{iyyyy}-{str(imonth).zfill(2)}"
                date_list_ecm.append(f"{iyyyy}-{str(imonth).zfill(2)}")

                ifile   = os.path.join(f"{ipath_ecmwf}/{indicator.lower()}/{indicator.lower()}{window}", f"{indicator}{window}_gamma_global_era5_moda_ref1991to2020_{iyyyy}{str(imonth).zfill(2)}.nc")
                spi_ecm = xr.open_dataset(ifile)[f'{indicator}{window}']
                spi_ecm = xr.where(spi_ecm == -9999, np.nan, spi_ecm).isel(time=0)

                for severity in severity_list:

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

                    # calculate area in drought
                    rspi   = spi_ecm.copy()*adminmask
                    dmask  = xr.where((rspi > thresh_min) & (rspi <= thresh_max), 1, np.nan)
                    tmp    = 100 * (dmask*area_2d_adj_ecm).sum(dim=["lat", "lon"]) / (adminmask*area_2d_adj_ecm).sum(dim=["lat", "lon"])

                    ivar = f"{indicator}{window}_{severity}"
                    aid_spi_ecm[ivar] = pd.concat([aid_spi_ecm[ivar], pd.Series({'aid': tmp.values[0]})], ignore_index=True)
                    #aid_spi_ecm[ivar] = pd.Series({'aid': tmp.values[0]})

        #print(aid_spi_ecm)

        # write to dataframe to write to csv
        dfdata = pd.DataFrame(aid_spi_ecm)
        dfdata.index = pd.to_datetime(date_list_ecm).strftime('%Y%m%d')
        dfdata.index.name = "YYYYMMDD"
        #print(dfdata)

        start_index = pd.to_datetime(date_list_ecm[0]).strftime('%Y%m%d')
        end_index   = pd.to_datetime(date_list_ecm[-1]).strftime('%Y%m%d')
        save_name = f"MOZ_WFS_0001_{indicator}{window}_{start_index}_{end_index}_AID_{ifnid}.csv"
        #save_path = os.path.join(tif_dir,save_name)
        print(save_name)
        dfdata.to_csv(save_name)

