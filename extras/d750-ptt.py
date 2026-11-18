#!/usr/bin/env python3
"""d750-ptt: key the Kenwood TM-D750 by CAT for xara, speaking rigctld's protocol.

xara connects to 127.0.0.1:4532 and sends "T 1" or "T 0", expecting "RPRT 0".
This program answers those by writing the radio's own TX and RX commands to
/dev/d750-cat, which the radio honours at once. hamlib's TH-D74 model also keys
this radio but waits seconds for a reply form the D750 never sends, so it is not used.

Safety: the radio is unkeyed at start, when a client disconnects while keyed,
on any serial error, and by a watchdog after MAX_KEY_SECONDS.
Written Saturday, November 7, 2026.

This was the first keying program, before d750d existed. d750d now does this and much more.
NEVER run this beside d750d: both open /dev/d750-cat and both listen on port 4532. It is kept
for a station that wants CAT keying for xara and nothing else. See extras/README.md.
"""
import os
import socket
import sys
import threading
import time

import serial

PORT_PATH = os.environ.get("D750_PORT", "/dev/d750-cat")
LISTEN = ("127.0.0.1", 4532)
MAX_KEY_SECONDS = 30.0


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Radio:
    def __init__(self):
        self.ser = None
        self.lock = threading.Lock()
        self.keyed_since = None

    def open(self):
        if self.ser is not None:
            return True
        try:
            self.ser = serial.Serial(PORT_PATH, 9600, timeout=0.3, write_timeout=0.3)
            self.ser.reset_input_buffer()
            log(f"serial port {PORT_PATH} open")
            return True
        except Exception as e:  # noqa: BLE001
            log(f"cannot open {PORT_PATH}: {e}")
            self.ser = None
            return False

    def command(self, cmd):
        """Send one Kenwood command, return the echoed reply or raise."""
        with self.lock:
            if not self.open():
                raise OSError("radio port not available")
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode() + b"\r")
                self.ser.flush()
                reply = self.ser.read_until(b"\r", 64)
                return reply.decode(errors="replace").strip()
            except Exception as e:  # noqa: BLE001
                try:
                    self.ser.close()
                finally:
                    self.ser = None
                raise OSError(f"serial error: {e}") from e

    def ptt(self, on):
        t0 = time.monotonic()
        reply = self.command("TX" if on else "RX")
        ms = (time.monotonic() - t0) * 1000
        self.keyed_since = time.monotonic() if on else None
        log(f"{'key' if on else 'unkey'} in {ms:.0f} ms, radio said {reply!r}")
        return reply

    def unkey_quietly(self, why):
        try:
            if self.keyed_since is not None:
                log(f"unkey: {why}")
                self.ptt(False)
        except Exception as e:  # noqa: BLE001
            log(f"unkey failed ({why}): {e}")


radio = Radio()


def watchdog():
    while True:
        time.sleep(1.0)
        since = radio.keyed_since
        if since is not None and time.monotonic() - since > MAX_KEY_SECONDS:
            radio.unkey_quietly(f"watchdog after {MAX_KEY_SECONDS:.0f} s")


def serve_client(conn, peer):
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
                log(f"error for {line!r}: {e}")
                f.write(b"RPRT -1\n")
    except Exception as e:  # noqa: BLE001
        log(f"client {peer} dropped: {e}")
    finally:
        radio.unkey_quietly("client disconnected while keyed")
        try:
            conn.close()
        except OSError:
            pass


def main():
    if radio.open():
        try:
            ident = radio.command("ID")
            log(f"radio answers {ident!r}")
            radio.ptt(False)
        except OSError as e:
            log(f"startup check failed: {e}")
    threading.Thread(target=watchdog, daemon=True).start()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN)
    srv.listen(4)
    log(f"listening on {LISTEN[0]}:{LISTEN[1]} for rigctld-style PTT")
    while True:
        conn, peer = srv.accept()
        threading.Thread(target=serve_client, args=(conn, peer), daemon=True).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        radio.unkey_quietly("stopping")
        sys.exit(0)
