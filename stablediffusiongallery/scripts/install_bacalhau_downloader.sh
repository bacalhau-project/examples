#!/bin/bash
source /gunicorn/set_env.sh

mkdir -p "$IMAGE_DOWNLOAD_DIR"

cd "$gunicorndir" || exit

pip3 install virtualenv
virtualenv "${pyenvname}"
# shellcheck source=/dev/null
source "${pyenvname}"/bin/activate
pip3 install apscheduler
deactivate

# Downloader service
cat <<EOF | tee /etc/systemd/system/bacalhau-downloader.service > /dev/null
[Unit]
Description=Bacalhau Downloader
After=multi-user.target
[Service]
Type=simple
User=root
Restart=always
ExecStartPre=${gunicorndir}/check_pid.sh ${BACALHAU_IMAGE_DOWNLOADER_PID_FILE} "downloader_runner.py"
ExecStart=${gunicorndir}/${pyenvname}/bin/python3 \
          ${gunicorndir}/downloader_runner.py ${SECONDS_BETWEEN_DOWNLOAD_QUERIES} ${IMAGE_DOWNLOAD_DIR} ${NUM_OF_JOBS_TO_LIST} ${BACALHAU_IMAGE_DOWNLOADER_PID_FILE}
ExecStopPost=rm -f ${BACALHAU_IMAGE_DOWNLOADER_PID_FILE}
ExecReload=/bin/kill -s HUP $MAINPID
[Install]
WantedBy=multi-user.target
EOF

rm -f "${BACALHAU_IMAGE_DOWNLOADER_PID_FILE}"

systemctl daemon-reload
sudo systemctl enable bacalhau-downloader.service
systemctl restart bacalhau-downloader
