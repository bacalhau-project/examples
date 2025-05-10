#!/bin/sh

echo "Iptables config"

delete_rules() {
  local chain=$1
  local proto=$2
  local port=$3

  while iptables -C "$chain" -p "$proto" --dport "$port" -j DROP 2>/dev/null; do
    iptables -D "$chain" -p "$proto" --dport "$port" -j DROP
    echo "Removed: $chain $proto $port"
  done
}

for chain in INPUT OUTPUT FORWARD; do
  for proto in tcp udp; do
    for port in 4222 9000; do
      delete_rules "$chain" "$proto" "$port"
    done
  done
done

echo "Allow All Connect"
