#!/usr/bin/env bash

set -e
sudo apt-get -y install hostapd udhcpd zip

# Set up virtual environment
sudo pip3 install virtualenv
# check there is a readable file called env/bin/activate
if [ ! -r env/bin/activate ]; then
    virtualenv --system-site-packages -p python3 env
fi
. env/bin/activate
pip install -r requirements.txt

if [ ! -d sandbox ]; then
    sudo mkdir sandbox
    sudo chown pi:pi sandbox
fi

if [ ! -e notify ]; then
    sudo mkfifo leds
fi

sudo cp rc_local.txt /etc/rc.local
sudo chmod +x /etc/rc.local
sudo chmod +x run.sh
sudo cp hostapd.conf /etc/hostapd/
sudo cp init.d_hostapd /etc/init.d/hostapd
sudo cp udhcpd.conf /etc/
sudo cp default_udhcpd /etc/default/udhcpd
sudo systemctl daemon-reload

