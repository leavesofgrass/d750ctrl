# Troubleshooting

When something is wrong, run two commands first: `d750 doctor` and `d750 log`. This page then lists
the troubles the project has met, each as what you see, why it happens, and what to do.

## Start here: d750 doctor and d750 log

```sh
d750 doctor
d750 log
```

`d750 doctor` prints one line per check. Each starts with Pass or Fail. A line that starts with note
is information. The last line counts the passes and fails, and the exit code is 0 only when there is
no Fail. It checks, in order:

- that the radio is on USB, and that `/dev/d750-cat` exists;
- that d750d is running, its port is open, and the radio answers the ID command;
- the radio's firmware and type, on one line (a `note:` line instead if the radio does not answer);
- that the CAT port carries only CAT, and the GPS output to the PC is off;
- the TNC mode, and that the data band's squelch is not 0;
- that the radio's sound card is present, and is not your default sound output;
- the Bluetooth pairing, only if you set an address, and that the PTT port answers;
- whether xara is running, as a note only.

`d750 log` prints the last 20 lines of today's d750d log. `d750 log 50` prints 50, and
`d750 log follow` keeps showing new lines. Before you share a log with anyone, read it first,
because logs can hold call signs, positions and the text of messages. The log is in
`~/.local/share/d750ctrl/log`, one file a day, each line with a time. It keeps keying, settings,
refusals, errors, the port opening and closing, and anything the radio sent unasked. Routine reads
are left out. The same error again is
logged once and then counted: one line a minute says "repeated N more times". Setting
`D750_LOG_ALL=1` for the daemon logs every exchange. d750d also prints to the systemd journal.

## When the commands do not answer

### d750d is not answering

- What you see: "d750d is not answering on 127.0.0.1:4533", with the hint to run
  `systemctl --user status d750d`. d750ctrl prints a line that starts with Fail and says the same.
- Why: the daemon is not running, or your settings or environment point at other ports.
- What to do: run `systemctl --user status d750d` and `d750 log`. Start it with
  `systemctl --user start d750d`. Check `ptt_port` and `cmd_port` in
  `~/.config/d750ctrl/d750ctrl.conf`, and that `D750_CMD_PORT` is not set to a test port.

### The radio is not on USB, or /dev/d750-cat is missing

- What you see: `d750 doctor` fails "radio not on USB" or "/dev/d750-cat missing". d750d logs "radio
  port not available".
- Why: the cable, the radio's power, or the udev rule. A radio switched off, at night for one, has
  no USB devices at all. That is normal.
- What to do: check the cable in the control head's socket and that the radio is on. Run
  `sudo ./install-udev.sh` if you have not. d750d opens the port by itself, up to about 45 seconds
  after the radio is back.

### Every command takes seconds

- What you see: commands are slow, and `d750 doctor` fails "unsolicited bytes on the CAT port" or
  "GPS PC output on".
- Why: GPS sentences are streaming on the CAT port.
- What to do: run `d750 gps output off`, or set menu 403 to Off. `d750 fixup` puts it back to off.
  Doctor also names menu 982 as another possible source. See [Radio setup](radio-setup.md).

### CAT stopped answering after a menu change

- What you see: with the TNC in KISS mode, the control head's port stops answering CAT.
- Why: menu 984 was set to USB (Main Unit). CAT then moved to the base unit's port.
- What to do: set menu 983 to USB (Main Unit) and menu 984 to USB (Panel), the layout that works.

### Everything on the USB bus vanished

- What you see: the radio and other devices on the same bus drop off at the same moment.
- Why: a transmitting handheld near the USB leads caused a bus reset.
- What to do: keep transmitting handhelds away from the USB leads.

## When a command is refused

### The radio refused a frequency

- What you see: a line that starts with Fail and says the radio refused the command, and exit code
  1.
- Why: the radio does not accept that frequency.
- What to do: use a frequency in the radio's range. d750d's Hamlib answer lists receive ranges of
  118 to 174 MHz and 400 to 524 MHz, and transmit ranges of 144 to 148 MHz and 430 to 450 MHz.

### I cannot select DR

- What you see: `d750 mode A dr` prints a usage line, and the screen's mode key cycles only FM, NFM,
  AM and DV.
- Why: modes over MD are 0 FM, 1 NFM, 2 AM and 3 DV. The radio refuses anything above 3, so DR is
  not reachable this way.
- What to do: select DR on the radio itself.

### A note that a command is not yet verified

- What you see: "note: PC not yet verified on this radio; run d750 probe when it is plugged in".
- Why: `d750 probe` has not yet recorded that the radio answers that command. It is not a failure.
- What to do: run `d750 probe`. It is read only and writes a table of what your radio answers.

### Keying is refused

