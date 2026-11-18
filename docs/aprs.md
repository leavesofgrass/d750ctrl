# d750-aprs: APRS through the radio's own TNC

## What it is for

`d750-aprs` turns the TM-D750's built-in TNC into a complete APRS station that runs in the
background. A TNC is a packet modem. d750-aprs reads every packet the radio decodes and says it as
one plain line of text. It can beacon your position, send and acknowledge APRS messages, act as a
receive-only iGate, act as a fill-in digipeater, and share the TNC with other APRS programs. (See
the [glossary](glossary.md) for APRS, iGate, digipeater and the other terms.)

**Nothing transmits until transmit is on.** Transmit starts off. With it off, d750-aprs holds back
every beacon, message, acknowledgement and frame from other programs, and says so in its log. Turn
it on with:

```sh
d750-aprs transmit on
```

and off again with `d750-aprs transmit off`. The setting is kept in `aprs.conf`, so it survives a
restart. The digipeater also needs transmit on, and it repeats nothing while transmit is off.

## Before you start

- The TNC must be in KISS mode, a plain framing that carries packets between a TNC and a computer.
  Set it with `d750 tnc kiss B` (mode 2 on band B), or from the [rig screen](d750ctrl.md) with the
  letter `t`. `d750 fixup` keeps it that way after a power cycle.
- The radio's USB layout that works is menu 983 on USB (Main Unit) and menu 984 on USB (Panel). In
  KISS mode, KISS frames arrive on the base unit's USB port, which the udev rule names
  `/dev/d750-tnc` (USB id 2166:9032), and CAT keeps answering on the control head's port,
  `/dev/d750-cat`. With menu 984 on USB (Main Unit) and the TNC in KISS mode, CAT moved to the base
  unit's port and the control head's port stopped answering, so do not use that layout. See [Radio
  setup](radio-setup.md).
- In KISS mode the radio's own APRS screen is off.
- Never run the TNC with the data band's squelch wide open (level 0) while menu 508 is on Busy: the
  TNC will not transmit. `d750 doctor` checks it.
- Keep transmitting handhelds away from the USB leads. A bus reset takes the radio and everything
  else on it.
- `python3` with the `pyserial` module installed. d750-aprs is plain Python and needs nothing else.
- A settings file. `install.sh` writes `~/.config/d750ctrl/aprs.conf` from `aprs.conf.example` if
  there is none, readable by you only, because it holds your exact position and a passcode. If you
  did not run `install.sh`, do the same by hand:

```sh
cp aprs.conf.example ~/.config/d750ctrl/aprs.conf
chmod 600 ~/.config/d750ctrl/aprs.conf
```

- Set at least `call`, `lat` and `lon` (see Settings below). Without a position there is no beacon.
- d750-aprs reads `aprs.conf` when it starts. After you edit it, restart the service. The
  subcommands `transmit`, `digi` and `igate` change their own lines in the file for you and tell the
  running daemon at once.

## Try it

Nothing in this section transmits, as long as transmit is still off.

Start following the plain lines, and press Ctrl+C to stop:

```sh
d750-aprs listen
```

It prints "Following" and the log file's name, and then each new line as it arrives. Each line
starts with the time (HH:MM), then the call sign first, then what the packet says. A position line
gives the distance and direction from your home position, the speed, the status or comment, and
whether the packet was heard direct or through a digipeater. The line "Our beacon, repeated via" and
a digipeater's call confirms that your beacon reached a digipeater.

Read back today's last lines, only those that mention a word:

```sh
d750-aprs last 20 W7XYZ
```

The first line says how many of today's lines matched. The lines follow.

Ask the daemon how it is:

```sh
d750-aprs status
```

The reply is one line. It names your call and says whether the TNC is connected, whether
transmitting is on or off, how many packets it has heard, how many KISS programs are connected, how
many messages are waiting, whether the iGate is on and logged in, and the digipeater state.

Queue a message. It waits, because transmit is off:

```sh
d750-aprs send W7XYZ "Meet at the food carts"
```

The reply says the message was queued with a number. The log says it waits until transmitting is on.
Turn transmit on only when you mean to send it.

