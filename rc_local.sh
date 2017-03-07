#!/bin/bash
printf "Enabling remote experiments"
rm /opt/sagan-control-daemon/*.pid
if [ -e /opt/sagan-control-daemon/enabled ]; then
    /opt/sagan-control-daemon/start.sh
fi