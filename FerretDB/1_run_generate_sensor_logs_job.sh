#!/bin/bash

JOB_ID=$(bacalhau job run generate_sensor_logs_job.yaml)
echo $JOB_ID > generate_sensor_log_job_id.txt
