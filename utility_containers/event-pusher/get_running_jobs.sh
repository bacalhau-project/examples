#!/usr/bin/env bash
bacalhau job list --output json --limit 1000 | jq -r '
  ["JOB_ID", "IMAGE", "STATUS", "STARTED"],
  (.[] | select(.State.StateType == "Running") | 
  [.ID, .Tasks[0].Engine.Params.Image, .State.StateType, (.CreateTime/1000000|strftime("%Y-%m-%d %H:%M"))]) | 
  @tsv' | 
  column -t
