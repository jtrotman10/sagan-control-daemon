#!/usr/bin/env bash

set -e

if [ $EUID -ne 0 ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

cd /opt/sagan-control-daemon

/opt/sagan-control-daemon/stop.sh 1>/dev/null
echo "Stopped Sagan daemon"
sleep 10

echo '{
    "pairing_code": "",
    "device_name": "",
    "device_id": "",
    "ssid": "",
    "psk": "",
    "host": "http://dreamcoder.dreamup.org",
    "interface": "wlan0",
    "user": "pi",
    "error": ""
}' > /opt/sagan-control-daemon/config.json
echo "Removed pairing config"

sed -n '/^network=/q;p' /etc/wpa_supplicant/wpa_supplicant.conf > /etc/wpa_supplicant/wpa_supplicant_defaults.conf
mv -f /etc/wpa_supplicant/wpa_supplicant_defaults.conf /etc/wpa_supplicant/wpa_supplicant.conf
echo "Removed WiFi config"

/opt/sagan-control-daemon/start.sh 1>/dev/null
