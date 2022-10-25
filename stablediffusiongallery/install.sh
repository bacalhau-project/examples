#!/bin/bash
set -e

# Export poetry requirements to scripts/requirements.txt
poetry export -f requirements.txt --output scripts/requirements.txt --without-hashes

# Run the terraform script to create the resources
cd tf || exit

# shellcheck disable=SC1091
terraform init && \
    terraform plan -out tf.plan && \
    terraform apply tf.plan

GENERATED_IP=$(terraform output -raw ip_address)
export GENERATED_IP

cd ..

# Use sed to replace the sqlite password in the .env file
SQLITE_KEY_GENERATED=$(openssl rand -base64 28)
export SQLITE_KEY_GENERATED

export DOMAIN="pintura.cloud"                      # Example DOMAIN name
export DOMAIN_PYTHON_SAFE="pintura-cloud"          # Example DOMAIN, no periods or spaces
export USER="${DOMAIN_PYTHON_SAFE}"

echo "User: ${USER}"
echo "Domain: ${DOMAIN}"
echo "Domain_python_safe: ${DOMAIN_PYTHON_SAFE}"

. envsubst < .env.template > .env

cat .env

./setenv.sh .env

cp .env scripts/.env

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

# Make all .sh files in the /gunicorn readable only by root
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ubuntu@"${IP}" \
    "sudo chmod 700 /gunicorn/*.sh"
