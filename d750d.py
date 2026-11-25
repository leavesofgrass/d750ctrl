#!/usr/bin/env python3
"""d750d: the one process that owns the Kenwood TM-D750's serial port on this computer.

Port 4532, hamlib's NET rigctl protocol, enough of it for xara, WSJT-X, fldigi, GridTracker,
OpenSlot and any other Hamlib-aware program (choose the rig "NET rigctl", address 127.0.0.1:4532):
chk_vfo and dump_state for the opening handshake, f F m M v V t T s S l L, get_vfo_info,
get_powerstat, get_lock_mode and the long names of the same. VFOA is band A, VFOB band B, the
current VFO the band that transmits; modes FM, FMN, AM and DSTAR; levels STRENGTH, RAWSTR,
RFPOWER and SQL. T 1 keys, T 0 unkeys, answered with RPRT 0. T takes exactly one value: 0 is off, 1 to 3 are on; any other is refused.
Port 4533, line protocol for the d750 command and the probe: one Kenwood command per
line, the radio's answer line back, or ERR and a reason. Daemon words: state, lock,
unlock, reconnect, quit, each only alone and in small letters.

What a line may hold. Each port's line end, a newline with one carriage return before it, is taken
off first, and a line over 512 characters is refused; it is read with a limit, never held whole. On
4533 a line may hold only letters, digits, the space and , . - / +, may not start with a digit, and
is refused when its command, its first two characters after leading spaces, is one that keys or moves
the radio (UNSAFE). On 4532 a line may hold any character from 32 to 126.

Safety: unkey at start, when a client drops, on serial errors, after MAX_KEY_SECONDS. While locked,
PTT is refused, and so are VX with any value but 0, TN with a value that is not TNC off, and PT with
any value, which can make the radio send by itself. lock and every unkey send RX and check the answer.
The log, with a time stamp, in ~/.local/share/d750ctrl/log/d750d-DATE.txt: keying, sets, refusals,
errors, the serial port opening and closing, and bytes the radio sends unasked, each APRS packet
as one line. Routine reads on 4533 that the radio answers stay out of it, and the same error
again is counted, one line a minute. D750_LOG_ALL=1 logs every exchange, as before November 11.
Grown out of a keying shim on Saturday, November 7, 2026. Runs as the user service d750d.service.
Environment: D750_PORT (device), D750_PTT_PORT, D750_CMD_PORT, D750_LOG_DIR, D750_BAUD, so a
second instance can run against the simulator (tests/d750-sim.py) without touching the real one.
"""
import math
import os
import re
import socket
import sys
import threading
import time

import serial

PORT_PATH = os.environ.get("D750_PORT", "/dev/d750-cat")
PTT_LISTEN = ("127.0.0.1", int(os.environ.get("D750_PTT_PORT", "4532")))
CMD_LISTEN = ("127.0.0.1", int(os.environ.get("D750_CMD_PORT", "4533")))
MAX_KEY_SECONDS = 30.0
LOG_DIR = os.path.expanduser(os.environ.get("D750_LOG_DIR", "~/.local/share/d750ctrl/log"))
BAUD = int(os.environ.get("D750_BAUD", "9600"))
DAEMON_WORDS = ("state", "lock", "unlock", "reconnect", "quit")
VERSION = "0.2.0-alpha.1"
# hamlib's bit values from rig.h: modes, levels. Kenwood MD codes as the TM-D750 accepts them (0 FM, 1 NFM, 2 AM, 3 DV).
HL_MODES = {"FM": (0, 1 << 5, 15000), "FMN": (1, 1 << 21, 8000), "AM": (2, 1 << 0, 8000), "DSTAR": (3, 1 << 24, 6250)}
MODE_NAME = {code: name for name, (code, _, _) in HL_MODES.items()}
MODE_ALIAS = {"PKTFM": "FM", "WFM": "FM", "NFM": "FMN", "DV": "DSTAR", "PKTAM": "AM"}
MODES_MASK = sum(bit for _, bit, _ in HL_MODES.values()) | (1 << 12)        # PKTFM is taken as FM
LEVEL_SQL, LEVEL_RFPOWER, LEVEL_RAWSTR, LEVEL_STRENGTH = 1 << 5, 1 << 12, 1 << 26, 1 << 30
POWER_AS_LEVEL = {0: 1.0, 1: 0.5, 2: 0.2, 3: 0.1}                             # PC high, mid, low, EL
LONG_NAMES = {"get_freq": "f", "set_freq": "F", "get_mode": "m", "set_mode": "M", "get_vfo": "v", "set_vfo": "V",
              "get_ptt": "t", "set_ptt": "T", "get_split_vfo": "s", "set_split_vfo": "S", "get_level": "l",
              "set_level": "L", "get_func": "u", "set_func": "U", "get_info": "_", "quit": "q"}