## What it can do

### Subcommands

These are the subcommands, from `d750-aprs help`:

```text
d750-aprs: APRS through the TM-D750's TNC in KISS mode.
  d750-aprs daemon             run the daemon (the user service does this)
  d750-aprs listen             follow packets as plain lines; Ctrl+C stops
  d750-aprs last [N] [TEXT]    the last N lines of today's log (20), only those with TEXT
  d750-aprs status             the daemon's state
  d750-aprs beacon             send the home beacon now
  d750-aprs announce           send the status message (status in aprs.conf) now; it also goes every 6 hours
  d750-aprs transmit on|off    allow or stop every transmission: beacons, messages, acks, KISS programs
  d750-aprs igate on|off       pass what the radio hears to APRS-IS (receive-only; needs aprsis_pass)
  d750-aprs digi off|fillin|wide   repeat APRS packets: fillin for WIDE1-1 and our call, wide also WIDEn-N
  d750-aprs send CALL TEXT     send an APRS message, retried until acknowledged
Settings: ~/.config/d750ctrl/aprs.conf. Logs: ~/.local/share/d750ctrl/log/aprs-DATE.txt.
```

Running `d750-aprs` with no arguments, or with anything it does not know, prints the same text.

- `transmit`, `digi` and `igate` save the new value in `aprs.conf` first and then tell the daemon.
  If the daemon is not running, the value is still saved, and the command says "The d750-aprs daemon
  is not running" and how to start it.
- `beacon` sends the home beacon now. It needs `lat` and `lon`, and it needs transmit on.
- `last N TEXT`: N is the first argument when it is a number. Any other words are the text to find,
  without regard to case.
- `listen` follows today's log, and moves on to the next day's file at midnight.

### Listening: the plain lines

The daemon says every packet the radio decodes as one line in
`~/.local/share/d750ctrl/log/aprs-DATE.txt`, where DATE is the day, as `YYYY-MM-DD`. Times are your
local time. A line gives the call first, then what the packet says in words:

- positions: distance and direction from your home position (in miles, or kilometers when
  `units = km`), speed and direction, status, weather, and the comment;
- statuses, objects, weather reports, telemetry and messages to other stations;
- the way it was heard: direct, or "via" the last digipeater that repeated it;
- "Our beacon, repeated via CALL" when a digipeater repeated your own beacon. Your own packets heard
  direct is not logged, because the radio does not hear itself.

A second file, `aprs-DATE.raw`, holds the packets in the usual one-line text form
(`CALL>DEST,PATH:info`), marked RX, TX, IS and so on. This is the file to read when you need the
exact packet.

A message addressed to your call (with or without an SSID) is logged as "Message from CALL: text"
and is not shown as an ordinary line.

### The beacon

d750-aprs beacons your home position on a timer, `interval` minutes (30 by default, never less than
10), with the path from `path`. A beacon never goes out within 20 seconds of the daemon starting,
and the time of the last one is kept in a state file, so a restart keeps the schedule. The beacon
needs `lat` and `lon` and needs transmit on. The log says "Beacon sent" when it goes.
`d750-aprs beacon` sends one now.

### Messages

- `d750-aprs send CALL TEXT` queues an APRS message. It is sent with retries until the other station
  acknowledges it. There are 5 tries, the first at once, and each wait is twice the one before,
  starting at 30 seconds. After 5 tries it gives up, logs "was not acknowledged after 5 tries", and
  sends a notice (see below).
- A message waits in the queue while transmit is off. It does not fail while it waits.
- Messages longer than 67 characters go in parts, split between words. Each part has its own message
  number. The characters `|`, `~` and `{` are replaced, because APRS keeps them for itself, and
  control characters are dropped.
- Messages for your call are acknowledged automatically. A message already seen in the last 30
  minutes is not logged again, but is acknowledged again.
- Every message event, in and out, is written to `~/.local/share/d750ctrl/log/messages.jsonl`, which
  [aprschat](aprschat.md) reads. With the iGate on, messages for your call sent through the internet
  (from aprs.fi, for one) also arrive, and are acknowledged back through the internet.

### Receive-only iGate

