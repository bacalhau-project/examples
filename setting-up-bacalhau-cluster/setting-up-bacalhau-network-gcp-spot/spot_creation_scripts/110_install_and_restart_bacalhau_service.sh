#!/usr/bin/env bash

# Create the systemd service file
cat << EOF > /etc/systemd/system/bacalhau-compute.service
[Unit]
Description=Bacalhau Compute Node
After=network.target

[Service]
Type=forking
User=root
Group=root
EnvironmentFile=/etc/node-config
ExecStart=/root/bacalhau_compute.sh start
ExecStop=/root/bacalhau_compute.sh stop
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd to recognize the new service
systemctl daemon-reload

# Enable the service to start on boot
systemctl enable bacalhau-compute.service

# Start the service
systemctl start bacalhau-compute.service

# Check the status of the service (optional)
# systemctl status bacalhau-compute.service