# d750ctrl

d750ctrl is keyboard control of the Kenwood TM-D750 mobile radio from a Linux computer, over the
radio's own USB serial port. It is for radio amateurs who want to tune, watch and configure the
radio from a terminal, and who may use a screen reader or a Braille display to do it. Every command
prints short plain lines with the answer first, and nothing needs a mouse.

**This project is experimental.** It is one operator's working station software, shared as it is.
Commands, settings and output can change between versions.

**It controls a real transmitter.** Some commands key the radio, and the APRS service can transmit
by itself once you turn transmitting on. You are responsible for every transmission and for your
license conditions. Start with the dry runs and with
[Try it without a radio](docs/try-without-a-radio.md).
[What has been tested](docs/what-has-been-tested.md) says how far each part has been proven. There
is no warranty; see the license.

## What you need

- A Kenwood TM-D750 and a USB-C cable to its control head.
- A Linux computer with systemd user services. The owner uses CachyOS.
- Python 3 with the pyserial module, bash, and git.
- Optional: tmux, for the rig screen's windows. A sound server with the pactl, parecord and paplay
  commands, for SSTV, RTTY and the level checks.

The full list, with a check for each item, is in [Install](docs/install.md).

## Quick start

```sh
git clone https://github.com/leavesofgrass/d750ctrl ~/d750ctrl
cd ~/d750ctrl
./install.sh YOURCALL
sudo ./install-udev.sh
d750 doctor
d750 status
```

Replace YOURCALL with your call sign. `install.sh` needs no root. `install-udev.sh` is the one step
that does. `d750 doctor` prints one line per check, each starting with Pass or Fail. `d750 status`
prints both bands, the transmit band, the TNC and the daemon.

When it works, `d750 status` answers with four lines. This is what the pretend radio prints, so
yours will show your own numbers:

```text
band A: 147.040 MHz, FM, squelch 6, busy, power high
band B: 144.390 MHz, FM, squelch 3, quiet, power mid, transmits, control
tnc: KISS on band B
daemon: port open /dev/pts/0; not keyed; unlocked; last answer 18:48:19; unsolicited bytes seen 0
```

No radio yet? [Try it without a radio](docs/try-without-a-radio.md) runs a pretend one.

The cabling is in [Quick start](docs/quickstart.md) and [Radio setup](docs/radio-setup.md).

## Your first five minutes

1. Run `d750 doctor`. Read each Fail line. [Troubleshooting](docs/troubleshooting.md) explains them.
2. Run `d750 status` to read both bands.
3. Change a frequency with a dry run first: `d750 freq A 146.520 -n` shows what would be sent and
   changes nothing. Run it again without `-n` to do it.
4. Watch a band for activity: `d750 watch B 30` prints a line only when the squelch opens or closes.
5. Run `d750ctrl` to open the rig screen. Press the question mark for help, and leave it open while
   you listen. Press the letter q to quit.

## The tools

- [d750d](docs/d750d.md): the daemon that alone opens the serial port and speaks hamlib to other
  programs.
- [d750](docs/d750.md): the command with plain verbs: status, freq, mode, squelch, power, mem and
  more.
- [d750ctrl](docs/d750ctrl.md): the full-screen rig control.
- [d750-aprs](docs/aprs.md): APRS through the radio's own TNC, including iGate and digipeater.
- [aprschat](docs/aprschat.md): APRS messages from the terminal, with a line mode for screen
  readers.
- [d750-sstv and d750-rtty](docs/sstv-and-rtty.md): pictures and text through the radio's sound
  card.
- [VARA and chat](docs/vara-and-chat.md): VarAC frames through xara, and the chat windows.
- [radiogram](docs/radiogram.md): write, check and log NTS radiograms.
- [d750-power](docs/power-relay.md): a fail-safe relay that can power cycle the radio.
- [Station tools](docs/station-tools.md): the owner's other small tools for running the station
  computer.

## Learn more

- [Documentation index](docs/README.md): every page, grouped.
- [A map of the repository](docs/repository-map.md): every file and where it is explained.
- [Recipes](docs/recipes.md): short how-tos for common tasks.
- [Screen readers and Braille](docs/screen-readers.md): how the tools are built for them.
- [Radio notes](docs/radio-notes.md): hard-won facts about the TM-D750.
- [Settings](docs/settings.md), [Testing](docs/testing.md) and the [Glossary](docs/glossary.md).

## Tested on

The tools are used every day with a real radio, reporting firmware 1.03 and connected by USB, on
CachyOS, an Arch Linux relative. Screen readers and Braille displays were used in the testing. The
first testing was on Debian 13. Bluetooth has not been used. The automated tests run against the
pretend radio on Ubuntu, Debian, Fedora and Arch. The installers have also been run by hand on
Debian. Fedora has been tried only by the automated tests. Other distributions may need adjusting;
see [Install](docs/install.md). To see what firmware your own radio reports, run `d750 doctor`.

## License

Copyright (c) 2026 Jon, KD7SWH.

d750ctrl is free software: you can redistribute it and modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 2 of the License, or (at
your option) any later version. It is distributed in the hope that it will be useful, but without
any warranty, without even the implied warranty of merchantability or fitness for a particular
purpose. The full text is in [LICENSE](LICENSE).

Some facts about the radio in these pages were first reported by the
[kenwood project](https://github.com/swiftraccoon/kenwood), which is also under the GNU General
Public License, version 2 or later. Each such fact is marked where it appears.
