#!/bin/bash
set -euo pipefail

export PATH=$PATH:/usr/local/go/bin

# Function to get instance metadata
get_metadata() {
    local metadata_path="$1"
    curl -s -H "Metadata-Flavor: Google" \
        "http://metadata.google.internal/computeMetadata/v1/instance/$metadata_path"
}

# Function to get project metadata
get_project_metadata() {
    local metadata_path="$1"
    curl -s -H "Metadata-Flavor: Google" \
        "http://metadata.google.internal/computeMetadata/v1/project/$metadata_path"
}

# Function to get config value from bacalhau config
get_config_value() {
    local key="$1"
    bacalhau config list --output json | jq -r ".[] | select(.Key == \"$key\") | .Value"
}

# Get instance metadata
INSTANCE_NAME=$(get_metadata "name")
ZONE=$(get_metadata "zone" | cut -d'/' -f4)
MACHINE_TYPE=$(get_metadata "machine-type" | cut -d'/' -f4)
PROJECT_ID=$(get_project_metadata "project-id")


# Get important Bacalhau config values
DATA_DIR=$(get_config_value "DataDir")
ALLOWED_PATHS=$(get_config_value "Compute.AllowListedLocalPaths")
COMPUTE_ORCHESTRATORS=$(get_config_value "Compute.Orchestrators")
ACCEPT_NETWORKED=$(get_config_value "JobAdmissionControl.AcceptNetworkedJobs")

# Build labels string
LABELS=(
    # GCP metadata labels
    "gcp.project=$PROJECT_ID"
    "gcp.zone=$ZONE"
    "gcp.instance.name=$INSTANCE_NAME"
    "gcp.machine.type=$MACHINE_TYPE"

    # Bacalhau configuration labels
    "DataDir=$DATA_DIR"
    "JobAdmissionControl.AcceptNetworkedJobs=$ACCEPT_NETWORKED"
    "Compute.AllowListedLocalPaths=$ALLOWED_PATHS"
    "Compute.Orchestrators=$COMPUTE_ORCHESTRATORS"
)

# Add allowed paths if configured
if [ ! -z "$ALLOWED_PATHS" ]; then
    LABELS+=("bacalhau.allowed.paths=$ALLOWED_PATHS")
fi

# Add compute orchestrators if configured
if [ ! -z "$COMPUTE_ORCHESTRATORS" ]; then
    LABELS+=("bacalhau.compute.orchestrators=$COMPUTE_ORCHESTRATORS")
fi

# Convert labels array to comma-separated string
LABELS_STRING=$(IFS=,; echo "${LABELS[*]}")

# Start Bacalhau with labels
bacalhau serve \
    --config /etc/bacalhau/config.yaml \
    -c Labels="$LABELS_STRING"