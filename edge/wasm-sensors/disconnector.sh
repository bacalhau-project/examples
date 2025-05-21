#!/bin/bash

ACTION_TO_PERFORM=$1
REGION="edge-eu"
DOCKER_ACTION=""
FINAL_VERB_STATE_STRING=""
TARGET_DOCKER_STATE_JSON="" # Used for grep in JSON output: "running" or "paused"

# Validate and map arguments
if [[ "$ACTION_TO_PERFORM" == "connect" ]]; then
    DOCKER_ACTION="unpause"
    FINAL_VERB_STATE_STRING="Connected"
    TARGET_DOCKER_STATE_JSON="running"
elif [[ "$ACTION_TO_PERFORM" == "disconnect" ]]; then
    DOCKER_ACTION="pause"
    FINAL_VERB_STATE_STRING="Disconnected"
    TARGET_DOCKER_STATE_JSON="paused"
else
    echo "Usage: $0 [connect|disconnect]"
    echo "  connect    - Attempts to connect (unpause) all nodes for '$REGION'."
    echo "  disconnect - Attempts to disconnect (pause) all nodes for '$REGION'."
    exit 1
fi

# Execute the Docker command, redirecting all output (stdout and stderr) to /dev/null
# This hides all errors, warnings, and normal output from the docker compose command.
docker compose $DOCKER_ACTION $REGION > /dev/null 2>&1

# Query current state to count nodes

# Get total number of nodes for the region
# `wc -l` on `docker compose ps` (after header) gives the count.
# Use awk to ensure only the number is captured if wc -l adds padding.
total_nodes_raw=$(docker compose ps $REGION 2>/dev/null | tail -n +2 | wc -l)
total_nodes=$(echo $total_nodes_raw | awk '{print $1}')

# Get JSON output for detailed state parsing
ps_json_output=$(docker compose ps $REGION --format json 2>/dev/null)

nodes_in_target_state=0
# Only try to parse JSON if total_nodes > 0 and ps_json_output is not empty/null
if [[ "$total_nodes" -gt 0 && -n "$ps_json_output" && "$ps_json_output" != "null" && "$ps_json_output" != "[]" ]]; then
    # Count how many nodes are in the TARGET_DOCKER_STATE_JSON (e.g., "running" or "paused")
    # grep -c counts lines matching the pattern.
    nodes_in_target_state=$(echo "$ps_json_output" | grep "\"State\":\"$TARGET_DOCKER_STATE_JSON\"" -c)
fi

# Print the final simplified summary
echo "$nodes_in_target_state/$total_nodes Nodes $FINAL_VERB_STATE_STRING"

exit 0