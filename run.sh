#!/usr/bin/env bash
cd /opt/sagan-control-daemon/

while true; do
    echo "~" > leds
    env/bin/python -u sagan-control-daemon.py config.json 1>>log.txt 2>>errors.txt
    killall python &> /dev/null
    echo "~" > leds
    sleep 10s
done