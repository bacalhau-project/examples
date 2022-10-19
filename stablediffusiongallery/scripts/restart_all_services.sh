#!/bin/bash
set -e

systemctl daemon-reload
systemctl enable nginx.service
systemctl restart nginx
systemctl enable gunicorn.socket
systemctl enable gunicorn.service
systemctl restart gunicorn
systemctl enable bacalhau-downloader.service
systemctl restart bacalhau-downloader
systemctl enable bacalhau-image-creator.service
systemctl restart bacalhau-image-creator