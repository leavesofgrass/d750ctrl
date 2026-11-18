# d750ctrl

Control a Kenwood TM-D750 radio from the keyboard, on Linux. Tune it, read it and run APRS through
it, in short plain lines of text that work well with a screen reader or a Braille display.

**Experimental.** This is one operator's station software, shared as it is. It controls a real
transmitter, and you are responsible for everything it sends.

## You need

- A Kenwood TM-D750 and a USB-C cable.
- A Linux computer.
- Python 3 with the pyserial module.

## Start

```sh
git clone https://github.com/leavesofgrass/d750ctrl ~/d750ctrl
cd ~/d750ctrl
./install.sh YOURCALL
sudo ./install-udev.sh
d750 doctor
d750 status
```

Put your call sign in place of YOURCALL. `d750 doctor` checks your setup and prints Pass or Fail for
each item. `d750 status` reads the radio.

- No radio yet? [Try it without a radio](docs/try-without-a-radio.md).
- Want each step explained? [Quick start](docs/quickstart.md).
- Something failed? [Troubleshooting](docs/troubleshooting.md).

## What is in it

- [d750](docs/d750.md): plain commands to read and set the radio.
- [d750ctrl](docs/d750ctrl.md): a full-screen rig control.
- [d750-aprs](docs/aprs.md) and [aprschat](docs/aprschat.md): APRS and its messages.
- [d750-sstv and d750-rtty](docs/sstv-and-rtty.md): pictures and text over the air.
- [Station tools](docs/station-tools.md): small helpers for running a station computer.

Everything else is in the [documentation](docs/README.md).

## Good to know

- [What has been tested](docs/what-has-been-tested.md), and what has not.
- [Radio setup](docs/radio-setup.md): cables and the radio's menu settings.
- [Recipes](docs/recipes.md): short how-tos.

## Honorable mention

[kenwood](https://github.com/swiftraccoon/kenwood), by swiftraccoon, is a set of Rust libraries and
command line tools for Kenwood radios, with a library for controlling the TM-D750. If you want to
build your own program for this radio, look there. Some facts about the radio in these docs were
first reported by that project, and each is marked where it appears. It is a separate project with
its own authors.

## License

GNU General Public License, version 2 or later. See [LICENSE](LICENSE).

This project is not connected with Kenwood, VARA or VarAC, and neither endorses them nor is endorsed
by them. VARA is not free software, and none of it is included. More in
[License and names](docs/license.md).
