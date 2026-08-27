# (C) Copyright 1996- ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

import eccodes as ec
import numpy as np
import pandas as pd
import netCDF4 as nc4
import os
import datetime as datetime

def load_grb_file(FNAME,retKeys=None,verbose=False):
  """
  Loads full grib file
  xdata,xKeys=load_for_file(FNAME,retKeys=None,verbose=False)
  input:
   FNAME: file name (including full path) to read from
   retKeys: list with extra keys to return (default: None)
   verbose: if true print some details
  returns
   xdata : np.array: (nflds,npoints)
   xKeys : if retKeys is not None: dictionary with a list for each key requested
  """

  if verbose:
    print('Reading:',FNAME)
  # open file
  fgrb = open(FNAME)
  # find # of fields in file
  nflds = ec.codes_count_in_file(fgrb)
  if verbose:
    print('Found ', nflds,' fields in,',FNAME)

  # create dictionary with empty lists for each requested key
  xKeys={}
  if retKeys is not None:
    for key in retKeys:
      xKeys[key]=[]

  # load fields
  for ikfld in range(nflds):
    gid = ec.codes_grib_new_from_file(fgrb)
    xtmp = ec.codes_get_values(gid)
    if ec.codes_get(gid,'bitmapPresent') == 1:
      zmiss=ec.codes_get(gid,'missingValue')
      xtmp[xtmp==zmiss]=np.nan
    if ikfld == 0  :
      xdata = np.zeros((nflds,xtmp.shape[0]),dtype=np.float32)
    xdata[ikfld,:] = xtmp
    if retKeys is not None:
      for key in retKeys:
        xKeys[key].append(ec.codes_get(gid,key))

    ec.codes_release(gid)

  fgrb.close()
  if retKeys is not None:
    for kk in xKeys.keys():
      xKeys[kk] = np.array(xKeys[kk])
    return xdata,xKeys
  else:
    return xdata

def write_grb_file(ofile, template, data, ZMISS=-99):
    """
    Makes a copy of template and writes data into ofile
    """
    fin = open(template, 'rb')
    fout = open(ofile, 'wb')
    ikfld=0
    
    while 1:
        gid = ec.codes_grib_new_from_file(fin)
        if gid is None:
          break
        clone_id = ec.codes_clone(gid)
        ec.codes_set(clone_id,'bitsPerValue',12)
        ec.codes_set(clone_id,'bitmapPresent',1)
        ec.codes_set(clone_id,'missingValue',ZMISS)
        xtmp = np.ma.filled(data, ZMISS)
        ec.codes_set_values(clone_id, xtmp)
        #ec.codes_set_values(clone_id, data)
        ec.codes_write(clone_id, fout)
        ec.codes_release(clone_id)
        ec.codes_release(gid)
        ikfld=ikfld+1
    fin.close()
    fout.close()
    print(ikfld,' fields written to:',ofile)

def writenc(
    ofile,
    fdate_seq,
    glon,
    glat,
    rspi,
    sspi,
    precision='f8',
):
    # delete nc file if it is present (avoiding error message)
    try:
        os.remove(ofile)
    except OSError:
        pass

    # create netCDF4 instance
    nc_f = nc4.Dataset(ofile, "w", format="NETCDF4")

    ### create dimensions ###
    nc_f.createDimension("time", len(fdate_seq))
    nc_f.createDimension("lat", glat.size)
    nc_f.createDimension("lon", glon.size)

    # create variables
    times = nc_f.createVariable("time", "f8", "time")
    latitudes = nc_f.createVariable("lat", "f8", "lat")
    longitudes = nc_f.createVariable("lon", "f8", "lon")
    spi = nc_f.createVariable(
        "SPI",
        precision,
        ("time", "lat", "lon"),
        fill_value=nc4.default_fillvals[precision]
    )
    sig_spi = nc_f.createVariable(
        "Significance of SPI",
        precision,
        ("time", "lat", "lon"),
        fill_value=nc4.default_fillvals[precision]
    )

    # set attributes
    nc_f.title = "SPI"
    nc_f.description = "Drought Index: Standardized Precipitation Index (SPI) calculated according to the WMO guidelines (see https://library.wmo.int/doc_num.php?explnum_id=7768), using monthly precipitation totals from ERA5 as input."
    today = datetime.datetime.now()
    nc_f.history = "Created " + today.strftime("%d/%m/%Y %H:%M:%S") + " using SPIDI."
    nc_f.institution = (
        "ECMWF"
    )
    nc_f.source = (
        "SPIDI v0.1"
    )
    times.units = "hours since 1900-01-01 00:00:00"
    times.calendar = "Standard"  # do NOT use gregorian here!
    latitudes.units = "degrees_north"
    longitudes.units = "degrees_east"
    spi.units = "-"
    spi.long_name = "Standardized Precipitation Index (SPI)"
    sig_spi.units = "-"
    sig_spi.long_name = "Significance of Standardized Precipitation Index (SPI)"
    
    # write data
    times[:] = nc4.date2num(fdate_seq, times.units, times.calendar)
    longitudes[:] = glon
    latitudes[:] = glat
    #rspi = np.nan_to_num(rspi, posinf=np.nan, neginf=np.nan)
    rspi = np.nan_to_num(rspi, nan=-9999, posinf=99999, neginf=-99999)
    spi[:,:,:] = rspi
    #sspi = np.nan_to_num(sspi, posinf=np.nan, neginf=np.nan)
    sspi = np.nan_to_num(sspi, nan=-9999, posinf=99999, neginf=-99999)
    sig_spi[:,:,:] = sspi
    
    # close file
    nc_f.close()
    print(
        "\n * Created file: "
        + ofile
        + " of dimension ("
        + str(len(fdate_seq))
        + ","
        + str(glat.size)
        + ","
        + str(glon.size)
        + ") !"
    )

def read_landmask(ifile):
    if os.path.isfile(str(ifile)):
        print("Reading landmask from file "+str(ifile))
        mask = load_grb_file(ifile, verbose=False)[0,:]
        return mask
    else:
        return None
    
def check_landmask(landmask, refdata):
    if landmask is None:
        return np.ones(shape=refdata.shape)
    elif (landmask is not None) and (landmask.shape != refdata.shape):
        print("The shape of the landmask is off! Processing all points.")
        return np.ones(shape=refdata.shape)
    else:
        return landmask
    
def get_landpoints_index(landmask, landmask_value=1):
    return np.where(landmask==landmask_value)[0]

def to_pandas(array, time_index):
    dfdata = pd.DataFrame(array, index=time_index)
    dfdata.index = pd.to_datetime(dfdata.index)
    return dfdata