An iGate passes packets heard on the air to APRS-IS, the internet network that APRS stations feed.
`d750-aprs igate on` makes your station a receive-only iGate:

- It passes what the radio hears to APRS-IS, marked `qAR` with your call.
- It skips packets marked NOGATE, RFONLY, TCPIP or TCPXX, empty packets, queries, third-party
  packets, and a packet it already passed in the last 30 seconds.
- It never transmits anything it gets from the internet.
- It needs your APRS-IS passcode in `aprsis_pass`. If it is empty, the log says the iGate is on but
  nothing is gated. If APRS-IS does not accept the passcode, the log says so and it tries again in
  30 minutes.
- Turn it off with `d750-aprs igate off`. The server is `aprsis_server`, `noam.aprs2.net:14580` by
  default. The daemon logs in with a filter that brings back only messages addressed to your call.
- The daemon says "iGate on" in the log with the server's name when it is logged in, and "Lost
  APRS-IS" when the link drops. It tries again, waiting longer each time, up to ten minutes.

### Fill-in digipeater

A digipeater repeats packets it hears so that others farther away can hear them.

- `d750-aprs digi fillin` repeats packets whose next hop is WIDE1-1, your call, or one of the names
  in `digi_aliases`.
- `d750-aprs digi wide` also repeats WIDEn-N up to `digi_max_hops` (2 by default). It puts your call
  in the path and takes one off N.
- It repeats only APRS packets. It never repeats one it has repeated, or heard repeated, in the last
  `digi_dupe` seconds (30 by default). It never repeats your own packets, never repeats anything
  while transmit is off, and repeats at most 20 packets a minute. It says in the log when it hits
  that limit, and skips packets until the minute is over.
- `digi_viscous` waits that many seconds before a fill-in repeat and drops it if another digipeater
  repeats it first. 0 repeats at once.
- `d750-aprs digi off` turns it off.
- A home station is usually a fill-in digipeater. Ask the local APRS group before running wide.

### The beacon watch

After each beacon on the air, the daemon watches APRS-IS for 60 seconds and says which iGate carried
it. This is the setting `aprsis_beacon`:

- `fallback` (the default): watch, and if no iGate carried the beacon, send it to APRS-IS directly
  (this needs the iGate logged in).
- `watch`: watch only.
- `on`: always send the beacon to APRS-IS directly as well.
- `off`: do neither.

The watch is a separate, read-only connection that needs no passcode. It runs whenever
`aprsis_beacon` is `watch` or `fallback`, even with the iGate off, so set `aprsis_beacon = off` if
you want no internet connection at all. The radio never hears its own beacon, so the iGate cannot be
the one that carries it.

### The status message

`status` in `aprs.conf` is a short line (up to 62 characters) about the station, such as "Fill-in
digipeater and RX iGate". It goes out every `status_interval` minutes (360, which is 6 hours, by
default, and never less than 30), on the air and straight to APRS-IS, so aprs.fi shows what the
station is. Leave `status` empty to send none. `d750-aprs announce` sends it now.

### Sharing the TNC with other programs

d750-aprs shares the TNC on KISS TCP port 8001 (`kiss_listen`), so YAAC, Xastir, APRSIS32 or Pat can
use it too. Frames that those programs send are transmitted only while transmit is on, and are held
back, and logged as held back, while it is off. A quick port check on 8001, with nothing sent, is
not logged.

### Watching it from outside

- Uptime Kuma, a self-hosted monitor, can watch the daemon. If the files
  `~/.config/kuma-push-url-aprs-tnc`, `-igate`, `-heard` and `-beacon` exist (each holding a Kuma
  push URL), d750-aprs pushes every 5 minutes while it holds the TNC and while the iGate is logged
  in, when it hears a packet, and when an iGate carries its beacon. It pushes nothing for a file
  that is not there.
- With `notify = on`, it posts through the `notify` command (one of the [station
  tools](station-tools.md)): APRS messages for this station go to the `notify_topic` (aprs), a
  message that failed after 5 tries goes there too, and the restart notices below go to the alerts
  topic.

### The radio switched off

