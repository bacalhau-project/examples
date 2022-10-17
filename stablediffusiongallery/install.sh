#!/bin/bash
set -e

# Run the terraform script to create the resources
cd tf || exit

# shellcheck disable=SC1091
source ../.env && \
    terraform init && \
    terraform plan -out tf.plan && \
    terraform apply tf.plan

IP=$(terraform output -raw ip_address)

cd ..

sed -i -r "/export IP/ s/\"[0-9.]*\"$/\"${IP}\"/" scripts/set_env.sh
rm -f scripts/set_env.sh-r

# Push the install script to the instance
# Copy all the files from ./website directory to
# /var/www/pintura using rsync
rsync -avz -e "ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null" --rsync-path="sudo rsync" \
    scripts/ ubuntu@"${IP}":/gunicorn

# Split out into its own file so we can update independantly
./update_website.sh

# Run the install script on the remote machine
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo bash /gunicorn/install_nginx.sh"

# Run the install script on the remote machine
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo bash /gunicorn/install_bacalhau.sh 2&1> /dev/null"

# Install the downloader
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo bash /gunicorn/install_bacalhau_downloader.sh"

# Install the downloader
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo bash /gunicorn/install_bacalhau_image_creator.sh"
