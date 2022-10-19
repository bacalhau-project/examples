#!/bin/bash
set -e

# Export poetry requirements to scripts/requirements.txt
poetry export -f requirements.txt --output scripts/requirements.txt --without-hashes

# Run the terraform script to create the resources
cd tf || exit

# shellcheck disable=SC1091
source ../.env && \
    terraform init && \
    terraform plan -out tf.plan && \
    terraform apply tf.plan

IP=$(terraform output -raw ip_address)

cd ..

# Use sed to replace the sqlite password in the .env file
SQLITE_PASSWORD=$(openssl rand -base64 28)
sed -i "s/SQLITE_PASSWORD=.*/SQLITE_PASSWORD=$SQLITE_PASSWORD/g" .env

sed -i -r "/export IP/ s/\"[0-9.]*\"$/\"${IP}\"/" scripts/set_env.sh
rm -f scripts/set_env.sh-r

# Push the install script to the instance
# Copy all the files from ./website directory to
# /var/www/pintura using rsync
rsync -avz -e "ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null" --rsync-path="sudo rsync" \
    scripts/ ubuntu@"${IP}":/gunicorn

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

# Split out into its own file so we can update independantly
./update_website.sh

# Restart all services just to be sure
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo bash /gunicorn/restart_all_services.sh"