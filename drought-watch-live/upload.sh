#!/usr/bin/bash

pwrd=`cat master_token`

module load lftp

# Start lftp session
lftp https://nejk:${pwrd}@sites.ecmwf.int/nejk/drought-watch-live <<EOF
mput *.html
bye
EOF
