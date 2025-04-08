#!/bin/bash

CONFIG_FILE="config.yaml_example"

if [[ -z "$COMPUTE_ORCHESTRATOR" || -z "$COMPUTE_AUTH_TOKEN" || -z "$COMPUTE_AWS_REGION" ]]; then
  echo "Error: COMPUTE_ORCHESTRATOR, COMPUTE_AUTH_TOKEN and COMPUTE_AWS_REGION must be set."
  exit 1
fi

cat <<EOF > "$CONFIG_FILE"
max_instances: 5
username: bacalhau-runner
public_ssh_key_path: /root/.ssh/id_rsa
compute_orchestrators:
  - $COMPUTE_ORCHESTRATOR
compute_auth_token: $COMPUTE_AUTH_TOKEN
compute_tls: "true"
regions:
  - $COMPUTE_AWS_REGION:
      image: "auto"
      machine_type: "m6gd.medium"
      node_count: auto
EOF

echo "Config written to $CONFIG_FILE"
