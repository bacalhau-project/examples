#!/bin/bash

# Run the terraform script to create the resources
cd tf || exit

# shellcheck disable=SC1091
source ../.env && \
    terraform init && \
    terraform plan -out tf.plan && \
    terraform apply tf.plan

IP=$(terraform output -raw ip_address)

cd ..

sed -i -r "/server_name/ s/ *[0-9.]*;$/ ${IP};/" install_nginx.sh

# Push the install script to the instance
scp -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    install_nginx.sh \
    ubuntu@"${IP}":/home/ubuntu/install_nginx.sh

# Run the install script on the remote machine
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo bash /home/ubuntu/install_nginx.sh"

./update_website.sh
