# VARA, xara and chat: data and keyboard chat through the radio

## What it is for

VARA is a modem for sending data over radio. xara is a VARA-compatible modem, a separate program
that this project keys through [d750d](d750d.md). With it you can exchange frames and text with
other stations, and send a CQ or a beacon in the way VarAC stations expect. VarAC is a chat program
for VARA that many stations use. This page covers the `d750 vara` verbs, the VarAC CQ and beacon
frames, and how the rig screen opens a chat window. (See the [glossary](glossary.md) for PTT and the
other terms.)

xara itself, and any chat program, are not part of this project. xara has its own documentation and
settings file.

## About VARA, VarAC and this project

VARA is proprietary software. It is not free software, and it is not part of this project.
d750ctrl does not include VARA and does not need it. This project does not endorse VARA, and it is
not endorsed by VARA or by its author.

The `d750 vara` verbs talk to xara. xara is a separate program, written independently, that speaks
a protocol compatible with VARA's. It is not VARA, and it has its own license.

VarAC is a separate chat program by its own authors. This project only sends frames in the form
that VarAC stations expect. It is not connected with VarAC and is not endorsed by it.

The names VARA and VarAC belong to their owners. They are used here only to say what these tools
can talk to.

## Before you start

- xara is installed and set up on your computer, running as the systemd user service `xara.service`,
  with its settings in `~/.config/xara/xara.conf`. This project does not install it. The `d750 vara`
  verbs, and the `c` key on the rig screen, only work with that service. xara listens on its own
  ports; `d750 vara status` lists the ones among 8300, 8100 and 8310 that are open. The CQ and
  beacon frames go to port 8300.
- xara keys the radio through d750d's Hamlib port, `127.0.0.1:4532`. Point xara's PTT at that
  address; how to write that in `xara.conf` is in xara's own documentation. See [d750d](d750d.md)
  for what the port speaks.
- xara uses the radio's sound card, on the control head's USB socket, through the PipeWire or
  PulseAudio names you give in `xara.conf`.
- Set `mycall` in `~/.config/d750ctrl/d750ctrl.conf`. The CQ and beacon frames use it. Without it,
  `d750 vara cq` stops with "no mycall".
- `nc` (netcat) for `d750 vara cq` and `d750 vara beacon`.

## Try it

**`cq` and `beacon` transmit.** Always look at the dry run first. `-n` sends nothing:

```sh
d750 -n vara cq
```

```text
transmit band B at 144.390 MHz
would send one VarAC cq frame through xara: CQFRAME N0CALL
```

```sh
d750 -n vara beacon
```

```text
transmit band B at 144.390 MHz
would send one VarAC beacon frame through xara: CQFRAME N0CALL-9
```

(The frequency is the simulator's. On your radio it is the transmit band's frequency.)

Check xara's state:

```sh
d750 vara status
```

It prints whether xara is active, then the `fm`, `hf`, `ptt`, `ptt-lead-ms` and `drive-db` lines
that are set in `xara.conf`, the xara ports that are listening, and the last time the radio was
keyed.

Switch xara to VARA FM, which restarts xara:

```sh
d750 vara fm
```

It prints xara's own mode line from its log, when it has one, and then "xara: active".

## What it can do

### The d750 vara verbs

- `d750 vara fm` and `d750 vara hf`: set xara's mode. The command edits `xara.conf`, so that the
  chosen `fm` or `hf` line is active and the other is commented out, and restarts the xara service.
  It waits 4 seconds, then prints xara's mode line and its state. If `xara.conf` is missing or
  cannot be written, it stops with `Fail: no` and the path. With `-n` it only says what it would do.
- `d750 vara off`: stop xara.
- `d750 vara status`: as above.
- `d750 vara cq`: send one VarAC CQ frame. **This transmits.**
- `d750 vara beacon`: send one VarAC beacon frame. **This transmits.**

### The VarAC CQ and beacon frames

VarAC's CQ is a CQ frame carrying your call sign with no SSID. VarAC's beacon is the same frame with
SSID 9. There are no slots on VARA FM.

- The CQ frame is for calling any station that is listening.
- The beacon frame is the one VarAC uses for its beacon, which lets stations hear that you are on
  the air.

`d750 vara cq` and `d750 vara beacon` build the frame from `mycall`: the call is made upper case and
any SSID you wrote is dropped, so `mycall = N0CALL-7` gives `CQFRAME N0CALL`, and the beacon
`CQFRAME N0CALL-9`. The verb then:

