#!/bin/bash

module load cdo

#indi="spei"
indi=$1
#window=12
window=$2
#iens="hr"
iens=$3
#syyyy=1990
syyyy=$4
#eyyyy=2023
eyyyy=$5
dd="01"
file_list=""

ipath="/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/era5/"
opath="/ec/vol/centaur/nejk/drought_monitor/tmp"
if [ "$indi" == "spi" ]; then distrib="gamma"; fi
if [ "$indi" == "spei" ]; then distrib="genlogistic"; fi
if [ "$iens" == "hr" ]; then stream="moda"; else stream="edmo_ens${iens}"; fi

for yyyy in `seq $syyyy $eyyyy`; 
do
	for im in `seq 1 12`; do
		mm=$(printf "%02d" $im)
		
		ifile=${ipath}/${yyyy}${mm}${dd}/${iens}/${indi}/${indi}${window}/${indi^^}${window}_${distrib}_global_era5_${stream}_ref1991to2020_${yyyy}${mm}.nc
		#/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/era5/19740601/hr/spei/spei6/SPEI6_genlogistic_global_era5_moda_ref1991to2020_197406.nc
		#/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/era5/19740601/09/spei/spei6/SPEI6_genlogistic_global_era5_edmo_ens09_ref1991to2020_197406.nc
	
		echo $ifile
		file_list+="${ifile} "

	done
done
echo $file_list

ofile="${opath}/${indi^^}${window}_${distrib}_global_era5_${stream}_ref1991to2020_${syyyy}to${eyyyy}.nc"
cdo mergetime $file_list $ofile
