#!/bin/bash

curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list

apt-get -y update
apt --reinstall  -y install tailscale

if [ -z "$1" ]
  then
	tailscale up  --auth-key tskey-auth-kBEwtV4CNTRL-F6UvB8r9qg7xU5LHWffFb7E4zzQh9YnM
  else
	tailscale up  --auth-key tskey-auth-kBEwtV4CNTRL-F6UvB8r9qg7xU5LHWffFb7E4zzQh9YnM --hostname "$1"
fi

while [ ! -S /run/tailscale/tailscaled.sock ]
do
  echo "Waiting for tailscaled to start..."
  sleep 1
done