#!/usr/bin/env bash
set -e
set -x

systemctl stop gunicorn.service
systemctl stop nginx.service

useradd -r "${USER}" || echo "User already exists."

# Clean up old files, just to be sure
rm -f /etc/nginx/sites-enabled/default

mkdir -p $APPDIR
mkdir -p $GUNICORNDIR
mkdir -p $STATICDIR

apt update -y
apt autoremove -y
apt reinstall -y -qq nginx python3 python3-pip

cd $GUNICORNDIR || exit

pip3 install virtualenv
virtualenv ${PYENVNAME}
# shellcheck source=/dev/null
source ${PYENVNAME}/bin/activate

# Install all python requirements from requirements.txt
pip3 install -r requirements.txt

deactivate

cat <<EOF | tee /etc/nginx/sites-available/${DOMAIN} > /dev/null
server {
    listen 80;
    server_name 127.0.0.1 localhost ${DOMAIN} www.${DOMAIN} ${IP};

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root $APPDIR/static;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/${DOMAIN}
ln -s /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/${DOMAIN}

# Gunicorn.socket
cat <<EOF | tee /etc/systemd/system/gunicorn.socket > /dev/null
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock
# Our service won't need permissions for the socket, since it
# inherits the file descriptor by socket activation
# only the nginx daemon will need access to the socket
SocketUser=www-data
# Optionally restrict the socket permissions even more.
# SocketMode=600

[Install]
WantedBy=sockets.target
EOF

mkdir -p /etc/systemd/system/gunicorn.service.d/
chmod 0700 /etc/systemd/system/gunicorn.service.d/

# Copy the generated SQLITE_KEY to the gunicorn.service.d directory
# so that it can be used by the gunicorn service
echo "SQLITE KEY: ${SQLITE_KEY}"
rm -f /etc/systemd/system/gunicorn.service.d/.env
echo "SQLITE_KEY=${SQLITE_KEY}" > /etc/systemd/system/gunicorn.service.d/.env
chmod 0600 /etc/systemd/system/gunicorn.service.d/.env

# Gunicorn config file
cat <<EOF | tee /etc/systemd/system/gunicorn.service.d/sqlite_key.conf > /dev/null
[Service]
EnvironmentFile=/etc/systemd/system/gunicorn.service.d/.env
EOF

# Gunicorn.service
mkdir -p /var/log/gunicorn
chown www-data:www-data /var/log/gunicorn

cat <<EOF | tee /etc/systemd/system/gunicorn.service > /dev/null
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket    
After=network.target

[Service]
PermissionsStartOnly=True
Type=notify
User=www-data
Group=www-data
RuntimeDirectory=gunicorn
WorkingDirectory=${APPDIR}
ExecStart=${GUNICORNDIR}/${PYENVNAME}/bin/gunicorn \
          --access-logfile /var/log/gunicorn/access.log \
          --error-logfile /var/log/gunicorn/error.log \
          --timeout 120 \
          --workers 1 \
          -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
          --chdir /var/www/pintura-cloud \
          --bind unix:/run/gunicorn.sock \
          wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF | tee /etc/logrotate.d/gunicorn > /dev/null 
/var/log/gunicorn/*.log {
	daily
	missingok
	rotate 14
	compress
	notifempty
	create 0640 www-data www-data
	sharedscripts
	postrotate
		systemctl reload your-app
	endscript
}
EOF

sudo systemctl enable gunicorn.socket
sudo systemctl enable gunicorn.service 

systemctl daemon-reload
systemctl restart gunicorn
systemctl restart nginx

# curl --unix-socket /run/gunicorn.sock localhost