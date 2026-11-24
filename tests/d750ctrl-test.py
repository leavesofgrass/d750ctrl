#!/usr/bin/env python3
"""d750ctrl-test: d750ctrl on a pseudo terminal against the test bed (tests/test-env.sh: the simulator
and a d750d on ports 4542 and 4543), and the parts of d750ui.screen that need no terminal.

The screen reaches d750d through counting relays, so the test sees every line it sends and how often
it reads the radio, and can hold the command port's reads back to show that unkey and lock do not
wait behind them. A small model of an xterm reads what curses draws and where the cursor is.

Nothing transmits and nothing plays sound: D750_XARA_PORT is a port this test picked, where only
the test itself listens, to see that no frame is sent; the tools on PATH are stubs that only write
down their arguments; no send question is ever answered y, and no send is ever finished. The test
ends only the test bed it started. Exit 0 when every test passes.
GPL-2.0-or-later.
"""
import curses
import fcntl
import os
import queue
import re
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
sys.path.insert(0, TOP)

from d750ui import lines  # noqa: E402
from d750ui import screen as scr  # noqa: E402
from d750ui import screen_model as sm  # noqa: E402

SCREEN = os.path.join(TOP, "d750ctrl")
CMD_PORT, PTT_PORT = 4543, 4542
LIMIT = 15.0
END_SECONDS = 5.0
UP, DOWN = "\x1bOA", "\x1bOB"
ESC_KEY = "\x1b"
PLAIN = (False, False, None, None)  # a cell's look: bold, reverse, foreground, background
ENTER_ALTERNATE, LEAVE_ALTERNATE = b"\x1b[?1049h", b"\x1b[?1049l"
PASTE_ON, PASTE_OFF = b"\x1b[?2004h", b"\x1b[?2004l"
OPEN, CLOSE = "\x1b[200~", "\x1b[201~"  # the marks a terminal puts around a paste
STATUS, BUSY = 3, 0.75  # not the defaults (2 and 1), so the test sees the settings read
DAEMON_WORDS = ("state", "lock", "unlock", "reconnect", "quit")
READY = "d750ctrl. Receiving."


class Timeout(Exception):
    """Something the test waited for did not happen in time."""


# --------------------------------------------------------------------------- a small xterm


