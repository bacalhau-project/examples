#!/bin/bash


if [[ $EUID -ne 0 ]]; then
   echo "Start as root"
   exit 1
fi

echo "Iptables config"

iptables -D DOCKER-USER -p tcp --dport 4222 -j DROP
iptables -D DOCKER-USER -p udp --dport 4222 -j DROP


echo "Allow All Connect"

