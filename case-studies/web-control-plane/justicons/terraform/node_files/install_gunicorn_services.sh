#!/usr/bin/env bash
set -e
set -x

export ENVFILE="/home/${APPUSER}/.env"

source "${ENVFILE}"

apt update
apt install -y gcc make pkg-config libsqlite3-dev liblzma-dev libbz2-dev libncurses5-dev libffi-dev libreadline-dev libssl-dev

apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-distutils python3.11-tk
update-alternatives --install /usr/bin/python python /usr/bin/python3.11 0
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Clean up old files, just to be sure
export USERHOME="/home/${APPUSER}"
export PATH="${USERHOME}/.local/bin:${PATH}"
export SETUPVENVSCRIPT="${USERHOME}/setup-venv.sh"

echo "USERHOME: ${USERHOME}"
echo "APPUSER: ${APPUSER}"
echo "APPDIR: ${APPDIR}"
echo "PATH: ${PATH}"

echo "Running setup-venv.sh ..."
pushd ${APPDIR}
chown -R ${APPUSER}:${APPUSER} ${SETUPVENVSCRIPT}
sudo -E -u ${APPUSER} bash -c "source ${ENVFILE} && ${SETUPVENVSCRIPT}"
popd

mkdir -p /etc/systemd/system/gunicorn.service.d/
chmod 0700 /etc/systemd/system/gunicorn.service.d/

# Gunicorn.service
echo "Creating gunicorn log directories..."
mkdir -p /var/log/gunicorn
chown ${APPUSER}:${APPUSER} /var/log/gunicorn

echo "Creating gunicorn service unit..."
cat <<EOF | tee /etc/systemd/system/gunicorn.service > /dev/null
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
PermissionsStartOnly=True
Type=notify
User=${APPUSER}
Group=${APPUSER}
WorkingDirectory=${APPDIR}
ExecStart=${APPDIR}/${PYENVNAME}/bin/gunicorn \
          --access-logfile /var/log/gunicorn/access.log \
          --error-logfile /var/log/gunicorn/error.log \
          --timeout 120 \
          --workers 2 \
          --chdir ${APPDIR} \
          -b 0.0.0.0:14041 \
          -b [::1]:16861 \
          wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "Restarting gunicorn log rotaters ..."
cat <<EOF | tee /etc/logrotate.d/gunicorn > /dev/null
/var/log/gunicorn/*.log {
	daily
	missingok
	rotate 14
	compress
	notifempty
	create 0640 ${APPUSER} ${APPUSER}
	sharedscripts
	postrotate
		systemctl reload gunicorn
	endscript
}
EOF

echo "Restarting all services ... "
sudo systemctl enable gunicorn.service

systemctl daemon-reload
systemctl restart gunicorn
echo "Done with Gunicorn."

echo "Installing lighthttpd for heartbeat"
apt install -y lighttpd
systemctl restart lighttpd
echo -n "ok" | sudo tee /var/www/html/index.lighttpd.html > /dev/null

# Ping itsadash.work/update_sites with a json of the form {"site": "site_name", "ip": "ip_address"}
echo "Pinging itsadash.work/update ..."
export PRIVATEIP=$(ip addr | awk '/inet/ && /10\./ {split($2, ip, "/"); print ip[1]}')
curl -X POST -H "Content-Type: application/json" -d "{\"site\": \"${SITEURL}\", \"TOKEN\": \"${TOKEN}\", \"SERVERIP\": \"${PRIVATEIP}\"  }" http://itsadash.work/update