# only PTT may key; the rest never go through 4533. BE can send an APRS beacon with the TNC in APRS mode.
UNSAFE = {"TX", "RX", "UP", "DW", "SR", "PS", "0M", "0G", "BE"}
# Refused on 4533 while locked: they arm the radio to send by itself (VOX on, the TNC in APRS or KISS, the beacon).
ARMS = ("VX", "TN", "PT")
LINE_LIMIT = 512
# The two ports differ on purpose. A line on 4533 goes to the radio as text, so it may hold only what a
# Kenwood command needs. Nothing on 4532 reaches the radio as text: d750d builds each command itself, and
# hamlib's clients need \ and _ there (\chk_vfo, \dump_state), so 4532 refuses only characters outside 32 to 126.
CMD_CHARS = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ,.-/+")
CMD_CHARS_SAID = "only plain letters, digits, spaces and , . - / + are allowed"
LOG_ALL = os.environ.get("D750_LOG_ALL", "").strip().lower() not in ("", "0", "no", "off", "false")
REPEAT_SECONDS = 60.0
# Kenwood reads that take one band or channel number: FQ 0, BY 1, ME 005. With a comma they are sets.
BAND_READS = {"FQ", "MD", "SQ", "BY", "PC", "VM", "MR", "ME", "SM", "FO"}
# In APRS mode the radio's TNC prints each packet it hears on the CAT port as a line: CALL>DEST,PATH:INFO
APRS_LINE = re.compile(rb"[A-Z0-9]{1,6}(-[A-Z0-9]{1,2})?>[A-Z0-9]{1,6}(-[A-Z0-9]{1,2})?(,[A-Za-z0-9-]{1,10}\*?)*:")


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, time.strftime("d750d-%Y-%m-%d.txt")), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def is_read(line):
    """A Kenwood read: the bare command (BC, TN, GP, VX, ID) or the command and one band or channel (FQ 0, ME 005)."""
    parts = line.split()
    if len(parts) == 1:
        return True
    return len(parts) == 2 and parts[0].upper() in BAND_READS and parts[1].isdigit()


def routine(line, reply):
    """A read the radio answered with its value: kept out of the log unless D750_LOG_ALL is set.
    An answer that only echoes the line was an action, and is logged."""
    if LOG_ALL or not is_read(line) or reply == line:
        return False
    word = line.split()[0].upper()
    return reply.split(" ", 1)[0].upper() == word and len(reply) > len(word)


def printable(data):
    """Packet text for the log: printable ASCII as it is, any other byte as \\xNN."""
    return "".join(chr(c) if 32 <= c < 127 else f"\\x{c:02x}" for c in data)


class Repeats:
    """The same trouble again and again, on every poll while the radio's port is missing, is logged the
    first time and then counted: one line a minute says how many more. After a quiet minute the next one
    is logged in full again. With D750_LOG_ALL every one is logged."""

    def __init__(self):
        self.lock = threading.Lock()
        self.seen = {}                  # trouble -> [count since the last report, time of the first of them]
        self.since = time.monotonic()

    def note(self, key, msg):
        with self.lock:
            if LOG_ALL or key not in self.seen:
                self.seen.setdefault(key, [0, 0.0])
                log(msg)
                return
            entry = self.seen[key]
            if not entry[0]:
                entry[1] = time.time()
            entry[0] += 1

    def tick(self, now=False):
        """Report the counts once a minute, or at once (now=True, when the port opens)."""
        with self.lock:
            if not now and time.monotonic() - self.since < REPEAT_SECONDS:
                return
            self.since = time.monotonic()
            for key, (count, first) in list(self.seen.items()):
                if count:
                    log(f"repeated {count} more times since {time.strftime('%H:%M:%S', time.localtime(first))}: {key}")
                    self.seen[key] = [0, 0.0]
                elif not now:
                    del self.seen[key]


