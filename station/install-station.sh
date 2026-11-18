#!/bin/sh
# install-station.sh: link the station tools into ~/.local/bin and write their settings files if there are none.
# No root. Safe to run twice. It never replaces a file of yours: a name in ~/.local/bin that is not already a link
# into this folder is left alone, and said. The Uptime Kuma timer is installed only when you ask for it.
#   station/install-station.sh [--kuma]
set -u
here=$(dirname "$(readlink -f "$0")")
kuma=0
for a in "$@"; do
  case $a in
    --kuma) kuma=1 ;;
    *) echo "Not a known option: $a. Use: install-station.sh [--kuma]"; exit 2 ;;
  esac
done
conf_dir=${D750_CONF_DIR:-$HOME/.config/d750ctrl}
mkdir -p "$HOME/.local/bin" "$conf_dir"
linked=""; kept=""
for c in station notify radiogram d750d-kuma xara-wait-audio xara-radio-pair mode-listen; do
  dest="$HOME/.local/bin/$c"
  if [ -L "$dest" ]; then
    case "$(readlink -f "$dest")" in
      "$here/$c") linked="$linked $c" ;;
      *) kept="$kept $c" ;;
    esac
  elif [ -e "$dest" ]; then
    kept="$kept $c"
  else
    ln -s "$here/$c" "$dest" && linked="$linked $c"
  fi
done
echo "1. linked into ~/.local/bin:${linked:- none}"
for c in $kept; do echo "   kept: ~/.local/bin/$c is not a link into this folder, so it was left alone"; done
conf="$conf_dir/station.conf"
if [ ! -f "$conf" ]; then
  cat "$here/station.conf.example" > "$conf"
  echo "2. station settings written to $conf"
else
  echo "2. station settings kept: $conf"
fi
nconf="$conf_dir/notify.conf"
if [ ! -f "$nconf" ]; then
  (umask 077; cat "$here/notify.conf.example" > "$nconf") && chmod 600 "$nconf"
  echo "3. notify settings written to $nconf, owner only; add a token there if your ntfy server asks for one"
else
  echo "3. notify settings kept: $nconf"
fi
if [ "$kuma" = 1 ]; then
  units="$HOME/.config/systemd/user"
  mkdir -p "$units"
  ok=1
  for u in d750d-kuma.service d750d-kuma.timer; do
    if [ -f "$units/$u" ] && [ "$(cat "$units/$u")" != "$(cat "$here/$u")" ]; then
      echo "   kept: $units/$u differs from this folder's copy, so it was left alone"; ok=0
    else
      cat "$here/$u" > "$units/$u"
    fi
  done
  if [ "$ok" = 1 ]; then
    systemctl --user daemon-reload
    systemctl --user enable --now d750d-kuma.timer >/dev/null 2>&1
    echo "4. Uptime Kuma timer $(systemctl --user is-active d750d-kuma.timer); push URLs go in ~/.config/kuma-push-url-d750d and ~/.config/kuma-push-url-xara"
  else
    echo "4. Uptime Kuma timer not changed"
  fi
else
  echo "4. Uptime Kuma timer not installed; run again with --kuma if you use Uptime Kuma"
fi
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "   note: ~/.local/bin is not on your PATH";; esac
echo "Done. Next: station status, then station help."
