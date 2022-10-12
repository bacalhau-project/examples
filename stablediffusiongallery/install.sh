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

# Copy all the files from ./website directory to
# /var/www/pictura using rsync
rsync -avz -e "ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null" \
    website/ ubuntu@"${IP}":/var/www/pictura-cloud

