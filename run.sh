#!/usr/bin/env bash

while true; do
    /opt/sagan-control-daemon/env/bin/python sagan-control-daemon.py config.json
    sleep 10s
done