repeats = Repeats()


class Radio:
    def __init__(self):
        self.ser = None
        # The serial lock. Held, too, while the lock is checked and set, so a lock and a keying command cannot
        # race; reentrant, because those callers then send their command through command().
        self.lock = threading.RLock()
        self.keyed_since = None
        self.unkey_failing = False          # an unkey failed and the belief stayed keyed
        self.locked = False
        self.last_answer = None
        self.unsolicited = 0

    def open(self):
        if self.ser is not None:
            return True
        try:
            self.ser = serial.Serial(PORT_PATH, BAUD, timeout=0.5, write_timeout=0.5)
            self.ser.reset_input_buffer()
            repeats.tick(now=True)          # how many times the port was missing, before saying it is back
            log(f"serial port {PORT_PATH} open")
            return True
        except Exception as e:  # noqa: BLE001
            self.ser = None
            raise OSError(f"radio port not available: {e}") from e

    def close(self, why=""):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:  # noqa: BLE001
                pass
            self.ser = None
            log(f"serial port closed{': ' + why if why else ''}")

    def command(self, cmd):
        """Send one Kenwood command, return its answer line. Raises OSError on trouble."""
        with self.lock:
            self.open()
            try:
                waiting = self.ser.in_waiting
                if waiting:
                    junk = self.ser.read(waiting)
                    if not junk.endswith((b"\r", b"\n")) and cmd not in ("TX", "RX"):
                        junk += self.ser.read_until(b"\r", 512)    # a line still arriving; keying never waits for it
                    self.unprompted(junk)
                self.ser.write(cmd.encode("ascii", "replace") + b"\r")
                self.ser.flush()
                reply = self.ser.read_until(b"\r", 512)
                for _ in range(3):                          # packet text that came out ahead of the answer
                    if not APRS_LINE.match(reply.strip()):
                        break
                    self.unprompted(reply)
                    reply = self.ser.read_until(b"\r", 512)
            except Exception as e:  # noqa: BLE001
                self.close(f"serial error: {e}")
                raise OSError(f"serial error: {e}") from e
            text = reply.decode(errors="replace").strip()
            self.last_answer = time.time()
            return text

    def unprompted(self, data):
        """Bytes the radio sent without being asked. Each APRS packet line is logged as one line,
        anything else as raw bytes, as before. Line ends alone are counted, not logged."""
        self.unsolicited += len(data)
        other = b""
        for piece, end in re.findall(rb"([^\r\n]*)([\r\n]*)", data):
            if APRS_LINE.match(piece):
                log(f"APRS packet on the CAT port: {printable(piece)}")
            else:
                other += piece + end
        if other.strip():
            log(f"unsolicited {len(other)} bytes on the port, discarded: {other[:40]!r}")

    def ptt(self, on):
        """TX or RX. The lock is checked with the serial lock held, so a lock cannot come between the check
        and TX. The radio counts as keyed from before TX is written, and an unkey counts only when the radio
        answers RX: until then the belief stays keyed, so the watchdog tries again."""
        with self.lock:
            if on and self.locked:
                raise OSError("locked: PTT refused")
            if on:
                self.keyed_since = time.monotonic()
                self.unkey_failing = False
            t0 = time.monotonic()
            reply = self.command("TX" if on else "RX")
            ms = (time.monotonic() - t0) * 1000
            if not on and reply == "RX":
                self.keyed_since = None
                self.unkey_failing = False
            log(f"{'key' if on else 'unkey'} in {ms:.0f} ms, radio said {reply!r}")
            return reply

    def unkey_quietly(self, why):
        with self.lock:
            return self._unkey_quietly(why)

    def _unkey_quietly(self, why):
        """RX whenever asked, keyed or not, and the answer checked. True when the radio said RX.
        "unkey" goes in the log only when the radio was keyed; a failure is logged, and counted when it repeats."""
        keyed = self.keyed_since is not None
        try:
            if keyed and not self.unkey_failing:     # the watchdog's tries after a failed one are counted below
                log(f"unkey: {why}")
            t0 = time.monotonic()
            reply = self.command("RX")
        except Exception as e:  # noqa: BLE001
            self.unkey_failing = keyed
            repeats.note(f"unkey failed ({why}): {e}", f"unkey failed ({why}): {e}")
            return False
        if reply != "RX":
            self.unkey_failing = keyed
            repeats.note(f"unkey not confirmed ({why})",
                         f"unkey not confirmed ({why}): the radio did not say it is receiving, it said {reply!r}")
            return False
        if keyed:
            log(f"unkey in {(time.monotonic() - t0) * 1000:.0f} ms, radio said {reply!r}")
        self.keyed_since = None
        self.unkey_failing = False
        return True

    def field(self, cmd, n=1):
        """Field n of the answer to a Kenwood query: FQ 0 -> 'FQ 0,0144990000' -> field 1 is the frequency."""
        reply = self.command(cmd)
        if reply in ("N", "?", ""):
            raise OSError(f"radio refused {cmd!r}: {reply!r}")
        parts = reply.split(" ", 1)[1].split(",") if " " in reply else []
        if len(parts) <= n:
            raise OSError(f"short answer to {cmd!r}: {reply!r}")
        return parts[n]

    def tx_band(self):
        v = self.field("BC", 1)
        return int(v) if v in ("0", "1") else 0

    def set_checked(self, cmd):
        """A Kenwood set command; N or ? from the radio is an error."""
        reply = self.command(cmd)
        if reply in ("N", "?", ""):
            raise ValueError(f"radio refused {cmd!r}")
        log(f"rigctl set {cmd!r} -> {reply!r}")
        return reply

    def state(self):
        with self.lock:     # never between a lock being set and its unkey
            return self._state()

    def _state(self):
        return (f"port {'open' if self.ser else 'closed'} {PORT_PATH}; "
                f"{'keyed' if self.keyed_since else 'not keyed'}; "
                f"{'locked' if self.locked else 'unlocked'}; "
                f"last answer {time.strftime('%H:%M:%S', time.localtime(self.last_answer)) if self.last_answer else 'none'}; "
                f"unsolicited bytes seen {self.unsolicited}")


