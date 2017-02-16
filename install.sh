#!/usr/bin/env bash

set -e
sudo apt-get -y install hostapd udhcpd
sudo pip3 install virtualenv
virtualenv -p python3 env
. env/bin/activate
pip install -r requirements.txt
sudo cp hostapd.conf /etc/hostapd/
sudo cp init.d_hostapd /etc/init.d/hostapd
sudo cp udhcpd.conf /etc/
sudo cp default_udhcpd /etc/default/udhcpd
sudo cp sagan-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start sagan-control
