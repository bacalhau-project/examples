#!/bin/bash
# Look up pintura.cloud IP address and if it doesn't work, exit
IP=$(dig +short pintura.cloud)
if [ -z "${IP}" ]; then
    echo "Could not find pintura.cloud IP address"
    exit 1
fi

# Copy all the files from ./website directory to
# /var/www/pintura using rsync
rsync -avz -e "ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null" --rsync-path="sudo rsync" \
    website/ ubuntu@pintura.cloud:/var/www/pintura-cloud

ssh ubuntu@pintura.cloud "sudo chown www-data:www-data /var/www/pintura-cloud"

ssh ubuntu@pintura.cloud "sudo /gunicorn/update_db.sh update"

# ssh ubuntu@pintura.cloud "sudo /gunicorn/update_db.sh reset"  