radio = Radio()


def watchdog():
    while True:
        time.sleep(1.0)
        repeats.tick()
        since = radio.keyed_since
        if since is not None and time.monotonic() - since > MAX_KEY_SECONDS:
            radio.unkey_quietly(f"watchdog after {MAX_KEY_SECONDS:.0f} s")


def dump_state():
    """What hamlib's client reads at open: ranges, steps, filters, capabilities, then key=value lines up to done."""
    lines = ["1", "2", "0"]                                   # protocol version, rig model NET rigctl, ITU region
    for a, b in ((118000000, 174000000), (400000000, 524000000)):
        lines.append(f"{a:.6f} {b:.6f} 0x{MODES_MASK:x} -1 -1 0x3 0x1")
    lines.append("0 0 0 0 0 0 0")
    for a, b in ((144000000, 148000000), (430000000, 450000000)):
        lines.append(f"{a:.6f} {b:.6f} 0x{MODES_MASK:x} 5000 50000 0x3 0x1")
    lines.append("0 0 0 0 0 0 0")
    for step in (5000, 6250, 10000, 12500, 15000, 20000, 25000, 50000, 100000):
        lines.append(f"0x{MODES_MASK:x} {step}")
    lines.append("0 0")
    for _, bit, width in HL_MODES.values():
        lines.append(f"0x{bit:x} {width}")
    lines.append(f"0x{1 << 12:x} 15000")
    lines.append("0 0")
    lines += ["0", "0", "0", "0", "", ""]                      # rit, xit, if shift, announces, preamps, attenuators
    lines += ["0x0", "0x0", f"0x{LEVEL_SQL | LEVEL_RFPOWER | LEVEL_RAWSTR | LEVEL_STRENGTH:x}",
              f"0x{LEVEL_SQL | LEVEL_RFPOWER:x}", "0x0", "0x0"]
    lines += ["vfo_ops=0x0", "ptt_type=0x1", "targetable_vfo=0x0", "has_set_vfo=1", "has_get_vfo=1", "has_set_freq=1",
              "has_get_freq=1", "has_set_conf=0", "has_get_conf=0", "has_power2mW=0", "has_mW2power=0", "has_get_ant=0",
              "has_set_ant=0", "timeout=0", "rig_model=2", f"rigctld_version=d750d {VERSION}", "done"]
    return "\n".join(lines) + "\n"


