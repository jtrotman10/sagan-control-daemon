#!/usr/bin/env bash

set -e
sudo apt-get -y install hostapd dnsmasq zip

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
fi
sudo chown pi:pi sandbox

if [ ! -e leds ]; then
    sudo mkfifo leds
fi
sudo chown pi:pi leds

# Set up start up script
sudo cp rc_local.txt /etc/rc.local
sudo chmod +x /etc/rc.local
sudo chmod +x run.sh
sudo chmod +x run-notifier.sh

sudo cp hostapd.conf /etc/hostapd/
sudo cp init.d_hostapd /etc/init.d/hostapd

sudo cp dnsmasq.conf /etc/
sudo cp hosts /etc/

sudo systemctl daemon-reload

