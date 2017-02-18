#!/usr/bin/env bash
cd /opt/sagan-control-daemon/
while true; do
    env/bin/python sagan-control-daemon.py config.json
    sleep 10s
done