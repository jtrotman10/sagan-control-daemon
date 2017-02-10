#!/usr/bin/env bash
set -e

interface=$1

sudo ifconfig $interface down
sudo mv /etc/network/interfaces.ap-backup /etc/network/interfaces
sudo ifup $interface
sudo service dhcpcd start