#!/bin/bash

# This script downloads many files from https://picsum.photos/500/500/
# And adds them one at a time to bacalhau

# The number of images to download
NUM_IMAGES=10

# Label to use for the images
LABEL="pictura-test"

# Loop running the bacalhau binary NUM_IMAGES times
for i in $(seq 1 $NUM_IMAGES); do
    # Download the image
    URL=https://picsum.photos/500/500/

    # Add the image to bacalhau
    bacalhau docker run \
    --id-only
    --input-urls $URL \
    -l $LABEL \
    ubuntu -- cp -rv /inputs/. /outputs/
done 
