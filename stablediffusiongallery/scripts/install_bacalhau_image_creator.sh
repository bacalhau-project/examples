#!/bin/bash
source /gunicorn/set_env.sh

# Downloader service
cat <<EOF | tee /etc/systemd/system/bacalhau-image-creator.service > /dev/null
[Unit]
Description=Bacalhau Image Creator
After=multi-user.target
[Service]
Type=simple
User=root
Restart=always
ExecStartPre=-${gunicorndir}/check_pid.sh ${BACALHAU_IMAGE_DOWNLOADER_PID_FILE} "image_creator_runner.py"
ExecStart=${gunicorndir}/${pyenvname}/bin/python3 \
          ${gunicorndir}/image_creator_runner.py ${SECONDS_BETWEEN_IMAGE_CREATES} ${LABEL} ${NUMBER_TO_CREATE} ${BACALHAU_IMAGE_CREATOR_PID_FILE}
ExecStopPost=rm -f ${BACALHAU_IMAGE_CREATOR_PID_FILE}
ExecReload=/bin/kill -s HUP $MAINPID
[Install]
WantedBy=multi-user.target
EOF

rm -f "${BACALHAU_IMAGE_CREATOR_PID_FILE}"

systemctl daemon-reload
sudo systemctl enable bacalhau-image-creator.service
systemctl restart bacalhau-image-creator
