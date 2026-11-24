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

- What you see: "ERR TX is not allowed on this port" from `d750 raw TX`, or from `d750 raw TX0` or
  any line whose first two characters are TX.
- Why: d750d refuses keying commands on port 4533, so only PTT on 4532 keys the radio. It judges a
  command by its first two characters, whatever follows.
- What to do: key through port 4532 with a Hamlib program. Unkey with `d750 ptt off`.

- What you see: the answer "RPRT -1" to a key request.
- Why: PTT is locked. A `T` with a value other than 0, 1, 2 or 3, a line with a control character
  in it or over 512 characters, and a frequency or level that is not a number get "RPRT -1" too.
- What to do: run `d750 state`. If it says locked, run `d750 unlock` if you locked it on purpose.
  If it says unlocked, read `d750 log`: it names the lines refused for a control character or their
  length.

### The command port refuses a line

d750d checks each line on port 4533 whole, before any of it reaches the radio. Each refusal has its
own words:

- What you see: "ERR a line may not start with a digit".
- Why: the line starts with a digit, such as `0M` or `0G`, which enter the radio's programming and
  service modes.
- What to do: nothing. The tools never need those modes.

- What you see: "ERR say the word alone, in small letters".
- Why: one of the daemon's words, state, lock, unlock, reconnect or quit, came in capitals, with
  spaces around it, or with more after it, such as `UNLOCK` or `lock now`.
- What to do: send the word alone in small letters, or use `d750 state`, `d750 lock` and
  `d750 unlock`.

- What you see: "ERR only plain letters, digits, spaces and , . - / + are allowed".
- Why: the line held another character: a carriage return inside the line, a semicolon, a tab,
  another control character, or a mark such as `_` or `*`.
- What to do: send one command per line with only those characters. A line ending in a carriage
  return and a newline is fine.

- What you see: "ERR the line is longer than 512 characters".
- Why: no Kenwood command is that long, so the line is not a command.
- What to do: check what the program sends.

### A change is refused while PTT is locked

- What you see: "ERR VX is refused while PTT is locked", or the same with TN or PT, from
  `d750 raw`. From `d750 vox on`, `d750 tnc aprs`, `d750 tnc kiss` or `d750 fixup`, the same words
  after "Fail:".
- Why: lock refuses more than keying. It also refuses what would let the radio send by itself:
  VOX on, the TNC in APRS or KISS mode, and any change to the beacon method. `d750 fixup` stops at
  that line.
- What to do: run `d750 unlock`, then the verb again. Turning VOX or the TNC off works while locked.

What lock covers, and what it does not, in plain words:

- Covered: keying through port 4532 by any program; turning VOX on; putting the TNC into APRS or
  KISS mode; changing the beacon method.
- Not covered: settings already in place, such as VOX that is on or a TNC already in KISS mode;
  KISS frames that d750-aprs or a KISS program sends through a TNC already in KISS mode (use
  `d750-aprs transmit off`); the radio's own front panel and microphone.
- After the radio restarts while locked, d750-aprs cannot put the TNC back in KISS mode: its reset
  turns the TNC off and is then refused, so the TNC stays off. Unlock, then run `d750 tnc kiss B`
  or `d750 fixup`.

The full account is on the [d750d page](d750d.md#what-lock-covers-and-what-it-does-not).

### d750 lock says the radio did not say it is receiving

- What you see: "OK locked; the radio did not say it is receiving" from `d750 lock`, or
  "Locked. The radio did not confirm RX." on the rig screen.
- Why: d750d sent the unkey command as part of the lock, and the radio did not answer with RX. The
  lock holds all the same.
- What to do: look at the radio, and read `d750 state` and `d750 log`. If the radio is still
  transmitting, switch it off.

### The rig screen will not take my y

- What you see: "Too fast. Answer again." in the message row, and the question stays.
- Why: a question takes no answer in its first half second, and a stream of keys, such as a paste,
  never answers one. Keys typed ahead of a question are thrown away, except the keys of unkey and lock.
- What to do: wait a moment, then press the small letter `y` once. With a terminal that marks
  pastes, a paste cannot answer a question. What is left: a marked paste can only add text to a
  typing line, unkey, or lock. Beyond that it takes a link that stalls inside a paste for more than
  a second or two, which makes the rest of the paste keys. A terminal that sends no marks pastes as
  keys, and there a paste that pauses for half a second or more and then has a small `y` could still
  answer a send question.
- What you see: "PTT state not read. Nothing sent." when you start a frame or a send.
- Why: the screen does not know yet whether PTT is locked, so it sends nothing.
- What to do: wait for the next read, or check that d750d answers.

### The rig screen ends with "Warn: unkey not confirmed."

- What you see: after you quit the rig screen, one or both of these lines, "Warn: unkey not confirmed."
  and "Warn: lock not confirmed."
- Why: you pressed unkey or lock just before you quit. On every way out the screen waits up to two
  seconds for d750d to answer it, and d750d did not answer in that time.
- What to do: run `d750 state` to see whether the radio is keyed and whether PTT is locked. Run
  `d750 lock` again if you wanted the lock.

### The rig screen says "PTT is no longer locked."

- What you see: "PTT is no longer locked." in the message row, and the top row says Unlocked.
- Why: the lock went away without this screen's unlock: another program, such as `d750 unlock`,
  unlocked it, or d750d started again, and a new daemon starts unlocked. The screen says it once.
- What to do: press the lock key, capital `L` by default, if you still want the lock. Run
  `d750 log` to see whether the daemon started again.
- One more thing: an unkey and Ctrl+C that arrive in the same burst lose the unkey, because the
  terminal throws waiting keys away at Ctrl+C. Press unkey first, then quit.

### "A paste was dropped."

- What you see: "A paste was dropped." in the message row.
- Why: the screen asks the terminal to mark pastes, and a marked paste is never keys. It is text
  only in a typing line, such as "Text to send:". Anywhere else it is dropped, and it never answers a
  question, never presses Enter and never changes the radio. In a typing line the message row says
  "Pasted 14 characters. Enter applies.", or "some left out" when characters could not be typed. An
  unkey key still unkeys while a paste is open, and Escape ends a paste that hangs.
- What to do: open the typing line first, paste, then press Enter.

### "A key after a paste was dropped." and "A paste is open."

- What you see: "A key after a paste was dropped." in the message row, or "A paste is open. Escape
  ends it." at the first key of a paste that has not finished.
- Why: after a paste no key acts for half a second, or two seconds when an Escape ended the paste. A
  key in that time is dropped and starts the wait again, which never lasts more than five seconds.
  So text that follows a paste's end is never keys. Only a key of unkey, and a key of lock when PTT
  is not locked, act inside or right after a paste.
- What to do: if Enter right after a paste did nothing, wait half a second and press it again. If a
  paste hangs, press Escape.

### My terminal does not mark pastes

- What you see: a paste into the main screen acts as keys, such as a tune or a question.
- Why: the terminal sends no bracketed paste marks. Inside the tmux workspace, tmux passes the marks
  only to a program that asked for them, and its own paste command marks a paste on that condition.
  Without marks the half second wait and the dropping of keys typed ahead still stand.
- What to do: type instead of pasting, or use a terminal that marks pastes.

### After Ctrl+Z

- After Ctrl+Z the shell sets its own paste mode. The screen does not handle Ctrl+Z. Quit the
  screen with capital Q instead.

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
- If PTT was locked, the reset cannot finish: "TNC reset tried twice after the radio came back: the
  radio did not confirm it." in the d750-aprs log, and the TNC is left off. Run `d750 unlock`, then
  `d750 tnc kiss B`.

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
