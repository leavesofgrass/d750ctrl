# Changelog

## Unreleased

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
