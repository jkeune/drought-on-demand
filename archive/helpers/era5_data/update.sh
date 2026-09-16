#!/bin/bash

module load cdo/2.6.0

yyyymmdd1="19900101" # start ERA5
yyyymmdd2="20260501" # end ERA5
yyyymmdd3="20260601" # start ERA5T
yyyymmdd4="20260801" # end ERA5T

mkdir data_retrieval
p_era5_grib="data_retrieval/precip_era5"
pet_era5_grib="data_retrieval/pet_era5"
./get_era_moda_precipitation.sh '90/-180/-90/180' ${yyyymmdd1} ${yyyymmdd2} ${p_era5_grib}
./get_era_moda_potevaporation.sh '90/-180/-90/180' ${yyyymmdd1} ${yyyymmdd2} ${pet_era5_grib}
#./get_era_moda_precipitation.sh '90/-180/-90/180' 19900101 20250701 data_retrieval/precip_19900101_20250701
#./get_era_moda_potevaporation.sh '90/-180/-90/180' 19900101 20250701 data_retrieval/pet_19900101_20250701

#cd data_retrieval
p_era5_nc="data_retrieval/precip_era5.nc"
pet_era5_nc="data_retrieval/pet_era5.nc"
cdo --eccodes -f nc copy -setgridtype,regular ${p_era5_grib} ${p_era5_nc}
cdo --eccodes -f nc copy -setgridtype,regular ${pet_era5_grib} ${pet_era5_nc}
#cdo --eccodes -f nc copy -setgridtype,regular precip_19900101_20250701 precip_19900101_20250701.nc
#cdo --eccodes -f nc copy -setgridtype,regular pet_19900101_20250701 pet_19900101_20250701.nc
#cd ..

p_era5t_grib="data_retrieval/precip_era5t"
pet_era5t_grib="data_retrieval/pet_era5t"
./get_erat_moda_precipitation.sh '90/-180/-90/180' ${yyyymmdd3} ${yyyymmdd4} ${p_era5t_grib}
./get_erat_moda_potevaporation.sh '90/-180/-90/180' ${yyyymmdd3} ${yyyymmdd4} ${pet_era5t_grib}
#./get_erat_moda_precipitation.sh '90/-180/-90/180' 20250801 20250901 data_retrieval/precip_era5t_20250801_20250901
#./get_erat_moda_potevaporation.sh '90/-180/-90/180' 20250801 20250901 data_retrieval/pet_era5t_20250801_20250901

#cd data_retrieval
p_era5t_nc="data_retrieval/precip_era5t.nc"
pet_era5t_nc="data_retrieval/pet_era5t.nc"
cdo -eccodes -f nc copy -setgridtype,regular ${p_era5t_grib} ${p_era5t_nc}
cdo -eccodes -f nc copy -setgridtype,regular ${pet_era5t_grib} ${pet_era5t_nc}
#cdo --eccodes -f nc copy -setgridtype,regular precip_era5t_20250801_20250901 precip_era5t_20250801_20250901.nc
#cdo --eccodes -f nc copy -setgridtype,regular pet_era5t_20250801_20250901 pet_era5t_20250801_20250901.nc
#cd ..

# merge all and calculate water balance for spei
#cd data_retrieval
cdo -mergetime ${pet_era5_nc} ${pet_era5t_nc} data_retrieval/pet_all.nc
#cdo -mergetime pet_19900101_20250701.nc pet_era5t_20250801_20250901.nc pet_all.nc
cdo -mergetime ${p_era5_nc} ${p_era5t_nc} data_retrieval/precip_all.nc
#cdo -mergetime precip_19900101_20250701.nc precip_era5t_20250801_20250901.nc precip_all.nc
cdo -expr,wb=tp-pev -merge data_retrieval/precip_all.nc data_retrieval/pet_all.nc data_retrieval/wb_all.nc
