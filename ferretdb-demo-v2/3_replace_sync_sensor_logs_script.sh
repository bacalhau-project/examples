#!/bin/bash
# this will copy averaged data-points
NEW_SYNC_SCRIPT="scripts/average_syncer.py"

# uncomment to switch to script that will copy all data-points
#NEW_SYNC_SCRIPT="scripts/sqlite_syncer.py"

bacalhau job run jobs/replace_sensor_logs_sync_script.yaml \
  -V code="$(base64 -w0 < $NEW_SYNC_SCRIPT)"
