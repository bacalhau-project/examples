#!/bin/bash

NEW_SYNC_SCRIPT="scripts/average_syncer.py"
#NEW_SYNC_SCRIPT="scripts/sqlite_syncer.py"

bacalhau job run jobs/replace_sensor_logs_sync_script.yaml --template-vars "code=$(cat $NEW_SYNC_SCRIPT | base64 -w0)"
