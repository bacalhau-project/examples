#!/bin/bash


if [[ $EUID -ne 0 ]]; then
   echo "Run as root"
   exit 1
fi




echo "Config iptables..."



iptables -I DOCKER-USER -p tcp --dport 4222 -j DROP
iptables -I DOCKER-USER -p udp --dport 4222 -j DROP



echo "Block all"
