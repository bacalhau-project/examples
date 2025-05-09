#!/bin/bash

# run sensor simulator within daemon job
bacalhau job run /jobs/generate_sensor_logs_job.yaml \
  --template-vars "config=$(cat /scripts/sensor_config.yaml | base64 -w0)" \
  --template-vars "identity=$(cat /scripts/node_identity.json | base64 -w0)"
