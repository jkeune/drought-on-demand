#!/usr/bin/bash

pwrd=`cat master_token2`
echo $pwrd

# using sitesctl (local copy from chris)
# ./sitesctl site content --help
./sitesctl site  --space nejk --name drought-watch-live --api-authentication-token $pwrd content upload --source index.html -f
./sitesctl site  --space nejk --name drought-watch-live --api-authentication-token $pwrd content upload --source figures --match *.png --destination figures/ -f

#module load lftp

# Start lftp session
#lftp https://nejk:${pwrd}@sites.ecmwf.int/nejk/drought-watch-live
#lftp https://nejk:${pwrd}@sites.ecmwf.int/nejk/drought-watch-live <<EOF
#mput *.html
#bye
#EOF
