# A map of the repository: every file and where it is explained

This page lists every file in the project, says in one line what it is, and points to the page that
explains it. Use it to find your way, or to study how the pieces fit even if you never run them.

## How the pieces fit

One program, d750d, opens the radio's serial port. Nothing else does. Everything that tunes, reads
or keys the radio asks d750d over two local network ports: one speaks hamlib's rigctl protocol, so
other radio programs can use it, and one takes the radio's own commands, one per line.

The radio's built-in packet modem, the TNC, has a serial port of its own. `d750-aprs` reads that
one.

The programs are in the project's top folder, because installed links and services point at them
there. Two folders hold what is not a program: `tests/` has the pretend radio and every test, and
`config/` has the settings examples, the service templates and the udev rule.

The command line tools are thin: a short wrapper script starts a Python program of the same name.
The tests never touch a radio. They run against `tests/d750-sim.py`, a pretend radio.

## Start here

- `README.md`: what the project is, what it needs and how to start.
- `LICENSE`: the GNU General Public License, version 2. The README's License section says how it
  applies.
- `CHANGELOG.md`: what changed, newest first.
- `.gitignore`: the files git leaves out, such as the Python environment and logs.

## The daemon

- `d750d.py`: the daemon. See [d750d](d750d.md).
- `config/d750d.service.in`: the template for its user service. `install.sh` fills in the folder.
  See [Install](install.md).

## The verbs and the rig screen

- `d750`: the verbs, a bash script. Its opening comment is the help text. See [d750](d750.md).
- `d750ctrl`: the full-screen rig control, in Python on curses. See [d750ctrl](d750ctrl.md).
- `config/d750ctrl.conf.example`: the settings file for both, with every key. See
  [Settings](settings.md).
- `probe.py`: asks the radio, read only, which commands it answers, and writes the table.
  `d750 probe` runs it. See [d750](d750.md) and [the radio reference](radio-reference.md).

## APRS

- `d750-aprs`: the wrapper script that starts `d750-aprs.py`.
- `d750-aprs.py`: the APRS program: beacon, receive-only iGate, digipeater, messages, notices. See
  [APRS](aprs.md).
- `config/d750-aprs.service.in`: the template for its user service. `install.sh` writes it and never
  starts it.
- `config/aprs.conf.example`: its settings, with every key. See [Settings](settings.md).
- `aprschat`: the wrapper script that starts `aprschat.py`.
- `aprschat.py`: APRS messages from the terminal, with a screen and a line mode. See
  [aprschat](aprschat.md).

## Pictures and text through the sound card

- `d750-sstv` and `d750-sstv.py`: send and receive SSTV. See [SSTV and RTTY](sstv-and-rtty.md).
- `d750-rtty` and `d750-rtty.py`: send and receive RTTY. The same page.
- `rttymodem.py`: the RTTY encoder and decoder, in Python with numpy. It can be read and tested with
  no radio. The same page.
- `d750-keyer.py`: shared by the two: it finds the radio's sound devices, holds the transmitter
  keyed through d750d for one transmission, and pauses xara meanwhile. The same page.

## Power

- `d750-power`: drives a relay on the radio's power feed. See [d750-power](power-relay.md).
- `relay/d750-relay/d750-relay.ino`: the Arduino sketch for that relay. The same page.

## Installing

- `install.sh`: links the commands, starts d750d, makes the Python environment and writes the
  settings files. No root. See [Install](install.md).
- `install-udev.sh`: the one step that needs root. It installs the udev rule. See
  [Install](install.md).
- `config/60-d750ctrl.rules`: the rule that gives the radio's two serial ports fixed names. See
  [Radio setup](radio-setup.md).

## Station tools

All of these are explained on [Station tools](station-tools.md), except radiogram.

- `station/station`: raise and lower the station's services.
- `station/station.conf.example`: its settings, with every field.
- `station/notify`: send a notice to an ntfy server.
- `station/notify.conf.example`: its settings: the server and an optional token.
- `station/radiogram`: write, check and log NTS radiograms. See [radiogram](radiogram.md).
- `station/d750d-kuma`: report the health of the daemon, the radio and xara to Uptime Kuma.
- `station/d750d-kuma.service` and `station/d750d-kuma.timer`: the user service and the timer that
  run it once a minute. `station/install-station.sh --kuma` installs them.
- `station/xara-wait-audio`: wait for the radio's sound card before xara starts.
- `station/xara-radio-pair`: pair with a radio over Bluetooth and list the sound names.
- `station/mode-listen`: a listening test for the radio's mode codes.
- `station/install-station.sh`: the installer for this folder.

## Extras

- `extras/README.md`: what is in the folder, and the warnings.
- `extras/d750-ptt.py`: the first keying program, kept for reference. Never run it beside d750d.

## Tests

All of these are explained on [Testing](testing.md).

- `tests/d750-sim.py`: the pretend radio. It answers the way the real one was seen to answer. See
  also [Try it without a radio](try-without-a-radio.md).
- `tests/test-env.sh`: starts the pretend radio and a second d750d on the test ports.
- `tests/tests.sh`: runs every verb against the pretend radio and checks the answers.
- `tests/output-rules-test.py`: holds what the verbs print to written rules.
- `tests/d750ctrl-test.py`: drives the rig screen in a pseudo terminal.
- `tests/d750-aprs-test.py`: the APRS program's checks. Nothing in it opens a port or transmits.
- `tests/aprschat-test.py`: the chat's checks, in line mode and on its screen.
- `station/station-test.py`: the station tool, with fake services.
- `station/notify-test.py`: notify, with a fake curl.
- `tests/modes-test.sh`: an SSTV and RTTY round trip over a virtual sound device. It needs a sound
  server, so it does not run on GitHub.
- `.github/workflows/tests.yml`: runs the tests on GitHub, on Ubuntu, Debian, Fedora and Arch.

## The documentation

- `docs/README.md`: the index of every page.
- Each other file in `docs/` is one page. The index lists them all.

## See also

- [Documentation index](README.md): every page, grouped.
- [What has been tested](what-has-been-tested.md): how far each part has been proven.
- [The TM-D750 from a computer](radio-reference.md): ports, commands, menus and quirks.
