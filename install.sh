#!/usr/bin/env bash

set -e
sudo apt-get install hostapd udhcpd
pip3 install -r requirements.txt
sudo cp hostapd.conf /etc/hostapd/
sudo cp udhcpd.conf /etc/udhcpd/
sudo cp sagan-control.service /etc/systemd/system/
