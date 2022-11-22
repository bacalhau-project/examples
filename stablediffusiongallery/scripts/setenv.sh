#!/usr/bin/env bash
set -e

# If $1 is not empty, the reject the script
if [ $# -eq 0 ]; then
    echo "This script should not be called with any arguments."
    exit 1
fi

# Sets the env variables for the ./install.sh script
envFile=$1


# Show env vars
# grep -v '^#' "${envFile}" | grep -o '^[^#]*'

# Export env vars
export "$(grep -v '^#' ${envFile} | grep -o '^[^#]*' | xargs)"