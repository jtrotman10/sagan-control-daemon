#!/bin/bash
echo "Enabling remote experiments"
rm /opt/sagan-control-daemon/*.pid
rm /opt/sagan-control-daemon/log.txt
rm /opt/sagan-control-daemon/errors.txt

if [ -e /opt/sagan-control-daemon/enabled ]; then
    /opt/sagan-control-daemon/start.sh
fi