The radio switched off, at night for one, is a normal state: both of its USB devices are gone.
d750-aprs then keeps its Kuma monitors (TNC, heard, beacon) up with "radio off since HH:MM" instead
of letting them go down, and sends no alert. Only a return within 3 minutes counts as a restart. A
longer absence is logged as "The radio is back after N minutes off".

### After a restart

After a restart, d750-aprs says only what it knows. When the TNC's port drops and comes back within
3 minutes, the radio restarted by itself. The log says so, and these notices go out on ntfy (a push
notification service) when `notify` is on:

- "TM-D750 restarted, 11:39", priority 3: "Restart 6 today. 3 h 4 min after the last one. TNC reset
  follows." It gives the day's count and the time since the last restart. The count and the time are
  kept in the state file `~/.local/state/d750ctrl/aprs.json`. Two drops within 2 minutes are one
  restart and one notice.
- "TM-D750 hearing again, 11:52", priority 2, for the first packet the TNC hears after the restart:
  "First packet 13 min after the 11:39 restart."
- "TM-D750 has heard nothing since 11:39", priority 4, when nothing is heard for `deaf_minutes` (90;
  0 turns it off): "90 min since it restarted. Check the radio." This is sent once for a restart,
  and not while the radio is switched off.
- "TM-D750 beacon carried by NAME, 11:42", priority 2, the first time an iGate carries the beacon
  after a restart.

After every return, whether the radio was switched on or restarted, d750-aprs resets the TNC 2
minutes later (TN 0,1, then TN 2,1, and the KISS settings) without waiting for any test. d750d
reopens its port up to about 45 seconds after the radio is back, so if the radio does not confirm
the reset, d750-aprs tries once more a minute later, and the log says whether it was confirmed.
Then, with `restart_check = on`, it sends one check beacon. An iGate carrying that beacon is good
news. None carrying it is usual at this station, and is one line in the log, never an alarm, a reset
or a power cycle.

d750-aprs also sends the KISS settings (TX delay, persistence and slot time) every time it connects
to the TNC. After the radio restarts by itself, its TNC may take commands but send nothing until
these are set again. On November 11, 2026, a power cycle did not clear that; sending the settings
did.

### Why it cannot know whether the radio transmits

The radio does not tell d750-aprs whether a packet went out. The radio never hears its own beacon,
and an iGate carries your beacon only now and then, so a beacon that nobody carried proves nothing.
On November 11, 2026, the radio restarted while receiving a long frame and came back receiving but
not transmitting, with nothing on its display to say so, until it was switched off and on. d750-aprs
cannot tell that from here. It says when the radio restarts and whether it hears again, and leaves
transmitting to a real check. The setting `power_cycle_cmd` is kept for such a check, but nothing
runs it now. See [d750-power and the relay](power-relay.md).

### Its service

The daemon runs as a systemd user service, so that it starts for you and restarts if it fails. The
file `d750-aprs.service.in` in the repository is the template: it runs `d750-aprs daemon` and
restarts it 15 seconds after a failure. `install.sh` links the `d750-aprs` command, writes this
service file from the template with the repository folder filled in, and writes `aprs.conf` from the
example if there is none, readable by you only. It does not start the service, because the daemon
can transmit. If the service already runs, it keeps running as it is. To turn APRS on:

1. Edit `~/.config/d750ctrl/aprs.conf`.
2. Run the service:

   ```sh
   systemctl --user enable --now d750-aprs.service
   ```

3. Nothing transmits until you run `d750-aprs transmit on`.

The commands `systemctl --user status d750-aprs` and `systemctl --user restart d750-aprs` check it
and restart it, and `journalctl --user -u d750-aprs` shows its output.

The daemon takes control commands on a Unix socket named `d750-aprs.sock` in your runtime folder
(`XDG_RUNTIME_DIR`, or `~/.cache` if it is not set), readable by you only.

## Settings

The file is `~/.config/d750ctrl/aprs.conf`. A new user needs to set these, and the [settings
page](settings.md) lists every one:

- `call`: your call sign with the SSID this station beacons as, for example `N0CALL-2`.
- `lat` and `lon`: your position in decimal degrees, north and east positive. For example, 45.5189
  and -122.6793 is an example position in downtown Portland, Oregon.
