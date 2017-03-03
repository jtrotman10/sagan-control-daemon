#!/usr/bin/env bash
cd /opt/sagan-control-daemon/

while true; do
    echo "~" > leds
    env/bin/python sagan-control-daemon.py config.json
    echo "~" > leds
    sleep 10s
done