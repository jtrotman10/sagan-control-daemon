#!/usr/bin/env bash

set -e
ssid=$1
psk=$2
echo "Adding wifi network ssid:$ssid psk:$psk"
network_id=$(wpa_cli -i wlan1 add_network)
echo "New network id: $network_id"
cat <<EOF | wpa_cli -i wlan1
set_network $network_id ssid "$ssid"
set_network $network_id psk "$psk"
enable_network $network_id
save
select_network $network_id
EOF

