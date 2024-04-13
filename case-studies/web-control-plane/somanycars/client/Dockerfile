FROM python:3.10.14-slim

WORKDIR /app

# All these must be present to run this file.
ARG UID=1000
ARG GID=1000
ARG APPUSER=somanycarsuser
ARG PYENVNAME=.venv
ARG APPDIR=/app
ARG SITEURL
ARG TOKEN
ARG ZONE
ARG REGION
ARG ABSOLUTE_LOCAL_PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
    && apt-get clean \
    && groupadd -g "${GID}" "${APPUSER}" \
    && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" "${APPUSER}" \
    && chown "${APPUSER}":"${APPUSER}" -R /app

RUN apt update \
    && apt install -y gcc make pkg-config libsqlite3-dev liblzma-dev libbz2-dev libncurses5-dev libffi-dev libreadline-dev libssl-dev sudo

# Need FFMPEG for video processing
RUN apt-get install ffmpeg libsm6 libxext6  -y

COPY scripts/ /tmp/scripts/
RUN chmod +x /tmp/scripts/*.sh

USER "${APPUSER}"

RUN echo "export PATH=/home/${APPUSER}/.local/bin:$PATH" >> /home/"${APPUSER}"/.bashrc

COPY --chown="${APPUSER}":"${APPUSER}" app/static/ app/templates/ app/ requirements.txt ./

RUN /tmp/scripts/setup-venv.sh

EXPOSE 14041
EXPOSE 16861

COPY gunicorn_config.py /app/gunicorn_config.py
CMD ["gunicorn", "-c", "/app/gunicorn_config.py", "wsgi:app"]


#   - echo "Creating gunicorn container service unit..."
# - |
# cat <<EOF | tee /etc/systemd/system/gunicorn.service > /dev/null
# [Unit]
# Description=gunicorn daemon
# After=network.target

# [Service]
# PermissionsStartOnly=True
# Type=notify
# User=${APPUSER}
# Group=${APPUSER}
# WorkingDirectory=${APPDIR}
# ExecStart=/usr/bin/docker-compose -f ${APPDIR}/docker-compose.yml up
# ExecReload=/bin/kill -s HUP $MAINPID
# KillMode=mixed
# TimeoutStopSec=5
# PrivateTmp=true

# [Install]
# WantedBy=multi-user.target
# EOF
# # Gunicorn.service
# echo "Creating gunicorn log directories..."
# mkdir -p /var/log/gunicorn
# chown "${APPUSER}":"${APPUSER}" /var/log/gunicorn

# echo "Restarting gunicorn log rotaters ..."
# cat <<EOF | tee /etc/logrotate.d/gunicorn > /dev/null
# /var/log/gunicorn/*.log {
# daily
# missingok
# rotate 14
# compress
# notifempty
# create 0640 ${APPUSER} ${APPUSER}
# sharedscripts
# postrotate
# systemctl reload gunicorn
# endscript
# }
# EOF

# echo "Restarting all services ... "
# sudo systemctl enable gunicorn.service

# systemctl daemon-reload
# systemctl restart gunicorn
# echo "Done with Gunicorn."

# - echo "Installing lighthttpd for heartbeat"
# - apt install -y lighttpd
# - systemctl restart lighttpd
# - echo -n "ok" | sudo tee /var/www/html/index.lighttpd.html > /dev/null

# #
# # Sync from /tmp
# #
# - rsync --no-relative /tmp/rsync/${ username }/setup-venv.sh /home/${ username }
# - rsync --no-relative /tmp/rsync/${ username }/.env /home/${ username }
# - rm -rf /tmp/rsync
# #
# # Install the gunicorn service
# #
# - git clone https://github.com/bacalhau-project/examples.git /tmp/web-control-plane
# - (cd /tmp/web-control-plane && git checkout web-control-plane)
# - rsync -av --no-relative /tmp/web-control-plane/${ relativecodeinrepodir }/* ${ appdir }
# - chown -R ${ username }:${ username } ${ appdir }
# - env $(cat /home/${ username }/.env | xargs) /node/install-gunicorn-service.sh


# - encoding: b64
# content: |
# ${ install_gunicorn_services }
# owner: root:root
# path: /node/install-gunicorn-service.sh
# permissions: "0700"
# - encoding: b64
# content: |
# ${ setup_venv }
# path: /tmp/rsync/${ username }/setup-venv.sh
# permissions: "0700"
# - content: |
# permissions: "0444"
# path: /tmp/rsync/${ username }/.env
# #
# # Make /data/config.yaml readable by the user
# #
# - chmod ugo+rx /data
# - chmod ugo+r /data/config.yaml
