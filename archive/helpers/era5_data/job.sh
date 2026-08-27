#!/bin/bash

#SBATCH --qos=nf
#SBATCH --job-name=era5
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

module load cdo
cd /home/nejk/code/drought-on-demand/helpers/era5_data
./update.sh



exit
