# Install: what you need, what the scripts do, how to update and remove

This page lists what must be installed first, shows how to check each item, and describes exactly
what `install.sh` and `install-udev.sh` do, so you can undo them by hand.

## What must be installed first

Each item has a check. A check that prints nothing, or a path, is a pass.

### Required

- Linux with systemd user services. `install.sh` runs d750d as a user service.

  ```sh
  systemctl --user --version
  ```

- bash. The `d750` command is a bash script and uses bash's built-in network access.

  ```sh
  bash --version
  ```

- Python 3 at `/usr/bin/python3`. The d750d service starts that exact path. The standard curses
  module must be present; it is on most Linux Pythons.

  ```sh
  /usr/bin/python3 -I -c "import curses"
  ```

- pyserial for that Python. d750d, d750-aprs and d750-power import it. The Python environment that
  `install.sh` makes does not help here, because these programs run on the system Python in
  isolated mode, which ignores your personal Python packages. Install it with your package
  manager: python3-serial on Debian and Ubuntu, python3-pyserial on Fedora, python-pyserial on Arch.

  ```sh
  /usr/bin/python3 -I -c "import serial"
  ```

- git, to clone the repository, and sudo, for the one root step.
- udev, with the `udevadm` command, for `install-udev.sh`.
- The usual command line tools: sed, awk, grep, cut, head, tail, date, mktemp, timeout and tr.
- A network connection during `install.sh`. Its third step downloads the Python packages sstv,
  pillow and numpy.
- Python's venv module. On some distributions it is a separate package. If `install.sh` fails on
  step 3, check this first. If you have the tool uv, `install.sh` uses it instead.

  ```sh
  python3 -m venv --help
  ```

### Optional

- usbutils, for `lsusb`. `d750 doctor` uses it to see the radio on USB.
- tmux. With it, `d750ctrl` runs in its own tmux session with a window for each tool.

  ```sh
  tmux -V
  ```

- A sound server with the commands pactl, parecord and paplay (PulseAudio, or PipeWire with its
  PulseAudio tools). `d750 level`, `d750 record`, `d750-sstv`, `d750-rtty` and the sound checks in
  `d750 doctor` use them.

  ```sh
  command -v pactl parecord paplay
  ```

- nc (netcat). `d750 vara cq` and `d750 vara beacon` use it, and so do the tests.
- ss and journalctl, which `d750 vara status` and `d750 vara fm` use.
- BlueZ, for the `bluetoothctl` command, if you put the radio's Bluetooth address in the settings.
- Hamlib, for the `rigctl` command. The tests use it. Programs that speak Hamlib connect to
  d750d without it being installed here.
- xara, xarachat or openslot, and ntfy and Uptime Kuma, for the features that talk to them. They
  are separate programs of your choosing; see [VARA and chat](vara-and-chat.md) and
  [d750-aprs](aprs.md).

## What install.sh does

Run it from your clone. It needs no root and is safe to run twice. The folder may live anywhere;
the links follow it. If you move the folder later, run `install.sh` again from the new place.

```sh
./install.sh YOURCALL
```

First it makes these folders if they are missing: `~/.local/bin`, `~/.config/systemd/user`,
`~/.config/d750ctrl` and `~/.local/share/d750ctrl/log`. Then it prints five numbered lines, one
for each step, in this order.

1. It links d750, d750ctrl, d750-sstv, d750-rtty, d750-aprs, aprschat and d750-power into
   `~/.local/bin`. A link of the same name is replaced.
2. It writes `~/.config/systemd/user/d750d.service` from the template `d750d.service.in`, with
   the path of your clone filled in, and reloads systemd. If d750d is already running it restarts
   it. If not, it enables d750d at login and starts it now. The line it prints says whether d750d
   is active. The service runs `/usr/bin/python3 -I` on `d750d.py` in your clone, restarts itself
   after a failure with a five second wait, and is ordered before the xara service.
3. It makes a Python environment in `.venv` inside your clone, if there is none, and installs
   sstv, pillow and numpy into it. SSTV and RTTY need it. If the environment exists, it says so and
   leaves it.
4. It writes `~/.config/d750ctrl/d750ctrl.conf` from `d750ctrl.conf.example`, with your call sign
   in capitals. If you gave no call sign, it asks. If the file exists, it keeps it. The line it
   prints says which, and reminds you to add the radio's Bluetooth address there if you pair it.
5. It writes the d750-aprs service, `~/.config/systemd/user/d750-aprs.service`, from the template
   `d750-aprs.service.in`, with the path of your clone filled in, and reloads systemd. It never
   enables or starts that service, because d750-aprs can transmit. If the service already runs, it
   keeps running as it is. It also writes `~/.config/d750ctrl/aprs.conf` from `aprs.conf.example`,
   readable by you only, if the file is missing, and keeps it if it exists. The line it prints says
   whether the service is active, and that this script did not start it. A second line says how to
   turn APRS on: edit `aprs.conf`, then run `systemctl --user enable --now d750-aprs.service`.
   Nothing transmits until you run `d750-aprs transmit on`.

