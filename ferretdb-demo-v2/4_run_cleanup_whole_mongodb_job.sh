#!/bin/bash

if [ "x${FERRETDB_URI}" == "x" ]; then
  echo "There is no FERRETDB_URI defined (i.e. mongodb://expansouser:safepassword@127.0.0.1/postgres)"
  exit 1
fi

bacalhau job run /jobs/clean_sensor_logs_data_job.yaml --template-vars "code=$(cat /scripts/cleanup_mongodb.py | base64 -w0),ferretdb_uri=${FERRETDB_URI}"
