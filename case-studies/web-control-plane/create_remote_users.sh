#!/usr/bin/env bash
set -e
set -x

source .env

gcloud compute ssh ${INSTANCENAME} --zone=${ZONE} -- "sudo useradd --create-home -r ${APPUSER} -s /usr/bin/bash || echo 'User already exists.'"
gcloud compute ssh ${INSTANCENAME} --zone=${ZONE} -- "sudo runuser -l ${APPUSER} -c \"mkdir -p /home/${APPUSER}/.ssh\" && sudo runuser -l ${APPUSER} -c \"chmod 700 /home/${APPUSER}/.ssh\""
gcloud compute ssh ${INSTANCENAME} --zone=${ZONE} -- "sudo echo $(cat ~/.ssh/id_ed25519.pub) > /tmp/authorized_keys && sudo runuser -l ${APPUSER} -c \"cp /tmp/authorized_keys /home/${APPUSER}/.ssh/authorized_keys\""

# Add this user to the NOPASSWD sudoers
gcloud compute ssh ${INSTANCENAME} --zone=${ZONE} -- "sudo echo \"${APPUSER} ALL=(ALL) NOPASSWD:ALL\" | sudo tee -a /etc/sudoers.d/${APPUSER}"
