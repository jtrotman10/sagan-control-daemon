#!/usr/bin/env bash
set -e
sudo ifconfig wlan1 down
sudo ifconfig wlan0 down
sudo mv /etc/network/interfaces.ap-backup /etc/network/interfaces 
sudo ifup wlan0
sudo ifup wlan1
sudo service dhcpcd start