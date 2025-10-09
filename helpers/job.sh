#!/bin/bash

#SBATCH --qos=nf
#SBATCH --job-name=spi_merge
#SBATCH --ntasks=1
#SBATCH --mem=128GB
#SBATCH --time=03:00:00
#SBATCH --mail-user=jessica.keune@ecmwf.int

set -u # fail when using an undefined variable
set -x # echo script lines as they are executedi
set -e # abort at first error

#module load Python/3.7.4-GCCcore-8.3.0
#module load h5py/2.10.0-intel-2019b-Python-3.7.4
#module load netcdf4-python/1.5.3-intel-2019b-Python-3.7.4
#module load cdo
#module load nco
#source $PERM/python-envs/myenv/bin/activate
module load python3/3.11.8-01

cd /home/nejk/code/drought_on_demand/helpers

#./merge_operational_era5.sh "spi" 1 "hr" 1940 2023
#./merge_operational_era5.sh "spi" 3 "hr" 1940 2023
#./merge_operational_era5.sh "spi" 6 "hr" 1940 2023
./merge_operational_era5.sh "spi" 24 "hr" 1942 2023
./merge_operational_era5.sh "spi" 24 "00" 1942 2023
./merge_operational_era5.sh "spi" 24 "01" 1942 2023
./merge_operational_era5.sh "spi" 24 "02" 1942 2023
./merge_operational_era5.sh "spi" 24 "03" 1942 2023
./merge_operational_era5.sh "spi" 24 "04" 1942 2023
./merge_operational_era5.sh "spi" 24 "05" 1942 2023
./merge_operational_era5.sh "spi" 24 "06" 1942 2023
./merge_operational_era5.sh "spi" 24 "07" 1942 2023
./merge_operational_era5.sh "spi" 24 "08" 1942 2023
./merge_operational_era5.sh "spi" 24 "09" 1942 2023

#python3 centaur_all_admins.py

exit