def parse_vfo(word):
    """VFOA and Main are band A, VFOB and Sub band B, anything current is the transmit band."""
    w = (word or "").upper()
    if w in ("VFOA", "MAIN", "A"): return 0
    if w in ("VFOB", "SUB", "B"): return 1
    if w in ("", "CURRVFO", "VFO", "RX", "TX", "NONE", "MEM"): return radio.tx_band()
    return None


def finite(text):
    """A number hamlib may send for F or L: not inf, not nan, not a word."""
    try:
        return math.isfinite(float(text))
    except (ValueError, OverflowError):
        return False


def rigctl(line):
    """Answer one line of hamlib's NET rigctl protocol; None means the client said quit."""
    ext = ""
    if line[:1] in "+;|,":
        ext, line = line[0], line[1:].strip()
    if line.startswith("\\"):
        parts = line[1:].split(); name = parts[0] if parts else ""; cmd = LONG_NAMES.get(name, name)
    else:
        parts = line.split(); name = parts[0] if parts else ""; cmd = name
    args = parts[1:]
    sep = "\n" if ext in ("", "+") else ext

    def out(values, long_name, labels=()):
        if not ext:
            return "".join(f"{v}\n" for v in values) if values else "RPRT 0\n"
        text = f"{long_name}:" + (" " + " ".join(args) if args else "") + sep
        for lab, v in zip(labels, values):
            text += f"{lab}: {v}{sep}"
        return text + "RPRT 0\n"

    def fail(code=-11):
        return (f"{cmd}:{sep}" if ext else "") + f"RPRT {code}\n"

    try:
        if cmd in ("q", "Q"): return None
        if cmd == "chk_vfo": return "0\n"
        if cmd == "dump_state": return dump_state()
        if cmd == "get_powerstat": return out(["1"], cmd, ["Power Status"])
        if cmd in ("set_powerstat", "set_lock_mode", "S", "set_split_vfo"): return out([], cmd)
        if cmd == "get_lock_mode": return out(["0"], cmd, ["Locked"])
        if cmd == "_": return out([f"TM-D750 through d750d {VERSION}"], "get_info", ["Info"])
        if cmd == "t": return out(["1" if radio.keyed_since is not None else "0"], "get_ptt", ["PTT"])
        if cmd == "T":
            if len(args) != 1 or args[0] not in ("0", "1", "2", "3"): return fail(-1)
            radio.ptt(args[0] != "0")
            return out([], "set_ptt")
        if cmd == "F" and (len(args) < 1 or not finite(args[0]) or not 0 <= float(args[0]) < 1e10): return fail(-1)
        # before anything is read from the radio: a value that is not a number, or overflows its field or SQL's scale
        if cmd == "L" and (len(args) < 2 or not finite(args[1]) or not math.isfinite(float(args[1]) * 9)): return fail(-1)
        band = radio.tx_band()
        if cmd == "v": return out([f"VFO{'AB'[band]}"], "get_vfo", ["VFO"])
        if cmd == "V":
            b = parse_vfo(args[0] if args else "")
            if b is None: return fail(-1)
            radio.set_checked(f"BC {radio.field('BC', 0)},{b}")
            return out([], "set_vfo")
        if cmd == "s": return out(["0", f"VFO{'AB'[band]}"], "get_split_vfo", ["Split", "TX VFO"])
        if cmd == "f": return out([str(int(radio.field(f"FQ {band}")))], "get_freq", ["Frequency"])
        if cmd == "F":
            if not args: return fail(-1)
            radio.set_checked(f"FQ {band},{int(float(args[0])):010d}")
            return out([], "set_freq")
        if cmd == "m":
            name = MODE_NAME.get(int(radio.field(f"MD {band}")), "FM")
            return out([name, str(HL_MODES[name][2])], "get_mode", ["Mode", "Passband"])
        if cmd == "M":
            name = (args[0] if args else "").upper(); name = MODE_ALIAS.get(name, name)
            if name not in HL_MODES: return fail(-1)
            radio.set_checked(f"MD {band},{HL_MODES[name][0]}")
            return out([], "set_mode")
        if cmd == "get_vfo_info":
            b = parse_vfo(args[0] if args else "")
            if b is None: return fail(-1)
            name = MODE_NAME.get(int(radio.field(f"MD {b}")), "FM")
            return out([str(int(radio.field(f"FQ {b}"))), name, str(HL_MODES[name][2]), "0", "0"], cmd,
                       ["Freq", "Mode", "Width", "Split", "SatMode"])
        if cmd == "l":
            what = (args[0] if args else "").upper()
            if what == "STRENGTH": return out([str((int(radio.field(f"SM {band}")) - 9) * 6)], "get_level", ["Level Value"])
            if what == "RAWSTR": return out([radio.field(f"SM {band}")], "get_level", ["Level Value"])
            if what == "RFPOWER": return out([f"{POWER_AS_LEVEL.get(int(radio.field(f'PC {band}')), 1.0):.6f}"], "get_level", ["Level Value"])
            if what == "SQL": return out([f"{int(radio.field(f'SQ {band}')) / 9:.6f}"], "get_level", ["Level Value"])
            return fail()
        if cmd == "L":
            what = (args[0] if args else "").upper(); value = float(args[1]) if len(args) > 1 else None
            if value is None: return fail(-1)
            if what == "RFPOWER":
                code = 0 if value >= 0.75 else 1 if value >= 0.35 else 2 if value >= 0.15 else 3
                radio.set_checked(f"PC {band},{code}"); return out([], "set_level")
            if what == "SQL":
                radio.set_checked(f"SQ {band},{max(0, min(9, round(value * 9)))}"); return out([], "set_level")
            return fail()
        return fail()
    except (ValueError, OverflowError):     # a value too big for its field is the protocol's error; the client is kept
        return fail(-1)


