#! /usr/bin/env bash
set -e

# Define the file list directly in the script
FILE_LIST_JSON='{
    "/root/cities.json": "https://gist.githubusercontent.com/aronchick/959e3f35a825ea1e3c5956cdc2280fc9/raw/3bae74a23cacec1381ae18caac5e2cf63206531e/cities.json",
    "/root/config.yaml": "https://gist.githubusercontent.com/aronchick/8fbb7edd71493b08708da701e69033f7/raw/a787cd9ed284c2fbe2ca22e2c3ae0759c02943e1/config.yaml",
    "/root/node_identity.json": "https://gist.githubusercontent.com/aronchick/5460df4815de1596fc7130e362d64755/raw/213f8ec8666f754bed5eb030d87780af14229550/node-identity.json"
}'

# Encode the file list
FILE_LIST_B64=$(echo "$FILE_LIST_JSON" | base64 -w 0)

echo "Processing files..."
bacalhau job run jobs/upload_file.yaml \
    -V script_b64="$(cat jobs/write_file.py | base64 -w 0)" \
    -V file_list_b64="$FILE_LIST_B64" \
    -V count=3

echo "File processing complete."