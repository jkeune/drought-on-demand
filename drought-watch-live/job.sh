#!/bin/bash

### sbatch 003_job.sh
### sbatch --array=3-12 003_job.sh

#SBATCH --qos=nf
#SBATCH --job-name=drought_watch
#SBATCH --ntasks=1
##SBATCH --mem=64G
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --mail-user=jessica.keune@ecmwf.int

set -u # fail when using an undefined variable
set -x # echo script lines as they are executedi
set -e # abort at first error

module load python3/3.11.10-01
module load cdo


cd /home/nejk/code/drought-on-demand/drought-watch-live
python3 update.py


exit
