# Radio notes: the TM-D750, as learned

These are hard-won facts about how the Kenwood TM-D750 behaves. They were found by using the radio,
and by listening to it. The dates are the days they were found. Several of them explain why a part
of d750ctrl works the way it does.

## The command dialect

The TM-D750 speaks the TH-D74 command dialect over USB: FQ, MD, SQ, BY, BC, PC, VM, MR, ME, FO, TN,
GP, RT, VX and more. `d750 probe` asks the radio, read only, which commands it answers, and lists
what your firmware answers.

## Three rules learned the hard way

- The CAT port must carry only CAT. Set menu 403 to Off, or run `d750 gps output off`. GPS sentences
  on the port slow every command to seconds.
- Never run the TNC with the data band's squelch wide open while menu 508 is on Busy. The TNC will
  not transmit.
- Keep transmitting handhelds away from the USB leads. A bus reset takes the radio and everything
  else on that bus with it.

## When the radio restarts by itself

- After the radio restarts by itself, its TNC may take commands but send nothing until the KISS
  settings are set again: TX delay, persistence and slot time. On November 11, 2026 a power cycle
  did not clear that. Sending those settings did. d750-aprs sends them every time it connects to the
  TNC, and resets the TNC (TN 0,1 then TN 2,1, with the settings again) after every return of its
  port.
- On November 11, 2026 the radio restarted while receiving a long frame and came back receiving but
  not transmitting, with nothing on its display to say so, until it was switched off and on.
  d750-aprs cannot tell that from the computer. An iGate carries this station's beacon only now and
  then, so a beacon nobody carried proves nothing. d750-aprs says when the radio restarts and
  whether it hears again, and leaves transmitting to a real check.

## Which command tells the transmit band

BC's second field is not the PTT band. It read 1 while the PTT stayed on band A, and it changed to 1
the moment the TNC transmitted on band B. d750d still takes it as the transmit band.

## The two USB serial ports

The radio shows two USB serial ports.

- The control head's port, USB id 2166:9030, comes with the sound card. It is the CAT port,
  `/dev/d750-cat`.
- The base unit's port, USB id 2166:9032, is `/dev/d750-tnc`.

The layout that works, found on November 11, 2026, is menu 983 on USB (Main Unit) and menu 984 on
USB (Panel).

### The TNC modes

- TNC in KISS mode (TN 2,1): KISS frames arrive on the base unit's port, `/dev/d750-tnc`, and CAT
  keeps answering on the control head's port. This is what d750-aprs uses.
- TNC in APRS mode (TN 1,1): each decoded packet arrives as one text line, CALL>DEST,PATH:INFO, on
  the control head's port beside the CAT answers. d750d logs each as one line, "APRS packet on the
  CAT port", and drops it.
- With menu 984 on USB (Main Unit) and the TNC in KISS mode, CAT moved to the base unit's port and
  the control head's port stopped answering.

### Serial lines and the radio's own APRS screen

d750-aprs opens the TNC port with DTR and RTS raised. The setting `tnc_lines = low` in its settings
holds them low. In KISS mode the radio's own APRS screen is off, so `d750 fixup` keeps TNC=2,1.

## Decoding

The TNC decodes far fewer packets than the squelch opens for. Most distant bursts never decode,
while a station nearby decodes every time.

To tell "not decoding" from "not reaching the computer", put the TNC in APRS mode with menu 570 RX
Beep on All. The radio then beeps for each packet it decodes. Listen for many minutes; the channel
can be quiet for a long while.

The data band's volume can stay all the way down. The TNC decodes with the speaker silent, tested on
November 11, 2026. The squelch must still open.

## Modes over MD

Modes over MD are 0 FM, 1 NFM, 2 AM and 3 DV. The radio refuses anything above 3, so DR is not
reachable this way.

## Hamlib's own radio model

Hamlib's TH-D74 model talks to this radio but takes seconds to unkey. That is why d750d keys with
the raw TX and RX commands, and offers Hamlib's protocol on its own port instead.

## Where another project found differently

