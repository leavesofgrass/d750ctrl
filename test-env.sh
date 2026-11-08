#!/bin/sh
# test-env.sh: start the radio simulator and a second d750d against it, on ports 4542 (PTT) and 4543 (commands),
# logging under ~/.local/share/d750ctrl/log/test. Prints the device path and keeps both running until killed.
# Use: D750_CMD_PORT=4543 d750 status     Written Saturday, November 7, 2026.
set -u
here=$(dirname "$(readlink -f "$0")"); T="$HOME/.local/share/d750ctrl/log/test"; mkdir -p "$T"
: > "$T/sim.out"; python3 -I -u "$here/d750-sim.py" --busy-flicker > "$T/sim.out" 2>&1 &
simpid=$!
pty=""
for _ in $(seq 1 40); do pty=$(head -1 "$T/sim.out" 2>/dev/null); case "$pty" in /dev/pts/*) break;; esac; pty=""; sleep 0.25; done
[ -n "$pty" ] || { echo "simulator gave no device path"; kill $simpid 2>/dev/null; exit 1; }
echo "simulator pid $simpid on $pty"
D750_PORT="$pty" D750_PTT_PORT=4542 D750_CMD_PORT=4543 D750_LOG_DIR="$T" python3 -I "$here/d750d.py" > "$T/d750d.out" 2>&1 &
echo "test daemon pid $! : PTT 4542, commands 4543"
echo "$simpid $!" > "$T/pids"
wait
