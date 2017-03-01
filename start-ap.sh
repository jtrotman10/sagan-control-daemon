#!/usr/bin/env bash
set -e

interface=$1

sudo ifdown $interface
sudo service hostapd stop
sudo service dnsmasq stop
sudo service dhcpcd stop
sudo ifconfig $interface 192.168.42.1 netmask 255.255.255.0
sudo service dnsmasq start
sudo service hostapd start
