# d750ctrl

Keyboard control of the Kenwood TM-D750 from a Linux box, over the radio's own USB serial port. One small
daemon owns the port; a command with plain verbs, a full screen rig control, and tools for VARA chat, NTS
radiograms, SSTV and RTTY sit on top of it. Python 3 and bash, nothing else to install for the core.

Written for a station where the computer is driven by keyboard and screen reader as much as by eye: every
verb prints one short line per fact, the answer first; the screen is for operators who want the dials.

## Getting started

    git clone https://github.com/leavesofgrass/d750ctrl ~/d750ctrl
    cd ~/d750ctrl
    ./install.sh YOURCALL          # links the commands, starts the daemon, makes the Python environment
    sudo ./install-udev.sh         # once: gives you the radio's serial port as /dev/d750-cat
    d750 doctor                    # every check in one list, Pass or Fail per line
    d750 status                    # both bands, transmit band, TNC, squelch, power
    d750ctrl                       # the screen

The radio's base unit USB-C socket is the serial port the daemon uses. The control head's socket carries the
sound card for digital modes, and it is also a charger, so put a data-only adapter or a powered hub between it
and the computer. Both sockets may be connected at once; the udev rule names them apart.

## The pieces

- d750d: the only process that opens the serial port. Port 4532 speaks the rigctld protocol, so xara or any
  hamlib-aware program keys the radio through it; port 4533 takes one Kenwood command per line and returns the
  answer. It refuses commands that key or reset the radio on 4533, unkeys on client loss and after 30 seconds,
  and logs every exchange under ~/.local/share/d750ctrl/log.
- d750: the verbs. status, freq, band, mode, squelch, power, busy, watch, tnc, vara, fixup, mem, gps, vox,
  clock, level, record, ptt off, doctor, probe, log, lock, unlock, raw. Add -n for a dry run of anything that
  changes the radio. Exit 0 Pass, 1 Fail, 2 usage.
- d750ctrl: the screen. Both bands, the active band in big digits, tuning by step or typed frequency, squelch,
  power, mode, VFO or memory, a memory browser read from the radio, TNC, GPS output, PTT lock, unkey, one CQ
  frame through xara, the radio clock, raw CAT, a scrolling CAT log; x, r, S and R hand the terminal to
  xarachat, radiogram, SSTV and RTTY and take it back.
- d750-sstv and d750-rtty: send and receive through the radio's sound card, keyed through d750d, with xara
  paused meanwhile. SSTV uses the sstv Python package; RTTY uses rttymodem.py, a Baudot modem written here.
- probe.py: asks the radio, read only, which commands it answers and writes the table the verbs rely on.
- d750-sim.py, test-env.sh, tests.sh, d750ctrl-test.py, modes-test.sh: a pretend radio on a pseudo terminal
  and the tests that run against it, so nothing here needs a radio to be proven.

## Settings

~/.config/d750ctrl/d750ctrl.conf, written by install.sh from d750ctrl.conf.example:

    mycall = N0CALL        your call, for the CQ frame
    bluetooth =            the radio's Bluetooth address, for the pairing checks; empty if unpaired
    ptt_port = 4532
    cmd_port = 4533

d750 fixup keeps its own file there, fixup.conf, with the TNC mode and band, the data band squelch and the GPS
output state it puts back after a power cycle. The probe's table is commands.txt beside them. Nothing about
your station is in this repository.

## The radio, as learned

The TM-D750 speaks the TH-D74 command dialect over USB: FQ, MD, SQ, BY, BC, PC, VM, MR, ME, FO, TN, GP, RT,
VX and more; d750 probe lists what your firmware answers. Three rules learned the hard way:

- The CAT port must carry only CAT. Menu 403 Off, or d750 gps output off; GPS sentences on the port slow every
  command to seconds.
- Never run the TNC with the data band's squelch wide open while menu 508 is on Busy: the TNC will not transmit.
- Keep transmitting handhelds away from the USB leads; a bus reset takes the radio and everything else on it.

Hamlib's TH-D74 model talks to this radio but takes seconds to unkey, which is why d750d keys with the raw
TX and RX commands and offers hamlib's protocol on its own port instead.

## Tests

    ./test-env.sh &                 the simulator and a second daemon on ports 4542 and 4543
    ./tests.sh                      the verbs, 46 checks
    python3 d750ctrl-test.py        the screen under a pseudo terminal, 18 checks
    ./modes-test.sh                 RTTY and SSTV round trips over a virtual sink
    .venv/bin/python rttymodem.py selftest

## License

MIT, see LICENSE.
