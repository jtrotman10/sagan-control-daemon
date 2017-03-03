#!/usr/bin/env bash
cd /opt/sagan-control-daemon/

if [ -e run-notifier.pid ]; then
    exit 0;
fi

echo $$ > run-notifier.pid


while true; do
    env/bin/python led_notify.py leds
    sleep 10s
done

rm run-notifier.pid
