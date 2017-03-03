#!/usr/bin/env bash
cd /opt/sagan-control-daemon/

if [ -e run.pid ]; then
    exit 0;
fi

echo $$ > run.pid

while true; do
    echo "~" > leds
    env/bin/python sagan-control-daemon.py config.json
    echo "~" > leds
    sleep 10s
done

rm pid
