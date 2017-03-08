#!/usr/bin/env bash

interface=$1

sudo service dnsmasq stop
sudo service hostapd stop
sudo ifconfig ${interface} 0.0.0.0
sudo service dhcpcd start

# Sometimes there is an error bringing up the interface.
# Try toggling it a few times to get it going. :S
i=0
while [ ${i} -le 10 ]; do
    sudo ifdown ${interface}
    if sudo ifup ${interface}; then
        exit 0;
    fi
    i=$((${i} + 1))
done
