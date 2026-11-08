#!/usr/bin/env python3
"""d750d: the one process that owns the Kenwood TM-D750's serial port on this computer.

Port 4532, hamlib's NET rigctl protocol, enough of it for xara, WSJT-X, fldigi, GridTracker,
OpenSlot and any other Hamlib-aware program (choose the rig "NET rigctl", address 127.0.0.1:4532):
chk_vfo and dump_state for the opening handshake, f F m M v V t T s S l L, get_vfo_info,
get_powerstat, get_lock_mode and the long names of the same. VFOA is band A, VFOB band B, the
current VFO the band that transmits; modes FM, FMN, AM and DSTAR; levels STRENGTH, RAWSTR,
RFPOWER and SQL. T 1 keys, T 0 unkeys, answered with RPRT 0.
Port 4533, line protocol for the d750 command and the probe: one Kenwood command per
line, the radio's answer line back, or ERR and a reason. Daemon words: state, lock,
unlock, reconnect, quit.

Safety: unkey at start, when a client drops while keyed, on serial errors, after
MAX_KEY_SECONDS, and TX is refused while locked. Every exchange is logged with a time
stamp to ~/.local/share/d750ctrl/log/d750d-DATE.txt. Grown out of a keying shim on Saturday,
November 7, 2026. Runs as the user service d750d.service.
Environment: D750_PORT (device), D750_PTT_PORT, D750_CMD_PORT, D750_LOG_DIR, D750_BAUD, so a
second instance can run against the simulator (d750-sim.py) without touching the real one.
"""
import os
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
VERSION = "0.1.0"
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
UNSAFE = {"TX", "RX", "UP", "DW", "SR", "PS", "0M", "0G"}   # only PTT may key; the rest never go through 4533


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, time.strftime("d750d-%Y-%m-%d.txt")), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


class Radio:
    def __init__(self):
        self.ser = None
        self.lock = threading.Lock()
        self.keyed_since = None
        self.locked = False
        self.last_answer = None
        self.unsolicited = 0

    def open(self):
        if self.ser is not None:
            return True
        try:
            self.ser = serial.Serial(PORT_PATH, BAUD, timeout=0.5, write_timeout=0.5)
            self.ser.reset_input_buffer()
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
                    self.unsolicited += len(junk)
                    log(f"unsolicited {len(junk)} bytes on the port, discarded: {junk[:40]!r}")
                self.ser.write(cmd.encode("ascii", "replace") + b"\r")
                self.ser.flush()
                reply = self.ser.read_until(b"\r", 200)
            except Exception as e:  # noqa: BLE001
                self.close(f"serial error: {e}")
                raise OSError(f"serial error: {e}") from e
            text = reply.decode(errors="replace").strip()
            self.last_answer = time.time()
            return text

    def ptt(self, on):
        if on and self.locked:
            raise OSError("locked: PTT refused")
        t0 = time.monotonic()
        reply = self.command("TX" if on else "RX")
        ms = (time.monotonic() - t0) * 1000
        self.keyed_since = time.monotonic() if on else None
        log(f"{'key' if on else 'unkey'} in {ms:.0f} ms, radio said {reply!r}")
        return reply

    def unkey_quietly(self, why):
        if self.keyed_since is None:
            return
        try:
            log(f"unkey: {why}")
            self.ptt(False)
        except Exception as e:  # noqa: BLE001
            log(f"unkey failed ({why}): {e}")

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
        return (f"port {'open' if self.ser else 'closed'} {PORT_PATH}; "
                f"{'keyed' if self.keyed_since else 'not keyed'}; "
                f"{'locked' if self.locked else 'unlocked'}; "
                f"last answer {time.strftime('%H:%M:%S', time.localtime(self.last_answer)) if self.last_answer else 'none'}; "
                f"unsolicited bytes seen {self.unsolicited}")


radio = Radio()


def watchdog():
    while True:
        time.sleep(1.0)
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
            if not args: return fail(-1)
            radio.ptt(args[0] != "0")
            return out([], "set_ptt")
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
    except ValueError:
        return fail(-1)


def serve_ptt(conn, peer):
    f = conn.makefile("rwb", buffering=0)
    try:
        for raw in f:
            line = raw.decode(errors="replace").strip()
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
        radio.unkey_quietly("ptt client disconnected while keyed")
        conn.close()


def serve_cmd(conn, peer):
    f = conn.makefile("rwb", buffering=0)
    try:
        for raw in f:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            word = line.split()[0]
            if word.lower() in DAEMON_WORDS:
                w = word.lower()
                if w == "state":
                    f.write((radio.state() + "\n").encode())
                elif w == "lock":
                    radio.locked = True; radio.unkey_quietly("lock requested"); f.write(b"OK locked, PTT refused until unlock\n")
                elif w == "unlock":
                    radio.locked = False; f.write(b"OK unlocked\n")
                elif w == "reconnect":
                    radio.close("reconnect requested")
                    try:
                        radio.open(); f.write(b"OK port reopened\n")
                    except OSError as e:
                        f.write(f"ERR {e}\n".encode())
                elif w == "quit":
                    break
                continue
            if word.upper() in UNSAFE:
                f.write(f"ERR {word} is not allowed on this port; keying goes through 4532\n".encode())
                log(f"cmd client {peer}: refused {line!r}")
                continue
            try:
                reply = radio.command(line)
                log(f"cmd {line!r} -> {reply!r}")
                f.write((reply + "\n").encode() if reply else b"ERR no answer\n")
            except OSError as e:
                log(f"cmd client {peer}: {line!r} failed: {e}")
                f.write(f"ERR {e}\n".encode())
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
        log(f"radio answers {radio.command('ID')!r}")
        radio.ptt(False)
    except OSError as e:
        log(f"startup: {e}; will open the port when it appears")
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=listen, args=(CMD_LISTEN, serve_cmd), daemon=True).start()
    listen(PTT_LISTEN, serve_ptt)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        radio.unkey_quietly("stopping")
        sys.exit(0)
