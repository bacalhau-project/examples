#!/bin/sh


if [[ $EUID -ne 0 ]]; then
   echo "Run as root"
   exit 1
fi



echo "Config iptables..."



iptables -A INPUT -p tcp --dport 9000 -j DROP
iptables -A OUTPUT -p tcp --dport 9000 -j DROP
iptables -A FORWARD -p tcp --dport 9000 -j DROP

iptables -A INPUT -p udp --dport 9000 -j DROP
iptables -A OUTPUT -p udp --dport 9000 -j DROP
iptables -A FORWARD -p udp --dport 9000 -j DROP


echo "Block all"
