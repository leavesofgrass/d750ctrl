"""Shared helpers for the external mode tools: the radio's audio device names, keying through d750d, and
pausing xara while another program owns the audio. Imported by d750-sstv and d750-rtty."""
import os, socket, subprocess, threading, time

def _conf():
    conf = {}
    try:
        for line in open(os.path.expanduser("~/.config/d750ctrl/d750ctrl.conf"), encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); conf[k.strip().lower()] = v.strip()
    except OSError:
        pass
    return conf


PTT_PORT = int(os.environ.get("D750_PTT_PORT", _conf().get("ptt_port", "4532")))


def pactl(args):
    try:
        return subprocess.run(["pactl"] + args, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def radio_sink():
    for line in pactl(["list", "short", "sinks"]).splitlines():
        if "TM-D750" in line:
            return line.split("\t")[1]
    return None


def radio_source():
    for line in pactl(["list", "short", "sources"]).splitlines():
        if "TM-D750" in line and "monitor" not in line:
            return line.split("\t")[1]
    return None


def ptt(on):
    try:
        s = socket.create_connection(("127.0.0.1", PTT_PORT), timeout=5)
        s.sendall(b"T 1\n" if on else b"T 0\n"); r = s.makefile("rb").readline().decode().strip(); s.close()
        return r == "RPRT 0", r
    except OSError as e:
        return False, str(e)


class Keyed:
    """Hold PTT for the duration of a block: keys, refreshes the daemon's watchdog every 15 seconds, unkeys.
    All of it on one connection to d750d's PTT port, held open for the whole block: d750d unkeys the radio
    whenever a client leaves while keyed, so a connection per command would key for a moment only. If the
    connection is lost, d750d has unkeyed the radio; the refresh stops and the block runs to its end."""

    def __init__(self, enabled=True, lead=0.3, tail=0.2):
        self.enabled, self.lead, self.tail = enabled, lead, tail
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.sock = self.reader = self.thread = None
        self.lost = False

    def _send(self, on):
        """One T 1 or T 0 on the held connection; (True, answer) only for RPRT 0."""
        with self.lock:
            try:
                self.sock.sendall(b"T 1\n" if on else b"T 0\n")
                r = self.reader.readline().decode(errors="replace").strip()
            except (OSError, AttributeError) as e:
                return False, str(e) or "connection closed"
            return r == "RPRT 0", r or "connection closed"

    def _close(self):
        for f in (self.reader, self.sock):
            try:
                if f is not None:
                    f.close()
            except OSError:
                pass
        self.sock = self.reader = None

    def __enter__(self):
        if self.enabled:
            try:
                self.sock = socket.create_connection(("127.0.0.1", PTT_PORT), timeout=5)
                self.reader = self.sock.makefile("rb")
            except OSError as e:
                self._close()
                raise RuntimeError(f"could not key the radio: {e}") from e
            ok, r = self._send(True)
            if not ok:
                self._close()
                raise RuntimeError(f"could not key the radio: {r}")
            self.thread = threading.Thread(target=self._refresh, daemon=True)
            self.thread.start()
            time.sleep(self.lead)
        return self

    def _refresh(self):
        while not self.stop.wait(15):
            ok, r = self._send(True)
            if not ok:
                if not self.stop.is_set():
                    self.lost = True
                    print(f"keying lost ({r}); d750d unkeyed the radio, the rest goes out unkeyed", flush=True)
                return

    def __exit__(self, *exc):
        if self.enabled:
            self.stop.set(); time.sleep(self.tail)
            if self.thread is not None:
                self.thread.join(timeout=10)
            ok, r = self._send(False)
            self._close()
            if not ok:
                ptt(False)      # the held connection is gone: unkey once more on a new one, to be sure
        return False


class XaraPaused:
    """Stop xara while another program uses the radio's audio, start it again afterwards if it was running."""

    def __enter__(self):
        r = subprocess.run(["systemctl", "--user", "is-active", "xara.service"], capture_output=True, text=True)
        self.was_active = r.stdout.strip() == "active"
        if self.was_active:
            subprocess.run(["systemctl", "--user", "stop", "xara.service"], check=False)
            print("xara paused while this runs", flush=True)
        return self

    def __exit__(self, *exc):
        if self.was_active:
            subprocess.run(["systemctl", "--user", "start", "xara.service"], check=False)
            print("xara started again", flush=True)
        return False


def play(wav, sink):
    subprocess.run(["paplay", f"--device={sink}", wav], check=True)


def record(wav, source, seconds):
    subprocess.run(["timeout", str(seconds + 1), "parecord", f"--device={source}", "--rate=48000", "--channels=1",
                    "--format=s16le", "--file-format=wav", wav], check=False)
