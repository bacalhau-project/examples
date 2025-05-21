#!/bin/bash

#
# synchronize sqlite from all sensors to FerretDB
#

# override FERRETDB_URI for job, as it has no access to docker-compose's network and cannot resolve name of FerretDB container
export FERRET_IP=$(getent hosts ferretdb | awk '{print $1}')
export FERRETDB_URI="mongodb://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${FERRET_IP}:27017/postgres"

# run sensor logs syncer within daemon job
bacalhau job run /jobs/run_sensor_logs_syncer.yaml \
  -V code="$(base64 -w0 < /scripts/sqlite_syncer.py)" \
  -V loop_code="$(base64 -w0 < /scripts/sync_loop_script.sh)" \
  -V ferretdb_uri="${FERRETDB_URI}"