def read_line(f, limit=LINE_LIMIT):
    """One line from a client: (bytes, too long), or (None, False) at the end of input. The line end,
    a newline with one carriage return before it, is taken off. The line is read with a limit, so one
    longer than limit is never held whole: the rest of it is read and dropped in pieces."""
    raw = f.readline(limit + 2)
    if not raw:
        return None, False
    if not raw.endswith(b"\n") and len(raw) >= limit + 2:
        while True:
            more = f.readline(4096)
            if not more or more.endswith(b"\n"):
                return b"", True
    if raw.endswith(b"\n"):
        raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
    return raw, len(raw) > limit


class Refused(Exception):
    """A command port line refused once the serial lock is held; its text is the reason."""


def judge_cmd(raw, locked):
    """What 4533 does with one line, its end taken off: ("refuse", why), ("word", the daemon word),
    ("blank", ""), or ("radio", the Kenwood command to send). Checked before anything else touches it."""
    if any(c not in CMD_CHARS for c in raw):
        return "refuse", CMD_CHARS_SAID
    text = raw.decode("ascii")
    if text in DAEMON_WORDS:
        return "word", text
    line = text.strip(" ")
    if not line:
        return "blank", ""
    if line[0].isdigit():
        return "refuse", "a line may not start with a digit"
    if line.split(" ")[0].lower() in DAEMON_WORDS:
        return "refuse", "say the word alone, in small letters"
    cmd = line[:2].upper()
    if cmd in UNSAFE:
        return "refuse", f"{cmd} is not allowed on this port"
    if locked and cmd in ARMS:
        value = line[2:].strip(" ")
        if (cmd == "VX" and value not in ("", "0")) or (cmd == "TN" and value and value.split(",")[0].strip(" ") != "0") \
                or (cmd == "PT" and value):
            return "refuse", f"{cmd} is refused while PTT is locked"
    return "radio", line


