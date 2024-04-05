#!/usr/bin/env bash
source .env

ssh-keygen -R ${INSTANCEIP}
rsync -av terraform/node_files/*.sh ${APPUSER}@${INSTANCEIP}:.
scp .env ${APPUSER}@${INSTANCEIP}:.
rsync -av --relative --exclude '\.*' --exclude "__*" client ${APPUSER}@${INSTANCEIP}:/tmp # APPDIR has a leading slash
ssh ${APPUSER}@${INSTANCEIP} "sudo ./install_gunicorn_services.sh"
