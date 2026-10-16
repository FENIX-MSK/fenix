#!/bin/sh
# Config is mounted at /etc/amnezia/amneziawg/awg0.conf (AllowedIPs = Telegram subnets only).
set -eu

awg-quick up awg0
trap 'awg-quick down awg0' INT TERM

# Reachable only from the internal Docker network; the port is never published.
microsocks -i 0.0.0.0 -p 1080 &
wait $!
