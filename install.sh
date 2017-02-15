#!/usr/bin/env bash

set -e
sudo apt-get -y install hostapd udhcpd
pwd
pip3 install -r requirements.txt
sudo cp hostapd.conf /etc/hostapd/
sudo cp udhcpd.conf /etc/
sudo cp sagan-control.service /etc/systemd/system/
