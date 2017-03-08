#!/usr/bin/env bash
cd /opt/sagan-control-daemon/

while true; do
    env/bin/python led_notify.py leds &> /dev/null
    sleep 10s
done
