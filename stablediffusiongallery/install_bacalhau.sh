#!/bin/bash
# Look up pintura.cloud IP address and if it doesn't work, exit
IP=$(dig +short pintura.cloud)
if [ -z "${IP}" ]; then
    echo "Could not find pintura.cloud IP address"
    exit 1
fi

# Install Bacalhau on the remote server over ssh
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@pintura.cloud \
    'curl -sL https://get.bacalhau.org/install.sh | bash'