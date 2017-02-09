#!/usr/bin/env bash
set -e
sudo mv /etc/network/interfaces /etc/network/interfaces.ap-backup
sudo cp interfaces-disabled /etc/network/interfaces
sudo ifdown wlan1
sudo ifdown wlan0
sudo service hostapd stop
sudo service udhcpd stop
sudo service dhcpcd stop
sudo ifconfig wlan1 192.168.42.1
sudo ifconfig wlan1 up
sudo service udhcpd start
sudo service hostapd start


