#!/bin/bash

# override FERRETDB_URI for job, as it has no access to docker-compose's network and cannot resolve name of FerretDB container
export FERRET_IP=$(getent hosts ferretdb | awk '{print $1}')
export FERRETDB_URI="mongodb://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${FERRET_IP}:27017/postgres"

bacalhau job run /jobs/clean_sensor_logs_data_job.yaml \
  -V code="$(base64 -w0 < /scripts/cleanup_mongodb.py)" \
  -V ferretdb_uri="${FERRETDB_URI}"