A public project, [kenwood](https://github.com/swiftraccoon/kenwood), licensed GPL-2.0-or-later,
also talks to the TM-D750. It was exercised on firmware 1.02 (type K,2,1). Two of its findings
differ from what d750ctrl recorded. Each side and its evidence is stated below, and no more than
the evidence. Nothing from the other project has been checked on the radio used here. For the
full list of commands and how each fact is sourced, see the
[radio reference](radio-reference.md).

### Mode codes over MD

d750ctrl's table: 0 FM, 1 NFM, 2 AM and 3 DV.

- The evidence is a listening test. On a weather broadcast, with band A stepped through the
  codes, code 1 gave the voice and code 3 went silent. Code 2 opened the squelch on noise, the way
  AM does.
- The radio answers `N` to any code above 3.
- The first table in this project's history was 1 DV and 3 NFM. It was replaced the same day,
  after the listening test. The test is the `mode-listen` tool in the `station` folder.
- The notes here do not record reading the radio's own label for code 1 or code 3.

The other project's table: 0 FM, 1 DV, 2 AM and 3 NFM.

- Its source says codes 0 to 3 were each written and read back on band A, and that code 2 also
  appeared by itself after tuning band B into the 118 MHz air band.
- Its source says 3 was assigned as the value the other four names leave for NFM, and that the
  panel label for 3 was not read.
- It also reports code 4 while a band is in the DR tuning mode, with an `MD band,4` write
  answered `N`, and codes 5 to 9 answered `N`.

What would settle it: set a band to code 1, then to code 3, and read what the radio itself shows
or announces for each one.

### The second field of BC

d750ctrl's notes say the second field of `BC` is not always the transmit band.

- It read 1 while the PTT stayed on band A.
- It changed to 1 at the moment the TNC transmitted on band B.
- It also read 0,1 each time beacons failed to reach an iGate one evening. That was a suspicion,
  not a conclusion.
- d750d still takes the second field as the transmit band.

The other project treats the second field of the band control as the PTT band.

- Its `TX` keys the band that field names, and its `bands` word sets both fields.
- Its hardware table lists `TX` and `RX` on either PTT band as exercised.
- The documents saved for this comparison do not say how the transmitting band was observed.

The conditions differ. d750ctrl's observation was a transmission by the TNC. The other project's
statement is about the `TX` command.

### Also reported there, not verified here

- After a `?` answer, firmware 1.02 sends the repeated reply again for the next two commands.
- `FQ` outside a band's receive ranges tunes a nearby frequency instead of refusing.
- A `VX` write sent at once is refused, so it waits a moment before returning.
- `UP` and `DW` are acknowledged before the step is applied. A second step within about 15 ms is
  dropped, and a setting write within about 20 ms of the acknowledgement is refused.
- With menu 984 on the main unit, selecting KISS over the operation-panel socket re-enumerated
  that socket before the radio replied, and the TNC then read off on the next connection.
- `ME Pri` and `MR band,Pri` are answered `N`, and the priority channel refuses writes over CAT.
- `BE` is answered `N` while the TNC is off. In APRS mode with the automatic or SmartBeaconing
  methods the radio beacons by itself.
- In CALL tuning mode, `MD` and `FO` writes are answered `N`. DR is selected with `VM band,3`.
- Its command help gives the squelch range as 0 to 31, where d750ctrl uses 0 to 9. It names three
  power levels, where d750ctrl names four.
- Over native Bluetooth, the radio holds the first reply of a connection opened within about five
  seconds of the previous one.

### Recorded here, not established there

- KISS with the TNC. The other project's README lists "KISS mode over CAT" as not established.
  Here, `TN 2,1` was sent over CAT and the radio answered it. KISS frames then arrived on the
  base unit's USB port, a frame sent into that port went out on the air, and the exit frame took
  the TNC out of KISS mode. The layout and the timing settings it needs are in the
  [radio reference](radio-reference.md#the-tnc).
- GPS output on the CAT port. The other project's README says no capture of the radio's own NMEA
  output has been decoded yet. Here, the stream was seen on the real radio's CAT port, and it
  slowed every command to seconds. This project has not decoded it either.

## See also

- [The TM-D750 from a computer](radio-reference.md): ports, commands, menus and quirks, each fact
  marked with its source.
- [Radio setup](radio-setup.md)
- [Troubleshooting](troubleshooting.md)
- [d750d](d750d.md)
- [d750-aprs](aprs.md)
- [Glossary](glossary.md)
