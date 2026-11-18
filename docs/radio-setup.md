# Radio setup: sockets, cables and menu settings

This page covers everything you do on the radio itself: which socket does what, how to cable it, and
which menu settings the project relies on. The menu numbers below are the ones the code and the
owner's notes name. They are stated as the code states them. Your radio's menu text may be worded a
little differently.

## The two USB sockets

The radio shows two USB serial ports. Each has its own socket and its own USB id.

- The control head's socket, id 2166:9030, is the CAT port. CAT is the command port: the computer
  reads and sets the radio over it. The udev rule names it `/dev/d750-cat`. The same socket carries
  the radio's sound card, which digital modes use. It is also a charger.
- The base unit's socket, id 2166:9032, is the TNC port. The TNC is the radio's built-in packet
  modem. The udev rule names it `/dev/d750-tnc`. d750-aprs reads it.

Both sockets may be connected at once. The udev rule, installed by `install-udev.sh`, names them
apart. See [Install](install.md).

### Which cable is which

You do not have to remember, and you do not have to see the sockets. The computer can tell you:

```sh
lsusb -d 2166:
ls -l /dev/d750-cat /dev/d750-tnc
```

The first command lists the radio's USB devices with their ids. The second shows which serial port
each name points at. The socket whose id ends in 9030 is the one with the sound card.

To find a cable by hand, unplug one and run the second command again. The name that is gone belongs
to the cable in your hand. If `/dev/d750-cat` is gone, that cable goes to the control head. Plug it
back in: d750d opens its port again by itself.

## Cabling

- Put a data-only USB adapter or a powered hub between the control head's socket and the computer.
  The socket is also a charger, so a plain cable is not the right link.
- Keep transmitting handhelds away from the USB leads. A bus reset takes the radio and everything
  else on that bus with it.
- The radio switched off, at night for one, is a normal state. Both its USB devices vanish and come
  back when it is switched on. d750d opens its port again by itself, up to about 45 seconds after
  the radio is back.
- Do not make the radio your computer's default sound output. `d750 doctor` reports that as a Fail.

## Menu settings

### The CAT port must carry only CAT

- Menu 403, the GPS output to the PC, must be Off. GPS sentences on the CAT port slow every command
  to seconds. You can also switch it off by command: `d750 gps output off`.
- `d750 doctor` and `d750 fixup` also name menu 982 as a possible source of data the radio sends on
  the CAT port without being asked. The code does not say what menu 982 controls. If doctor reports
  unsolicited bytes and menu 403 is already Off, look at menu 982.

### The TNC on USB

The layout that works, found on November 11, 2026, is menu 983 on USB (Main Unit) and menu 984 on
USB (Panel).

- With that layout and the TNC in KISS mode, KISS frames arrive on the base unit's port,
  `/dev/d750-tnc`, and CAT keeps answering on the control head's port. This is what d750-aprs uses.
- Do not set menu 984 to USB (Main Unit) with the TNC in KISS mode. CAT then moves to the base
  unit's port and the control head's port stops answering.
- The TNC mode is not a menu you must visit. `d750 tnc kiss B` sets it by command, and `d750 fixup`
  puts it back. In KISS mode the radio's own APRS screen is off.

### The data band's squelch and menu 508

- If menu 508 is on Busy, never run the TNC with the data band's squelch wide open. The squelch
  level 0 is wide open. The TNC will not transmit then. `d750 fixup` keeps the data band (band B)
  squelch at the level in its `fixup.conf`, 3 by default, and `d750 doctor` fails the check when it
  is 0.
- The data band's volume can stay all the way down. The TNC decodes with the speaker silent. The
  squelch must still open.

### Checking that the TNC decodes

- Menu 570, RX Beep, set to All makes the radio beep for each packet its TNC decodes. Use it with
  the TNC in APRS mode (`d750 tnc aprs`) to tell "the TNC is not decoding" from "the packets are not
  reaching the computer". Listen for many minutes; the channel can be quiet for a long while. Set it
  back afterwards, and put the TNC back in KISS mode with `d750 fixup`.

### Sound level

- Menu 913 is the one `d750 level` points to. It listens to the radio's sound card for a few seconds
  and says silence, clipping, hot, good or quiet. It tells you to lower menu 913 when the level is
  hot, and says menu 913 could go up when it is quiet. The code does not say more about what menu
  913 is called.

## Bluetooth

d750ctrl does not pair the radio. The only Bluetooth feature is a check. If you put the radio's
Bluetooth address in the `bluetooth` setting of `~/.config/d750ctrl/d750ctrl.conf`, `d750 doctor`
and `d750 fixup` ask your system whether it is paired, using the `bluetoothctl` command. Pair the
radio with your system's own tools first. Leave the setting empty if you do not pair; the checks are
then skipped with a note.

The code names no radio menu for Bluetooth. See [Settings](settings.md) for the setting.

## After the radio restarts by itself

A brownout or a reset can leave the TNC taking commands but sending nothing. [Radio
notes](radio-notes.md) records what happened and what d750-aprs does about it, and
[Troubleshooting](troubleshooting.md) says what to look for.

## See also

- [Quick start](quickstart.md)
- [Radio notes](radio-notes.md)
- [d750-aprs](aprs.md)
- [Settings](settings.md)
- [Troubleshooting](troubleshooting.md)