After that, if `~/.local/bin` is not on your PATH, it prints a note saying so. The last line tells
you the root step to run next, then `d750 doctor`, `d750 status` and `d750ctrl`, and points to
`station/install-station.sh` for the [station tools](station-tools.md).

See [d750-aprs](aprs.md) for how to run the APRS service.

## What install-udev.sh does

```sh
sudo ./install-udev.sh
```

It must run as root once, because it writes into `/etc/udev/rules.d`, which only root may do. It
uses the user who ran sudo. You can name another user: `sudo ./install-udev.sh USER`.

1. It writes `/etc/udev/rules.d/60-d750ctrl.rules` from `udev/60-d750ctrl.rules`, with your user
   name filled in.
2. It tells udev to reload its rules and to apply them again to serial devices that are already
   plugged in, so you do not need to replug anything.
3. It prints "1. rule installed for user", then one line each for `/dev/d750-cat` and
   `/dev/d750-tnc`, saying what each points to and who owns it, or that it is not present.

The rule matches the radio's USB ids. The control head's socket (id 2166:9030) becomes
`/dev/d750-cat`. The base unit's socket (id 2166:9032) becomes `/dev/d750-tnc`. Both devices are
owned by your user, with mode 0660, so you do not need to join any group to use them. The rule also
names the group uucp.

## Updating

```sh
cd ~/d750ctrl
git pull
./install.sh
```

`install.sh` links the commands again, restarts d750d so it runs the new code, and keeps your
settings. If you run d750-aprs as a service, restart it yourself. Run `install-udev.sh` again only
when `CHANGELOG.md` says the udev rule changed.

## Removing

There is no uninstall script. Everything `install.sh` and `install-udev.sh` made is listed here, so
you can undo it by hand.

1. Stop d750d and take it out of your login:

   ```sh
   systemctl --user disable --now d750d.service
   ```

2. Remove the service file `~/.config/systemd/user/d750d.service`, then run
   `systemctl --user daemon-reload`.
3. Remove the seven links in `~/.local/bin`: d750, d750ctrl, d750-sstv, d750-rtty, d750-aprs,
   aprschat and d750-power.
4. Remove the udev rule, with root, then reload udev:

   ```sh
   sudo rm /etc/udev/rules.d/60-d750ctrl.rules
   sudo udevadm control --reload
   ```

5. If the rig screen's tmux session is running, stop it: `tmux -L d750 kill-server`.
6. Remove your clone. This also removes the `.venv` folder inside it.
7. Your own data is separate, and is yours to keep or remove: `~/.config/d750ctrl` holds your
   settings, `aprs.conf` and `fixup.conf`; `~/.local/share/d750ctrl` holds the logs, received
   pictures, RTTY text and APRS message history.

If you ran the d750-aprs service, disable it with `systemctl --user disable --now
d750-aprs.service`. Then remove `~/.config/systemd/user/d750-aprs.service` in the same way as the
d750d one.

## Other distributions

The owner uses the tools with a real radio on CachyOS, an Arch Linux relative. The automated tests
run against the pretend radio on Ubuntu, Debian, Fedora and Arch, on GitHub. Only an Arch relative
has been used with a real radio. These are the places where another system is likely to differ.

What the automated tests install, which is a fact about the test machines and not a promise about
yours, is this:

- Ubuntu and Debian: python3, python3-serial, netcat-openbsd, libhamlib-utils and procps.
- Fedora: python3, python3-pyserial, netcat, hamlib and procps-ng.
- Arch: python, python-pyserial, openbsd-netcat, hamlib and procps-ng.

- Package names. pyserial is python3-serial on Debian and Ubuntu, python3-pyserial on Fedora, and
  python-pyserial on Arch. The Python venv module may be a separate package. The sound tools may
  come with a different package name.
- Systemd user services. They are standard on current systemd systems, but a system without systemd
  cannot run `install.sh` as written. Systemd starts user services at login, unless you turn on
  lingering for your user with `loginctl enable-linger`; that is systemd's own setting and is not
  tested here.
- The udev rule. It names the group uucp, which Arch has. If your distribution has no such group,
  edit the rule, or the files in `udev/`, before running the script. The device is owned by your
  user either way.
- The Python path. The service starts `/usr/bin/python3`. If yours is elsewhere, edit the line in
  `d750d.service.in` before running `install.sh`.

## See also

- [Quick start](quickstart.md)
- [Radio setup](radio-setup.md)
- [Settings](settings.md)
- [Troubleshooting](troubleshooting.md)
