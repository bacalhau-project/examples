#!/bin/sh






echo "Config iptables..."



iptables -I INPUT -p tcp --dport 4222 -j DROP
iptables -I INPUT -p udp --dport 4222 -j DROP

iptables -I OUTPUT -p tcp --dport 4222 -j DROP
iptables -I OUTPUT -p udp --dport 4222 -j DROP

iptables -I FORWARD -p tcp --dport 4222 -j DROP
iptables -I FORWARD -p udp --dport 4222 -j DROP

iptables -D INPUT -p tcp --dport 9000 -j DROP
iptables -D OUTPUT -p tcp --dport 9000 -j DROP
iptables -D FORWARD -p tcp --dport 9000 -j DROP

iptables -D INPUT -p udp --dport 9000 -j DROP
iptables -D OUTPUT -p udp --dport 9000 -j DROP
iptables -D FORWARD -p udp --dport 9000 -j DROP
echo "Block all"
