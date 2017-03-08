#!/usr/bin/env bash
set -e

if [ $EUID -ne 0 ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

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

if [ -e enabled ]; then
    rm enabled
fi
