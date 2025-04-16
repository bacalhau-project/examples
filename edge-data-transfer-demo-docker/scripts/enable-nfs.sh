#!/bin/sh


if [[ $EUID -ne 0 ]]; then
   echo "Start as root"
   exit 1
fi

echo "Iptables config"


iptables -D INPUT -p tcp --dport 9000 -j DROP
iptables -D OUTPUT -p tcp --dport 9000 -j DROP
iptables -D FORWARD -p tcp --dport 9000 -j DROP

iptables -D INPUT -p udp --dport 9000 -j DROP
iptables -D OUTPUT -p udp --dport 9000 -j DROP
iptables -D FORWARD -p udp --dport 9000 -j DROP

echo "Allow All Connect"

