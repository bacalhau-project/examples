#!/usr/bin/env bash

BACALHAU_INSTALL_ID=${BACALHAU_INSTALL_ID:-"BACA14A0-eeee-eeee-eeee-eeeeeeeeeeee"}

# Replace the last 12 characters of the BACALHAU_INSTALL_ID with random 12 characters
BACALHAU_INSTALL_ID=$(echo "${BACALHAU_INSTALL_ID}" | \
    python3 -c "
import sys
import uuid

id = sys.stdin.read().strip()
new_id = id[:-12] + uuid.uuid4().hex[:12]
print(new_id)
    ")

sudo curl https://get.bacalhau.org/install.sh?dl="${BACALHAU_INSTALL_ID}" | sudo bash