class Term:
    """Enough of an xterm to read what ncurses draws: the cells, their looks and the cursor."""

    def __init__(self, cols, rows):
        self.raw = bytearray()
        self.resize(cols, rows)

    def resize(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.grid = [[" "] * cols for _ in range(rows)]
        self.pen = PLAIN
        self.looks = [[PLAIN] * cols for _ in range(rows)]
        self.insert = False
        self.y = self.x = 0
        self.wrap = False
        self.top, self.bottom = 0, rows - 1
        self.saved = (0, 0)
        self.visible = getattr(self, "visible", True)
        self.state = "text"
        self.params = ""
        self.last = " "

    def feed(self, data):
        self.raw += data
        for ch in data.decode("latin-1"):
            self._char(ch)

    def text(self, row):
        return "".join(self.grid[row]).rstrip(" ")

    def screen(self):
        return [self.text(r) for r in range(self.rows)]

    @property
    def cursor(self):
        return (self.y, self.x)

    def _blank(self):
        return (False, False, None, self.pen[3])

    def _clear(self, row, cols):
        for i in cols:
            self.grid[row][i] = " "
            self.looks[row][i] = self._blank()

    def _go(self, y, x):
        self.y = max(0, min(self.rows - 1, y))
        self.x = max(0, min(self.cols - 1, x))
        self.wrap = False

    def _scroll_up(self, n=1, at=None):
        start = self.top if at is None else at
        for _ in range(n):
            del self.grid[start]
            del self.looks[start]
            self.grid.insert(self.bottom, [" "] * self.cols)
            self.looks.insert(self.bottom, [self._blank()] * self.cols)

    def _scroll_down(self, n=1, at=None):
        start = self.top if at is None else at
        for _ in range(n):
            del self.grid[self.bottom]
            del self.looks[self.bottom]
            self.grid.insert(start, [" "] * self.cols)
            self.looks.insert(start, [self._blank()] * self.cols)

    def _index(self):
        if self.y == self.bottom:
            self._scroll_up()
        elif self.y < self.rows - 1:
            self.y += 1
        self.wrap = False

    def _char(self, ch):
        if self.state == "esc":
            self._esc(ch)
        elif self.state == "csi":
            if ch.isdigit() or ch in ";?>=!<" or " " <= ch <= "/":
                self.params += ch
            else:
                self.state = "text"
                self._csi(ch, self.params)
        elif self.state == "osc":
            if ch == "\x07":
                self.state = "text"
            elif ch == "\x1b":
                self.state = "esc"
        elif self.state == "charset":
            self.state = "text"
        elif ch == "\x1b":
            self.state = "esc"
        elif ch == "\r":
            self.x, self.wrap = 0, False
        elif ch in "\n\x0b\x0c":
            self._index()
        elif ch == "\x08":
            self._go(self.y, self.x - 1)
        elif ch == "\t":
            self._go(self.y, (self.x // 8 + 1) * 8)
        elif ch < " " or ch == "\x7f":
            pass
        else:
            self._put(ch)

    def _put(self, ch):
        if self.wrap:
            self.x = 0
            self._index()
        if self.insert:
            self._csi("@", "1")
        self.grid[self.y][self.x] = ch
        self.looks[self.y][self.x] = self.pen
        self.last = ch
        if self.x == self.cols - 1:
            self.wrap = True
        else:
            self.x += 1

    def _esc(self, ch):
        self.state = "text"
        if ch == "[":
            self.state, self.params = "csi", ""
        elif ch == "]":
            self.state = "osc"
        elif ch in "()*+":
            self.state = "charset"
        elif ch == "7":
            self.saved = (self.y, self.x)
        elif ch == "8":
            self._go(*self.saved)
        elif ch == "D":
            self._index()
        elif ch == "E":
            self.x = 0
            self._index()
        elif ch == "M":
            if self.y == self.top:
                self._scroll_down()
            else:
                self._go(self.y - 1, self.x)

    def _csi(self, final, params):
        private = params[:1] in ("?", ">", "=", "!", "<")
        body = params.lstrip("?>=!<").rstrip(" !\"#$%&'()*+,-./")
        nums = [int(p) if p else None for p in body.split(";")] if body else [None]
        n = nums[0] or 1
        if private:
            if final in "hl" and 25 in nums:
                self.visible = final == "h"
            return
        y, x = self.y, self.x
        if final in "Hf":
            row = nums[0] or 1
            col = (nums[1] if len(nums) > 1 else None) or 1
            self._go(row - 1, col - 1)
        elif final == "A":
            self._go(y - n, x)
        elif final in "Be":
            self._go(y + n, x)
        elif final in "Ca":
            self._go(y, x + n)
        elif final == "D":
            self._go(y, x - n)
        elif final == "E":
            self._go(y + n, 0)
        elif final == "F":
            self._go(y - n, 0)
        elif final in "G`":
            self._go(y, n - 1)
        elif final == "d":
            self._go(n - 1, x)
        elif final == "K":
            mode = nums[0] or 0
            span = {0: range(x, self.cols), 1: range(0, x + 1), 2: range(self.cols)}.get(mode, ())
            self._clear(y, span)
        elif final == "J":
            mode = nums[0] or 0
            if mode == 0:
                self._csi("K", "0")
                rows = range(y + 1, self.rows)
            elif mode == 1:
                self._csi("K", "1")
                rows = range(0, y)
            else:
                rows = range(self.rows)
            for r in rows:
                self._clear(r, range(self.cols))
        elif final == "X":
            self._clear(y, range(x, min(self.cols, x + n)))
        elif final == "@":
            row, looks = self.grid[y], self.looks[y]
            self.grid[y] = (row[:x] + [" "] * n + row[x:])[: self.cols]
            self.looks[y] = (looks[:x] + [self._blank()] * n + looks[x:])[: self.cols]
        elif final == "P":
            row, looks = self.grid[y], self.looks[y]
            self.grid[y] = (row[:x] + row[x + n:] + [" "] * min(n, self.cols - x))[: self.cols]
            self.looks[y] = (looks[:x] + looks[x + n:] + [self._blank()] * min(n, self.cols - x))[: self.cols]
        elif final == "m":
            self._sgr(nums)
        elif final in "hl" and 4 in nums:
            self.insert = final == "h"
        elif final == "L":
            if self.top <= y <= self.bottom:
                self._scroll_down(min(n, self.bottom - y + 1), at=y)
        elif final == "M":
            if self.top <= y <= self.bottom:
                self._scroll_up(min(n, self.bottom - y + 1), at=y)
        elif final == "S":
            self._scroll_up(n)
        elif final == "T":
            self._scroll_down(n)
        elif final == "r":
            top = (nums[0] or 1) - 1
            bottom = ((nums[1] if len(nums) > 1 else None) or self.rows) - 1
            self.top, self.bottom = max(0, top), min(self.rows - 1, bottom)
            self._go(0, 0)
        elif final == "b":
            for _ in range(n):
                self._put(self.last)
        elif final == "s":
            self.saved = (y, x)
        elif final == "u":
            self._go(*self.saved)

    def _sgr(self, nums):
        bold, reverse, fg, bg = self.pen
        i = 0
        while i < len(nums):
            n = nums[i] or 0
            if n == 0:
                bold, reverse, fg, bg = PLAIN
            elif n == 1:
                bold = True
            elif n in (21, 22):
                bold = False
            elif n == 7:
                reverse = True
            elif n == 27:
                reverse = False
            elif 30 <= n <= 37 or 90 <= n <= 97:
                fg = n % 10
            elif n == 39:
                fg = None
            elif 40 <= n <= 47 or 100 <= n <= 107:
                bg = n % 10
            elif n == 49:
                bg = None
            elif n in (38, 48):
                kind = nums[i + 1] if i + 1 < len(nums) else None
                color = nums[i + 2] if kind == 5 and i + 2 < len(nums) else "other"
                i += 2 if kind == 5 else 4
                if n == 38:
                    fg = color
                else:
                    bg = color
            i += 1
        self.pen = (bold, reverse, fg, bg)


# --------------------------------------------------------------------------- the test bed


def ask(line, port=CMD_PORT):
    """One line straight to the test daemon, for what the pretend radio holds now."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        f = s.makefile("rwb", buffering=0)
        f.write((line + "\n").encode())
        return f.readline().decode().strip()


class Relay:
    """Listens on a free port and passes each line on to a daemon port, and its one answer back.

    sent holds (time, line) for every line. While slow is above 0, every line that is not a
    daemon word is held that many seconds first; holding counts the lines held right now.
    """

    def __init__(self, upstream):
        self.upstream = upstream
        self.sent = []
        self.slow = 0.0
        self.holding = 0
        self.lock = threading.Lock()
        self.open = []  # the sockets of the connections open now, both sides
        self.answered = []  # (time, line) for each answer handed back
        self.holds = {}  # line: seconds that line is held, daemon words too
        self.never = set()  # lines held for good: never forwarded, never answered
        self.connections = 0
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            c, _ = self.srv.accept()
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def drop(self):
        """Close every connection open now, as a daemon restart does; new ones are still taken."""
        with self.lock:
            socks, self.open = self.open, []
        for s in socks:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()

    def _serve(self, c):
        try:
            with self.lock:
                self.connections += 1
            up = socket.create_connection(("127.0.0.1", self.upstream), timeout=10)
            with self.lock:
                self.open += [c, up]
            cf, uf = c.makefile("rwb", buffering=0), up.makefile("rwb", buffering=0)
            for raw in cf:
                line = raw.decode(errors="replace").strip()
                if not line:
                    continue
                self.sent.append((time.monotonic(), line))
                if line in self.never:
                    threading.Event().wait()  # never forwarded, never answered
                pause = self.holds.get(line, self.slow)
                if pause > 0 and (line in self.holds or line.split()[0].lower() not in DAEMON_WORDS):
                    with self.lock:
                        self.holding += 1
                    time.sleep(pause)
                    with self.lock:
                        self.holding -= 1
                uf.write(raw)
                cf.write(uf.readline())
                self.answered.append((time.monotonic(), line))
        except OSError:
            pass

    def lines_since(self, t0):
        return [line for t, line in list(self.sent) if t >= t0]

    def first(self, line, after=0.0):
        return next((t for t, l in list(self.sent) if t >= after and l == line), None)


def free_port():
    """A port nobody listens on: bound for a moment, then let go."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(check, limit=5.0, step=0.1):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        try:
            if check():
                return True
        except OSError:
            pass
        time.sleep(step)
    try:
        return bool(check())
    except OSError:
        return False


WORK = tempfile.mkdtemp(prefix="d750ctrl-test-")
STUBS = os.path.join(WORK, "stubs")
STUB_LOG = os.path.join(WORK, "stub-log.txt")
class Catcher:
    """Listens on a port this test picked, never 8300, and keeps what each connection sent.

    It stands where xara would, so that a frame sent by mistake is seen, and nothing transmits.
    """

    def __init__(self):
        self.got = []
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            c.settimeout(3)
            data = b""
            try:
                while not data.endswith(b"\r"):
                    piece = c.recv(64)
                    if not piece:
                        break
                    data += piece
            except OSError:
                pass
            self.got.append(data)
            c.close()


XARA = Catcher()
XARA_PORT = XARA.port
STUB ='#!/bin/sh\necho "$(basename "$0") $*" >> "$STUB_LOG"\necho "stub $(basename "$0") $*"\n'


def make_stubs():
    os.makedirs(STUBS, exist_ok=True)
    for name in ("xarachat", "openslot", "radiogram", "d750-sstv", "d750-rtty"):
        path = os.path.join(STUBS, name)
        with open(path, "w", encoding="ascii") as f:
            f.write(STUB)
        os.chmod(path, 0o755)


def stub_log():
    try:
        with open(STUB_LOG, encoding="ascii") as f:
            return f.read().splitlines()
    except OSError:
        return []


_confs = [0]


def conf_dir(text=""):
    """A settings folder of the test's own, so the operator's settings stay out."""
    _confs[0] += 1
    path = os.path.join(WORK, f"conf-{_confs[0]}")
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "d750ctrl.conf"), "w", encoding="ascii") as f:
        f.write(f"status_seconds = {STATUS}\nbusy_seconds = {BUSY}\nmycall = W9XYZ\n" + text)
    return path


def child_env(conf, cmd_port, ptt_port, **more):
    env = {k: v for k, v in os.environ.items() if k not in ("LINES", "COLUMNS", "TERMINFO", "NO_COLOR", "ESCDELAY")}
    env.update(TERM="xterm", D750_CONF_DIR=conf, D750_CMD_PORT=str(cmd_port), D750_PTT_PORT=str(ptt_port),
               D750_XARA_PORT=str(XARA_PORT), STUB_LOG=STUB_LOG, PYTHONUNBUFFERED="1",
               PATH=STUBS + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"))
    env.update(more)
    return env


# --------------------------------------------------------------------------- the child


def _take_terminal():
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class Running:
    """d750ctrl on a pseudo terminal of a given size, with the test's model of the screen."""

    def __init__(self, cols, rows, args=(), conf_text="", argv=None, **env):
        self.cmd = Relay(CMD_PORT)
        self.ptt = Relay(PTT_PORT)
        self.master, self.slave = os.openpty()
        self._winsize(cols, rows)
        self.before = termios.tcgetattr(self.slave)
        self.term = Term(cols, rows)
        argv = argv or [sys.executable, SCREEN, *args]
        self.proc = subprocess.Popen(
            argv, stdin=self.slave, stdout=self.slave, stderr=self.slave, cwd=TOP,
            env=child_env(conf_dir(conf_text), self.cmd.port, self.ptt.port, **env),
            start_new_session=True, preexec_fn=_take_terminal, close_fds=True)
        os.set_blocking(self.master, False)

    def _winsize(self, cols, rows):
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def resize(self, cols, rows):
        """A new size: the kernel tells the child with SIGWINCH."""
        self.pump(0.05)
        self.term.resize(cols, rows)
        self._winsize(cols, rows)

    def pump(self, wait):
        readable, _, _ = select.select([self.master], [], [], wait)
        if not readable:
            return False
        try:
            data = os.read(self.master, 65536)
        except OSError:
            return False
        if data:
            self.term.feed(data)
        return bool(data)

    def soak(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.pump(min(0.1, max(0.0, end - time.monotonic())))

    def dump(self):
        return "\n".join(f"  {i}: {row!r}" for i, row in enumerate(self.term.screen()))

    def wait_for(self, check, what, limit=LIMIT):
        end = time.monotonic() + limit
        while True:
            if check():
                return
            left = end - time.monotonic()
            if left <= 0:
                raise Timeout(f"{what} did not happen in {limit:g} s. Cursor {self.term.cursor}, "
                              f"visible {self.term.visible}. Screen:\n{self.dump()}")
            self.pump(min(left, 0.2))

    def press(self, keys):
        os.write(self.master, keys.encode("ascii"))

    def rows(self):
        return self.term.screen()

    def find(self, start):
        for i, row in enumerate(self.rows()):
            if row.startswith(start):
                return i
        return None

    def has(self, text):
        return any(text in row for row in self.rows())

    def shows(self, text, row=None, limit=LIMIT):
        """Wait until text shows at the start of a row (or is the given row)."""
        if row is None:
            self.wait_for(lambda: self.find(text) is not None, f"the text {text!r}", limit)
        else:
            self.wait_for(lambda: self.term.text(row % self.term.rows) == text, f"{text!r} on row {row}", limit)

    def shows_in(self, text, limit=LIMIT):
        self.wait_for(lambda: self.has(text), f"the text {text!r} anywhere", limit)

    def ready(self):
        self.wait_for(lambda: self.term.text(0).startswith(READY), "the status row", 20)
        self.wait_for(lambda: PASTE_ON in bytes(self.term.raw), "bracketed paste turned on", 5)

    def exited(self, limit=LIMIT):
        end = time.monotonic() + limit
        while self.proc.poll() is None:
            if time.monotonic() > end:
                raise Timeout("d750ctrl did not end in time")
            self.pump(0.02)
        self.ended_at = time.monotonic()
        while self.pump(0):
            pass
        return self.proc.returncode

    def settings_back(self):
        assert termios.tcgetattr(self.slave) == self.before, "the terminal's settings were not put back"

    def left_the_screen(self):
        raw = bytes(self.term.raw)
        entered = raw.rfind(ENTER_ALTERNATE)
        assert entered >= 0, "curses never entered the alternate screen"
        assert raw.rfind(LEAVE_ALTERNATE) > entered, "curses.endwin() did not leave the alternate screen"
        on, off = raw.rfind(PASTE_ON), raw.rfind(PASTE_OFF)
        assert on > entered, "bracketed paste was not turned on after the screen was up"
        assert off > on, "the last paste off does not come after the last paste on"
        assert off > raw.rfind(LEAVE_ALTERNATE), "paste off was not written after the terminal was put back"

    def quit_cleanly(self, key="Q"):
        self.press(key)
        code = self.exited()
        assert code == 0, f"exit code {code}"
        self.settings_back()
        self.left_the_screen()

    def end(self):
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=END_SECONDS)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=END_SECONDS)
        finally:
            os.close(self.master)
            os.close(self.slave)


def rows_keep_the_rules(run, skip=()):
    for i, row in enumerate(run.rows()):
        if i in skip:
            continue
        found = lines.problems(row, 40) if row else []
        assert not found, f"row {i} {row!r}: {found}"


# --------------------------------------------------------------------------- bookkeeping

def answer(run, key):
    """Answer a question as a person does: after its quiet time of 0.5 seconds."""
    run.soak(0.7)
    run.press(key)


TOTAL = [0]
FAILED = []


def check(desc, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        FAILED.append(desc)
        print(f"Fail: {desc}" + (f"\n{detail}" if detail else ""), flush=True)


def test(fn):
    """Run one test function; any failure in it is one failed test."""
    TOTAL[0] += 1
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        FAILED.append(fn.__name__)
        text = str(e) or type(e).__name__
        if isinstance(e, AssertionError):
            frame = traceback.extract_tb(e.__traceback__)[-1]
            text = f"line {frame.lineno}: {text}"
        print(f"Fail: {fn.__name__}: {text}", flush=True)


# --------------------------------------------------------------------------- today's run, and more


def todays_run():
    """Today's checks, in today's order, on the face at 120 by 40 with today's options."""
    run = Running(120, 40, ["--ascii", "--theme", "mono", "--plain"])
    try:
        try:
            run.ready()
            run.shows_in("147.040 MHz")
            ok = True
        except Timeout as e:
            ok = False
            check("the face starts", False, str(e))
        if not ok:
            return
        check("both band panels and the command log drawn",
              run.has("Band A") and run.has("Band B") and run.find("Command log") is not None, run.dump())
        check("frequency shown in the panel", run.has("144.390") or run.has("147.040"))
        try:
            run.wait_for(lambda: run.term.visible and run.term.cursor == (2, 0), "the cursor on row 2", 5)
            check("the cursor shows on band A's frequency, row 2", True)
        except Timeout as e:
            check("the cursor shows on band A's frequency, row 2", False, str(e))
        window = 7.5
        t0 = time.monotonic()
        run.soak(window)
        quiet = [l for t, l in list(run.cmd.sent) if t0 <= t < t0 + window]
        cat = [l for l in quiet if l.split()[0].lower() not in DAEMON_WORDS]
        n_fq, n_by0, n_by1 = quiet.count("FQ 0"), quiet.count("BY 0"), quiet.count("BY 1")
        check(f"full sweep every {STATUS} s from the settings: FQ 0 read {n_fq} times in {window:g} s", 2 <= n_fq <= 3)
        check(f"busy every {BUSY:g} s from the settings: BY 0 read {n_by0} times, BY 1 {n_by1} times",
              9 <= n_by0 <= 11 and 9 <= n_by1 <= 11)
        check(f"{len(cat) / window:.1f} commands a second, under 10", len(cat) / window < 10)
        n_state = quiet.count("state")
        check(f"the state every 0.5 s: read {n_state} times in {window:g} s", 10 <= n_state <= 17)

        run.press("\t")
        run.soak(0.6)
        run.press(UP)
        check("Up tunes the active band one step", wait_until(lambda: ask("FQ 1") == "FQ 1,0144400000"))
        before = ask("SQ 1")
        run.press("]")
        check("] raises the squelch", wait_until(lambda: ask("SQ 1") == "SQ 1,4"), before)
        run.soak(1.0)
        t_set = run.cmd.first("SQ 1,4")
        t_back = None if t_set is None else run.cmd.first("SQ 1", after=t_set)
        check("a change is read back at once, not at the next sweep",
              t_set is not None and t_back is not None and t_back - t_set < 0.6, f"{t_set} {t_back}")
        run.press("p")
        check("p cycles the power", wait_until(lambda: ask("PC 1") == "PC 1,2"))
        run.press("m")
        check("m cycles the mode to NFM (code 1)", wait_until(lambda: ask("MD 1") == "MD 1,1"))
        run.press("b")
        check("b makes the band control and transmit", wait_until(lambda: ask("BC") == "BC 1,1"))
        run.soak(0.5)
        run.press("146.520\r")
        check("a typed frequency tunes", wait_until(lambda: ask("FQ 1") == "FQ 1,0146520000"))
        run.soak(0.5)
        run.press("M")
        try:
            run.shows_in("memory channels in 000 to 199", 60)
            run.shows_in("000 146.520 MHz", 5)
            listed = True
        except Timeout as e:
            listed = False
            check("the memory list shows channels", False, str(e))
        if listed:
            check("the memory list shows channels", True)
            check("memory reads stay out of the command log", not run.has("ME 0"), run.dump())
            run.press("\r")
            check("Enter recalls a channel into memory mode", wait_until(lambda: ask("VM 1") == "VM 1,1"))
        tn_before = ask("TN")
        run.press("t")
        try:
            run.wait_for(lambda: run.term.text(39).startswith("TNC to ") and run.term.text(39).endswith("? y or n"),
                         "the TNC question", 5)
            asked = True
        except Timeout:
            asked = False
        answer(run, "n")
        try:
            run.shows("TNC unchanged.", 38, 5)
            said = True
        except Timeout:
            said = False
        check("t asks before changing the TNC and n leaves it",
              asked and said and tn_before.startswith("TN") and ask("TN") == tn_before, run.dump())
        run.press("L")
        check("L locks PTT in the daemon", wait_until(lambda: "; locked" in ask("state")))
        try:
            run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. PTT locked."), "PTT locked shown", 5)
        except Timeout:
            pass
        run.soak(1.5)  # a read that was out before the lock came back can say unlocked for a moment
        run.press("L")
        try:
            run.shows("Unlock PTT? y or n", 39, 5)
            asked = True
        except Timeout:
            asked = False
        answer(run, "n")
        run.soak(0.8)
        check("L again asks, and n keeps the lock",
              asked and "; locked" in ask("state") and run.term.text(38) == "Still locked.", run.dump())
        run.press("L")
        try:
            run.shows("Unlock PTT? y or n", 39, 5)
            answer(run, "y")
            check("L, then y, unlocks", wait_until(lambda: "; unlocked" in ask("state")))
        except Timeout as e:
            check("L, then y, unlocks", False, str(e))
        if "; locked" in ask("state"):
            ask("unlock")  # so that one failure does not become many
        run.soak(0.6)
        run.press(":")
        run.soak(0.5)
        run.press("ID\r")
        try:
            run.shows("Answer: ID TM-D750", 38, 5)
            check("a raw command shows its answer", True)
        except Timeout as e:
            check("a raw command shows its answer", False, str(e))
        run.press("?")
        try:
            run.shows_in("Tab: the other band.", 5)
            run.press(ESC_KEY)
            run.shows("Tab band. Up, Down tune. V view. ? help", 39, 5)
            check("help shows the keys, and Escape goes back", True)
        except Timeout as e:
            check("help shows the keys, and Escape goes back", False, str(e))
        for key, name in (("S", "SSTV"), ("R", "RTTY")):
            run.press(key)
            try:
                run.shows(f"{name}: r receive, s send", 39, 5)
                run.soak(0.7)
                run.press(ESC_KEY)
                run.shows(f"{name}: nothing done.", 38, 5)
                check(f"{key} offers the {name} menu, and Escape leaves it", True)
            except Timeout as e:
                check(f"{key} offers the {name} menu, and Escape leaves it", False, str(e))
            run.soak(0.3)
        # A send is asked last; n sends nothing, and the stub is never run with tx.
        run.press("S")
        run.soak(0.7)
        run.press("s")
        try:
            run.shows("Picture file to send:", 39, 5)
            run.press("~/pic_1.png\r")
            run.shows("SSTV mode, ROBOT 36:", 39, 5)
            run.press("\r")
            run.wait_for(lambda: run.term.text(39).startswith("Send the picture on band B"), "the send question", 5)
            answer(run, "n")
            run.shows("Nothing sent.", 38, 5)
            sent_nothing = not any(" tx" in line for line in stub_log())
            check("an SSTV send is asked last, and n sends nothing", sent_nothing, "\n".join(stub_log()))
        except Timeout as e:
            check("an SSTV send is asked last, and n sends nothing", False, str(e))
        run.soak(0.3)
        # A receive takes the terminal outside the workspace, and gives it back.
        run.press("R")
        run.soak(0.7)
        run.press("r")
        try:
            run.shows("Seconds to listen, 60:", 39, 5)
            run.press("\r")
            run.wait_for(lambda: b"Enter goes back to d750ctrl" in bytes(run.term.raw), "the pause after the tool", 10)
            run.press("\r")
            run.wait_for(lambda: run.term.text(0).startswith(READY), "the screen back", 10)
            check("RTTY receive runs the tool in this terminal and comes back", "d750-rtty rx 60" in stub_log(),
                  "\n".join(stub_log()))
            raw = bytes(run.term.raw)
            ran = raw.find(b"stub d750-rtty rx 60")
            run.wait_for(lambda: bytes(run.term.raw).find(PASTE_ON, ran) > ran, "paste on again after the tool", 5)
            check("the tool gets the terminal with bracketed paste off, and it is on again after",
                  ran > 0 and raw.rfind(PASTE_OFF, 0, ran) > raw.rfind(PASTE_ON, 0, ran), repr(raw[max(0, ran - 300):ran]))
        except Timeout as e:
            check("RTTY receive runs the tool in this terminal and comes back", False, str(e))
        run.press("x")
        try:
            run.wait_for(lambda: "xarachat --tui" in stub_log(), "the chat tool", 10)
            run.wait_for(lambda: run.term.text(0).startswith(READY), "the screen back", 10)
            check("x runs xarachat --tui", True)
        except Timeout as e:
            check("x runs xarachat --tui", False, str(e))
        check("no tool was ever run with tx", not any(" tx" in line for line in stub_log()), "\n".join(stub_log()))
        run.soak(0.5)
        run.press("q")
        try:
            code = run.exited()
            check("q quits", code == 0, f"exit code {code}")
            run.settings_back()
            run.left_the_screen()
            check("q puts the terminal back", True)
        except (Timeout, AssertionError) as e:
            check("q puts the terminal back", False, str(e))
    finally:
        run.end()


# --------------------------------------------------------------------------- the views


def _a_view(view, cols, rows):
    run = Running(cols, rows, ["--view", view, "--no-tmux"])
    try:
        run.ready()
        assert run.term.visible, "the cursor is hidden"
        wide = view == "face" and cols >= 80 and rows >= 12
        if view == "list":
            run.wait_for(lambda: run.term.cursor[1] == 0 and 1 <= run.term.cursor[0] <= rows - 3,
                         "the cursor on column 0 of a row", 5)
            rows_keep_the_rules(run)
        elif wide:
            run.wait_for(lambda: run.term.text(2).startswith("147.040 MHz") and run.term.cursor == (2, 0),
                         "the cursor on band A's frequency", 5)
            assert run.has("Band A") and run.has("Band B")
        else:
            run.wait_for(lambda: run.term.text(1).startswith("A 147.040 MHz") and run.term.cursor == (1, 0),
                         "the cursor on band A's first row", 5)
            rows_keep_the_rules(run)
        assert run.term.text(rows - 1), "the bottom row is empty"
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_list_at_40_by_12():
    _a_view("list", 40, 12)


def test_list_at_120_by_40():
    _a_view("list", 120, 40)


def test_face_at_40_by_12():
    _a_view("face", 40, 12)


def test_face_at_120_by_40():
    _a_view("face", 120, 40)


def test_compact_at_40_by_12():
    _a_view("compact", 40, 12)


def test_compact_at_120_by_40():
    _a_view("compact", 120, 40)


def test_capital_v_goes_round_with_its_question():
    run = Running(40, 12, ["--view=list", "--no-tmux"])
    try:
        run.ready()
        run.press("V")
        run.shows("Face? Letters change the radio. y or n", 11, 5)
        answer(run, "n")
        run.shows("Still the list. y goes to the face.", 10, 5)
        run.press("V")
        run.shows("Face? Letters change the radio. y or n", 11, 5)
        answer(run, "y")
        run.shows("View: face. Letters change the radio.", 10, 5)
        run.wait_for(lambda: run.term.text(1).startswith("A ") and run.term.cursor == (1, 0), "the stacked face", 5)
        run.press("V")
        run.shows("View: compact.", 10, 5)
        run.press("V")
        run.shows("View: list.", 10, 5)
        rows_keep_the_rules(run)
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_keys_section_is_in_force():
    before = ask("PC 0")
    want = f"PC 0,{(int(before.split(',')[1]) + 1) % 4}"
    run = Running(80, 24, ["--no-tmux"], conf_text="[keys]\nact_power = z\n")
    try:
        run.ready()
        run.press("z")
        assert wait_until(lambda: ask("PC 0") == want), f"z did not step the power: {ask('PC 0')} not {want}"
        run.press("p")
        run.shows("Nothing on p. ? lists the keys.", 22, 5)
        assert ask("PC 0") == want, "p still changed the power"
        run.quit_cleanly("q")
    finally:
        run.end()


def test_a_window_too_small():
    run = Running(80, 24, ["--no-tmux"])
    try:
        run.ready()
        before = ask("PC 0")
        run.resize(36, 5)
        run.shows("Window too small. Need 40 by 6.", 0, 5)
        assert run.term.cursor == (0, 0), f"cursor {run.term.cursor}"
        t0 = time.monotonic()
        run.press("p")
        run.soak(1.0)
        assert ask("PC 0") == before, "p changed the power in a window too small"
        assert not any(l.startswith("PC 0,") for l in run.cmd.lines_since(t0)), "a power set was sent"
        run.resize(80, 24)
        run.ready()
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_broken_key_sequence_changes_nothing():
    run = Running(80, 24, ["--no-tmux"])
    try:
        run.ready()
        before = ask("SQ 0")
        t0 = time.monotonic()
        run.press(ESC_KEY)  # alone: curses gives it once ESCDELAY passes
        run.soak(0.4)
        run.press("[")  # squelch down in the face, were it a key
        run.soak(0.15)
        run.press("A")
        run.soak(0.15)
        run.shows("A broken key sequence was dropped.", 22, 5)
        run.press("?")  # a key with an effect: once help shows, the keys before it were taken
        run.shows_in("Tab: the other band.", 5)
        run.press(ESC_KEY)
        run.soak(1.0)
        assert ask("SQ 0") == before, f"the squelch changed: {ask('SQ 0')} not {before}"
        assert not any(l.startswith("SQ 0,") for l in run.cmd.lines_since(t0)), "a squelch set was sent"
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_unkey_and_lock_do_not_wait_behind_a_slow_read():
    run = Running(80, 24, ["--no-tmux"])
    try:
        run.ready()
        run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. Unlocked."), "Unlocked", 5)
        run.soak(0.5)
        run.cmd.slow = 1.5
        assert wait_until(lambda: run.cmd.holding > 0, 8, 0.02), "no read was held"
        t0 = time.monotonic()
        run.press("U")
        assert wait_until(lambda: run.ptt.first("T 0", t0) is not None, 2, 0.02), "T 0 never reached the PTT port"
        t_unkey = run.ptt.first("T 0", t0) - t0
        run.shows("Unkey sent.", 22, 2)
        still_held = run.cmd.holding > 0
        t1 = time.monotonic()
        run.press("L")
        assert wait_until(lambda: run.cmd.first("lock", t1) is not None, 2, 0.02), "lock never reached the daemon"
        t_lock = run.cmd.first("lock", t1) - t1
        run.cmd.slow = 0.0
        assert t_unkey < 0.5, f"T 0 took {t_unkey:.2f} s"
        assert t_lock < 0.5, f"lock took {t_lock:.2f} s"
        assert still_held, "the slow read was over before Unkey sent. showed"
        assert wait_until(lambda: "; locked" in ask("state")), "not locked"
        run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. PTT locked."), "PTT locked", 5)
        run.soak(1.5)  # a read that was out before the lock came back can say unlocked for a moment
        run.press("L")
        run.shows("Unlock PTT? y or n", 23, 5)
        answer(run, "y")
        assert wait_until(lambda: "; unlocked" in ask("state")), "not unlocked"
        run.quit_cleanly("Q")
    finally:
        run.cmd.slow = 0.0
        run.end()


# --------------------------------------------------------------------------- every way out

BUG = (
    "import sys\n"
    f"sys.path.insert(0, {TOP!r})\n"
    "import d750ui.screen_model as m\n"
    "def boom(self, name, early=False):\n"
    "    raise RuntimeError('planted for a test')\n"
    "m.ScreenModel.key = boom\n"
    "import d750ui.screen as s\n"
    "sys.exit(s.main(['--no-tmux']))\n"
)


def _way_out(how, want):
    argv = [sys.executable, "-c", BUG] if how == "bug" else None
    run = Running(40, 12, ["--no-tmux"], argv=argv)
    try:
        run.ready()
        if how == "ctrl-c":
            run.press("\x03")
        elif how == "bug":
            run.press("x")
        else:
            run.proc.send_signal(how)
        code = run.exited()
        assert code == want, f"exit code {code}, not {want}"
        run.settings_back()
        run.left_the_screen()
        if how == "bug":
            found = re.findall(r"Fail:[^\r\n\x1b]*", run.term.raw.decode("latin-1"))
            assert found == ["Fail: a bug in d750ctrl. RuntimeError: planted for a test"], found
            assert not lines.problems(found[0])
    finally:
        run.end()


def test_ctrl_c_puts_the_terminal_back():
    _way_out("ctrl-c", 0)


def test_sigterm_puts_the_terminal_back():
    _way_out(signal.SIGTERM, 128 + signal.SIGTERM)


def test_sighup_puts_the_terminal_back():
    _way_out(signal.SIGHUP, 128 + signal.SIGHUP)


def test_a_bug_puts_the_terminal_back_and_says_fail():
    _way_out("bug", 1)


def test_a_signal_while_typing_puts_the_terminal_back():
    run = Running(40, 12, ["--no-tmux"])
    try:
        run.ready()
        run.press("14")
        run.wait_for(lambda: run.term.text(11).endswith("14"), "the typing line", 5)
        run.proc.send_signal(signal.SIGTERM)
        assert run.exited() == 128 + signal.SIGTERM
        run.settings_back()
        run.left_the_screen()
    finally:
        run.end()


# --------------------------------------------------------------------------- with no terminal


def run_plain(*args, conf_text="", **env):
    environ = child_env(conf_dir(conf_text), free_port(), free_port(), **env)
    done = subprocess.run([sys.executable, SCREEN, *args], stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, env=environ, timeout=30)
    return done.returncode, done.stdout.splitlines(), done.stderr.splitlines()


def test_check_with_no_terminal_and_no_daemon():
    code, out, err = run_plain("--check")
    assert code == 0, err
    assert out[:5] == ["View face.", "Theme dark.", "Digits big.", "Live meters auto.", "Announce message."], out
    for line in out:
        assert not lines.problems(line, 80), (line, lines.problems(line, 80))
    code, out, err = run_plain("--check", conf_text="theme = red\nview = List\n[keys]\nhelp = f1\n")
    assert code == 0, err
    assert out[:5] == ["View list.", "Theme dark.", "Digits big.", "Live meters auto.", "Announce message."], out
    assert "Setting theme skipped. red is not known." in out, out
    code, out, err = run_plain("--check", "--view", "compact", "--ascii", NO_COLOR="1")
    assert out[:3] == ["View compact.", "Theme mono.", "Digits plain."], out
    code, out, err = run_plain("--check", "--theme=blue", NO_COLOR="1")
    assert out[1] == "Theme blue.", out


def test_help_and_bad_options():
    code, out, err = run_plain("--help")
    assert code == 0 and out and out[0] == "d750ctrl: the TM-D750 on one screen.", out
    for line in out:
        assert not lines.problems(line, 80), (line, lines.problems(line, 80))
    for option in ("--view", "--theme", "--digits", "--ascii", "--no-tmux", "--plain", "--step", "--check", "--help"):
        assert any(line.startswith(option + " ") or line.startswith(option + ":") for line in out), option
    assert not any("--inside" in line for line in out), "--inside is hidden"
    for args, name in ((["--view", "wide"], "view"), (["--view=wide"], "view"), (["--theme", "red"], "theme"),
                       (["--digits=huge"], "digits"), (["--view"], "view")):
        code, out, err = run_plain(*args)
        assert code == 2 and err == [f"Fail: no such {name}. Try: d750ctrl --help"], (args, code, err)
    code, out, err = run_plain("--loud")
    assert code == 2 and err == ["Fail: unknown option. Try: d750ctrl --help"], err


def test_no_daemon_is_said_before_curses_starts():
    port = free_port()
    code, out, err = run_plain(D750_CMD_PORT=str(port))
    assert code == 1, (code, out, err)
    assert out == [f"Fail: d750d is not answering on 127.0.0.1:{port} (systemctl --user status d750d)"], out


# --------------------------------------------------------------------------- the parts, with no terminal


def guarded(steps):
    guard = scr.SequenceGuard()
    kept, notes = [], 0
    for key, at in steps:
        code = key if isinstance(key, int) else ord(key)
        out, broken = guard.take(code, at)
        notes += broken
        if out is not None:
            kept.append(out if out > 255 else chr(out))
    return kept, notes


def test_sequence_guard():
    e = ESC_KEY
    assert guarded([(e, 0.0), ("[", 0.1), ("A", 0.2), ("x", 0.3)]) == ([e, "x"], 1)
    assert guarded([(e, 0.0), ("O", 0.1), ("B", 0.15), ("[", 0.2)]) == ([e, "["], 1)
    steps = [(e, 0.0), ("[", 0.05), ("1", 0.06), (";", 0.07), ("5", 0.08), ("A", 0.09), ("k", 0.1)]
    assert guarded(steps) == ([e, "k"], 1)
    assert guarded([(e, 0.0), ("[", 0.05), ("5", 0.06), ("~", 0.07), ("-", 0.08)]) == ([e, "-"], 1)
    assert guarded([(e, 0.0), ("[", 0.6), ("A", 1.2), ("x", 1.3)]) == ([e, "x"], 1)
    steps = [(e, 0.0), ("[", 0.9), ("1", 1.8), (";", 2.7), ("5", 3.6), ("A", 4.5), ("k", 4.6)]
    assert guarded(steps) == ([e, "k"], 1), "each dropped byte starts the second again"
    typed = ["1", "4", "6", ".", "5", "2", "\n"]
    steps = [(e, 0.0), ("[", 0.3)] + [(key, 0.6 + 0.3 * i) for i, key in enumerate(typed)]
    assert guarded(steps) == ([e, "\n"], 1)
    for key in ("\t", "\x7f", "\x08", "\r"):
        assert guarded([(e, 0.0), ("[", 0.1), ("1", 0.2), (key, 0.3), ("5", 0.4)]) == ([e, key, "5"], 1), key
    assert guarded([(e, 0.0), ("[", 0.1)] + [("1", 0.2 + 0.01 * i) for i in range(17)]) == ([e, "1"], 1)
    ones = [("1", 0.2 + 0.01 * i) for i in range(15)]
    assert guarded([(e, 0.0), ("[", 0.1), *ones, ("A", 0.5), ("k", 0.6)]) == ([e, "k"], 1)
    assert guarded([(e, 0.0), ("[", 1.1)]) == ([e, "["], 0)
    assert guarded([(e, 0.0), ("O", 1.1), ("A", 1.15)]) == ([e, "O", "A"], 0)
    assert guarded([(e, 0.0), ("[", 1.0), ("D", 2.0)]) == ([e], 1), "one second is still in"
    assert guarded([("[", 0.0), ("O", 0.1), ("]", 0.2)]) == (["[", "O", "]"], 0)
    assert guarded([(e, 0.0), ("q", 0.1), ("[", 0.2), ("A", 0.3)]) == ([e, "q", "[", "A"], 0)
    assert guarded([(e, 0.0), (e, 0.8), ("[", 1.6), ("C", 1.65)]) == ([e, e], 1)
    steps = [(e, 0.0), ("[", 0.1), ("1", 0.2), ("5", 0.9), ("j", 2.0), ("[", 2.1), ("A", 2.2)]
    assert guarded(steps) == ([e, "j", "[", "A"], 1)
    assert guarded([(e, 0.0), ("[", 0.1), ("5", 0.9), ("j", 1.5)]) == ([e], 1)
    assert guarded([(e, 0.0), ("[", 0.1), (curses.KEY_UP, 0.2), ("A", 0.3)]) == ([e, curses.KEY_UP, "A"], 1)
    assert guarded([(e, 0.0), ("[", 0.1), (e, 0.2), ("[", 0.3), ("B", 0.4)]) == ([e, e], 2)


def test_key_names():
    assert scr.key_name(9) == "tab"
    for n in range(1, 13):
        assert scr.key_name(curses.KEY_F0 + n) == f"f{n}"
    assert scr.key_name(curses.KEY_F0 + 13) is None
    assert scr.key_name(ord("V")) == "V" and scr.key_name(32) == "space"
    assert scr.key_name(curses.KEY_UP) == "up" and scr.key_name(12) == "ctrl-l" and scr.key_name(3) == "ctrl-c"
    assert scr.key_name(1) is None


def test_settings_are_chosen():
    o = scr.Options()
    chosen = scr.choose({}, o, {})
    assert (chosen.view, chosen.theme, chosen.digits, chosen.live_meters, chosen.announce) == \
        ("face", "dark", "big", "auto", "message")
    for value, meant in (("on", "yes"), ("TRUE", "yes"), ("1", "yes"), ("off", "no"), ("false", "no"), ("0", "no")):
        assert scr.choose({"live-meters": value}, o, {}).live_meters == meant, value
    chosen = scr.choose({"live_meters": "maybe", "announce": "loud"}, o, {})
    assert (chosen.live_meters, chosen.announce) == ("auto", "message") and len(chosen.skipped) == 2
    o.view, o.theme = "compact", "mono"
    chosen = scr.choose({"view": "list", "theme": "blue"}, o, {})
    assert (chosen.view, chosen.theme) == ("compact", "mono")
    assert scr.choose({"theme": "blue"}, scr.Options(), {"NO_COLOR": "1"}).theme == "mono"
    assert scr.choose({"theme": "blue"}, scr.Options(), {"NO_COLOR": ""}).theme == "blue"
    opts = scr.parse_args(["--step", "12.5", "--ascii", "--plain"])
    assert scr.step_khz(opts) == 12.5 and opts.digits == "plain" and opts.no_tmux
    assert scr.step_khz(scr.parse_args(["--step=7"])) == 10


def test_the_looks_keep_red_and_green_out():
    look = scr.Look("dark", colors={})
    assert look.theme == "mono", "a terminal with no colors is mono"
    cells, attrs = look.row_attrs("#.#", 3, False, [(0, 3, "history")])
    assert cells == [" ", ".", " "] and attrs[0] & curses.A_REVERSE and not attrs[1] & curses.A_REVERSE
    cells, attrs = look.row_attrs("BUSY", 4, False, [(0, 4, "busy")])
    assert cells == list("BUSY") and attrs[0] & curses.A_REVERSE


def test_carriers_never_raise_for_a_socket_fault():
    dead = free_port()
    ports = scr.Ports(cmd_port=dead, ptt_port=dead, xara_port=dead, mycall="W9XYZ")
    link = scr.Link(dead)
    answers = scr.carry(sm.Ask(("state", "FQ 0"), "state"), link, ports)
    assert len(answers) == 2 and all(a.startswith("ERR ") for a in answers), answers
    assert scr.carry(sm.Unkey(), link, ports).startswith("ERR ")
    assert scr.carry(sm.Windows(), link, ports) == ()
    assert scr.is_urgent(sm.Unkey()) and scr.is_urgent(sm.Set("lock"))
    assert not scr.is_urgent(sm.Set("unlock")) and not scr.is_urgent(sm.Set("SQ 0,4"))


def test_the_frame_is_sent_to_the_port_given():
    catcher = Catcher()
    try:
        assert scr.send_frame(catcher.port, "W9XYZ-7", False) == ""
        assert scr.send_frame(catcher.port, "w9xyz", True) == ""
        assert wait_until(lambda: len(catcher.got) == 2, 5, 0.05), catcher.got
        assert catcher.got == [b"CQFRAME W9XYZ\r", b"CQFRAME W9XYZ-9\r"], catcher.got
        # Refused with the server still open: nothing reaches it.
        assert scr.send_frame(catcher.port, "N0CALL", False).startswith("ERR ")
        assert scr.send_frame(catcher.port, "", False).startswith("ERR ")
        assert scr.send_frame(None, "W9XYZ", False).startswith("ERR ")
        time.sleep(0.5)
        assert len(catcher.got) == 2, catcher.got
    finally:
        catcher.srv.close()
    assert scr.send_frame(free_port(), "W9XYZ", False).startswith("ERR ")


def test_the_frames_port_comes_from_the_environment():
    catcher = Catcher()
    try:
        ports = scr.ports_from({"mycall": "w9xyz"}, {"D750_XARA_PORT": str(catcher.port)}, False)
        assert ports.xara_port == catcher.port, ports.xara_port
        assert scr.carry(sm.SendFrame(False), scr.Link(free_port()), ports) == ""
        assert wait_until(lambda: catcher.got == [b"CQFRAME W9XYZ\r"], 5, 0.05), catcher.got
    finally:
        catcher.srv.close()
    assert scr.ports_from({}, {}, False).xara_port == 8300
    for bad in ("abc", "8300x", "0", "70000", "-1"):
        assert scr.ports_from({}, {"D750_XARA_PORT": bad}, False).xara_port is None, bad
    made = []

    class Recorder:
        def __init__(self, **kwargs):
            made.append(kwargs)

    real = scr.sm.ScreenModel
    scr.sm.ScreenModel = Recorder
    try:
        settings, chosen, keys = {}, scr.choose({}, scr.Options(), {}), scr.keymap.Keymap()
        scr.make_model(settings, chosen, keys, scr.Options(), scr.ports_from({}, {"D750_XARA_PORT": "4999"}, False))
        scr.make_model(settings, chosen, keys, scr.Options(), scr.ports_from({}, {"D750_XARA_PORT": "x"}, False))
    finally:
        scr.sm.ScreenModel = real
    assert [m["xara_port"] for m in made] == [4999, None], made


def test_a_lock_is_tried_once_more_on_a_new_connection():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    port = srv.getsockname()[1]
    seen = []

    def serve():
        c, _ = srv.accept()  # the first: closed before any answer, as a daemon restart does
        c.recv(64)
        c.close()
        c, _ = srv.accept()
        seen.append(c.recv(64))
        c.sendall(b"OK locked, PTT refused until unlock\n")
        c.close()

    threading.Thread(target=serve, daemon=True).start()
    try:
        answer = scr.carry(sm.Set("lock"), scr.Link(free_port()), scr.Ports(cmd_port=port))
    finally:
        srv.close()
    assert answer == "OK locked, PTT refused until unlock", answer
    assert seen == [b"lock\n"], seen


def test_the_quiet_time():
    quiet = scr.QuietTime()
    assert not quiet.early(0.0) and not quiet.key(0.0)
    assert quiet.seen(0, 0.0) is False
    assert quiet.seen(1, 1.0) is True, "a new question opens"
    assert quiet.early(1.0) and quiet.early(1.49)
    assert not quiet.early(1.5)
    assert quiet.seen(1, 1.1) is False, "the same question is not new"
    assert quiet.early(1.2), "the quiet time counts from the opening"
    assert quiet.seen(2, 2.0) is True and quiet.early(2.1), "the second frame question is new"
    assert quiet.seen(0, 2.1) is False and not quiet.early(2.15), "no question, no quiet time"
    # A stream of keys, one every 30 milliseconds for a minute, is early to the last.
    quiet.seen(3, 10.0)
    assert all(quiet.key(10.0 + 0.03 * i) for i in range(1, 2001)), "a key in a stream was not early"
    last = 10.0 + 0.03 * 2000
    assert quiet.key(last + 0.49), "the quiet time starts again at each early key"
    assert not quiet.key(last + 0.49 + 0.5), "half a second with no key ends it"


class PretendWindow:
    """Hands out key codes, as curses would, then -1 once none is pending."""

    def __init__(self, codes):
        self.codes = list(codes)
        self.waits = []

    def getch(self):
        return self.codes.pop(0) if self.codes else -1

    def nodelay(self, flag):
        self.waits.append(("nodelay", flag))

    def timeout(self, ms):
        self.waits.append(("timeout", ms))


class PretendModel:
    """Says which keys are urgent, and keeps what it was given."""

    def __init__(self, urgent=("U", "L", "u")):
        self.urgent_keys = urgent
        self.given = []

    def urgent(self, name):
        return name in self.urgent_keys

    def key(self, name, early=False):
        self.given.append((name, early))
        return ["todo " + name]

    def paste(self, text, left_out=False):
        self.given.append(("paste", text, left_out))
        return []

    def late(self, name):
        self.given.append(("late", name))
        return ["todo late " + str(name)]

    def note(self, text):
        self.given.append(("note", text))


def C(text):
    return [ord(c) for c in text]


def K(text):
    return [("key", ord(c)) for c in text]


def LATE(text):
    return [("late", ord(c)) for c in text]


def P(text, left_out=False):
    return [("paste", text, left_out)]


def pasted(bursts, timed=False):
    """Feed (text or codes, time) bursts, or (None, time) for a poll, to a fresh PasteGuard.
    The times of key items are left out unless timed."""
    guard = scr.PasteGuard()
    items = []
    for burst, at in bursts:
        if burst is None:
            items += guard.poll(at)
        else:
            items += guard.take(C(burst) if isinstance(burst, str) else burst, at)
    if timed:
        return items
    return [item[:2] if item[0] == "key" else item for item in items]


def guarded_pair(bursts):
    """The paste guard and then the key guard, as the loop puts them: (the codes the key guard
    passes on, as text, the times the key items came, how many broken sequences it noted)."""
    keys = scr.SequenceGuard()
    kept, times, notes = [], [], 0
    for item in pasted(bursts, timed=True):
        if item[0] != "key":
            continue
        times.append(item[2])
        code, broken = keys.take(item[1], item[2])
        notes += broken
        if code is not None:
            kept.append(chr(code))
    return "".join(kept), times, notes


def test_the_paste_guard_never_changes_what_the_key_guard_does():
    # A bracket held as the start of a mark, then nothing: poll at 1.2 hands it over with its own
    # time, 0.1, and the key guard drops it as a broken sequence.
    assert guarded_pair([("\x1b", 0.0), ("[", 0.1), (None, 1.2)]) == ("\x1b", [0.0, 0.1], 1)
    # Escape, a bracket, a capital A: both go on at 0.2 with times 0.1 and 0.2, and both are dropped.
    items = pasted([("\x1b", 0.0), ("[", 0.1), ("A", 0.2)], timed=True)
    assert items == [("key", 27, 0.0), ("key", ord("["), 0.1), ("key", ord("A"), 0.2)], items
    assert guarded_pair([("\x1b", 0.0), ("[", 0.1), ("A", 0.2)]) == ("\x1b", [0.0, 0.1, 0.2], 1)
    # The same codes in one burst, as before the paste guard was there.
    assert guarded_pair([("\x1b[A", 0.0)]) == ("\x1b", [0.0, 0.0, 0.0], 1)


def test_paste_guard_whole_pastes_and_keys_around_them():
    assert pasted([(OPEN + "hello world" + CLOSE, 0.0)]) == P("hello world")
    assert pasted([("ab" + OPEN + "x" + CLOSE + "cd", 0.0)]) == K("ab") + P("x") + LATE("cd"), "keys right after an end mark are dropped"
    assert pasted([(OPEN + "a" + CLOSE + OPEN + "b" + CLOSE, 0.0)]) == P("a") + P("b"), "two pastes in one burst"
    assert pasted([("\x1bq", 0.0)]) == K("\x1bq"), "an Escape and a key are keys"
    assert pasted([(OPEN + "a\x1bb" + CLOSE, 0.0)]) == P("ab", True), "an Escape inside is left out"


def test_paste_guard_marks_in_separate_bursts_and_late_codes():
    items = pasted([(OPEN, 0.0), ("hello", 0.1), (CLOSE, 0.2)])
    assert items == LATE("hello") + LATE(CLOSE) + P("hello"), items
    items = pasted([(OPEN + "ab", 0.0), ("U", 0.5), ("L" + CLOSE, 0.6)])
    assert items == LATE("U") + LATE("L" + CLOSE) + P("abUL"), items


def test_paste_guard_a_start_mark_cut_at_every_point():
    for cut in range(1, len(OPEN)):
        head, rest = OPEN[:cut], OPEN[cut:]
        items = pasted([(head, 0.0), (rest + "hi" + CLOSE, 0.5)])
        assert items == K("\x1b") + P("hi"), (cut, items)
        items = pasted([(head, 0.0), ("zz", 0.5)])
        assert items == K(head + "zz"), ("not going on", cut, items)
        items = pasted([(head, 0.0), (None, 1.5), ("zz", 1.6)])
        assert items == K(head + "zz"), ("a second passed", cut, items)
        items = pasted([(head, 0.0), (rest + "hi" + CLOSE, 1.5)])
        assert items[: len(head)] == K(head) and ("key", 27) in items[len(head) :], ("late rest are keys", cut, items)
        assert not any(item[0] == "paste" for item in items), ("late rest are keys", cut, items)


def test_paste_guard_an_end_mark_cut_at_every_point():
    for cut in range(1, len(CLOSE)):
        head, rest = CLOSE[:cut], CLOSE[cut:]
        items = pasted([(OPEN + "hi" + head, 0.0), (rest + "ab", 0.5)])
        if cut == 1:  # an Escape that ends a burst ends the paste and acts; what follows in two seconds is dropped
            assert items == P("hi") + K("\x1b") + LATE(rest + "ab"), (cut, items)
        else:
            assert items == LATE(rest) + P("hi") + LATE("ab"), (cut, items)
        items = pasted([(OPEN + "hi" + head, 0.0), ("zz", 0.5), (None, 3.0)])
        if cut == 1:
            assert items == P("hi") + K("\x1b") + LATE("zz"), (cut, items)
        else:
            assert items == LATE("zz") + P("hi" + head[1:] + "zz", True), (cut, items)


def test_paste_guard_an_escape_then_a_start_mark():
    items = pasted([("\x1b", 0.0), ("[200~hi" + CLOSE, 0.5)])
    assert items == K("\x1b") + P("hi"), items
    items = pasted([("\x1b", 0.0), ("[200~hi" + CLOSE, 1.5)])
    assert items == K("\x1b[200~hi\x1b[201~"), "after a second the rest are keys, for the key guard"
    items = pasted([(OPEN + "ab\x1b", 0.0), ("[201~", 0.3), ("c", 0.4)])
    assert items == P("ab") + K("\x1b") + LATE("[201~c"), "an end mark cut after its Escape is dropped"


def test_paste_guard_a_paste_that_never_ends():
    items = pasted([(OPEN + "abc", 0.0), (None, 1.0)])
    assert items == [], items
    items = pasted([(OPEN + "abc", 0.0), (None, 1.0), (None, 2.5), ("q", 2.6)])
    assert items == P("abc") + K("q"), items
    items = pasted([(OPEN + "abc", 0.0), ("d", 1.5), (None, 3.0), (None, 3.6)])
    assert items == LATE("d") + P("abcd"), "two quiet seconds count from the last code"


def test_paste_guard_text_and_what_is_left_out():
    assert scr.paste_text(C("  a\tb\nc\rd   e  ")) == ("a b c d e", False)
    assert scr.paste_text(C("a") + [7, 200, curses.KEY_UP, 127, 0] + C("b")) == ("ab", True)
    assert scr.paste_text([]) == ("", False)
    items = pasted([(C(OPEN) + [7, 200, curses.KEY_UP] + C(" a\n\nb ") + C(CLOSE), 0.0)])
    assert items == P("a b", True), items
    items = pasted([(OPEN + "x" * 5000 + CLOSE, 0.0)])
    assert items == P("x" * 4096, True), "at most 4,096 characters are kept"
    burst = C(OPEN) + [ord("x")] * (scr.BURST_MOST - len(OPEN) - 3) + C(CLOSE[:3])
    assert len(burst) == scr.BURST_MOST
    items = pasted([(burst, 0.0), (CLOSE[3:] + "k", 0.2)])
    assert items == LATE(CLOSE[3:]) + P("x" * 4096, True) + LATE("k"), items[-3:]


def test_the_wait_after_a_paste():
    blocker = OPEN + "hi" + CLOSE + "y" + CLOSE
    assert pasted([(blocker, 0.0)]) == P("hi") + LATE("y" + CLOSE), "an end mark in the text: the rest is dropped"
    for gap in (0.05, 0.3):
        assert pasted([(OPEN + "hi" + CLOSE, 0.0), ("y" + CLOSE, gap)]) == P("hi") + LATE("y" + CLOSE), gap
    assert pasted([(OPEN + "hi" + CLOSE, 0.0), ("y", 0.6)]) == P("hi") + K("y"), "half a second after, keys act"
    items = pasted([(OPEN + "a" + CLOSE, 0.0), ("b", 0.4), ("c", 0.8), ("d", 1.2), ("e", 1.8)])
    assert items == P("a") + LATE("bcd") + K("e"), "each dropped code starts the wait again"
    items = pasted([(OPEN + "a" + CLOSE, 0.0)] + [("x", i / 10) for i in range(1, 61)])
    assert items == P("a") + LATE("x" * 50) + K("x" * 10), "a held key ends its wait after five seconds"
    items = pasted([(OPEN + "a\x1b", 0.0), ("q", 1.5), ("r", 3.6)])
    assert items == P("a") + K("\x1b") + LATE("q") + K("r"), "two seconds after an Escape ended the paste"
    items = pasted([(OPEN + "a" + CLOSE + "x" + OPEN + "b" + CLOSE, 0.0)])
    assert items == P("a") + LATE("x") + P("b"), "a start mark in a wait starts a new paste"
    guard = scr.PasteGuard()
    guard.take(C(OPEN + "a" + CLOSE + "xy"), 0.0)
    guard.take(C("z"), 0.1)
    assert guard.notes == [scr.WAIT_WORDS], "said once for each paste"
    guard.notes.clear()
    guard.take(C(OPEN + "b"), 1.0)
    guard.take(C("c"), 1.1)
    guard.take(C("d"), 1.2)
    assert guard.notes == [scr.OPEN_WORDS], guard.notes


def test_the_blocker_at_a_question_with_no_clock():
    # At the place of the frame question: no y is ever written to a pretend terminal at a send question.
    blocker = OPEN + "hi" + CLOSE + "y" + CLOSE
    for bursts in ([(blocker, 1.0)], [(OPEN + "hi" + CLOSE, 1.0), ("y" + CLOSE, 1.05)],
                   [(OPEN + "hi" + CLOSE, 1.0), ("y" + CLOSE, 1.3)]):
        model = QuestionModel(question=1, mode="asking")
        keys, win = _keys(model, "", question=1)
        for codes, at in bursts:
            keys.burst(C(codes), at)
        assert not any(given[0] == "y" for given in model.given), (bursts, model.given)
        assert ("late", "y") in model.given and model.question == 1, (bursts, model.given)


def test_a_burst_has_a_limit_and_no_resize():
    win = PretendWindow([ord("a")] * 70000)
    codes, resized = scr.read_burst(win)
    assert len(codes) == scr.BURST_MOST and len(win.codes) == 70000 - scr.BURST_MOST and not resized
    win = PretendWindow([ord("a"), curses.KEY_RESIZE, ord("b")])
    assert scr.read_burst(win, ord("x")) == ([ord("x"), ord("a"), ord("b")], True)


def test_the_quiet_time_asks_the_clock_when_a_key_is_handled():
    clock = [10.0]
    model = QuestionModel()
    keys = scr.Keys(PretendWindow([]), model, lambda todos: False, clock=lambda: clock[0])
    model.question, model.mode = 1, "asking"
    keys.watch()  # the question opens at 10.0
    clock[0] = 10.4
    keys.burst(C("x"), 10.0)  # read at 10.0, handled at 10.4: the quiet time starts again at 10.4
    clock[0] = 10.7
    keys.burst(C("x"), 10.7)
    assert model.given == [("x", True), ("x", True)], model.given


def test_draining_takes_a_paste_to_the_model():
    model = PretendModel()
    items = [("paste", "ab", False), ("key", ord("m"), 1.0), ("key", ord("U"), 1.0)]
    scr.drain(PretendWindow([]), scr.SequenceGuard(), model, lambda todos: False, lambda: 1.0,
              scr.PasteGuard(), items)
    assert model.given == [("paste", "ab", False), ("U", True)], model.given


def test_keys_take_pastes_and_an_open_paste_never_eats_an_unkey():
    for mode in ("main", "typing"):
        model = QuestionModel(mode=mode)
        keys, win = _keys(model, "")
        keys.burst(C(OPEN + "ab"), 1.0)
        keys.burst(C("U"), 1.1)
        assert model.given == [("late", "U"), ("note", scr.OPEN_WORDS)], (mode, model.given)
        keys.burst(C("L"), 1.2)
        assert model.given[2:] == [("late", "L")], ("a late key goes to model.late, said once", mode, model.given)
        keys.poll(4.0)
        assert model.given[-1] == ("paste", "abUL", False), (mode, model.given)
    model = QuestionModel()
    keys, win = _keys(model, "")
    keys.burst(C("1\nm"), 1.0)  # no marks: a digit, Enter and a letter in one burst
    assert model.given == [("1", False), ("enter", False)], model.given
    model = QuestionModel()
    keys, win = _keys(model, "")
    keys.burst(C("\x1b"), 1.0)
    keys.burst(C("[200~x" + CLOSE), 1.2)
    keys.burst(C("["), 1.8)  # after the wait, inside the second after the Escape
    assert model.given == [("esc", False), ("paste", "x", False), ("[", False)], \
        ("a bracket after a paste is a key, not a broken sequence", model.given)


def test_draining_gives_only_unkey_and_lock():
    codes = [ord(c) for c in "y\rUmpL"] + [curses.KEY_UP, 27, ord("["), ord("u"), ord("u")]
    win, model, handed = PretendWindow(codes), PretendModel(), []

    def hand(todos):
        handed.extend(todos)
        return False

    assert scr.drain(win, scr.SequenceGuard(), model, hand, lambda: 1.0) is False
    # The u after Escape and a bracket is the end of a broken sequence, dropped by the guard; the next acts.
    assert model.given == [("U", True), ("L", True), ("u", True)], model.given
    assert handed == ["todo U", "todo L", "todo u"], handed
    assert win.codes == [] and win.waits[-2:] == [("nodelay", True), ("timeout", scr.POLL)], win.waits

    def quits(todos):
        return True

    model = PretendModel()
    win = PretendWindow([ord("U"), ord("L")])
    assert scr.drain(win, scr.SequenceGuard(), model, quits, lambda: 1.0) is True
    assert model.given == [("U", True)] and win.waits[-1] == ("timeout", scr.POLL)


def test_escdelay_default():
    env = {}
    scr.set_escdelay(env)
    assert env == {"ESCDELAY": "100"}
    env = {"ESCDELAY": "40"}
    scr.set_escdelay(env)
    assert env == {"ESCDELAY": "40"}


def test_tool_arguments():
    home = os.path.expanduser("~")
    argv = scr.tool_argv(("d750-sstv", "tx", "~/pic_1.png", "ROBOT_36"))
    assert argv == ["d750-sstv", "tx", os.path.join(home, "pic_1.png"), "ROBOT_36"], argv
    for kept in (("d750-rtty", "tx", "~/pic_1.png"), ("d750-sstv", "rx", "~"), ("radiogram", "new"),
                 ("d750-sstv", "tx", "pic.png", "~"), ("xarachat", "~/x")):
        assert scr.tool_argv(kept) == list(kept), kept
    ports = scr.Ports(rig_key="F9")
    typed = "hi $(touch x); `id` 'q' \"d\""
    win = scr.window_argv(sm.Tool("rtty", ("d750-rtty", "tx", typed), True, None), ports)
    assert win[:3] == ["sh", "-c", scr.PAUSE_SCRIPT] and win[3:] == ["sh", "F9", "d750-rtty", "tx", typed], win
    assert typed not in win[2]
    win = scr.window_argv(sm.Tool("sstv", ("d750-sstv", "tx", "~/p.png", "ROBOT_36"), False, None), ports)
    assert win[:3] == ["sh", "-c", scr.RUN_SCRIPT] and win[5:] == scr.tool_argv(("d750-sstv", "tx", "~/p.png", "ROBOT_36"))
    # The fixed script hands the arguments over whole, as the shell would never read them.
    shown = subprocess.run(scr.window_argv(sm.Tool("x", ("printf", "%s|", typed, "a b"), False, None), ports),
                           capture_output=True, text=True, timeout=10).stdout
    assert shown == f"{typed}|a b|", shown


ESCDELAY_CHILD = (
    "import curses, os, sys\n"
    f"sys.path.insert(0, {TOP!r})\n"
    "out = sys.argv[1]\n"
    "real = curses.initscr\n"
    "def initscr():\n"
    "    with open(out, 'w', encoding='ascii') as f:\n"
    "        f.write(os.environ.get('ESCDELAY', 'unset'))\n"
    "    return real()\n"
    "curses.initscr = initscr\n"
    "import d750ui.screen as s\n"
    "sys.exit(s.main(['--no-tmux']))\n"
)


def test_escdelay_is_set_before_curses_starts():
    for given, want in ((None, "100"), ("40", "40")):
        out = os.path.join(WORK, f"escdelay-{want}.txt")
        env = {} if given is None else {"ESCDELAY": given}
        run = Running(40, 12, argv=[sys.executable, "-c", ESCDELAY_CHILD, out], **env)
        try:
            run.ready()
            run.quit_cleanly("Q")
        finally:
            run.end()
        with open(out, encoding="ascii") as f:
            assert f.read() == want, want


def _unlocked_face():
    run = Running(80, 24, ["--no-tmux"])
    run.ready()
    run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. Unlocked."), "Unlocked", 5)
    run.soak(0.5)
    return run


def test_a_paste_at_a_send_sends_nothing():
    run = _unlocked_face()
    try:
        before = len(stub_log())
        run.press("R")
        run.shows("RTTY: r receive, s send", 23, 5)
        run.soak(0.7)
        run.press("s")
        run.shows("Text to send:", 23, 5)
        run.soak(0.4)
        run.press("hello\ry")  # one write, as a paste comes
        run.soak(1.0)
        bottom = run.term.text(23)
        assert stub_log()[before:] == [], stub_log()[before:]
        assert bottom.startswith("Send this text on band"), f"the question went: {bottom!r}\n{run.dump()}"
        answer(run, "n")
        run.shows("Nothing sent.", 22, 5)
        assert stub_log()[before:] == [], stub_log()[before:]
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_paste_at_the_frame_sends_nothing():
    run = _unlocked_face()
    try:
        before = len(XARA.got)
        run.press("ccy")  # one write: the frame key, its first answer, and a yes
        run.soak(1.0)
        bottom = run.term.text(23)
        assert len(XARA.got) == before, XARA.got
        assert bottom.startswith("Frame:") or bottom.startswith("Send one"), f"no question: {bottom!r}\n{run.dump()}"
        answer(run, "n")
        run.shows("Nothing sent.", 22, 5)
        run.soak(0.5)
        assert len(XARA.got) == before, XARA.got
        run.quit_cleanly("Q")
    finally:
        run.end()


class QuestionModel(PretendModel):
    """A pretend model with a question and a mode: t opens a question, n closes it, 1 starts
    typing and Enter ends it, U is urgent."""

    def __init__(self, question=0, mode="main"):
        super().__init__(urgent=("U",))
        self.question = question
        self.mode = mode

    def key(self, name, early=False):
        self.given.append((name, early))
        if name == "t":
            self.question, self.mode = self.question + 1, "asking"
        elif name == "n" and self.question:
            self.question, self.mode = 0, "main"
        elif name == "1":
            self.mode = "typing"
        elif name == "enter" and self.mode == "typing":
            self.mode = "main"
        return []

    def note(self, text):
        self.given.append(("note", text))


def _keys(model, pending, question=0):
    win = PretendWindow([ord(c) if isinstance(c, str) else c for c in pending])
    keys = scr.Keys(win, model, lambda todos: False, quiet=scr.QuietTime(seconds=0), clock=lambda: 5.0)
    keys.question = question
    return keys, win


def test_the_loops_work_for_one_key_drains_when_the_question_changes():
    # The quiet time is off here (0 seconds), so that only the draining is tested.
    model = QuestionModel()
    keys, win = _keys(model, "yp")
    assert keys.key(ord("t"), 5.0) is False
    assert model.given == [("t", False)] and win.codes == [], (model.given, win.codes)
    model = QuestionModel()
    keys, win = _keys(model, "Uy")
    keys.key(ord("t"), 5.0)
    assert model.given == [("t", False), ("U", True)] and win.codes == [], model.given
    model = QuestionModel(question=3, mode="asking")
    keys, win = _keys(model, "mp", question=3)
    keys.key(ord("n"), 5.0)
    assert model.given == [("n", False)] and win.codes == [], "a question that closes drains too"
    model = QuestionModel(mode="typing")
    keys, win = _keys(model, "mp")
    keys.key(10, 5.0)
    assert model.given == [("enter", False)] and win.codes == [], "a key that ends typing drains"
    model = QuestionModel()
    keys, win = _keys(model, "m")
    keys.key(ord("x"), 5.0)
    assert model.given == [("x", False)] and win.codes == [ord("m")], "nothing changed, nothing drained"
    model = QuestionModel(mode="typing")
    keys, win = _keys(model, "4")
    keys.key(ord("1"), 5.0)
    assert win.codes == [ord("4")], "typing goes on: the next digit is not drained"


def test_urgent_threads_one_of_each_kind():
    gate = threading.Event()
    calls = []

    def carrier(todo):
        calls.append(todo)
        gate.wait(5)
        return "RPRT 0"

    results = queue.Queue()
    urgent = scr.Urgent(scr.Ports(), results, carrier)
    first, second, third, lock = sm.Unkey(), sm.Unkey(), sm.Unkey(), sm.Set("lock")
    assert urgent.put(first) is True
    assert urgent.put(second) is False and urgent.put(third) is False, "a second unkey thread started"
    assert urgent.put(lock) is True, "a lock has a thread of its own"
    assert wait_until(lambda: len(calls) == 2, 2, 0.01) and len(urgent.threads()) == 2, calls
    gate.set()
    urgent.wait()
    got = []
    while not results.empty():
        got.append(results.get_nowait())
    assert sorted(id(item[1]) for item in got) == sorted(id(t) for t in (first, second, third, lock)), got
    assert all(item[0] == "done" and item[2] == "RPRT 0" for item in got), got
    assert urgent.threads() == []
    hang = scr.Urgent(scr.Ports(), queue.Queue(), lambda todo: threading.Event().wait(10))
    hang.put(sm.Unkey())
    hang.put(sm.Set("lock"))
    t0 = time.monotonic()
    hang.wait(0.3)
    assert time.monotonic() - t0 < 0.6, "the wait is bounded in all, not for each thread"


def _unkey_then_end(how):
    run = _unlocked_face()
    try:
        run.ptt.slow = 0.6  # the PTT port answers after a pause
        t0 = time.monotonic()
        if how == "quit":
            run.press("UQ")  # one write
        else:
            run.press("U")
            assert wait_until(lambda: run.ptt.first("T 0", t0) is not None, 3, 0.01), "no unkey went out"
            run.press("\x03")
        code = run.exited()
        assert code == 0, f"exit code {code}"
        assert wait_until(lambda: run.ptt.first("T 0", t0) is not None, 2, 0.02), "the unkey never arrived"
        answered = [t for t, line in run.ptt.answered if line == "T 0" and t >= t0]
        assert answered, "the unkey was not answered"
        assert run.ended_at >= answered[0] - 0.05, \
            f"the program ended {answered[0] - run.ended_at:.2f} s before its unkey was answered"
        run.settings_back()
        run.left_the_screen()
    finally:
        run.ptt.slow = 0.0
        run.end()


def test_an_unkey_then_quit_is_not_lost():
    _unkey_then_end("quit")


def test_an_unkey_then_ctrl_c_is_not_lost():
    _unkey_then_end("ctrl-c")


def test_an_unkey_and_a_lock_both_out_at_quit_both_arrive():
    run = _unlocked_face()
    try:
        run.ptt.holds["T 0"] = 0.6
        run.cmd.holds["lock"] = 1.2  # answered last, so a wait on the first thread only ends too soon
        t0 = time.monotonic()
        run.press("ULQ")  # one write: unkey, lock, quit
        code = run.exited()
        assert code == 0, f"exit code {code}"
        unkey = [t for t, line in run.ptt.answered if line == "T 0" and t >= t0]
        lock = [t for t, line in run.cmd.answered if line == "lock" and t >= t0]
        assert unkey and lock, f"unkey answered {unkey}, lock answered {lock}"
        last = max(unkey[0], lock[0])
        assert run.ended_at >= last - 0.05, f"the program ended {last - run.ended_at:.2f} s before both were answered"
        assert "; locked" in ask("state"), "the lock never reached the daemon"
        assert b"Warn:" not in bytes(run.term.raw), "a warning with both answered"
        run.settings_back()
        run.left_the_screen()
    finally:
        run.ptt.holds.clear()
        run.cmd.holds.clear()
        run.end()
        if "; locked" in ask("state"):
            ask("unlock")


class Silent:
    """Takes connections and never answers."""

    def __init__(self):
        self.held = []
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            self.held.append(c)


def test_a_lock_and_an_unkey_never_answered_are_said():
    silent = Silent()
    run = Running(80, 24, ["--no-tmux"], D750_PTT_PORT=str(silent.port))
    try:
        run.ready()
        run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. Unlocked."), "Unlocked", 5)
        run.soak(0.5)
        run.cmd.never.add("lock")
        t0 = time.monotonic()
        run.press("ULQ")
        code = run.exited()
        assert code == 0, f"exit code {code}"
        assert run.ended_at - t0 < 4.0, f"the wait took {run.ended_at - t0:.1f} s"
        said = re.findall(r"Warn:[^\r\n\x1b]*", run.term.raw.decode("latin-1"))
        assert said == ["Warn: lock not confirmed.", "Warn: unkey not confirmed."], said
        for line in said:
            assert not lines.problems(line, 40), line
        raw = bytes(run.term.raw)
        assert raw.rfind(LEAVE_ALTERNATE) < raw.find(b"Warn:"), "a warning before the terminal was back"
        run.settings_back()
    finally:
        run.cmd.never.clear()
        run.end()
        silent.srv.close()
        if "; locked" in ask("state"):
            ask("unlock")


def test_many_unkeys_start_one_connection():
    run = _unlocked_face()
    try:
        run.ptt.slow = 1.5
        before = run.ptt.connections
        for _ in range(6):
            run.press("U")
            run.soak(0.05)
        run.soak(0.3)
        held = run.ptt.connections - before
        run.ptt.slow = 0.0
        run.shows("Unkey sent.", 22, 5)
        assert held == 1, f"{held} connections while the PTT port held its answer"
        run.quit_cleanly("Q")
    finally:
        run.ptt.slow = 0.0
        run.end()


def test_an_unkey_in_a_paste_ends_the_question_and_the_rest_is_dropped():
    run = _unlocked_face()
    try:
        before = len(stub_log())
        run.press("R")
        run.shows("RTTY: r receive, s send", 23, 5)
        run.soak(0.7)
        run.press("s")
        run.shows("Text to send:", 23, 5)
        run.soak(0.3)
        radio = (ask("MD 0"), ask("PC 0"), ask("BC"))
        t0 = time.monotonic()
        run.press("CQ de W9XYZ\ryou mp b")  # the reviewer's probe, in one write
        assert wait_until(lambda: run.ptt.first("T 0", t0) is not None, 3, 0.02), "the u did not unkey"
        run.soak(1.5)
        assert (ask("MD 0"), ask("PC 0"), ask("BC")) == radio, "the rest of the paste changed the radio"
        sets = [l for l in run.cmd.lines_since(t0) if l.startswith(("MD ", "PC ", "BC")) and "," in l]
        assert sets == [], sets
        assert stub_log()[before:] == [], stub_log()[before:]
        assert not run.term.text(23).startswith("Send this text"), f"the question stayed:\n{run.dump()}"
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_an_unkey_typed_ahead_of_a_question_is_kept():
    run = _unlocked_face()
    try:
        t0 = time.monotonic()
        run.press("RU")  # one write: the RTTY question opens, and the U behind it is drained, not lost
        assert wait_until(lambda: run.ptt.first("T 0", t0) is not None, 3, 0.02), "the unkey never reached the PTT port"
        answer(run, "n")
        run.soak(0.5)
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_stream_of_keys_never_answers_a_question():
    run = _unlocked_face()
    try:
        before = ask("TN")
        run.press("t")
        run.wait_for(lambda: run.term.text(23).startswith("TNC to "), "the TNC question", 5)
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            run.press("y")
            run.soak(0.03)
        run.soak(0.3)  # under the quiet time after the last y
        assert run.term.text(23).startswith("TNC to "), f"the question went:\n{run.dump()}"
        assert ask("TN") == before, f"the TNC changed: {ask('TN')}"
        answer(run, "n")
        run.shows("TNC unchanged.", 22, 5)
        assert ask("TN") == before
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_paste_after_typing_changes_nothing_more():
    run = _unlocked_face()
    try:
        md, pc = ask("MD 0"), ask("PC 0")
        t0 = time.monotonic()
        run.press("146.52\rmp")  # one write: a frequency, its line end, and two face keys
        assert wait_until(lambda: ask("FQ 0") == "FQ 0,0146520000"), "the frequency was not set"
        run.soak(1.5)
        assert (ask("MD 0"), ask("PC 0")) == (md, pc), "a key typed ahead changed the radio"
        sets = [l for l in run.cmd.lines_since(t0) if l.startswith(("MD 0,", "PC 0,"))]
        assert sets == [], sets
        run.press("147.04\r")
        assert wait_until(lambda: ask("FQ 0") == "FQ 0,0147040000")
        run.soak(0.5)
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_marked_paste_at_a_typing_line_is_text_only():
    run = _unlocked_face()
    try:
        before = len(stub_log())
        run.press("R")
        run.shows("RTTY: r receive, s send", 23, 5)
        run.soak(0.7)
        run.press("s")
        run.shows("Text to send:", 23, 5)
        run.soak(0.3)
        run.press(OPEN + "hello\ry" + CLOSE)  # one write: text, a line end and a y, marked
        run.wait_for(lambda: run.term.text(23) == "Text to send: hello y", "the pasted text in the line", 5)
        run.shows("Pasted 7 characters. Enter applies.", 22, 5)
        run.soak(1.0)
        assert run.term.text(23) == "Text to send: hello y", "the line changed after the paste"
        assert stub_log()[before:] == [], stub_log()[before:]
        run.press(ESC_KEY)
        run.wait_for(lambda: not run.term.text(23).startswith("Text to send"), "Escape cancels", 5)
        assert stub_log()[before:] == [], stub_log()[before:]
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_marked_paste_in_the_face_sets_nothing():
    run = _unlocked_face()
    try:
        radio = [ask(line) for line in ("FQ 0", "MD 0", "PC 0", "SQ 0", "BC", "TN")]
        t0 = time.monotonic()
        run.press(OPEN + "mpb][t146.52\rUL" + CLOSE)
        run.shows("A paste was dropped.", 22, 5)
        run.soak(1.5)
        assert [ask(line) for line in ("FQ 0", "MD 0", "PC 0", "SQ 0", "BC", "TN")] == radio, "the paste changed the radio"
        sets = [l for l in run.cmd.lines_since(t0) if "," in l or l.split()[0].lower() in ("lock", "unlock")]
        assert sets == [], sets
        assert run.ptt.first("T 0", t0) is None, "a paste in one burst unkeyed"
        assert run.term.text(23) == "Tab band. Up, Down tune. V view. ? help", run.term.text(23)
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_marked_paste_at_a_question_leaves_it_open():
    run = _unlocked_face()
    try:
        before = ask("TN")
        run.press("t")
        run.wait_for(lambda: run.term.text(23).startswith("TNC to "), "the TNC question", 5)
        question = run.term.text(23)
        run.soak(0.7)
        run.press(OPEN + "y" + CLOSE)
        run.shows("A paste was dropped.", 22, 5)
        run.soak(1.0)
        assert run.term.text(23) == question and ask("TN") == before, run.dump()
        answer(run, "n")
        run.shows("TNC unchanged.", 22, 5)
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_an_open_paste_never_eats_an_unkey():
    run = _unlocked_face()
    try:
        t0 = time.monotonic()
        run.press(OPEN + "abc")  # a paste left open
        run.soak(0.3)
        run.press("U")  # the unkey key, in a later burst
        assert wait_until(lambda: run.ptt.first("T 0", t0) is not None, 2, 0.02), "the unkey was eaten by the paste"
        run.shows("A paste was dropped.", 22, 5)  # two quiet seconds end the paste
        run.quit_cleanly("Q")
    finally:
        run.end()


def _lock_and_ask(run):
    """Lock, then open the unlock question. Returns when it shows."""
    run.press("L")
    assert wait_until(lambda: "; locked" in ask("state")), "not locked"
    run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. PTT locked."), "PTT locked", 5)
    run.soak(1.5)  # a read that was out before the lock came back can say unlocked for a moment
    run.press("L")
    run.shows("Unlock PTT? y or n", 23, 5)
    run.soak(0.7)


def _still_locked_then_unlock(run):
    run.soak(1.5)
    assert "; locked" in ask("state"), "the paste unlocked"
    assert run.term.text(23) == "Unlock PTT? y or n", f"the question went:\n{run.dump()}"
    answer(run, "n")
    run.shows("Still locked.", 22, 5)
    run.soak(0.7)
    run.press("L")
    run.shows("Unlock PTT? y or n", 23, 5)
    answer(run, "y")
    assert wait_until(lambda: "; unlocked" in ask("state")), "not unlocked"


def test_the_blocker_at_the_unlock_question():
    run = _unlocked_face()
    try:
        _lock_and_ask(run)
        run.press(OPEN + "hi" + CLOSE + "y" + CLOSE)  # one write: a paste whose text holds an end mark and a y
        _still_locked_then_unlock(run)
        run.quit_cleanly("Q")
    finally:
        if "; locked" in ask("state"):
            ask("unlock")
        run.end()


def test_the_blocker_in_separate_writes():
    for gap in (0.05, 0.3):
        run = _unlocked_face()
        try:
            _lock_and_ask(run)
            run.press(OPEN + "hi" + CLOSE)
            time.sleep(gap)
            run.press("y" + CLOSE)
            _still_locked_then_unlock(run)
            run.quit_cleanly("Q")
        finally:
            if "; locked" in ask("state"):
                ask("unlock")
            run.end()


def test_a_paste_then_letters_in_the_wait_set_nothing():
    run = _unlocked_face()
    try:
        radio = [ask(line) for line in ("MD 0", "PC 0", "BC")]
        t0 = time.monotonic()
        run.press(OPEN + "x" + CLOSE)
        time.sleep(0.2)
        run.press("mpb")
        run.shows("A key after a paste was dropped.", 22, 5)
        run.soak(1.5)
        assert [ask(line) for line in ("MD 0", "PC 0", "BC")] == radio, "a letter after the paste changed the radio"
        assert [l for l in run.cmd.lines_since(t0) if "," in l] == [], run.cmd.lines_since(t0)
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_a_late_lock_key_while_locked_does_nothing():
    run = _unlocked_face()
    try:
        _lock_and_ask(run)
        answer(run, "n")
        run.shows("Still locked.", 22, 5)
        run.soak(0.7)
        run.press(OPEN + "abc")  # a paste left open
        run.soak(0.3)
        run.press("L")  # the lock key, late in the paste, while locked
        run.shows("A paste is open. Escape ends it.", 22, 5)
        run.soak(1.0)
        assert run.term.text(23) != "Unlock PTT? y or n", "the late lock key asked to unlock"
        assert "; locked" in ask("state")
        run.shows("A paste was dropped.", 22, 5)
        run.soak(0.7)
        run.press("L")
        run.shows("Unlock PTT? y or n", 23, 5)
        answer(run, "y")
        assert wait_until(lambda: "; unlocked" in ask("state")), "not unlocked"
        run.quit_cleanly("Q")
    finally:
        if "; locked" in ask("state"):
            ask("unlock")
        run.end()


def test_an_escape_then_a_bracket_alone_sets_nothing():
    run = _unlocked_face()
    try:
        before = ask("SQ 0")
        t0 = time.monotonic()
        run.press(ESC_KEY)  # alone: curses gives it once ESCDELAY passes
        run.soak(0.4)
        run.press("[")  # squelch down in the face, were it a key; then nothing more
        run.shows("A broken key sequence was dropped.", 22, 5)
        run.soak(2.0)
        assert ask("SQ 0") == before, f"the squelch changed: {ask('SQ 0')} not {before}"
        assert not any(l.startswith("SQ 0,") for l in run.cmd.lines_since(t0)), "a squelch set was sent"
        run.quit_cleanly("Q")
    finally:
        run.end()


def test_check_and_help_write_no_paste_bytes():
    for args in (("--check",), ("--help",)):
        environ = child_env(conf_dir(), free_port(), free_port())
        done = subprocess.run([sys.executable, SCREEN, *args], stdin=subprocess.DEVNULL, capture_output=True,
                              env=environ, timeout=30)
        assert b"\x1b[?2004" not in done.stdout + done.stderr, args


def test_the_first_lock_after_a_restart_is_kept():
    run = _unlocked_face()
    try:
        run.cmd.drop()  # every connection to the daemon ends, as when it restarts
        run.press("L")
        assert wait_until(lambda: "; locked" in ask("state")), "the lock was lost"
        run.wait_for(lambda: run.term.text(0).startswith("d750ctrl. Receiving. PTT locked."), "PTT locked", 5)
        run.soak(1.5)
        run.press("L")
        run.shows("Unlock PTT? y or n", 23, 5)
        answer(run, "y")
        assert wait_until(lambda: "; unlocked" in ask("state")), "not unlocked"
        run.quit_cleanly("Q")
    finally:
        if "; locked" in ask("state"):
            ask("unlock")
        run.end()


# --------------------------------------------------------------------------- the run


def start_test_bed():
    """The test bed, in a process group of its own, so that only it is ended afterwards."""
    proc = subprocess.Popen(["sh", os.path.join(HERE, "test-env.sh")], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    if not wait_until(lambda: ask("state").startswith("port open"), 20, 0.25):
        print("Fail: the test bed did not start.", flush=True)
    return proc


def stop_test_bed(proc):
    """End this run's test bed: its own child and that child's process group, nothing else."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)


def main():
    make_stubs()
    for fn in (test_sequence_guard, test_key_names, test_settings_are_chosen, test_the_looks_keep_red_and_green_out,
               test_carriers_never_raise_for_a_socket_fault, test_the_frame_is_sent_to_the_port_given,
               test_the_frames_port_comes_from_the_environment, test_a_lock_is_tried_once_more_on_a_new_connection,
               test_the_quiet_time, test_draining_gives_only_unkey_and_lock, test_paste_guard_whole_pastes_and_keys_around_them,
               test_paste_guard_marks_in_separate_bursts_and_late_codes, test_paste_guard_a_start_mark_cut_at_every_point,
               test_paste_guard_an_end_mark_cut_at_every_point, test_paste_guard_an_escape_then_a_start_mark,
               test_paste_guard_a_paste_that_never_ends, test_paste_guard_text_and_what_is_left_out,
               test_keys_take_pastes_and_an_open_paste_never_eats_an_unkey, test_check_and_help_write_no_paste_bytes,
               test_the_paste_guard_never_changes_what_the_key_guard_does, test_the_wait_after_a_paste,
               test_the_blocker_at_a_question_with_no_clock, test_a_burst_has_a_limit_and_no_resize,
               test_the_quiet_time_asks_the_clock_when_a_key_is_handled, test_draining_takes_a_paste_to_the_model,
               test_the_loops_work_for_one_key_drains_when_the_question_changes, test_urgent_threads_one_of_each_kind,
               test_escdelay_default, test_tool_arguments,
               test_check_with_no_terminal_and_no_daemon, test_help_and_bad_options,
               test_no_daemon_is_said_before_curses_starts):
        test(fn)
    bed = start_test_bed()
    try:
        todays_run()
        for fn in (test_list_at_40_by_12, test_list_at_120_by_40, test_face_at_40_by_12, test_face_at_120_by_40,
                   test_compact_at_40_by_12, test_compact_at_120_by_40, test_capital_v_goes_round_with_its_question,
                   test_a_keys_section_is_in_force, test_a_window_too_small, test_a_broken_key_sequence_changes_nothing,
                   test_unkey_and_lock_do_not_wait_behind_a_slow_read, test_ctrl_c_puts_the_terminal_back,
                   test_sigterm_puts_the_terminal_back, test_sighup_puts_the_terminal_back,
                   test_a_bug_puts_the_terminal_back_and_says_fail, test_a_signal_while_typing_puts_the_terminal_back,
                   test_escdelay_is_set_before_curses_starts, test_a_paste_at_a_send_sends_nothing,
                   test_a_paste_at_the_frame_sends_nothing, test_the_first_lock_after_a_restart_is_kept,
                   test_an_unkey_typed_ahead_of_a_question_is_kept, test_a_stream_of_keys_never_answers_a_question,
                   test_a_paste_after_typing_changes_nothing_more, test_an_unkey_then_quit_is_not_lost,
                   test_an_unkey_then_ctrl_c_is_not_lost, test_an_unkey_and_a_lock_both_out_at_quit_both_arrive,
                   test_a_lock_and_an_unkey_never_answered_are_said, test_many_unkeys_start_one_connection,
                   test_an_unkey_in_a_paste_ends_the_question_and_the_rest_is_dropped,
                   test_a_marked_paste_at_a_typing_line_is_text_only, test_a_marked_paste_in_the_face_sets_nothing,
                   test_a_marked_paste_at_a_question_leaves_it_open, test_an_open_paste_never_eats_an_unkey,
                   test_an_escape_then_a_bracket_alone_sets_nothing, test_the_blocker_at_the_unlock_question,
                   test_the_blocker_in_separate_writes, test_a_paste_then_letters_in_the_wait_set_nothing,
                   test_a_late_lock_key_while_locked_does_nothing):
            test(fn)
    finally:
        stop_test_bed(bed)
    if FAILED:
        print(f"Fail: d750ctrl, {len(FAILED)} of {TOTAL[0]} tests.")
        return 1
    print(f"Pass: d750ctrl, {TOTAL[0]} tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
