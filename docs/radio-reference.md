# The TM-D750 from a computer: a reference

This page collects what is known about how the Kenwood TM-D750 looks and behaves to a computer:
its USB sockets, the command port, the commands, the TNC, the menus that matter, and the
surprises. It is a reference to dip into, not a guide to read in order. Every fact says where it
comes from, so you can weigh it.

For the short list of lessons the project learned the hard way, read [Radio notes](radio-notes.md)
first. For the cabling and menu settings to use, read [Radio setup](radio-setup.md).

## How to read this page

Every fact carries one of three labels, written exactly like this:

- Seen on the author's radio: from this project's own code, simulator, change log and old README.
  It was observed on one radio, which reports firmware 1.03, and may differ on yours.
- Reported by another project, not verified here: from a public project that was exercised on
  firmware 1.02 (type K,2,1). It is written here in this project's words, and nobody here has
  checked it.
- From the manual or the manufacturer's software: only where this project's own notes say a fact
  comes from there.

The other project is [kenwood](https://github.com/swiftraccoon/kenwood), a public project licensed
GPL-2.0-or-later. Its TM-D750 parts are a Rust library and a text shell. d750ctrl does not use
its code. Where the two projects disagree, the disagreement is stated in
[Radio notes](radio-notes.md), under "Where another project found differently".

Three more things to know:

- The project's tools never state your firmware version. The pretend radio (the simulator,
  `tests/d750-sim.py`) answers a made-up one for the tests. `d750 doctor` shows the one your radio
  reports.
- The pretend radio is written to answer the way the real radio was seen to answer for `ID`, `FV`,
  `TY`, `BC`, `FQ`, `MD`, `SQ`, `BY`, `TN`, `TX` and `RX`. For the other commands it follows a
  community command list for the TH-D74, a different Kenwood radio. Its answers are a guide, not
  evidence about your radio.
- Menu names and numbers are the ones the project's code and notes use. The wording on your radio
  may differ a little.

## The USB sockets and ports

The radio has two USB-C sockets, and each one shows up as its own device.

- The control head's socket has USB id 2166:9030. It carries the CAT serial port and the radio's
  sound card. It is also a charger. The udev rule names its serial port `/dev/d750-cat`. Seen on
  the author's radio.
- The base unit's socket has USB id 2166:9032. It carries serial ports only: two serial
  interfaces and no sound card. The udev rule names its port `/dev/d750-tnc`. Seen on the
  author's radio.
- CAT is the radio's command port: the computer reads and sets the radio over it. udev is the part
  of Linux that names devices. See the [glossary](glossary.md).

### Names and rules

- The rule file is `config/60-d750ctrl.rules`, installed by `install-udev.sh`. Its two rule lines
  match the two USB ids above, give the owner you name and the group `uucp`, and allow read and
  write for owner and group (mode 0660). Seen on the author's radio.
- Both sockets report the same product name and no serial number. The usual names under
  `/dev/serial/by-id` would collide, so the project names the ports by USB id instead. Seen on the
  author's radio.
- The numbers in names like `/dev/ttyACM1` change with plug order. The same port was seen as
  `ttyACM1` on one day and `ttyACM2` on another. Seen on the author's radio.
- `d750 doctor` prints the ids it finds with `lsusb -d 2166:`. The one ending in 9030 is the
  control head's, the one with the sound card. Seen on the author's radio.

### The sound card

- The sound card is mono, 48 kHz, 16-bit. It is on the control head's socket only. Seen on the
  author's radio.
- The sound server lists it with TM-D750 in its name. The verbs `d750 level` and `d750 record` find
  it by that word. Seen on the author's radio.
- When the radio was first plugged in, it became the computer's default speaker and microphone
  for a while. `d750 doctor` fails if the radio is the default sound output. Seen on the author's
  radio.

### Which menus decide where things come out

- Menu 980 sets what the USB socket offers. The author's notes record it as set so that the
  socket gives both a serial port and a sound card. From the manual or the manufacturer's
  software.
