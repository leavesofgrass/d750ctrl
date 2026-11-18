# Quick start: from a fresh clone to a working radio

This page takes you from nothing to `d750 status` answering, and then to the rig screen. Each step
says what you should see. If a step does not match, go to "If it did not work" at the end.

## Step 1: connect the radio

The TM-D750 has two USB-C sockets that matter here. They do different jobs.

- The control head's socket is the CAT port. CAT is the radio's command port: a serial line over
  which the computer reads and sets the radio. This is the port d750d, the daemon, opens. The same
  socket carries the radio's sound card for digital modes, and it is also a charger. Put a data-only
  USB adapter or a powered hub between it and the computer.
- The base unit's socket is a second serial port. d750-aprs uses it to talk to the radio's built-in
  TNC (the radio's own packet modem). You do not need it for this quick start.

Both sockets may be connected at once. The udev rule, installed in step 4, names them apart:
`/dev/d750-cat` for the control head and `/dev/d750-tnc` for the base unit.

Switch the radio on. See [Radio setup](radio-setup.md) for the radio's menu settings.

## Step 2: check that Python has pyserial

d750d needs the pyserial module. The service runs with the system Python in isolated mode, so check
it the same way:

```sh
/usr/bin/python3 -I -c "import serial"
```

You should see nothing at all. If you see ModuleNotFoundError, install pyserial first. The package
is python3-serial on Debian and Ubuntu, python3-pyserial on Fedora, and python-pyserial on Arch.
[Install](install.md) lists everything else.

## Step 3: get the code and run install.sh

```sh
git clone https://github.com/leavesofgrass/d750ctrl ~/d750ctrl
cd ~/d750ctrl
./install.sh YOURCALL
```

Replace YOURCALL with your call sign. If you leave it out, the script asks for it. It needs no root
and is safe to run twice.

You should see five numbered lines, then a last line that starts with Done:

1. The commands are linked into `~/.local/bin`.
2. d750d is active and running from your clone.
3. The Python environment for SSTV and RTTY is made, or is already present. The first time, this
   downloads packages and takes a minute.
4. The settings file is written to `~/.config/d750ctrl/d750ctrl.conf`, or kept if it exists.
5. The d750-aprs service is written, not started, and the APRS settings file is written to
   `~/.config/d750ctrl/aprs.conf`, or kept if it exists. APRS stays off until you turn it on; see
   [d750-aprs](aprs.md).

If a line starts with the word note and says `~/.local/bin` is not on your PATH, add that folder to
your PATH, then open a new terminal.

## Step 4: run install-udev.sh, once, with root

```sh
sudo ./install-udev.sh
```

You should see "1. rule installed for user" followed by your user name, then one line for
`/dev/d750-cat` and one for `/dev/d750-tnc`. A line that says a device is not present means no cable
is in that socket, or it needs replugging. d750d keeps trying, so you do not need to restart it.

## Step 5: run d750 doctor

```sh
d750 doctor
```

You should see one line per check. Each starts with Pass or Fail, and the last line counts them, in
the form "N pass, M fail". A line that starts with note is information, not a failure. See
[Troubleshooting](troubleshooting.md) for each Fail. A radio that is not yet paired over Bluetooth,
or a missing sound card, does not stop the next step.

## Step 6: run d750 status

```sh
d750 status
```

You should see four lines: one for band A, one for band B, one for the TNC and one for the daemon.
This is what the pretend radio prints, so yours will have your own numbers:

```text
band A: 147.040 MHz, FM, squelch 6, busy, power high
band B: 144.390 MHz, FM, squelch 3, quiet, power mid, transmits, control
tnc: KISS on band B
daemon: port open /dev/pts/0; not keyed; unlocked; last answer 18:48:19; unsolicited bytes seen 0
```

The words transmits and control mark the band that transmits and the band the controls act on. The
exit code is 0 for Pass, 1 for Fail and 2 for a usage mistake.

## Step 7: open the rig screen

```sh
d750ctrl
```

You should see both bands side by side, with the active band's frequency in large digits, a key bar
near the bottom, and a message line below it. Press the question mark for help and the letter q to
quit. If tmux is installed, the screen opens inside its own tmux session, and the bottom line lists
the tool windows you open. Details are on the [d750ctrl](d750ctrl.md) page.

## Your first five minutes

With the radio answering, try these in order. None of them transmits.

1. Change a frequency with a dry run first. `-n` shows what would be sent and changes nothing:

   ```sh
   d750 freq A 146.520 -n
   ```

   Run it again without `-n` to do it.
2. Watch a band for activity. This prints a line only when the squelch opens or closes:

   ```sh
   d750 watch B 30
   ```

3. Open the rig screen with `d750ctrl`, and leave it open while you listen.
4. Read `d750 help` for every verb. [Recipes](recipes.md) has short how-tos.

## If it did not work

- Start with `d750 doctor`, then `d750 log`. Both are described on the
  [Troubleshooting](troubleshooting.md) page.
- If `d750 status` says d750d is not answering, run `systemctl --user status d750d`.
- If `/dev/d750-cat` is missing, check the cable, the radio's power, and that you ran
  `install-udev.sh` with sudo.

## See also

- [Install](install.md)
- [Radio setup](radio-setup.md)
- [Recipes](recipes.md)
- [Try it without a radio](try-without-a-radio.md)
- [Troubleshooting](troubleshooting.md)
