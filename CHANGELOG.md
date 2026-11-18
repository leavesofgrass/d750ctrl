# Changelog

## Unreleased

- License: GNU General Public License, version 2 or later, from this change on. Version 0.1.0 and everything
  published before it stays available under the MIT license.
- Documentation: a short README with a quick start, and a docs folder with a page for each tool, a settings
  reference, radio setup, a glossary, recipes, troubleshooting, a page on what has and has not been tested, and a
  reference to the radio as a computer sees it. "Try it without a radio" runs the tools against the pretend radio.
- Fixed: `d750-sstv tx` and `d750-rtty tx` keyed the radio and unkeyed it a few milliseconds later. The keyer
  closed its connection after keying, and d750d unkeys when a keying client disconnects. The keyer now holds one
  connection for the whole transmission. Checked against the pretend radio, and then on the air.
- Fixed: `d750 raw`, `d750 tnc off` and `d750 tnc aprs` exited 1 on success, and `d750 vara status` did with no
  log yet. `d750 ptt off` now exits 1 when the radio does not confirm the unkey, and `d750 level` when it
  recorded nothing.
- `d750 help` is one verb per line, each line 80 characters or fewer, for speech and Braille. `d750 vox on` and
  `d750 vox off` answer `VOX: on` and `VOX: off`. `d750 doctor` shows the radio's firmware and type. The note
  after `d750 tnc kiss` names the TNC's USB port and no longer says Bluetooth.
- A new test, output-rules-test.py, holds what the verbs print to written rules: plain text, line length, exit
  codes, failures that say so, the answer first, on and off, and dry runs that change nothing.
- install.sh links d750-power, writes the d750-aprs service without starting it, and writes aprs.conf, owner only,
  when it is missing.
- Station tools, in station/, with an installer of their own: `station` (raise and lower services, from a
  settings file), `notify` (ntfy notices, token in a settings file), `radiogram`, `d750d-kuma`, `xara-wait-audio`,
  `xara-radio-pair` and `mode-listen`. Two new tests cover `station` and `notify`.
- extras/d750-ptt.py: the first keying program, kept for reference. Never run it beside d750d.
- The tests run on Ubuntu, Debian, Fedora and Arch on GitHub.
- The comment in the udev rule file named the two sockets the wrong way round; the rules were right.
- `d750 probe` no longer sends BE, and d750d refuses it on the command port. Another project reports that BE sends
  an APRS beacon when the TNC is in APRS mode with the manual beacon method, so a read-only probe must not send it.
- Restart notices say only what is known. The "not transmitting" alert went out after nearly every restart,
  true or not, because an iGate here carries the beacon only now and then. Now each restart gives one
  notice with the day's count and the time since the last one, kept in aprs.json; two drops within 2
  minutes are one restart. The TNC reset runs after every return, before the check beacon, and once more a
  minute later if the radio does not confirm it. The first packet heard after a restart is said, and so is
  nothing heard for deaf_minutes (90). A beacon an iGate carries after a restart is good news on ntfy; none
  carrying it is a log line, never an alarm, a reset or a power cycle. The "not transmitting", "power
  cycled by the station computer" and "sending again" notices are gone; nothing runs power_cycle_cmd until a real
  transmit check exists. 53 new checks, 8 old ones replaced; 182 in all.
- The radio switched off is no longer an alarm: with the radio gone from USB, d750-aprs reports its Kuma
  monitors up as "radio off", and the USB alert goes out only when the radio comes back within 3 minutes, a
  restart. The check beacon still follows every return. 4 new checks; 137 in all.
- KISS settings (TX delay 300 ms, persistence 255, slot time 100 ms, half duplex) sent to the TNC on every connect,
  and a TNC reset before any power cycle: after a brownout restart the TNC took commands but sent nothing until
  they were set again, which a power cycle had not fixed. 3 new checks; 133 in all.
- A status message: status in aprs.conf every 6 hours, on the air and to APRS-IS; `d750-aprs announce` sends
  it now. It replaced a test status that had stayed on aprs.fi. 5 new checks; 130 in all.
- Unattended recovery: after the TNC port returns, a check beacon watched on APRS-IS; when the radio is not
  sending, power_cycle_cmd once in 30 minutes, never while keyed, with ntfy alerts at each step. d750-power and
  relay/d750-relay.ino: a fail-safe relay on the Leonardo, normally closed, never off for more than 60 s.
  7 new checks; 125 in all.
- aprschat: APRS messages from the terminal, a curses screen in xarachat's manner and a line mode, through
  d750-aprs. d750-aprs now keeps a message history (messages.jsonl), sends long messages in parts, takes
  messages for this station from APRS-IS with a g/ filter on the iGate login, and acknowledges each the
  way it came. install.sh links d750-aprs and aprschat into ~/.local/bin. 11 new checks in d750-aprs-test.py
  (118), 18 in aprschat-test.py.
- d750-aprs reports to Uptime Kuma through push URLs in ~/.config/kuma-push-url-aprs-*: the TNC and the iGate
  every 5 minutes, a packet heard, and a beacon an iGate carried. With notify = on, ntfy notices for APRS
  messages to this station (topic aprs), messages that failed, and the TNC port dropping (alerts). Kuma's
  quick port checks on 8001 are no longer logged as KISS programs. 5 new checks; 107 in all.
- d750-aprs is an APRS digipeater when asked: `d750-aprs digi fillin` for WIDE1-1, our call and aliases,
  `d750-aprs digi wide` also for WIDEn-N up to digi_max_hops, with our call traced into the path. Duplicate
  check, never its own or twice, at most 20 a minute, an optional viscous delay for fill-in, and only with
  transmitting on. Off by default. 26 new checks; 102 in all.
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
- After each beacon, d750-aprs watches APRS-IS for 60 seconds and says which iGate carried it; with
  aprsis_beacon = fallback, the default, it sends the beacon to APRS-IS directly when no iGate did.
  The watch has its own read-only login, because APRS-IS never sends a client the packets of its own login
  call; with the filter on the iGate login every beacon looked missed and was sent a second time.
- d750-aprs says when the TNC port drops and returns that a radio restarted by itself may need a power
  cycle before it transmits again, and says so too after two beacons in a row that reach no iGate.
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
- d750d's log is small again: 44 to 516 MB a day becomes 76 to 215 kB. Reads on 4533 that the radio answers
  are no longer logged; sets, refusals, errors, keying, the port opening and closing, and bytes sent unasked
  still are. The same error again, as on every poll while /dev/d750-cat was missing, is logged once and then
  counted, one line a minute. Each APRS packet line on the CAT port is one log line. D750_LOG_ALL=1 logs every
  exchange. 15 new checks in tests.sh.
- d750ctrl reads everything every 2 seconds, the busy flags of both bands every second, and the radio again at
  once after a change from the screen: about 10 CAT commands a second instead of about 29. Settings
  status_seconds and busy_seconds. 4 new checks in d750ctrl-test.py.

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
