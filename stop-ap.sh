#!/usr/bin/env bash
set -e

interface=$1

sudo ifconfig ${interface} 0.0.0.0
sudo service dnsmasq stop
sudo service hostapd stop
sudo service dhcpcd start
sleep 2
sudo ifup ${interface}
