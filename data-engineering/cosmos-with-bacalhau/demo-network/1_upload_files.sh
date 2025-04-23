#! /usr/bin/env bash
set -e

# Get count of nodes in the network
COUNT=$(bacalhau node list --output json | jq -r '[.[] | select(.Info.NodeType == "Compute")] | length')
NUM_CITIES=${NUM_CITIES:-20}

echo "Processing config.yaml..."
bacalhau job run jobs/upload_file.yaml \
    -V script_b64="$(cat jobs/add_sensor_config.py | base64 -w 0)" \
    -V file_b64="$(cat files/sensor-config.yaml | base64 -w 0)" \
    -V file_name="config.yaml" \
    --id-only \
    -V count="$COUNT" \
    --wait

echo "Processing node_identity.json..."
bacalhau job run jobs/upload_file.yaml \
    -V script_b64="$(cat jobs/add_sensor_config.py | base64 -w 0)" \
    -V file_b64="$(cat files/node-identity.json | base64 -w 0)" \
    -V file_name="node_identity.json" \
    --id-only \
    -V count="$COUNT" \
    --wait

echo "Processing cosmos-config.yaml..."
bacalhau job run jobs/upload_file.yaml \
    -V script_b64="$(cat jobs/add_sensor_config.py | base64 -w 0)" \
    -V file_b64="$(cat files/cosmos-config.yaml | base64 -w 0)" \
    -V file_name="cosmos-config.yaml" \
    --id-only \
    -V count="$COUNT" \
    --wait

# Create a simplified cities.json file with just name, country, and coordinates
TEMP_DIR=$(mktemp -d)
jq '{cities: [.cities[] | {full_name, country, latitude, longitude}]}' files/cities.json > "$TEMP_DIR/cities.json"

# Debug output
# echo "Debug: Cities file contents:"
# cat "$TEMP_DIR/cities.json"
# echo "Debug: Cities file structure:"
# jq '.' "$TEMP_DIR/cities.json"

trap "rm -rf $TEMP_DIR" EXIT

echo "Cities file has $(jq -r 'length' "$TEMP_DIR/cities.json") cities"

# Upload the simplified cities.json file
echo "Uploading cities.json..."
bacalhau job run jobs/upload_file.yaml \
    -V script_b64="$(cat jobs/add_sensor_config.py | base64 -w 0)" \
    -V file_b64="$(cat "$TEMP_DIR/cities.json" | base64 -w 0)" \
    -V file_name="cities.json" \
    --id-only \
    -V count="$COUNT" \
    --wait

echo "Randomizing locations..."
bacalhau job run jobs/run_python_script.yaml \
    -V script_b64="$(cat jobs/update_location.py | base64 -w 0)" \
    -V count="$COUNT" \
    --id-only \
    --wait

echo "File processing complete."