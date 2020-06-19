#!/bin/sh
ip=$(ip addr show $1 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)
echo $ip
