#!/bin/bash

# retrieves precipitation montly means of daily values from ERA5 for a range of years in one file
#
# usage
# ./get_era_moda_precipitation.sh 'N/W/S/E' startdate enddate filename
# ./get_era_moda_precipitation.sh '90/-180/-90/180' 19400101 20230901 precipitation.grb
#

# settings
coords=$1
startdate=$2
syyyy=${startdate:0:4}
smm=${startdate:4:2}
enddate=$3
eyyyy=${enddate:0:4}
emm=${enddate:4:2}
ofile=$4

# construct date sequence moda stream
alldates=""
for yyyy in `seq $syyyy $eyyyy`; do
	if [ "$yyyy" == "$syyyy" ]; then sm=${smm##+(0)}; else sm=1; fi 
	if [ "$yyyy" == "$eyyyy" ]; then em=${emm##+(0)}; else em=12; fi 
        for im in `seq $sm $em`; do
		mm=$(printf "%02d" $im)
                alldates+="${yyyy}${mm}01/"
        done
done
# remove last /
alldates=${alldates::-1}
echo $alldates

# PRECIPITATION
cp retrieve_era5_moda_precipitation_all.template retrieve_era5_moda_precipitation_${startdate}${enddate}

# modify parameter retrieval (adjust region and dates)
sed -i "s,__NORTH_WEST_SOUTH_EAST__,$coords,g" retrieve_era5_moda_precipitation_${startdate}${enddate}
sed -i "s,__DATES__,$alldates,g" retrieve_era5_moda_precipitation_${startdate}${enddate}
sed -i "s,__OFILE__,$ofile,g" retrieve_era5_moda_precipitation_${startdate}${enddate}

# run mars
export TMPDIR=$SCRATCHDIR
mars retrieve_era5_moda_precipitation_${startdate}${enddate}

exit
