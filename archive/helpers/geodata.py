# (C) Copyright 1996- ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

import numpy as np
import pandas as pd
import geopandas as gpd

EARTHRADIUS = 6371  # earth radius [km]

def calculate_gridarea(lats_centr, res, nlon):
    """
    INPUT
        - lats_centr :  latitute of the center [deg N], between -90 to +90 (float or 1D np ary)
        - res :         regular (!) grid resolution [deg]
        - nlon :        to return array of dim (nlat x nlon)

    RETURNS
        - area :        EXACT gridded area, shape as defined by input [km^2] as array of dimension (nlon x nlat)

    ACTION
        based on the grid spacing inferred by lats & lons,
        areas of all grid cells specified by indices and coordinates (lats)
        are computed and summed up in the end.
        Since the spacing between grid cell border longitudes ALWAYS remains
        the same, that is, the resolution in degrees, this function does NOT
        rely on any longitudinal input.

    CAUTION
        1.) this will NOT work properly close to the poles!
        2.) this is based on input coordinates referring to CENTROIDS
        3.) only for regular grids (independent from longitude)
        4.) will produce CRAP if / results in integer division (Python 2.7) !

    NOTES
        - original formula, using degrees (caution -- np.sin requires radian)
            A = (pi/180)R^2 |sin(lat1)-sin(lat2)| |lon1-lon2|
          obtained from:
            pmel.noaa.gov/maillists/tmap/ferret_users/fu_2004/msg00023.html

    """

    ## make use of numpy vectorization
    lats1 = (lats_centr + (res / 2)) * np.pi / 180  # np.sin requires radians
    lats2 = (lats_centr - (res / 2)) * np.pi / 180
    areas = (
        (np.pi / 180) * (EARTHRADIUS ** 2) * np.abs(np.sin(lats1) - np.sin(lats2)) * res
    )

    ## overwrite any areas of 0 (at the poles) with np.NaN to prevent problems
    areas[np.where(areas == 0.0)] = np.nan  # only works for arrays
    # return array of dimension nlat x nlon
    area_2d = np.swapaxes(np.tile(areas, (nlon, 1)), 0, 1)
    return area_2d


# get mask of grid points in countryshp
def grid2df(grid_lon2d, grid_lat2d, ret='gpd', **kwargs):
    # creates either a pandas(ret=pd) or geopandas (ret=gpd) dataframe of all grid points (lon2d, lat2d = np.meshgrid(...))
    df = pd.DataFrame({'lon': grid_lon2d.reshape(-1), 'lat': grid_lat2d.reshape(-1)})
    if ret=='pd':
        return df
    else:
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), **kwargs)
        return gdf

def mask_gridpoints_in_polygon(gridpoint_df, polygon, return_shape=None, **kwargs):
    # returns a mask (0,1) of 2d shape, indicating of grid points are in polygon
    if return_shape is None:
        return_shape = (gridpoint_df.shape[0],)
        print(return_shape)
    gpinside= gridpoint_df.within(polygon).astype(int).values
    mask    = np.asarray(gpinside).reshape(return_shape)
    return mask

def mask_3darray(data_3d, mask_2d, maskval=1, fillval=0):
    # data_3d of dimension time x lat x lon
    # mask_2d of dimension        lat x lon
    # masking all but maskval(default=1) values
    index_in = np.where(mask_2d == maskval)
    #assert fillval in [0, np.nan]
    #if fillval == 0:
    #    data_3d_masked = np.zeros(data_3d.shape)
    #if np.isnan(fillval):
    data_3d_masked = np.full_like(data_3d, np.nan)
    for i in range(len(index_in[0])):
        data_3d_masked[:,index_in[0][i],index_in[1][i]] = data_3d[:,index_in[0][i],index_in[1][i]]
    return data_3d_masked
