#!/usr/bin/env python3
"""d750d: the one process that owns the Kenwood TM-D750's serial port on this computer.

Port 4532, rigctld protocol for xara: T 1 keys, T 0 unkeys, answered with RPRT 0.
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


def serve_ptt(conn, peer):
    f = conn.makefile("rwb", buffering=0)
    try:
        for raw in f:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            parts = line.split()
            cmd = parts[0]
            try:
                if cmd == "T" and len(parts) >= 2 and parts[1] in ("0", "1"):
                    radio.ptt(parts[1] == "1")
                    f.write(b"RPRT 0\n")
                elif cmd == "t":
                    f.write(b"1\n" if radio.keyed_since is not None else b"0\n")
                elif cmd == "f":
                    reply = radio.command("FQ 0")
                    hz = reply.split(",")[1] if "," in reply else "0"
                    f.write(f"{int(hz)}\n".encode())
                elif cmd in ("q", "Q"):
                    break
                else:
                    f.write(b"RPRT -11\n")
            except OSError as e:
                log(f"ptt client {peer}: error for {line!r}: {e}")
                f.write(b"RPRT -1\n")
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
