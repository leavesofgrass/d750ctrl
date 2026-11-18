# Try it without a radio: the pretend radio

You can run the whole d750ctrl chain against a pretend TM-D750. This page says what it needs, how to
start it, how to point `d750` and `d750ctrl` at it, what it starts with, and how to stop it. Nothing
here transmits, and no real radio is involved.

## What it is for

The pretend radio is a small program, `tests/d750-sim.py`. It answers the radio's commands on a
pseudo terminal, which is a software stand-in for a serial port. A second copy of d750d talks to it
on test ports, so the real daemon and your real radio are never touched. It is the same test bed the
automated tests use. This page is for a curious reader who has no radio connected yet.

## Before you start

- A Linux computer. The pretend radio uses a pseudo terminal, which is not available on Windows.
- Python 3 with the pyserial module, because the test daemon is d750d. Check it with
  `/usr/bin/python3 -I -c "import serial"`. See [Install](install.md).
- bash and a clone of the repository. You do not need `install-udev.sh`, systemd or a radio.
- The `d750` command on your PATH, which `install.sh` arranges. Without it, run `./d750` from the
  clone instead.
- Nothing else for `d750` itself. The checks in `d750 doctor` and the sound verbs need things the
  pretend radio does not have, and report Fail for them.

## Try it

Start the pretend radio in a terminal of its own and leave it running:

```sh
cd ~/d750ctrl
tests/test-env.sh
```

It prints two lines. The first begins "simulator pid" and names the pseudo terminal. The second
begins "test daemon pid" and says the PTT port is 4542 and the commands port is 4543. If it prints
"simulator gave no device path", the simulator did not start.

In a second terminal, point the tools at the test ports. The ports are the two environment variables
`D750_CMD_PORT` and `D750_PTT_PORT`. Then ask for the status:

```sh
export D750_CMD_PORT=4543 D750_PTT_PORT=4542
d750 status
```

```text
band A: 147.040 MHz, FM, squelch 6, busy, power high
band B: 144.390 MHz, FM, squelch 3, quiet, power mid, transmits, control
tnc: KISS on band B
daemon: port open /dev/pts/0; not keyed; unlocked; last answer 18:48:19; unsolicited bytes seen 0
```

Your device path and time will differ. Band A may show busy or quiet, because the pretend radio is
started with an option that makes the busy flag flicker now and then.

Change a frequency, dry run first, then for real:

```sh
d750 freq A 146.520 -n
d750 freq A 146.520
```

```text
before: band A 147.040 MHz
would send: FQ 0,0146520000
```

```text
before: band A 147.040 MHz
after: band A 146.520 MHz
```

Open the rig screen against it. `--plain` keeps the screen in this one terminal, which is how the
tests run it:

```sh
d750ctrl --plain
```

Read the daemon's own log of what you did. The test daemon logs to its own folder, so say so:

```sh
D750_LOG_DIR="$HOME/.local/share/d750ctrl/log/test" d750 log 12
```

To keep your real settings out of the way, you can also point the tools at a scratch settings
folder. The tests do the same:

```sh
mkdir -p "$HOME/.config/d750ctrl-test"
export D750_CONF_DIR="$HOME/.config/d750ctrl-test"
```

Programs that speak Hamlib can use the pretend radio too. Choose the rig "NET rigctl" and the
address 127.0.0.1:4542.

## What the pretend radio starts with

- Band A: 147.040 MHz, FM, squelch 6, power high.
- Band B: 144.390 MHz, FM, squelch 3, power mid. Band B is the transmit band and the control band.
- The TNC is in KISS mode on band B.
- Two memory channels: 000 at 146.520 MHz and 001 at 144.390 MHz, both FM.
- The GPS is on and its output to the PC is off. VOX is off. The radio clock shows the time of your
  computer. The radio identifies itself as TM-D750.
- It answers some commands the way the real radio answered on November 7, 2026, and the rest the way
  the community's TH-D74 command list says. Commands it does not know get a question mark. For
  commands the real radio has not confirmed, `d750` prints a line starting with note and saying the
  command is not yet verified on this radio.
- It has no radio waves, no sound card, no USB and no Bluetooth. `d750 doctor` fails on those, and
  `d750 level` says the sound card is not present. That is expected.

The pretend radio accepts a key command and an unkey command from the daemon but does not transmit.
`d750 raw TX` is still refused, as on a real radio: keying goes through port 4542.

## Stop it

The two programs stop together when you end them with the process numbers the test bed saved. In any
terminal:

```sh
kill $(cat "$HOME/.local/share/d750ctrl/log/test/pids")
```

The test logs stay in `~/.local/share/d750ctrl/log/test` until you remove that folder yourself.
Unset the two variables in the second terminal, or close it, to talk to a real radio again:

```sh
unset D750_CMD_PORT D750_PTT_PORT D750_CONF_DIR
```

## When something goes wrong

- `d750 status` says d750d is not answering. The test bed is not running, or you did not export the
  two variables in this terminal. Check both.
- The test bed prints "simulator gave no device path". Python could not start the simulator. Run
  `python3 -I tests/d750-sim.py` by hand in the clone to see the error.
- The test daemon logs an error about the module serial. Install pyserial; see
  [Install](install.md).

## See also

- [Testing](testing.md): the tests that run against this pretend radio.
- [d750](d750.md) and [d750ctrl](d750ctrl.md)
- [Quick start](quickstart.md)
- [Recipes](recipes.md)