def serve_ptt(conn, peer):
    f = conn.makefile("rwb", buffering=0)
    try:
        while True:
            raw, too_long = read_line(f)
            if raw is None:
                break
            if too_long or any(not 32 <= c <= 126 for c in raw):
                why = f"longer than {LINE_LIMIT} characters" if too_long else "a character outside 32 to 126"
                log(f"rigctl client {peer}: refused {printable(raw[:80])!r}: {why}")
                f.write(b"RPRT -1\n")
                continue
            line = raw.decode("ascii").strip()
            if not line:
                continue
            try:
                answer = rigctl(line)
            except OSError as e:
                log(f"rigctl client {peer}: error for {line!r}: {e}")
                answer = "RPRT -1\n"
            if answer is None:
                break
            f.write(answer.encode())
    except Exception as e:  # noqa: BLE001
        log(f"ptt client {peer} dropped: {e}")
    finally:
        radio.unkey_quietly("ptt client disconnected")
        conn.close()


def serve_cmd(conn, peer):
    f = conn.makefile("rwb", buffering=0)
    try:
        while True:
            raw, too_long = read_line(f)
            if raw is None:
                break
            if too_long:
                what, line = "refuse", f"the line is longer than {LINE_LIMIT} characters"
            else:
                what, line = judge_cmd(raw, radio.locked)
            if what == "blank":
                continue
            if what == "refuse":
                f.write(f"ERR {line}\n".encode())
                log(f"cmd client {peer}: refused {printable(raw[:80])!r}: {line}")
                continue
            if what == "word":
                w = line
                if w == "state":
                    f.write((radio.state() + "\n").encode())
                elif w == "lock":
                    with radio.lock:        # set, and the radio unkeyed, with nothing able to come between
                        radio.locked = True
                        confirmed = radio.unkey_quietly("lock requested")
                    if confirmed:
                        f.write(b"OK locked, PTT refused until unlock\n")
                    else:
                        log("lock: locked, but the radio did not say it is receiving")
                        f.write(b"OK locked; the radio did not say it is receiving\n")
                elif w == "unlock":
                    with radio.lock:
                        radio.locked = False
                    f.write(b"OK unlocked\n")
                elif w == "reconnect":
                    radio.close("reconnect requested")
                    try:
                        radio.open(); f.write(b"OK port reopened\n")
                    except OSError as e:
                        f.write(f"ERR {e}\n".encode())
                elif w == "quit":
                    break
                continue
            try:
                with radio.lock:
                    # judged again with the serial lock held, so a lock cannot come between the check and the
                    # command: VX, TN and PT may have passed above while unlocked
                    if radio.locked:
                        what, why = judge_cmd(raw, True)
                        if what == "refuse":
                            raise Refused(why)
                    reply = radio.command(line)
            except Refused as e:
                f.write(f"ERR {e}\n".encode())
                log(f"cmd client {peer}: refused {printable(raw[:80])!r}: {e}")
                continue
            except OSError as e:
                repeats.note(f"{e}", f"cmd client {peer}: {line!r} failed: {e}")
                f.write(f"ERR {e}\n".encode())
                continue
            if not reply:
                repeats.note("no answer from the radio", f"cmd {line!r} -> no answer from the radio")
            elif reply in ("N", "?") and is_read(line):
                repeats.note(f"radio refused {line!r} with {reply!r}", f"cmd {line!r} -> {reply!r}")
            elif not routine(line, reply):
                log(f"cmd {line!r} -> {reply!r}")
            f.write((reply + "\n").encode() if reply else b"ERR no answer\n")
    except Exception as e:  # noqa: BLE001
        log(f"cmd client {peer} dropped: {e}")
    finally:
        conn.close()


def listen(addr, handler):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(addr)
    srv.listen(8)
    log(f"listening on {addr[0]}:{addr[1]} for {handler.__name__[6:]}")
    while True:
        conn, peer = srv.accept()
        threading.Thread(target=handler, args=(conn, peer), daemon=True).start()


def main():
    try:
        radio.open()
        # The radio may have been keyed before this daemon started: it counts as keyed, for longer than the
        # watchdog allows, until it answers RX. So an unkey it does not confirm is tried again each second.
        radio.keyed_since = time.monotonic() - MAX_KEY_SECONDS - 1
        log(f"radio answers {radio.command('ID')!r}")
    except OSError as e:
        log(f"startup: {e}; will open the port when it appears")
    if radio.keyed_since is not None:
        radio.unkey_quietly("start")
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=listen, args=(CMD_LISTEN, serve_cmd), daemon=True).start()
    listen(PTT_LISTEN, serve_ptt)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        radio.unkey_quietly("stopping")
        sys.exit(0)