- Menus 983 and 984 choose which USB socket carries data. The layout that worked for the author
  is menu 983 on USB (Main Unit) and menu 984 on USB (Panel). With the TNC in KISS mode, the
  KISS frames then arrive on the base unit's port. With the TNC in APRS mode, each decoded packet
  arrives as a text line on the control head's port, beside the CAT answers. Seen on the author's
  radio. Which of the two menus is the KISS one is not settled; see [Menus that
  matter](#menus-that-matter).
- Menu 403 and menu 982 decide whether GPS sentences are sent to the computer. See [Menus that
  matter](#menus-that-matter).

### Radio off, restarts and bus resets

- With the radio switched off, both USB devices are gone. d750-aprs uses that to tell "off" from
  "restarted". Seen on the author's radio.
- A handheld radio transmitting close to the USB cables reset the USB bus once. The radio and
  other devices on that bus dropped and came back. Seen on the author's radio.
- The control head's socket is a charger, so a plain cable fed power into the computer. The
  author used a data-only adapter or a powered hub between that socket and the computer. Seen on
  the author's radio.

### Other sockets and links

- Every typed CAT read worked over both the main unit's USB socket and the operation panel's USB
  socket, and over native Bluetooth on a Mac. That project's words for the two sockets are "main
  unit" and "operation panel". Reported by another project, not verified here.
- The radio's Bluetooth offers a serial profile (SPP) and a headset profile (HSP). The serial one
  can carry KISS and GPS data. The headset one carries narrow, compressed voice audio. From the
  manual or the manufacturer's software.
- Over Bluetooth, the author's computer found the radio's serial channel by trial. The first
  connection after an idle spell failed with "Host is down", and the second, a few seconds later,
  worked. Seen on the author's radio.
- Reported by another project, not verified here: over Bluetooth the radio holds the first reply
  of a connection that was opened within about five seconds of the previous one.

## Talking to it

### The serial line

- d750d opens `/dev/d750-cat` at 9600 baud and sets nothing else except short time-outs: half a
  second to read and half a second to write. The rest of the line settings are the serial
  library's defaults. Seen on the author's radio.
- 57600 baud also worked in an early test. Seen on the author's radio.
- Only one program should open the CAT port. d750d is that program. Other programs talk to the
  radio through d750d: port 4532 speaks Hamlib's NET rigctl protocol, and port 4533 takes one
  Kenwood command per line. See [d750d](d750d.md).
- Reported by another project, not verified here: it opens the port at 9600 baud with a preset
  for the RTS/CTS, DTR and RTS lines, and treats 9600 as the validated speed.

### One command per line

- A command is two letters, then a space, then arguments separated by commas. A bare read has no
  arguments (`ID`, `BC`, `TN`). A read of one band or channel has one (`FQ 0`, `ME 005`). A set
  carries the new value (`FQ 0,0146520000`). Seen on the author's radio.
- Bands are numbered: 0 is band A and 1 is band B. Seen on the author's radio.
- Each command ends with a carriage return. d750d writes the command and the return, then reads
  up to the next return, at most 512 bytes. Seen on the author's radio.

### How answers look

- An answer is one line: the two command letters, a space, then the values separated by commas.
  `FQ 0` is answered like `FQ 0,0146520000`. A set is answered with the new state, which is an
  echo of what was asked. Seen on the author's radio.
- The routing in d750d treats an answer that only repeats the line as an action, and logs it.
  Seen on the author's radio.
- Memory channels are numbered with three digits (`ME 005`). Frequencies in `FQ` have ten digits
  and are in hertz. Seen on the author's radio.

### What N and ? mean

- `?` means the radio does not know the command. The probe reports it as "unknown to the radio".
  The first time the author ran the probe, 51 commands answered and 22 were unknown. The probe's
  list has 73 lines, and the notes do not say which 22 were unknown. Seen on the author's radio.
- `N` means the radio knew the command and refused it or had nothing to give. Seen on the
  author's radio: any mode code above 3 was answered `N`. The pretend radio also uses `N` for a
  set outside the allowed range, for a recall when the band is not in memory mode, and for a
  memory channel that holds nothing.
- An empty answer means no answer in time. d750d reports it as "no answer from the radio".
  Seen on the author's radio.
- d750d and the d750 verbs treat `N`, `?` and an empty answer as a refusal. Seen on the author's
  radio.
- Reported by another project, not verified here: `?` is a rejection and `N` is "not available".
  On firmware 1.02, after a `?`, the radio sends the repeated reply again for the next two
  commands, so a program has to discard those repeats.

### Lines the radio sends by itself

- With the TNC in APRS mode, every packet it decodes comes out on the CAT port as a text line,
  `CALL>DEST,PATH:INFO`, sometimes just ahead of a command's answer. d750d recognizes these
  lines, logs each as "APRS packet on the CAT port", and reads on for the real answer, up to
  three lines. Seen on the author's radio.
- With the GPS output on, a stream of NMEA lines such as `$GPGGA,...` comes out on the CAT port.
  It slowed every command to seconds. Seen on the author's radio.
- Before each command d750d reads whatever is already waiting, counts it, and discards it. Seen
  on the author's radio.

### Try it by hand

This sends one read to the radio through d750d, and shows that keying is refused on port 4533.
The output was captured against the pretend radio.

```sh
d750 raw ID
d750 raw TX
```

```text
ID TM-D750
ERR TX is not allowed on this port
```

Keying goes through port 4532. d750d judges a line on port 4533 by its first two characters, so `TX0`
is refused as `TX` is, and it refuses a line with any character but letters, digits, spaces and
`, . - / +`. See [d750d](d750d.md#port-4533-the-plain-command-port).

## The commands

This is every CAT command the project uses or has probed. The two letters come first. Where a
meaning comes from the community list for the TH-D74, it is a guide: that list is for a different
radio, and `d750 probe` shows what yours answers. See [d750](d750.md) for the verbs built on these
commands.

### Identity

- `ID` reads the model name. The answer is `ID TM-D750`. d750d asks it first at start-up, and
  `d750 doctor` and `d750 fixup` use it to prove the right radio is on the port. Seen on the
  author's radio.
- `ID` proves the model. A USB id only selects a candidate port. Reported by another project, not
  verified here.
- `FV` reads the firmware version and `TY` reads the radio type. `d750 doctor` prints both as
  "radio firmware ..., type ...". If the radio keeps them to itself, doctor says so and does not
  fail. Seen on the author's radio.
- The meaning of the three parts of a `TY` answer is not known. Reported by another project, not
  verified here.
- `AE` is listed in the probe as serial number and model. The pretend radio answers it as the
  model, a comma, and a serial number. The notes do not say what the real radio answered. Seen on
  the author's radio.

### Frequency and mode

- `FQ band` reads a band's frequency, and `FQ band,hz` sets it. The frequency has ten digits in
  hertz, for example `FQ 0,0146520000`. The radio answers with the same form. Seen on the
  author's radio.
- The pretend radio answers `N` to a frequency outside 118 to 524 MHz. The notes do not say the
  real radio does the same. Seen on the author's radio, as far as the simulator goes.
- A frequency outside a band's receive ranges is not refused: the radio tunes a nearby in-range
  frequency, so the answer differs from the request. Reported by another project, not verified
  here.
- `MD band` reads a band's mode and `MD band,code` sets it. The codes are 0 FM, 1 NFM, 2 AM and
  3 DV in d750ctrl. See [Mode codes](#mode-codes), where the other project's table differs.
- `VM band` reads or sets whether the band is on a memory channel or the VFO. d750ctrl uses
  1 for memory and 0 for VFO. Seen on the author's radio.
- Reported by another project, not verified here: `VM band,3` selects the DR tuning mode, and the
  tuning modes are VFO, memory, CALL and DR.
- `BC` reads the control band and the transmit band, and sets them. The answer is like `BC 1,1`:
  the control band, a comma, the transmit band. `d750 band A` sends `BC 0,0`. Seen on the
  author's radio. Whether the second number really is the transmit band is disputed; see
  [Radio notes](radio-notes.md).
- `FO band` reads the band's VFO record: frequency, offset, steps, mode and more. The pretend
  radio answers with a record shaped like a memory record. The notes do not describe the real
  answer. Seen on the author's radio, as far as the simulator goes.
- Reported by another project, not verified here: `FO` can replace a band's whole VFO record in
  one write. In CALL tuning mode `FO` reads the stored CALL channel, and a write of `MD` or `FO`
  is answered `N`. In DR mode `FO` reports the selected repeater.
- `SF`, `FS` and `FT` are asked by the probe: receive step size, fine step and fine tuning, from
  the community list. The radio answered `SF`. Seen on the author's radio.
- The rig screen of d750ctrl offers tuning steps of 5, 6.25, 10, 12.5, 15, 20, 25, 50 and
  100 kHz. Seen on the author's radio.
- Reported by another project, not verified here: its step command accepts 1 to 100 kHz.

### Squelch and power

- `SQ band` reads the squelch level and `SQ band,level` sets it. The verbs and the rig screen use
  0 to 9. On the real radio, 0 (fully open) and 3 were set. The pretend radio refuses a level
  above 9. Seen on the author's radio.
- Reported by another project, not verified here: its command help gives the squelch range as
  0 to 31.
- `PC band` reads the output power and `PC band,code` sets it. d750ctrl names 0 high, 1 mid, 2 low
  and 3 EL. The radio answered the read when probed, but the notes do not record the real radio
  accepting a set to 3. Seen on the author's radio.
- Reported by another project, not verified here: it names three power levels only, high, medium
  and low.
- `RA band` is the attenuator and `SH band` is a filter cutoff, from the community list. Both
  were asked by the probe, and `RA` answered. Seen on the author's radio.

### Busy and signal

- `BY band` reads the squelch state of a band: `BY 1,1` is open (busy) and `BY 1,0` is closed.
  `d750 busy`, `d750 watch` and the rig screen use it. Seen on the author's radio.
- On one occasion `BY 1` read 0 while the squelch was fully open. Seen on the author's radio.
- `SM band` is the signal meter per band. d750d hands its raw value to Hamlib as RAWSTR and
  computes STRENGTH as the value minus 9, times 6. That is how d750d treats it, not a measured
  fact about the radio. An early note of the author's wondered whether the community list's `SM`
  was a squelch value rather than a meter, and the notes do not settle it. Seen on the author's
  radio.
- Reported by another project, not verified here: `SM` reads the S-meter.
- `BL` is the battery level in the community list for the handheld. The pretend radio answers
  it. Whether this mobile answers is shown by your probe. Seen on the author's radio, as far as
  the simulator goes.

### Memories

- `ME channel` reads one memory channel, for example `ME 000`. The answer has 23 comma-separated
  fields: the channel number first, then 22 more. Seen on the author's radio.
- The field names `d750 mem show` prints come from the community list: frequency, offset, step,
  transmit step, mode, fine, fine step, tone, CTCSS, DCS, CTCSS/DCS, reverse, odd split, shift,
  tone frequency, CTCSS frequency, DCS code, cross, URCALL, D-STAR squelch type, D-STAR squelch
  code, and lockout. The count of 23 was seen on the radio, and the names were taken on trust.
  Seen on the author's radio.
- A memory write sends the same record back, `ME channel,field,field,...`. `d750 mem import` plays
  back a file of such lines, and `d750 mem export` writes them. The pretend radio clears a channel
  with `ME channel,C`. Seen on the author's radio.
- A channel that holds nothing is answered `N`. Seen on the author's radio.
- `MR band,channel` recalls a channel on a band, and the pretend radio answers `MR` and the
  channel number. A plain `MR band` read when the band is not in memory mode is answered `N`.
  Seen on the author's radio.
- Reported by another project, not verified here: channels are 000 to 999, program-scan channels
  `L00` to `U49`, and the priority channel `Pri`. `ME Pri` and `MR band,Pri` are answered `N`, and
  the priority channel refuses writes over CAT. A stored channel reads back as written, except
  that an empty URCALL becomes CQCQCQ. A CAT store keeps a channel's name, a clear erases it,
  and names are not part of the CAT record at all.
- The radio holds 1000 memory channels, 0 to 999, in 30 groups, with names of up to 16
  characters. The project's notes cite the user manual for this. From the manual or the
  manufacturer's software.
- Reported by another project, not verified here: a CAT store resets a channel's group to the
  hundreds digit of its number.

### TNC

- `TN` reads the TNC mode and data band: the mode, a comma, the band. The mode is 0 off, 1 APRS or
  2 KISS. `TN 2,1` is KISS on band B. `d750 tnc` and the rig screen set it. Seen on the author's
  radio.
- `TN 0,1` and `TN 2,1` sent one after the other make a TNC reset. See [The TNC](#the-tnc).
  Seen on the author's radio.
- `AS` is listed as the TNC baud rate and `DS` as a D-STAR callsign slot. Both answered when
  probed, and the notes say their meaning was unknown. Seen on the author's radio.
- `BE` is listed as the APRS beacon and `PT` as beacon control. An earlier version of the probe
  sent `BE` bare. The probe no longer sends it, and d750d refuses it on the command port, because
  of the report in the next item. Seen on the author's radio.
- Reported by another project, not verified here: `BE` transmits one APRS beacon when the TNC is
  in APRS mode and the beacon method is manual, and it is answered `N` while the TNC is off. In
  APRS mode with the automatic or SmartBeaconing methods, the radio beacons by itself.
- Reported by another project, not verified here: `TN 2,0` is KISS on band A and `TN 2,1` is KISS
  on band B, as the user manual says.
- While PTT is locked, d750d refuses `TN` with a mode other than 0, `PT` with any value, and `VX`
  with any value but 0, since each can let the radio send by itself. The reads still pass, and so
  do `TN 0,1` and `VX 0`. See [What lock covers](d750d.md#what-lock-covers-and-what-it-does-not).

### GPS

- `GP` reads the GPS state: `GP 1,0` is GPS on with the PC output off. `GP 1,1` turns the PC
  output on and a stream of NMEA sentences starts on the CAT port. `d750 gps` reads it, and
  `d750 gps output off` and `d750 fixup` write the second number back to 0. Seen on the author's
  radio.
- `GP` reports whether the GPS is on and where its output goes. It does not report a position.
  Seen on the author's radio.
- `GS`, `GM` and `MS` are listed as GPS sentence, "radio or GPS" and my position. They are asked
  by the probe only. Seen on the author's radio.
- Reported by another project, not verified here: the radio sends the sentences it was told to
  send to the interface that Menu 982 names, and the sentences can be GGA, GLL, GSA, GSV, RMC and
  VTG. The APRS position source can be the GPS or one of five stored positions.

### Clock

- `RT` reads the radio clock as twelve digits, year, month, day, hour, minute, second, like
  `RT 261117184825`. `RT` and the same twelve digits set it. `d750 clock set` and the `k` key on
  the rig screen set it from the computer. The author's radio clock was eight minutes off when
  first read. Seen on the author's radio.

### VOX

- `VX` reads VOX: 0 is off. `VX 0` and `VX 1` set it. `VD` reads the VOX delay and `VG` the VOX
  gain. All three answered when probed. `d750 vox` shows all three. The notes do not state the
  units of `VD` and `VG`. Seen on the author's radio.
- Reported by another project, not verified here: the delay is in milliseconds and the gain is 0
  to 9. A `VX` write sent at once after another command is refused, so it waits a moment before
  returning.

### Keying and the commands never sent

- `TX` keys the radio and `RX` releases it. The radio answers `TX 1` and `RX`. d750d sends them
  only on port 4532, from a Hamlib `T 1` or `T 0`, and refuses them on port 4533. Seen on the
  author's radio.
- Key and unkey took about 30 milliseconds each. Seen on the author's radio.
- Reported by another project, not verified here: `TX` keys the PTT band, which it takes to be the
  second number of `BC`, and the radio transmits until `RX`, its time-out timer, or power loss.
- d750d and the probe never send these. d750d refuses them on port 4533, and the probe lists
  them without sending:
  - `UP` and `DW`, the microphone up and down keys.
  - `SR`, which resets the radio.
  - `PS`, which powers the radio off.
  - `0M`, programming mode. See [Programming mode](#programming-mode).
  - `0G`, which the code calls service mode.
- Reported by another project, not verified here: the radio acknowledges `UP` and `DW` before the
  step is applied, a second step within about 15 ms is dropped, and a setting write within about
  20 ms of the acknowledgement is refused. Its `PS 0` powers the radio off, and no reply to it
  has been read from a radio.
- Reported by another project, not verified here: the `BE` beacon and `TX` are both transmissions.
  For that reason `BE` is on the list of commands the probe never sends and d750d refuses on the
  command port.

### Callsigns, D-STAR, display and the rest

These are in the probe's list, with the meaning the community list gives. The notes do not say
which ones your radio answers; the probe's table does.

- `CS` is the callsign, `DC` is the D-STAR slot with callsign and message, and `DS` is the slot
  selection. `DS` answered when probed. Seen on the author's radio.
- Reported by another project, not verified here: `CS` is the APRS My Callsign, `DC` is one of six
  ordinary MY callsign slots (a callsign of up to eight characters and a memo of up to four), and
  `DS` selects the slot. A separate list, the DV Gateway MY list, is not reachable over CAT.
- `DL` is dual or single display, and it answered when probed. `LC` is the display light, and it
  answered. Seen on the author's radio.
- `BT` is Bluetooth, `BS` is bar antenna, `FR` is FM broadcast radio, `IO` is IF output mode and
  `AI` is auto information, all from the community list. They were asked by the probe only. Seen
  on the author's radio.
- Reported by another project, not verified here: Bluetooth can be switched on and off, and the
  backlight value is 0 to 3.
- Reported by another project, not verified here: a read-only `GW` command reports the DV Gateway
  mode, 0 for off and 2 for Terminal. No CAT command selects it.

## Mode codes

- d750ctrl uses 0 FM, 1 NFM, 2 AM and 3 DV. The radio answers `N` to any code above 3. Seen on the
  author's radio.
- How it was found: on a weather broadcast, stepping band A through the codes by ear, code 1 gave
  the voice and code 3 went silent. Code 2 opened the squelch on noise, the way AM does. The
  listening test is the `mode-listen` tool in the `station` folder. Seen on the author's radio.
- The first guess in this project's history was 1 DV and 3 NFM, which is what the other project
  reports. It was changed after the listening test. Seen on the author's radio.
- DR is not reachable through `MD`. Seen on the author's radio.
- Reported by another project, not verified here: 0 FM, 1 DV, 2 AM and 3 NFM. Its source says that
  3 is the value the other four names left over for NFM, and that the panel label for 3 was not
  read. It also reports code 4 while a band is in the DR tuning mode, an `MD band,4` write answered
  `N`, and codes 5 to 9 refused. Code 2 appeared by itself after tuning band B into the 118 MHz air
  band.
- d750d maps Hamlib's modes to the same codes d750ctrl uses: FM to 0, FMN to 1, AM to 2 and DSTAR
  to 3. Seen on the author's radio.
- What would settle it: read what the radio itself shows or announces for codes 1 and 3.

## The TNC

The TNC is the radio's built-in packet modem. KISS is a simple way for a TNC to hand packets to
a computer. See the [glossary](glossary.md).

### The two modes

- In KISS mode (`TN 2,1`), KISS frames arrive on the base unit's port, `/dev/d750-tnc`. CAT keeps
  answering on the control head's port. d750-aprs uses this. Seen on the author's radio.
- In APRS mode (`TN 1,1`), each decoded packet arrives as a text line on the control head's port,
  beside the CAT answers. d750d logs each as one line and drops it. Seen on the author's radio.
- In KISS mode, the radio's own APRS screen is off. `d750 fixup` keeps `TN` at 2,1 for that
  reason. Seen on the author's radio.
- With menu 984 on USB (Main Unit) and the TNC in KISS mode, CAT moved to the base unit's port and
  the control head's port stopped answering. Seen on the author's radio.
- The TNC can be put into KISS mode by CAT. The manual's key sequence is not needed. Seen on the
  author's radio.
- Sending the KISS exit frame (the bytes C0 FF C0) to the TNC took it out of KISS mode: `TN` then
  read 0,1. `TN 2,1` put it back. Seen on the author's radio.
- Reported by another project, not verified here: it selects the TNC on a data band with `TN`. KISS
  mode hands the TNC to the interface that Menu 984 selects. On the operation-panel socket, with
  Menu 984 on the main unit, selecting KISS made that socket re-enumerate before the radio
  replied, and the TNC then read off on the next connection.

### The KISS port

- d750-aprs opens `/dev/d750-tnc` at 9600 baud with DTR and RTS raised. The setting
  `tnc_lines = low` holds them low. The radio was not keyed by those lines in days of use. Seen on
  the author's radio.
- KISS over Bluetooth also reached the TNC. A status frame sent that way went out on the air.
  Seen on the author's radio.

### KISS timing settings

- d750-aprs sends four KISS commands to the TNC on every connect: TX delay, persistence, slot
  time and half duplex. The defaults are a TX delay of 30 (300 ms), persistence 255 and a slot
  time of 10 (100 ms). The settings are `kiss_txdelay`, `kiss_persist` and `kiss_slottime`; TX
  delay and slot time are in 10 ms units. Seen on the author's radio.

### After the radio restarts

- On November 11, 2026, after a restart, the TNC took commands but sent nothing until the KISS
  timing settings were sent again. A power cycle did not clear it that time. Sending the settings
  did. Seen on the author's radio.
- An earlier restart that day left the radio receiving but not transmitting, with nothing on the
  display to say so. A TNC reset did not help, and switching the radio off and on did. Seen on the
  author's radio.
- d750-aprs resets the TNC two minutes after the radio's port returns: `TN 0,1`, then `TN 2,1`,
  then the timing settings. If d750d does not confirm the reset, it tries once more a minute
  later. Seen on the author's radio.

### Decoding and transmitting

- The TNC decodes far fewer packets than the squelch opens for. Most distant bursts never decode,
  and a nearby station decodes every time. Seen on the author's radio.
- With the TNC in APRS mode and menu 570 RX Beep on All, the radio beeps for each packet it
  decodes. That tells "not decoding" from "not reaching the computer". Seen on the author's
  radio.
- The TNC decodes with the data band's volume all the way down. The squelch must still open. Seen
  on the author's radio.
- With menu 508 on Busy and the data band's squelch wide open, the TNC held a frame and did not
  transmit. With the squelch back at level 3, the same frame went out. Seen on the author's
  radio.
- The radio never hears its own beacon. Seen on the author's radio.

## Menus that matter

Each entry says what the menu must be, and why. The names are as the project's notes give them.

- Menu 403, GPS output to the PC: Off. GPS sentences on the CAT port slow every command to
  seconds. `d750 gps output off` and `d750 fixup` set the same thing by command. Seen on the
  author's radio.
- Menu 982: named by `d750 doctor` and `d750 fixup` as another possible source of data the radio
  sends on the CAT port without being asked. The author's early notes moved the GPS output away
  from the USB panel port with it. Seen on the author's radio.
- Reported by another project, not verified here: with the GPS PC output on (Menu 403), the radio
  sends the sentences to the interface Menu 982 names.
- Menu 983: USB (Main Unit), in the layout that worked. The example settings file ties KISS to it:
  "KISS comes out here with radio menu 983 on USB (Main Unit) and the TNC in KISS mode". Seen on
  the author's radio.
- Menu 984: USB (Panel), in the layout that worked. With 984 on USB (Main Unit) and the TNC in
  KISS mode, CAT moved to the base unit's port. Seen on the author's radio.
- Which of 983 and 984 is "the KISS menu" is not settled here. The author's notes from the manual
  call 984 the choice of USB (Main Unit), USB (Panel) or Bluetooth for KISS, and the other project
  says the same, but the layout that worked for the author put the KISS frames on the base unit's
  port with 984 on Panel and 983 on Main Unit. Menus 983 to 986 choose which socket carries data.
  From the manual or the manufacturer's software.
- Menu 508, DCD Sense: if it is on Busy, never run the TNC with the data band's squelch wide
  open, or the TNC will not transmit. `d750 doctor` fails when the data band's squelch is 0 with
  the TNC on. The author's notes say Detect Data would decouple the two and do not record trying
  it. Seen on the author's radio.
- Menu 570, RX Beep: All, to make the radio beep for each packet its TNC decodes. Use it with the
  TNC in APRS mode. Seen on the author's radio.
- Menu 913, USB Audio Out Level: the receive level sent to the computer, levels 1 to 7.
  `d750 level` tells you to lower it when it reads hot and says it could go up when quiet. The
  author measured, with the squelch open: level 7 clipped, and level 4 gave about -33 dBFS RMS,
  about 8 dB per step. Seen on the author's radio. From the manual or the manufacturer's
  software: the name and the range of levels.

Other menu numbers appear in the author's notes, not in the code. Each says where it comes from.

- Menu 981, USB Audio In/Out: Ext. Data for the flat data audio digital modes need, and AF for the
  filtered speaker and microphone path. From the manual or the manufacturer's software.
- Menu 988, Ext. Data Speed: 9600 bps for flat audio, and 1200 bps for the filtered path. With
  menu 981 on Ext. Data and menu 988 on 9600, open-squelch noise arrived at the computer with
  strong energy above 3 kHz, which is the flat audio wide modes need. Seen on the author's radio.
- Menu 987, Ext. Data Band: the band the external data path transmits on. From the manual or the
  manufacturer's software.
- Menus 505, 506, 508 and 509 are the TNC's data speed (1200 or 9600), data band (A or B), DCD
  sense and TX delay. From the manual or the manufacturer's software.
- Menus 150, 151 and 152 are VOX with its gain and delay. The notes use VOX On (Data) to key the
  radio from the data audio. From the manual or the manufacturer's software.
- Menu 934, Pairing Mode: the radio sat in it while it paired over Bluetooth. Seen on the author's
  radio.

## Timing and quirks

### Timing

- The radio keyed about 30 ms after a raw `TX` and unkeyed about 26 ms after a raw `RX`, over CAT.
  Seen on the author's radio.
- The pretend radio answers after 20 ms. d750d reads with a half-second time-out. Seen on the
  author's radio.
- d750d unkeys at start-up, when a client drops while keyed, on serial errors, and after 30
  seconds of keying. Seen on the author's radio.
- The rig screen used to poll about 29 commands a second and now polls about 10: it reads
  everything every 2 seconds and the busy flags of both bands every second. By default only the wide
  face reads the busy flags that often; the other views read them with the full read (see
  `live_meters` in [Settings](settings.md)). Seen on the author's radio.
- One early note records about 48 CAT commands a second from the screen and asks whether that hurt
  decoding. It was left open. Seen on the author's radio.
- The probe waits 0.05 seconds between commands. Seen on the author's radio.
- After the radio comes back on USB, d750d reopens its port up to about 45 seconds later. Seen on
  the author's radio.
- Reported by another project, not verified here: the radio acknowledges `UP` and `DW` within
  milliseconds, and the timings of dropped steps and refused writes are in the commands section
  above.

### Restarts

- The radio restarted by itself while receiving a long frame, and came back receiving but not
  transmitting until it was switched off and on. Seen on the author's radio.
- Later the radio restarted about every three hours for a stretch: from return to loss, three
  hours and about four minutes each time. Both USB devices dropped within 150 ms of each other
  and came back three and eleven seconds later. A command from the computer did not restart the
  clock, and the restarts were not tied to transmitting. The cause was not found. Seen on the
  author's radio.
- After a restart, hearing came back by itself once the TNC was reset. Seen on the author's radio.
- `BC` read 0,1 each time beacons failed to reach an iGate one evening. This was a suspicion, not
  a conclusion. Seen on the author's radio.

### Quirks

- Hamlib's own TH-D74 model (number 2042) reads the frequency but takes about 2.6 seconds to unkey
  and reports an error, because it waits for a reply form the radio does not give. The TM-D710
  model (2034) does not talk to this radio at all. The radio's own `RX` unkeys at once. That is why
  d750d keys with raw `TX` and `RX`. Seen on the author's radio.
- GPS sentences on the CAT port slowed an unkey to seconds. Seen on the author's radio.
- The first connection over Bluetooth after an idle spell failed, and the second worked. Seen on
  the author's radio.
- The radio's clock was eight minutes off when first read. Seen on the author's radio.
- On November 11, 2026, a restart showed nothing on the radio's display. Seen on the author's
  radio.
- A `?` answer is followed by a repeated reply on firmware 1.02. Reported by another project, not
  verified here.

## Programming mode

- The radio has a programming mode. The manufacturer's programming software uses it. From the
  manual or the manufacturer's software.
- d750ctrl does not use it. d750d refuses the command that enters it on port 4533, and the probe
  only lists it. Seen on the author's radio.
- `d750 mem export` and `d750 mem import` read and write memory channels with `ME` in normal
  operation. That is a different thing from programming mode. Seen on the author's radio.

## See also

- [Radio notes](radio-notes.md): the short list of lessons, and where another project found
  differently.
- [Radio setup](radio-setup.md): sockets, cables and menu settings.
- [d750d](d750d.md): the port daemon.
- [d750](d750.md): the verbs.
- [APRS](aprs.md): d750-aprs and the TNC.
- [Station tools](station-tools.md): including `mode-listen`, the listening test for mode codes.
- [Troubleshooting](troubleshooting.md): when something goes wrong.
- [Glossary](glossary.md): CAT, KISS, TNC and the rest.
