#!/bin/bash

#
# synchronize sqlite from all sensors to FerretDB
#

if [ "${FERRETDB_URI}" == "x" ]; then
  echo "There is no FERRETDB_URI defined (i.e. mongodb://expansouser:safepassword@127.0.0.1/postgres)"
  exit 1
fi

# run sensor logs syncer within daemon job
bacalhau job run /jobs/run_sensor_logs_syncer.yaml \
  -V code="$(base64 -w0 < /scripts/sqlite_syncer.py)" \
  -V loop_code="$(base64 -w0 < /scripts/sync_loop_script.sh)" \
  -V ferretdb_uri="${FERRETDB_URI}"

