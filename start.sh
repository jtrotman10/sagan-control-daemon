#!/usr/bin/env bash
if [ ! -e run-notifier.pid ]; then
    /opt/sagan-control-daemon/run-notifier.sh &
    echo $! > /opt/sagan-control-daemon/run-notifier.pid
fi

if [ ! -e run.pid ]; then
    /opt/sagan-control-daemon/run.sh &
    echo $! > /opt/sagan-control-daemon/run.pid
fi