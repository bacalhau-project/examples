#!/bin/bash

# run sensor simulator within daemon job
bacalhau job run /jobs/generate_sensor_logs_job.yaml \
  -V config="$(base64 -w0 < /scripts/sensor_config.yaml)" \
  -V identity="$(base64 -w0 < /scripts/node_identity.json)"