- What you see: "ERR TX is not allowed on this port; keying goes through 4532" from `d750 raw TX`,
  or the answer "RPRT -1" to a key request.
- Why: d750d refuses keying commands on port 4533, so only PTT on 4532 keys the radio. The second
  case is also what you get while the transmitter is locked.
- What to do: use the proper PTT path. Run `d750 unlock` if you locked it on purpose.

### Other software unkeys slowly

- What you see: a program using Hamlib's own TH-D74 radio model takes seconds to unkey.
- Why: that model talks to this radio but is slow to unkey. d750d keys with the raw TX and RX
  commands instead.
- What to do: choose the rig "NET rigctl" at 127.0.0.1:4532, which is d750d.

## When the TNC and APRS misbehave

### Nothing transmits from d750-aprs

- What you see: beacons, messages and acknowledgements do not go out. aprschat says "Transmit off,
  messages wait".
- Why: nothing transmits until you turn it on. With it off, beacons, messages, acknowledgements and
  frames from KISS programs are held back.
- What to do: run `d750-aprs transmit on`. Run `d750-aprs transmit off` to hold everything back
  again.

### The TNC does not transmit although it receives

- What you see: `d750 doctor` fails "data band squelch is 0".
- Why: with menu 508 on Busy, the TNC will not transmit while the data band's squelch is wide open.
- What to do: run `d750 squelch B 3`, or `d750 fixup`, which sets it to the level in `fixup.conf`.

### The TNC takes commands but sends nothing after a restart

- What you see: after the radio restarts by itself, d750-aprs reports a restart, and nothing goes
  out.
- Why: the TNC may take commands but send nothing until the KISS settings are set again. A power
  cycle did not clear it once. Sending the settings did.
- What to do: d750-aprs sends the settings every time it connects to the TNC, and resets the TNC two
  minutes after every return of its port, trying once more a minute later if the radio does not
  confirm. The log says whether it was confirmed. If the radio still sends nothing, switch it off
  and on.

### The radio is receiving but not transmitting, with nothing on its display

- What you see: no sign on the radio. d750-aprs says only that the radio restarted.
- Why: on November 11, 2026 the radio restarted while receiving a long frame and came back receiving
  but not transmitting until it was switched off and on. d750-aprs cannot tell that from the
  computer, and an iGate carries this station's beacon only now and then, so a beacon nobody carried
  proves nothing.
- What to do: switch the radio off and on, and run a real check. d750-aprs claims nothing about it.

### The notice "has heard nothing since"

- What you see: an ntfy notice, "TM-D750 has heard nothing since" a time, saying that some number of
  minutes have passed since the restart and to check the radio.
- Why: nothing was heard for `deaf_minutes` after a restart. The default is 90. It is sent once for
  a restart, and not while the radio is switched off.
- What to do: check the radio. Set `deaf_minutes` to 0 in `aprs.conf` to turn the notice off.

### The TNC hears much less than the squelch opens for

- What you see: the squelch opens often, but few packets reach the computer.
- Why: the TNC decodes far fewer packets than the squelch opens for. Most distant bursts never
  decode, while a station nearby decodes every time.
- What to do: to tell "not decoding" from "not reaching the computer", put the TNC in APRS mode with
  menu 570 RX Beep on All and listen for many minutes. See [Radio setup](radio-setup.md).

### No iGate carried my beacon

- What you see: a log line that says no iGate carried the check beacon.
- Why: the radio never hears its own beacon, so this iGate cannot carry it, and a beacon an iGate
  carries only now and then proves nothing.
- What to do: nothing. It is never an alarm, a reset or a power cycle.

### The radio switched off shows as "radio off"

- What you see: the Uptime Kuma monitors for the TNC, heard packets and the beacon stay up with
  "radio off since" a time, and no alert goes out.
- Why: a radio switched off is a normal state. Only a return within 3 minutes counts as a restart.
- What to do: nothing.

## When the sound tools fail

- What you see: `d750 level` says "Fail: the radio's sound card is not present", and `d750 fixup`
  warns about the sound card.
- Why: the radio's sound card is on the control head's USB socket. It is not there when that socket
  is not connected or the radio is off.
- What to do: connect the control head's socket and switch the radio on. `d750 doctor` also fails
  when the radio is your default sound output. Choose another default output in your sound settings.

## When a command is not found

- What you see: the shell says the command is not found.
- Why: `install.sh` links the commands into `~/.local/bin`, which is not on your PATH.
- What to do: add `~/.local/bin` to your PATH and open a new terminal.

## See also

- [Quick start](quickstart.md)
- [Radio setup](radio-setup.md)
- [Radio notes](radio-notes.md)
- [d750](d750.md)
- [d750-aprs](aprs.md)
