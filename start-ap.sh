#!/usr/bin/env bash
set -e

interface=$1

sudo mv /etc/network/interfaces /etc/network/interfaces.ap-backup
sudo cp interfaces-disabled /etc/network/interfaces
sudo ifdown $interface
sudo service hostapd stop
sudo service udhcpd stop
sudo service dhcpcd stop
sudo ifconfig $interface 192.168.42.1
sudo ifconfig $interface up
sudo service udhcpd start
sudo service hostapd start


