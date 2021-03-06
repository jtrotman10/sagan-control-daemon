#!/usr/bin/env bash

set -e

if [ $EUID -ne 0 ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

cd /opt/sagan-control-daemon

touch enabled

if [ ! -e run-notifier.pid ]; then
    nohup ./run-notifier.sh >/dev/null 2>&1 &
    run_notifier_pid=$!
    disown ${run_notifier_pid}
    echo ${run_notifier_pid} > run-notifier.pid
fi

if [ ! -e run.pid ]; then
    nohup ./run.sh >/dev/null 2>&1 &
    run_pid=$!
    disown ${run_pid}
    echo ${run_pid} > run.pid
fi