1. reads which band transmits and its frequency, and prints them;
2. in a dry run, stops there;
3. stops with "xara is not running" if the service is not active;
4. sends the frame to xara's command port (8300) and prints xara's reply lines that mention PTT, OK
   or PENDING;
5. prints the last key and unkey lines from the d750d log, so you can see the radio keyed.

One frame goes out for each command. xara and the radio decide the timing, and d750d's 30-second
limit and the lock still apply. `d750 lock` stops xara from keying the radio.

On the [rig screen](d750ctrl.md), the letter `c` does the same, in the same format. It asks twice,
and the only key that sends is the last `y`. First `c` shows "Frame: c CQ, b beacon, n no". Press
`c` for a CQ or `b` for a beacon; any other key sends nothing. Then it asks "Send one CQ frame on
band B? y or n", or the same for a beacon, naming the transmit band. Only the small letter `y`
sends. Pressing `c` twice no longer sends: the second `c` only chooses the CQ. Both questions are
refused while PTT is locked ("PTT is locked. Nothing sent."), and the first is also refused while
`mycall` is empty or N0CALL ("Set mycall in the settings first."). In the list view the same
thing is the row "Send a CQ or beacon frame", done with Enter.

### Chat

A chat program is optional and your choice. The rig screen has two keys that open one in a window of
its own, if you have it:

- `x` opens a chat window. It starts a program named `xarachat` with `--tui`.
- `o` opens a VarAC chat window. What it runs depends on the `varac` setting in `d750ctrl.conf`:
  - `varac = xarachat` (the default value): the `xarachat` program with VarAC's framing on, run as
    `xarachat --tui --varac yes`;
  - `varac = openslot`: OpenSlot's terminal client, run as `openslot --tui`. OpenSlot is one chat
    program that the settings already support.
  - any other value acts like `xarachat`.
- xara takes one client at a time. `x` and `o` share one `xarachat` window: pressing the other
  letter jumps to the open window and tells you to type `/varac on` or `/varac off` there to switch.
- With `varac = openslot`, only `o` opens OpenSlot. The `x` key still starts a program named
  `xarachat`.
- A chat program's own quit key closes its window: F10 in xarachat, Ctrl+Q in openslot.

If the program you chose is not installed, its window closes right away, and nothing else is
affected. Radiograms, which many people send over a chat link, are covered on the [radiogram
page](radiogram.md).

## Settings

- In `~/.config/d750ctrl/d750ctrl.conf`: `mycall` (your call, for the CQ and beacon frames) and
  `varac` (what `o` opens: `xarachat`, the default, or `openslot`).
- In `~/.config/xara/xara.conf`, which is xara's own file: the lines that `d750 vara` reads and
  edits are `fm`, `hf`, `ptt`, `ptt-lead-ms` and `drive-db`.

See the [settings page](settings.md).

## When something goes wrong

- **You see:** "Fail: xara is not running".
  - **Why:** the xara service is stopped.
  - **What to do:** `systemctl --user start xara`.

- **You see:** "Xara does not answer on port 8300." on the rig screen.
  - **Why:** the frame could not be handed to xara's command port. The port in the message is
    `D750_XARA_PORT`, 8300 by default.
  - **What to do:** start xara, and check `d750 vara status`.

- **You see:** "Fail: no mycall in" your settings folder's file.
  - **Why:** `mycall` is not set.
  - **What to do:** add `mycall = YOURCALL` to `d750ctrl.conf`.

- **You see:** "xara gave no mode line yet" after `d750 vara fm` or `hf`.
  - **Why:** xara did not log its mode line within a few seconds, perhaps because it is waiting for
    the radio's sound card.
  - **What to do:** run `d750 vara status`, and look at `journalctl --user -u xara`.

- **You see:** the radio does not key when a frame is sent.
  - **Why:** d750d is locked, or xara's PTT is not pointed at port 4532.
  - **What to do:** `d750 unlock`, and check xara's PTT setting.

## See also

- [d750: the verbs](d750.md)
- [d750d: the daemon](d750d.md)
- [d750ctrl: the rig screen](d750ctrl.md)
- [radiogram](radiogram.md)
- [Settings reference](settings.md)
- [Glossary](glossary.md)
