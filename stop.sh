#!/usr/bin/env bash
cd /opt/sagan-control-daemon
if [ -e run.pid ]; then
    sudo kill $(cat run.pid)
fi;
if [ -e run-notifier.pid ]; then
    sudo kill $(cat run-notifier.pid)
fi
sudo killall python
./stop-ap.sh wlan0
