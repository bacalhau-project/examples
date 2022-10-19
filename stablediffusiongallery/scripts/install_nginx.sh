#!/bin/bash
set -e

source /gunicorn/set_env.sh

useradd -r "${user}" || echo "User already exists."

# Clean up old files, just to be sure
rm -f /etc/nginx/sites-enabled/default

mkdir -p $appdir
mkdir -p $gunicorndir
mkdir -p $staticdir

apt update -y
apt autoremove -y
apt reinstall -y -qq nginx python3 python3-pip

cd $gunicorndir || exit

pip3 install virtualenv
virtualenv ${pyenvname}
# shellcheck source=/dev/null
source ${pyenvname}/bin/activate

# Install all python requirements from requirements.txt
pip3 install -r requirements.txt

deactivate

cat <<EOF | tee /etc/nginx/sites-available/${domain} > /dev/null
server {
    listen 80;
    server_name 127.0.0.1 localhost ${domain} www.${domain} ${IP};

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root $appdir/static;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/${domain}
ln -s /etc/nginx/sites-available/${domain} /etc/nginx/sites-enabled/${domain}

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
echo "SQLITE_KEY=${SQLITE_KEY}" > /etc/systemd/system/gunicorn.service.d/.env
chmod 0600 /etc/systemd/system/gunicorn.service.d/.env

# Gunicorn config file
cat <<EOF | tee /etc/systemd/system/gunicorn.service.d/sqlite_key.conf > /dev/null
[Service]
EnvironmentFile=/etc/systemd/system/gunicorn.service.d/.env
EOF

# Gunicorn.service
cat <<EOF | tee /etc/systemd/system/gunicorn.service > /dev/null
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
PermissionsStartOnly=True
Type=notify
DynamicUser=yes
RuntimeDirectory=gunicorn
WorkingDirectory=${appdir}
ExecStart=${gunicorndir}/${pyenvname}/bin/gunicorn \
          --access-logfile - \
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

sudo systemctl enable gunicorn.socket
sudo systemctl enable gunicorn.service 

systemctl daemon-reload
systemctl restart gunicorn
systemctl restart nginx

# curl --unix-socket /run/gunicorn.sock localhost