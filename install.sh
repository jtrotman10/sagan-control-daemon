#!/usr/bin/env bash

set -e
sudo apt-get -y install hostapd udhcpd

# Set up virtual environment
sudo pip3 install virtualenv
# check there is a readable file called env/bin/activate
if [ ! -r env/bin/activate ]; then
    virtualenv -p python3 env
fi
. env/bin/activate
pip install -r requirements.txt

if [ ! -d sandbox ]; then
    sudo mkdir sandbox
    sudo chown pi:pi sandbox
fi
sudo cp hostapd.conf /etc/hostapd/
sudo cp init.d_hostapd /etc/init.d/hostapd
sudo cp udhcpd.conf /etc/
sudo cp default_udhcpd /etc/default/udhcpd
sudo cp sagan-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start sagan-control
