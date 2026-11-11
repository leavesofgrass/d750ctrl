# Changelog

## Unreleased

- d750-aprs: APRS through the TM-D750's TNC in KISS mode, as a user service. Every packet as one plain line
  with distance and direction from home and how it was heard; the home beacon on a timer; APRS messages sent
  with retries and acknowledged when received; the TNC shared on KISS TCP port 8001. Nothing transmits until
  `d750-aprs transmit on`. 53 offline checks in d750-aprs-test.py.
- The TNC's USB layout, found by listening: menu 983 on USB (Main Unit) puts KISS on the base unit's port,
  menu 984 on USB (Panel) puts the APRS mode's packet text on the control head's port beside CAT. d750-aprs
  raises DTR and RTS (tnc_lines = low holds them low) and counts the bytes from the TNC in its status line.
- d750-aprs is a receive-only iGate when asked: `d750-aprs igate on` passes what the radio hears to APRS-IS
  (noam.aprs2.net by default) by the usual rules, with the passcode in aprsis_pass. It reconnects by itself,
  says problems once, and shows the server and the count gated in its status line. 12 new checks.
- d750-aprs keeps the time of its last beacon, so a restart no longer sends an extra one, and its settings
  writer keeps aprs.conf owner only (mode 600): the file holds the exact home position.
- udev: the control head's port (2166:9030) is /dev/d750-cat and the base unit's (2166:9032) /dev/d750-tnc. The
  rules file had them the other way round; the working system rule was already this way.
- VarAC as an option: o opens xarachat with VarAC's framing on, in the varac window, or openslot when the
  settings say varac = openslot; x and o share one xarachat and jump to each other's window. c offers a
  VarAC CQ frame or a beacon frame; d750 vara cq and d750 vara beacon do the same from the command line,
  with the call from the settings instead of a fixed one.
- d750d speaks enough of hamlib's NET rigctl protocol for WSJT-X, fldigi, GridTracker, OpenSlot and hamlib's own
  rigctl: the chk_vfo and dump_state handshake, f F m M v V t T s S l L, get_vfo_info, get_powerstat,
  get_lock_mode, the long command names and the extended reply form. Before, only T (PTT) was answered and
  hamlib's client gave up at chk_vfo. VFOA is band A, VFOB band B, the current VFO the transmit band; modes FM,
  FMN, AM, DSTAR; levels STRENGTH, RAWSTR, RFPOWER, SQL. 15 new checks in tests.sh use hamlib's client.
- d750ctrl: o opens openslot --tui, the VarAC-compatible chat client, in a window named varac, next to x for
  xarachat; F9 comes back to the rig screen and Ctrl-Q in openslot closes its window. openslot reads
  ~/.config/openslot/config.toml, with the xara modem on 8300 and rig_backend = "none" until d750d speaks the
  full rigctld handshake.

## 0.1.0, Sunday, November 8, 2026

First release.

- d750d, the port daemon: the only process that opens the radio's serial port. The rigctld protocol on 4532 for
  xara and hamlib-aware programs, one Kenwood command per line on 4533, raw TX and RX keying in about 30 ms, a
  30 second watchdog, unkey on client loss, a log of every exchange.
- d750, the verbs: status, freq, band, mode, squelch, power, busy, watch, tnc, vara, fixup, mem, gps, vox, clock,
  level, record, ptt off, doctor, probe, log, lock, unlock, raw; -n shows what would be sent.
- d750ctrl, the screen: both bands, big digits, tuning, squelch, power, mode, VFO or memory, a memory browser, TNC,
  GPS output, PTT lock, CQ frame, clock, raw CAT, a CAT log. Inside tmux each tool gets a window of its own: x
  xarachat, r radiogram, S SSTV, R RTTY; F9 back to the rig screen, F12 next window.
- d750-sstv and d750-rtty: pictures and Baudot text through the radio's sound card, keyed through d750d, with
  rttymodem.py written here.
- probe.py asks the radio which commands it answers; udev rule and install scripts; d750ctrl.conf for the
  station's own details, nothing of them in the repository.
- A simulator and tests: 46 verb checks, 18 screen checks, RTTY and SSTV round trips over a virtual sink.
- Mode codes as the TM-D750 accepts them, confirmed on the radio: 0 FM, 1 NFM, 2 AM, 3 DV.
