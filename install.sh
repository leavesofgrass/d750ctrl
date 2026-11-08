#!/bin/sh
# install.sh: link the d750ctrl commands into ~/.local/bin, run d750d as a user service from this folder,
# make the Python environment for SSTV and RTTY, and write the settings file if there is none. No root.
# Safe to run twice. The folder may live anywhere; the links follow it.
#   ./install.sh [YOURCALL]
set -u
here=$(dirname "$(readlink -f "$0")")
call=${1:-}
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user" "$HOME/.config/d750ctrl" "$HOME/.local/share/d750ctrl/log"
for c in d750 d750ctrl d750-sstv d750-rtty; do ln -sf "$here/$c" "$HOME/.local/bin/$c"; done
echo "1. d750, d750ctrl, d750-sstv and d750-rtty linked into ~/.local/bin"
sed "s|@REPO@|$here|" "$here/d750d.service.in" > "$HOME/.config/systemd/user/d750d.service"
systemctl --user daemon-reload
if systemctl --user is-active --quiet d750d.service; then systemctl --user restart d750d.service; else systemctl --user enable --now d750d.service >/dev/null 2>&1; fi
echo "2. d750d $(systemctl --user is-active d750d.service), running from $here"
if [ ! -x "$here/.venv/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then uv venv --quiet "$here/.venv" && uv pip install --quiet --python "$here/.venv/bin/python" sstv pillow numpy
  else python3 -m venv "$here/.venv" && "$here/.venv/bin/pip" install --quiet sstv pillow numpy; fi
  echo "3. Python environment for SSTV and RTTY made in $here/.venv"
else
  echo "3. Python environment present"
fi
conf="$HOME/.config/d750ctrl/d750ctrl.conf"
if [ ! -f "$conf" ]; then
  [ -n "$call" ] || { printf 'Your call sign: '; read -r call; }
  sed "s/^mycall = N0CALL/mycall = $(printf '%s' "$call" | tr '[:lower:]' '[:upper:]')/" "$here/d750ctrl.conf.example" > "$conf"
  echo "4. settings written to $conf; add the radio's Bluetooth address there if you pair it"
else
  echo "4. settings kept: $conf"
fi
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "   note: ~/.local/bin is not on your PATH";; esac
echo "Done. Root once, for the serial port: sudo $here/install-udev.sh. Then: d750 doctor, d750 status, d750ctrl."
