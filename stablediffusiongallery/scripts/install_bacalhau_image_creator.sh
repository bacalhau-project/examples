#!/usr/bin/env bash

# Exit on error
set -e

# Downloader service
cat <<EOF | tee /etc/systemd/system/bacalhau-image-creator.service > /dev/null
[Unit]
Description=Bacalhau Image Creator
After=multi-user.target
[Service]
Type=simple
User=root
Restart=always
ExecStartPre=-${GUNICORNDIR}/check_pid.sh ${BACALHAU_IMAGE_DOWNLOADER_PID_FILE} "image_creator_runner.py"
ExecStart=${GUNICORNDIR}/${PYENVNAME}/bin/python3 \
          ${GUNICORNDIR}/image_creator_runner.py ${SECONDS_BETWEEN_IMAGE_CREATES} ${LABEL} ${NUMBER_TO_CREATE} ${BACALHAU_IMAGE_CREATOR_PID_FILE}
ExecStopPost=rm -f ${BACALHAU_IMAGE_CREATOR_PID_FILE}
ExecReload=/bin/kill -s HUP $MAINPID
[Install]
WantedBy=multi-user.target
EOF

rm -f "${BACALHAU_IMAGE_CREATOR_PID_FILE}"

systemctl daemon-reload
sudo systemctl enable bacalhau-image-creator.service
systemctl restart bacalhau-image-creator
