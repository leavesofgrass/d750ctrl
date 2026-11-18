# d750-power and the relay: power cycle the radio from the computer

## What it is for

`d750-power` cuts the radio's DC power for a few seconds and restores it, from the computer, by
talking to a small relay board. It is for a radio that sits out of reach, or that needs a power
cycle to recover after a restart. The relay sketch in `relay/d750-relay/d750-relay.ino` is the
program for that board. This is an optional extra. The rest of the project does not need it.

**Nothing runs a power cycle automatically yet.** The `power_cycle_cmd` setting in `aprs.conf` is
kept for a real transmit check that does not exist, and today nothing calls it. You run `d750-power`
by hand.

## Before you start

- A relay on the radio's DC feed, wired as the sketch's comments describe, and an Arduino Leonardo
  (ATmega32U4) board running the sketch. The sketch's comments name a LattePanda board's built-in
  Leonardo, but any Leonardo works if you set its port (see Settings).
- **The fail-safe wiring.** The radio's +13.8 V runs through the relay's normally closed contact.
  With the relay at rest, the radio is powered. So a dead Leonardo, a reboot of the computer, or a
  cut USB cable all leave the radio on. Keep it that way.
- **The contact must be rated for the load.** The radio draws over 10 A at 50 W, so the contact that
  carries it must be rated 20 A DC or more. The sketch's comments give one way to build it: a small
  relay module on the control pin driving an automotive relay. This page does not give wiring
  instructions. Follow your radio's installation manual and good electrical practice.
- The sketch uses pin 7 for the relay module's input, and assumes a module that switches on when its
  input is LOW (active low). The two constants at the top of the sketch, `RELAY_PIN` and
  `RELAY_ACTIVE_LOW`, change that. Load the sketch onto the Leonardo with the Arduino tools you use.
- `python3` with the `pyserial` module on the computer.
- `d750-power` is linked into `~/.local/bin` by `install.sh`, so it is on your PATH like the other
  commands. Open a new terminal if `~/.local/bin` was not on your PATH before.

## Try it

These commands talk only to the relay board. They do not touch the radio's own USB ports.

Ask whether the radio is powered:

```sh
d750-power status
```

The relay says "Pass: radio power on" when the radio is powered, or "Note: radio power off, back on
in" some seconds, during a cycle.

Ask which version of the sketch is running, which pin it uses and whether it is active low:

```sh
d750-power id
```

The relay answers with "d750-relay", its version, the pin and the polarity.

Cycle the power, with the radio off for 10 seconds and then back on by itself:

```sh
d750-power cycle 10
```

The relay says "OK: radio power off for 10 s". When the time is up, the radio is powered again.

## What it can do

### The commands

From the tool's docstring:

- `d750-power status`: is the radio powered.
- `d750-power cycle [N]`: the radio off for N seconds, then on again by itself. N is 3 to 60, and
  the default is 10. A number outside that range is brought into it.
- `d750-power on`: power back on now.
- `d750-power id`: the relay sketch's version, pin and polarity.

Run with no arguments, or an unknown word, the tool prints this list and exits with code 2. The exit
code is 0 for a Pass, 1 for a Fail, and 2 for a usage mistake. The tool prints the relay's reply
line as it is.

### Safety limits in the sketch

- There is no plain "off". The relay can never leave the radio off for more than 60 seconds
  (`MAX_OFF_S`).
- A new cycle is accepted only 30 seconds after the last one ended (`MIN_GAP_S`). Otherwise the
  relay says "Fail: the last cycle ended less than 30 s ago".
- A cycle that is already running is answered with "Fail: already cycling".
- At start the sketch puts the relay at rest first, so the radio is powered before anything else
  happens.
- The tool opens the serial port at 9600 baud, never 1200, because opening a Leonardo at 1200 baud
  puts it in its bootloader.
- `d750-power` does not check whether the radio is transmitting. Look at `d750 state` first, and run
  `d750 lock` before you cut power so that nothing keys it in the meantime.

### After a power cycle

When the radio comes back, d750d reopens its port by itself, up to about 45 seconds later. Then run
`d750 fixup` to put back the TNC mode, the data band's squelch and the GPS output, and `d750 doctor`
to check everything. [d750-aprs](aprs.md) resets the TNC by itself after every return of its port.

## Settings

- `D750_RELAY_PORT`: the relay's serial port. The default is a `/dev/serial/by-id/` path for the
  LattePanda's Leonardo. For another board, set this to its path from `/dev/serial/by-id/`.
- `power_cycle_cmd` in `aprs.conf`: a command that [d750-aprs](aprs.md) would run for a power cycle,
  at most once in 30 minutes and never while the radio is keyed. Nothing calls it today. The example
  in the file is `d750-power cycle 10`.

See the [settings page](settings.md).

## When something goes wrong

- **You see:** "Fail: the relay's port ... cannot be opened".
  - **Why:** the board is not plugged in, the path is wrong, your user may not open it, or
    `pyserial` is missing.
  - **What to do:** check `ls /dev/serial/by-id/`, set `D750_RELAY_PORT`, and check the permissions
    on the port.

- **You see:** "Fail: no answer from the relay. Is d750-relay.ino on the Leonardo?"
  - **Why:** the port opened but nothing answered. The sketch is not loaded.
  - **What to do:** load `relay/d750-relay/d750-relay.ino` onto the Leonardo.

- **You see:** "Fail: unknown command; try status, cycle 10, on, id".
  - **Why:** the relay received a word it does not know.
  - **What to do:** use one of the four commands.

## See also

- [d750-aprs](aprs.md)
- [d750: the verbs](d750.md)
- [Settings reference](settings.md)
- [Troubleshooting](troubleshooting.md)
