#!/bin/sh



echo "Iptables config"


delete_rules() {
  local chain=$1
  local proto=$2

  while iptables -C "$chain" -p "$proto" --dport 4222 -j DROP 2>/dev/null; do
    iptables -D "$chain" -p "$proto" --dport 4222 -j DROP
    echo "Removed: $chain $proto 4222"
  done
}

for chain in INPUT OUTPUT FORWARD; do
  for proto in tcp udp; do
    delete_rules "$chain" "$proto"
  done
done


echo "Allow All Connect"

