FROM python:3.10-slim-bullseye

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

COPY scripts/setup-venv.sh /tmp/scripts/setup-venv.sh
RUN chmod +x /tmp/scripts/setup-venv.sh

USER "${APPUSER}"

RUN echo "export PATH=/home/${APPUSER}/.local/bin:/home/${APPUSER}/.cargo/bin:$PATH" >> /home/"${APPUSER}"/.bashrc

COPY requirements.txt /tmp/requirements.txt
RUN /tmp/scripts/setup-venv.sh

COPY --chown="${APPUSER}":"${APPUSER}" app/*.py ./
COPY --chown="${APPUSER}":"${APPUSER}" static/ ./static/
COPY --chown="${APPUSER}":"${APPUSER}" templates/ ./templates/

EXPOSE 14041
EXPOSE 16861

COPY scripts/start-server.sh /tmp/scripts/start-server.sh
CMD ["/tmp/scripts/start-server.sh"]


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

# - echo "Installing lighthttpd for heartbeat"
# - apt install -y lighttpd
# - systemctl restart lighttpd
# - echo -n "ok" | sudo tee /var/www/html/index.lighttpd.html > /dev/null

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
