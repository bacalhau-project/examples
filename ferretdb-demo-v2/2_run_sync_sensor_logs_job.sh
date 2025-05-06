#!/bin/bash

#
# synchronize sqlite from all sensors to FerretDB
#

if [ "x${FERRETDB_URI}" == "x" ]; then
  echo "There is no FERRETDB_URI defined (i.e. mongodb://expansouser:safepassword@127.0.0.1/postgres)"
  exit 1
fi

bacalhau job run /jobs/run_sensor_logs_syncer.yaml --template-vars "code=$(cat /scripts/sqlite_syncer.py | base64 -w0),loop_code=$(cat /scripts/sync_loop_script.sh | base64 -w0),ferretdb_uri=${FERRETDB_URI}"