- `symbol` and `comment`: the APRS symbol (table, then code; `/-` is a house) and the beacon
  comment.
- `transmit`: off until you turn it on.
- `igate` and `aprsis_pass`: only if you want to be an iGate.
- `digi`: only if you want to be a digipeater.

A `#` in the file starts a comment, even in the middle of a line, so a `#` cannot be part of a
value. The file holds your position and passcode. When a subcommand changes a value in it, the
daemon rewrites the file so that only you can read it.

## When something goes wrong

- **You see:** "Held back, transmitting is off" in the log.
  - **Why:** transmit is off. That is the starting state.
  - **What to do:** run `d750-aprs transmit on` when you want it to transmit.

- **You see:** "No beacon: the home position is not set."
  - **Why:** `lat` and `lon` are empty.
  - **What to do:** set them in `aprs.conf` and restart the service.

- **You see:** "Not sent, the TNC is not connected".
  - **Why:** the daemon has no connection to `/dev/d750-tnc`.
  - **What to do:** check that the radio is on, the base unit's USB cable is in, and the udev rule
    is installed. `d750 doctor` helps.

- **You see:** "The TNC port /dev/d750-tnc is not there yet. Waiting for it", or "is not there: the
  radio is off".
  - **Why:** the radio is off or restarting, or the cable is out. The daemon checks again every 30
    seconds.
  - **What to do:** switch the radio on, or check the cable. See "The radio switched off".

- **You see:** "is not yours to open".
  - **Why:** your user does not own the port, because the udev rule is not installed for your user.
  - **What to do:** run `sudo ./install-udev.sh` and replug the cable.

- **You see:** "The iGate is on, but aprsis_pass is not set".
  - **Why:** the iGate needs your APRS-IS passcode.
  - **What to do:** set `aprsis_pass` and restart the service.

- **You see:** "APRS-IS did not verify the passcode".
  - **Why:** the passcode is wrong for the call in `call`.
  - **What to do:** check `aprsis_pass`. The daemon tries again every 30 minutes.

- **You see:** "The d750-aprs daemon is not running."
  - **Why:** the service is stopped.
  - **What to do:** `systemctl --user start d750-aprs`.

- **You see:** "Cannot share KISS on 127.0.0.1:8001".
  - **Why:** another program is using that port.
  - **What to do:** change `kiss_listen`, or stop the other program.

- **You see:** the TNC decodes far fewer packets than the squelch opens for.
  - **Why:** this is normal: most distant bursts never decode, while a nearby station decodes every
    time.
  - **What to do:** to tell "not decoding" from "not reaching the computer", put the TNC in APRS
    mode (`d750 tnc aprs B`) and turn menu 570 RX Beep to All: the radio beeps for each packet it
    decodes. Listen for many minutes, because the channel can be quiet for a long while. The data
    band's volume can stay all the way down, since the TNC decodes with the speaker silent (tested
    November 11, 2026), but the squelch must still open. Put the TNC back with `d750 tnc kiss B`.

- **You see:** packets as text lines in the d750d log, "APRS packet on the CAT port".
  - **Why:** the TNC is in APRS mode (TN 1,1), where each decoded packet arrives as one text line on
    the control head's port beside the CAT answers. d750d logs each as one line and drops it.
  - **What to do:** `d750-aprs` needs KISS mode. Run `d750 tnc kiss B`.

- **You see:** the TNC takes commands but the radio sends nothing.
  - **Why:** after the radio restarts by itself, the TNC's KISS settings may be lost.
  - **What to do:** d750-aprs sends them again on every connect and resets the TNC after every
    return. If it persists, switch the radio off and on.

## See also

- [aprschat: APRS messages from the terminal](aprschat.md)
- [d750d: the daemon](d750d.md)
- [d750: the verbs](d750.md)
- [d750-power and the relay](power-relay.md)
- [Settings reference](settings.md)
- [Station tools](station-tools.md)
- [Radio setup](radio-setup.md)
- [Troubleshooting](troubleshooting.md)
- [Glossary](glossary.md)
