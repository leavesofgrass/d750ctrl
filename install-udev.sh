#!/bin/sh
# install-udev.sh: the one root step. Gives the user who runs the tools the radio's serial port, with a fixed name.
#   sudo ./install-udev.sh            uses the user who invoked sudo
set -u
[ "$(id -u)" -eq 0 ] || { echo "Run me with sudo."; exit 1; }
user=${SUDO_USER:-${1:-}}
[ -n "$user" ] || { echo "usage: sudo ./install-udev.sh [USER]"; exit 2; }
here=$(dirname "$(readlink -f "$0")")
sed "s/@USER@/$user/" "$here/udev/60-d750ctrl.rules" > /etc/udev/rules.d/60-d750ctrl.rules
udevadm control --reload
udevadm trigger --subsystem-match=tty --action=add
sleep 1
echo "1. rule installed for user $user"
for n in d750-cat d750-head; do
  if [ -e /dev/$n ]; then echo "2. /dev/$n -> $(ls -l /dev/$n | awk '{print $NF}') owned by $(stat -L -c '%U:%G %a' /dev/$n)"; else echo "2. /dev/$n not present: no cable in that socket, or replug it"; fi
done
echo "Done."
