#!/bin/bash

# This script downloads many files from https://picsum.photos/500/500/
# And adds them one at a time to bacalhau

# The number of images to download
NUM_IMAGES=${2:-1}

# Label to use for the images
LABEL=${1:-"pintura-default-sd"}

# Use the third argument as the pid file
PID_FILE=${3:-"/var/run/bacalhau-image-creator-add-many-images.pid"}

# If the pid file exists, it's already running, so just exit
if [ -f "${PID_FILE}" ]; then
    echo "Already running. PID: $(cat "${PID_FILE}")"
    exit 1
fi

# Save the pid of this process
echo $$ > "${PID_FILE}"

# Loop running the bacalhau binary NUM_IMAGES times
for i in $(seq 1 "$NUM_IMAGES"); do
    # Add the image to bacalhau

        --id-only
done 

# Remove the pid file
rm "${PID_FILE}"