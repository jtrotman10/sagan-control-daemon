#!/usr/bin/env bash

echo "Checking internet connection. Will timeout in $1"

t0=$(date +%s)

while test $(date +%s) -le $((${t0} + $1))
do
    if ping -c 1 cuberider.com 1,2>>/dev/null
    then
        exit 0
    fi
done

exit 1