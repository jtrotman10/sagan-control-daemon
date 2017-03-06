#!/usr/bin/env bash
cd /opt/sagan-control-daemon
if [ -e run.pid ]; then
    kill $(cat run.pid)
    rm run.pid
fi;
if [ -e run-notifier.pid ]; then
    kill $(cat run-notifier.pid)
    rm run-notifier.pid
fi
killall python
