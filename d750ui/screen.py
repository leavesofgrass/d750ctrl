"""d750ui.screen: the program d750ctrl, the thin curses part of the rig screen.

It reads a key, names it, asks the model in d750ui.screen_model, hands the things to do
to the worker threads through queues, and paints the frame the model gives. Curses is
called on the main thread only. One worker does the daemon's command port and the tmux
calls. Unkey and Set("lock") each run in a short thread of their own, on a fresh
connection, so that neither waits behind a sweep, a memory read or each other. Keys typed
ahead of a question, or after typing ends, are drained: only unkey and lock act on them.
carry() is the one place a thing to do meets a socket, and has no curses in it. A tool
that takes the terminal runs on the main thread.

Keys are read in bursts: one key, then every key ready with no waiting. PasteGuard finds
the marks of a bracketed paste in them, so that a paste is never keys: it goes to the
model as text, which keeps it in a typing line and drops it everywhere else.

Every way out puts the terminal back as it was: quit, Ctrl+C, SIGTERM, SIGHUP, SIGQUIT
(Ctrl+backslash) and a bug, which then prints one line starting "Fail:" and exits 1. While
the screen's own loop runs, a signal is only noted, and the loop takes the way out between
keys, after every key it read has acted; then each key still waiting goes to the late path,
so that an unkey typed just ahead of Ctrl+C still unkeys. NOFLSH is set while the screen is
up, so that the signal keys do not throw those keys away. The tmux workspace is ended last,
after the terminal is back, since ending it ends this terminal too.

Importing this module only defines things: the settings are read in main().

GPL-2.0-or-later.
"""

import curses
import os
import queue
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import termios
import threading
import time

from d750ui import keymap, lines
from d750ui import screen_model as sm

HELP = (
    "d750ctrl: the TM-D750 on one screen.",
    "Usage: d750ctrl, options if wanted.",
    "--view NAME: list, face or compact.",
    "--theme NAME: mono, dark or blue.",
    "--digits NAME: big or plain.",
    "--ascii: the same as --digits plain.",
    "--step KHZ: the tuning step in kHz.",
    "Steps: 5, 6.25, 10, 12.5, 15 or 20.",
    "Or 25, 50 or 100. 10 by default.",
    "--no-tmux: no tool windows. One terminal.",
    "--plain: the same as --no-tmux.",
    "--check: say the settings and the keys.",
    "--help: say this.",
    "The settings file is d750ctrl.conf.",
    "Its folder is .config/d750ctrl at home.",
    "Keys: press ? on the screen.",
    "GPL-2.0-or-later.",
)
POLL = 100  # milliseconds a key is waited for before the results and the clock are looked at
EXIT_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)  # SIGQUIT is Ctrl+backslash
LONGEST = 80

# The settings the screen chooses from, each with its words and its default first.
CHOICES = {
    "view": ("face", "list", "compact"),
    "theme": ("dark", "mono", "blue"),
    "digits": ("big", "plain"),
    "live_meters": ("auto", "yes", "no"),
    "announce": ("message", "cursor"),
}
OLDER_LIVE = {"on": "yes", "true": "yes", "1": "yes", "off": "no", "false": "no", "0": "no"}
NAMED_OPTIONS = ("view", "theme", "digits")  # the options that take a name
NONE_SKIPPED = "No settings line was skipped."
STEPS_KHZ = (5, 6.25, 10, 12.5, 15, 20, 25, 50, 100)

TMUX_SOCKET = "d750"  # a tmux server of its own, so nothing here touches the operator's other tmux sessions
SESSION = "d750"
XARA_PORT = 8300


# --------------------------------------------------------------------------- settings


def conf_dir(environ=None):
    environ = os.environ if environ is None else environ
    return environ.get("D750_CONF_DIR") or os.path.expanduser("~/.config/d750ctrl")


def _lines(environ=None):
    """Every settings line as (line number, in the keys section, lowercase name, value)."""
    found = []
    in_keys = False
    try:
        with open(os.path.join(conf_dir(environ), "d750ctrl.conf"), encoding="utf-8", errors="replace") as f:
            for number, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_keys = line[1:-1].strip().lower() == "keys"
                    continue
                if "=" in line:
                    name, value = line.split("=", 1)
                    found.append((number, in_keys, name.strip().lower(), value.strip()))
                elif in_keys:
                    found.append((number, True, line.lower(), None))
    except OSError:
        pass
    return found


def read_conf(environ=None):
    """The settings as a dict of lowercase names to text. A missing file is no settings.

    The lines of the [keys] section are not settings; read_keys() gives those.
    """
    return {name: value for _number, in_keys, name, value in _lines(environ) if not in_keys}


def read_keys(environ=None):
    """The lines of the [keys] section as (line number, lowercase name, value), in file order.

    A line that is [keys], in any case, starts the section; any other line in square
    brackets ends it. A line of the section with no equals sign comes with value None.
    """
    return [(number, name, value) for number, in_keys, name, value in _lines(environ) if in_keys]


def conf_seconds(conf, key, default, least):
    """A time from the settings in seconds, no shorter than least; 0 stays 0 (off). A bad value is the default."""
    try:
        v = float(conf.get(key) or default)
    except ValueError:
        return default
    if v != v:
        return default
    return 0.0 if v <= 0 else max(least, v)


def port(environ, name, conf, key, default):
    """A port from the environment, else the settings, else the default."""
    for value in (environ.get(name), conf.get(key)):
        if value:
            try:
                return int(value)
            except ValueError:
                pass
    return default


def xara_port(environ):
    """xara's port: D750_XARA_PORT, else 8300. None when it is set and is not a port number:
    the frame is then refused, and never goes to 8300 instead."""
    value = environ.get("D750_XARA_PORT")
    if value is None or value == "":
        return XARA_PORT
    try:
        number = int(value.strip())
    except ValueError:
        return None
    return number if 0 < number < 65536 else None


class Ports:
    """Where things are: the daemon's two ports, xara's port, and the workspace's keys."""

    def __init__(self, cmd_port=4533, ptt_port=4532, xara_port=XARA_PORT, mycall="N0CALL",
                 workspace=False, rig_key="F9", next_key="F12"):
        self.cmd_port = cmd_port
        self.ptt_port = ptt_port
        self.xara_port = xara_port
        self.mycall = mycall
        self.workspace = workspace
        self.rig_key = rig_key
        self.next_key = next_key


def ports_from(conf, environ, workspace):
    return Ports(
        cmd_port=port(environ, "D750_CMD_PORT", conf, "cmd_port", 4533),
        ptt_port=port(environ, "D750_PTT_PORT", conf, "ptt_port", 4532),
        xara_port=xara_port(environ),
        mycall=(conf.get("mycall") or "").upper() or "N0CALL",
        workspace=workspace,
        rig_key=conf.get("rig_key") or "F9",
        next_key=conf.get("next_key") or "F12",
    )


# --------------------------------------------------------------------------- the workspace


def tmux(*args, capture=False):
    """One tmux call on the workspace's own server. Never raises for a missing tmux."""
    cmd = ["tmux", "-L", TMUX_SOCKET, *args]
    try:
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
        return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "" if capture else 1


def tmux_windows():
    return tmux("list-windows", "-t", SESSION, "-F", "#W", capture=True).split()


def workspace_start(conf, args):
    """Run this screen inside its own tmux session so each tool gets a window of its own and keeps
    running while the operator tunes. Returns only when tmux cannot be used; the caller then runs plainly."""
    if shutil.which("tmux") is None or not sys.stdout.isatty():
        return
    cmd = shlex.join([sys.executable, os.path.abspath(sys.argv[0]), *args, "--inside"])
    rig_key, next_key = conf.get("rig_key") or "F9", conf.get("next_key") or "F12"
    if tmux("has-session", "-t", SESSION) == 0:
        if "rig" not in tmux_windows():
            tmux("new-window", "-t", SESSION, "-n", "rig", cmd)
        tmux("select-window", "-t", f"{SESSION}:rig")
    else:
        if tmux("new-session", "-d", "-s", SESSION, "-n", "rig", cmd) != 0:
            return
        for opt in (("status-left", "d750 windows: "), ("status-left-length", "16"), ("status-right", ""),
                    ("window-status-format", "#I #W"), ("window-status-current-format", "[#I #W]"),
                    ("window-status-separator", "  "), ("status-style", "default"), ("escape-time", "25"),
                    ("mouse", "off"), ("allow-rename", "off"), ("automatic-rename", "off"), ("set-titles", "off")):
            tmux("set-option", "-g", *opt)
        tmux("bind-key", "-n", rig_key, "select-window", "-t", f"{SESSION}:rig")
        tmux("bind-key", "-n", next_key, "next-window")
    os.execvp("tmux", ["tmux", "-L", TMUX_SOCKET, "attach-session", "-t", SESSION])


# --------------------------------------------------------------------------- carrying out


class Link:
    """One connection to the daemon's command port: one line in, one line out.

    Never raises for a socket fault: the answer is then "ERR " and the reason, and the
    next line connects again.
    """

    def __init__(self, cmd_port):
        self.cmd_port = cmd_port
        self.sock = None
        self.f = None
        self.answered = False  # whether the last line got an answer from the daemon

    def ask(self, line):
        self.answered = False
        try:
            if self.sock is None:
                self.sock = socket.create_connection(("127.0.0.1", self.cmd_port), timeout=5)
                self.f = self.sock.makefile("rwb", buffering=0)
            self.f.write((line + "\n").encode())
            reply = self.f.readline()
            if not reply:
                raise OSError("the daemon closed the connection")
            self.answered = True
            return reply.decode(errors="replace").strip()
        except OSError as e:
            self.close()
            return f"ERR {e}"

    def close(self):
        sock, self.sock, self.f = self.sock, None, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def ptt(ptt_port, line):
    """One line to the daemon's PTT port, on a connection of its own. The answer, or ERR."""
    try:
        with socket.create_connection(("127.0.0.1", ptt_port), timeout=5) as s:
            s.sendall((line + "\n").encode())
            reply = s.makefile("rb").readline()
        if not reply:
            return "ERR the daemon closed the connection"
        return reply.decode(errors="replace").strip()
    except OSError as e:
        return f"ERR {e}"


def lock(cmd_port):
    """lock on a fresh connection; a lock that fails before an answer is tried once more on a
    new one, so the first lock after the daemon restarted is not lost."""
    answer = ""
    for _ in range(2):
        link = Link(cmd_port)
        try:
            answer = link.ask("lock")
            if link.answered:
                return answer
        finally:
            link.close()
    return answer


def send_frame(xara_port, mycall, beacon):
    """VarAC's CQ frame, CQFRAME CALL, to xara; a beacon is the same with SSID 9.

    An empty text when it was handed over, else ERR and the reason. A call that is not
    set is refused here too, whatever the model said, and so is a port that is not a number.
    """
    call = (mycall or "").split("-")[0].strip().upper()
    if not call or call == "N0CALL":
        return "ERR mycall is not set"
    if not isinstance(xara_port, int) or isinstance(xara_port, bool):
        return "ERR the frame's port is not a number"
    try:
        with socket.create_connection(("127.0.0.1", xara_port), timeout=5) as s:
            s.sendall(f"CQFRAME {call}{'-9' if beacon else ''}\r".encode())
            time.sleep(0.5)
        return ""
    except OSError as e:
        return f"ERR {e}"


def tool_argv(argv):
    """The argv a tool is run with: a picture path for d750-sstv tx has its ~ made the home folder,
    as today's screen did, since neither tmux's quoting nor subprocess does it."""
    argv = list(argv)
    if len(argv) >= 3 and os.path.basename(argv[0]) == "d750-sstv" and argv[1] == "tx":
        argv[2] = os.path.expanduser(argv[2])
    return argv


# The fixed scripts a tool's window runs with sh -c. The program and its arguments come after the
# script as "$@", and the rig key as $1 before them: nothing typed is ever part of a script.
RUN_SCRIPT = 'shift; exec "$@"'
PAUSE_SCRIPT = ('key=$1; shift; "$@"; '
                'printf "\\nDone. Enter closes this window. %s is the rig screen.\\n" "$key"; read _')


def window_argv(todo, ports):
    """What follows tmux new-window's options: sh, a fixed script, and the arguments one by one.

    tmux runs a command of more than one argument itself, with no shell reading it as a line.
    """
    script = PAUSE_SCRIPT if todo.pause else RUN_SCRIPT
    return ["sh", "-c", script, "sh", str(ports.rig_key), *tool_argv(todo.argv)]


def tool_in_workspace(todo, ports):
    """A tool in the workspace: go to its window, or open one. The result word."""
    argv = tool_argv(todo.argv)
    if shutil.which(argv[0]) is None:
        return "missing"
    names = tmux_windows()
    if todo.other and todo.other in names:
        tmux("select-window", "-t", f"{SESSION}:{todo.other}")
        return "other"
    if todo.name in names:
        tmux("select-window", "-t", f"{SESSION}:{todo.name}")
        return "selected"
    opened = tmux("new-window", "-t", SESSION, "-n", todo.name, *window_argv(todo, ports))
    return "opened" if opened == 0 else "failed"


def is_urgent(todo):
    """Unkey and Set("lock") each run in a short thread of their own, never behind a read."""
    if isinstance(todo, sm.Unkey):
        return True
    return isinstance(todo, sm.Set) and str(todo.line).strip().lower() == "lock"


def carry(todo, link, ports):
    """Carry out one thing to do against a link. Returns its result. No curses here."""
    if isinstance(todo, sm.Ask):
        return tuple(link.ask(line) for line in todo.lines)
    if isinstance(todo, sm.Set):
        if is_urgent(todo):
            return lock(ports.cmd_port)
        return link.ask(todo.line)
    if isinstance(todo, sm.Unkey):
        return ptt(ports.ptt_port, "T 0")
    if isinstance(todo, sm.Clock):
        return link.ask("RT " + time.strftime("%y%m%d%H%M%S"))
    if isinstance(todo, sm.SendFrame):
        return send_frame(ports.xara_port, ports.mycall, todo.beacon)
    if isinstance(todo, sm.MemoryRead):
        return tuple((n, link.ask(f"ME {n:03d}")) for n in range(todo.first, todo.last + 1))
    if isinstance(todo, sm.Tool):
        if not ports.workspace:
            raise RuntimeError("a tool outside the workspace runs on the main thread")
        return tool_in_workspace(todo, ports)
    if isinstance(todo, sm.Windows):
        if not ports.workspace:
            return ()
        return tuple(w for w in tmux_windows() if w != "rig")
    raise RuntimeError(f"no carrier for {type(todo).__name__}")


class Worker:
    """A thread that takes things to do from a queue and puts what came of them on results."""

    def __init__(self, link, ports, results, name):
        self.link = link
        self.ports = ports
        self.results = results
        self.jobs = queue.Queue()
        self.thread = threading.Thread(target=self._run, name=name, daemon=True)

    def start(self):
        self.thread.start()

    def put(self, todo):
        self.jobs.put(todo)

    def stop(self):
        self.jobs.put(None)

    def _run(self):
        try:
            while True:
                todo = self.jobs.get()
                if todo is None:
                    return
                try:
                    result, error = carry(todo, self.link, self.ports), None
                except Exception as e:  # handed to the model, which says it
                    result, error = None, e
                self.results.put(("done", todo, result, error, time.strftime("%H:%M:%S")))
        except BaseException as e:  # a thread never dies silently: the main thread raises it
            self.results.put(("dead", e))


def run_here(win, todo, signals=None):
    """A tool outside the workspace takes this terminal, and gives it back when it ends.

    signals, the session's Signals: a way out already noted is taken before the tool starts,
    and while the tool runs the old handlers are back, so that Ctrl+C belongs to the tool.
    """
    argv = tool_argv(todo.argv)
    if shutil.which(argv[0]) is None:
        return "missing"
    if signals is not None:
        signals.stop_if_asked()
    curses.def_prog_mode()
    curses.endwin()
    paste_mode(False)  # the tool gets the terminal with bracketed paste off
    if signals is not None:
        signals.loud()
    try:
        print(f"\nRunning {todo.name}. This screen comes back when it ends.", flush=True)
        subprocess.call(argv)
        if todo.pause:
            input("\nDone. Enter goes back to d750ctrl. ")
    except (KeyboardInterrupt, EOFError):
        pass
    except OSError as e:
        print(lines.clean(f"Could not run {todo.name}: {e}", LONGEST), flush=True)
        try:
            input("Enter goes back to d750ctrl. ")
        except (KeyboardInterrupt, EOFError):
            pass
    finally:
        if signals is not None:
            signals.quiet()  # the screen's own loop again: a signal is only noted
        curses.reset_prog_mode()
        win.clear()
        win.refresh()
        paste_mode(True)  # the screen has the terminal back
    return "ran"


# --------------------------------------------------------------------------- keys and paint

_NAMED = {
    curses.KEY_UP: "up",
    curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
    curses.KEY_PPAGE: "pgup",
    curses.KEY_NPAGE: "pgdn",
    curses.KEY_HOME: "home",
    curses.KEY_END: "end",
    curses.KEY_ENTER: "enter",
    curses.KEY_BACKSPACE: "backspace",
    10: "enter",
    13: "enter",
    27: "esc",
    127: "backspace",
    8: "backspace",
    32: "space",
    9: "tab",
    12: "ctrl-l",
    3: "ctrl-c",
}
_NAMED.update({curses.KEY_F0 + n: f"f{n}" for n in range(1, 13)})


def key_name(code):
    """The model's name for a key curses read, or None for a key it does not use."""
    if code in _NAMED:
        return _NAMED[code]
    if 33 <= code <= 126:
        return chr(code)
    return None


ESC = 27
BROKEN = "A broken key sequence was dropped."
BROKEN_SECONDS = 1.0  # the window after a lone Escape, and after each dropped byte
INTRODUCERS = (ord("["), ord("O"))  # what follows Escape in a CSI or an SS3 sequence
MOST_DROPPED = 16  # bytes after the introducer; the seventeenth key acts


class SequenceGuard:
    """Drops what is left of a key sequence that curses took apart. No clock inside.

    Over a slow link an arrow can arrive as Escape, then a left square bracket, then a
    letter; curses gives the Escape alone once ESCDELAY passes, and the rest would be keys.
    After a lone Escape, for one second, a left square bracket or a capital O starts a
    drop: it and everything after it up to the sequence's last byte, 64 to 126, is dropped.
    While dropping, the second is counted again from each dropped byte, so a sequence that
    pauses partway is still dropped whole, and one never finished holds keys for one second
    at most after its last piece. The Escape itself still acts. Only bytes from 32 to 126
    are dropped: a control byte (Enter, Tab, Backspace), the byte 127, a new Escape and a
    key curses named itself, above 255, end the drop and act. A drop also ends after 16
    dropped bytes, so the seventeenth key acts; no real sequence is that long.
    """

    def __init__(self, seconds=BROKEN_SECONDS):
        self.seconds = seconds
        self.escape_at = None  # when the last lone Escape came, while the next key may follow it
        self.dropping = False
        self.dropped_at = None  # when the last byte was dropped, while dropping
        self.count = 0  # bytes dropped after the bracket or O, while dropping

    def take(self, code, now):
        """(the code to act on or None, True when a broken sequence starts being dropped)."""
        if self.dropping:
            if now - self.dropped_at <= self.seconds and 32 <= code <= 126 and self.count < MOST_DROPPED:
                self.dropped_at = now
                self.count += 1
                if code >= 64:
                    self.dropping = False
                return None, False
            self.dropping = False
        if code == ESC:
            self.escape_at = now
            return code, False
        fresh = self.escape_at is not None and now - self.escape_at <= self.seconds
        self.escape_at = None
        if fresh and code in INTRODUCERS:
            self.dropping = True
            self.dropped_at = now
            self.count = 0
            return None, True
        return code, False

    def forget(self):
        """Clear what is remembered of the last Escape: it was the start of a paste, not a key."""
        self.escape_at = None

    def saw_escape(self, at):
        """An Escape came at at that was dropped after a paste: remember it, and do nothing else,
        so that the rest of its sequence is still dropped if the link stalls after it."""
        self.escape_at = at


# --------------------------------------------------------------------------- pastes

PASTE_ON = b"\x1b[?2004h"  # bracketed paste on: the terminal marks what is pasted
PASTE_OFF = b"\x1b[?2004l"
START_MARK = tuple(ord(c) for c in "[200~")  # after an Escape: a paste starts
END_MARK = tuple(ord(c) for c in "[201~")  # after an Escape: the paste ends
MARK_SECONDS = 1.0  # a mark cut by the link must go on within this
PASTE_SECONDS = 2.0  # a paste with no end mark ends when this passes with nothing more
PASTE_MOST = 4096  # characters kept of a paste
BURST_MOST = 65536  # codes read in one burst
WAIT_AFTER_MARK = 0.5  # after an end mark, no key acts for this long, started again by each code
WAIT_AFTER_ESCAPE = 2.0  # the same after an Escape ended a paste
WAIT_MOST = 5.0  # a wait never lasts longer than this in all
OPEN_WORDS = "A paste is open. Escape ends it."
WAIT_WORDS = "A key after a paste was dropped."
LINE_ENDS = (9, 10, 13)  # a tab, a line end or a carriage return becomes one space


def paste_mode(on, fd=None):
    """Bracketed paste on or off: the bytes go straight to the terminal's own descriptor, never
    through curses. A write that fails is passed over."""
    try:
        os.write(sys.stdout.fileno() if fd is None else fd, PASTE_ON if on else PASTE_OFF)
    except (OSError, ValueError):
        pass


def paste_text(codes):
    """The text of a paste and whether anything was left out but spaces and line ends."""
    out = []
    left_out = False
    for code in codes:
        if code in LINE_ENDS:
            code = 32
        if 32 <= code <= 126:
            if code == 32 and (not out or out[-1] == " "):
                continue
            out.append(chr(code))
        else:
            left_out = True
    text = "".join(out).strip(" ")
    if len(text) > PASTE_MOST:
        text = text[:PASTE_MOST].rstrip(" ")
        left_out = True
    return text, left_out


def _is_prefix(seen, mark):
    return len(seen) < len(mark) and tuple(seen) == mark[: len(seen)]


class PasteGuard:
    """Finds the marks of a bracketed paste in the bursts of codes curses gives. No clock, no curses.

    take(codes, now) is given each burst; poll(now) is called on every pass of the loop. Both
    return items, in order: ("key", code, at) for a key that came at at; ("paste", text,
    left_out) for a whole paste; ("late", code) for each code of an open paste that came in a
    later burst than its start mark, and for each code dropped in the wait after a paste, so
    that the loop can still unkey. notes holds the words to say for what was dropped, each
    once for each paste; the loop says them and empties it.

    An Escape that ends a burst is a key at once; when the next burst, within a second, starts
    with the rest of a start mark, the paste starts there. The characters of a mark the link
    cut are held until the next burst says what they are; after a second they go on as keys,
    or, inside a paste, as its text. Inside a paste, an Escape that ends a burst ends the
    paste and then acts as a key, and a paste with no end mark ends after two quiet seconds.

    After a paste comes a wait in which no key acts: half a second after an end mark, two
    seconds after an Escape ended the paste, each started again by every code that comes in
    it, and never more than five seconds in all. A start mark in a wait starts a new paste. A
    start mark the link cut, in a wait, is held as outside one: when the rest comes within a
    second a new paste starts; when it does not, its codes that came in the wait were dropped
    there as late codes, and are never keys.
    """

    def __init__(self):
        self.bursts = 0
        self.open = False  # inside a paste
        self.codes = []  # the codes of the open paste
        self.left_out = False  # an Escape was left out of the open paste
        self.opened_in = 0  # the burst the open paste started in
        self.last_at = None  # when the open paste last had a code
        # ([(code, when it came)] of a start mark seen after an Escape key, when the Escape came)
        self.start_seen = None
        self.start_dropped = 0  # how many of the held start mark's first codes came in a wait, dropped there
        self.end_seen = None  # (the part of an end mark seen after an Escape, inside a paste, when)
        self.wait = None  # after a paste: [how long, when the last code came, when the wait began]
        self.notes = []  # words to say, for the loop
        self.said_open = self.said_wait = False  # each said once for each paste

    def _late(self, items, codes, waiting=False):
        """Late items: codes of an open paste from a later burst, or codes dropped in a wait."""
        codes = list(codes)
        if not codes:
            return
        items.extend(("late", code) for code in codes)
        if waiting and not self.said_wait:
            self.said_wait = True
            self.notes.append(WAIT_WORDS)
        elif not waiting and not self.said_open:
            self.said_open = True
            self.notes.append(OPEN_WORDS)

    def _waiting(self, now):
        """Is the wait after a paste still on?"""
        if self.wait is None:
            return False
        span, last, began = self.wait
        if now - last <= span and now - began <= WAIT_MOST:
            return True
        self.wait = None
        return False

    # ----------------------------------------------------------------- what is held

    def _release_start(self, items):
        """The held characters of a start mark that did not go on: keys, for the key guard."""
        seen, _at = self.start_seen
        self.start_seen = None
        dropped, self.start_dropped = self.start_dropped, 0
        # The codes that came in a wait were dropped there as late codes, never keys; the rest are
        # keys, each with its own time, for the key guard.
        items.extend(("key", code, at) for code, at in seen[dropped:])

    def _release_end(self):
        """The held characters of an end mark that did not go on: text of the paste, its Escape left out."""
        seen, _at = self.end_seen
        self.end_seen = None
        self.left_out = True
        self.codes.extend(seen)

    def _give(self, items, now=None, wait=None):
        """End the open paste and give it; then a wait of that many seconds, when given."""
        if self.end_seen is not None:
            self._release_end()
        text, left_out = paste_text(self.codes)
        items.append(("paste", text, left_out or self.left_out))
        self.open = False
        self.codes = []
        self.left_out = False
        self.last_at = None
        self.wait = None if wait is None else [wait, now, now]

    def _start(self, now):
        self.start_dropped = 0
        self.open = True
        self.codes = []
        self.left_out = False
        self.opened_in = self.bursts
        self.last_at = now
        self.wait = None
        self.said_open = self.said_wait = False

    # ----------------------------------------------------------------- the two calls

    def take(self, codes, now):
        codes = list(codes)
        self.bursts += 1
        items = self.poll(now)
        i, n = 0, len(codes)
        # What the burst before left held.
        if self.start_seen is not None and i < n:
            seen, at = self.start_seen
            want = START_MARK[len(seen) :]
            got = tuple(codes[i : i + len(want)])
            if got == want:
                self.start_seen = None
                i += len(want)
                self._start(now)
            elif got == want[: len(got)] and i + len(got) == n:
                if self.start_dropped == len(seen) and self._waiting(now):  # still in the wait: dropped
                    self.wait[1] = now
                    self._late(items, got, waiting=True)
                    self.start_dropped += len(got)
                self.start_seen = (seen + [(c, now) for c in got], at)
                return items
            else:
                self._release_start(items)
        if self.open and self.end_seen is not None and i < n:
            seen, _at = self.end_seen
            want = END_MARK[len(seen) - 1 :]
            got = tuple(codes[i : i + len(want)])
            if self.bursts > self.opened_in and got == want[: len(got)]:
                self._late(items, got)
            if got == want:
                self.end_seen = None
                i += len(want)
                self._give(items, now, WAIT_AFTER_MARK)
            elif got == want[: len(got)] and i + len(got) == n:
                self.end_seen = (seen + list(got), self.end_seen[1])
                self.last_at = now
                return items
            else:
                self._release_end()
        while i < n:
            code = codes[i]
            if not self.open:
                if code == ESC:
                    after = tuple(codes[i + 1 : i + 1 + len(START_MARK)])
                    if after == START_MARK:  # a start mark, in a wait or not, starts a paste
                        self._start(now)
                        i += 1 + len(START_MARK)
                        continue
                if self._waiting(now):  # in the wait after a paste: dropped, and the wait starts again
                    self.wait[1] = now
                    if code == ESC and i + 1 + len(after) == n and _is_prefix(after, START_MARK):
                        # A start mark the link cut, in a wait: dropped, and held as outside a
                        # wait, so that when the rest comes within a second a new paste starts.
                        self._late(items, (code, *after), waiting=True)
                        self.start_seen = ([(c, now) for c in after], now)
                        self.start_dropped = len(after)
                        return items
                    self._late(items, (code,), waiting=True)
                    i += 1
                    continue
                if code == ESC:
                    items.append(("key", code, now))
                    if i + 1 + len(after) == n and _is_prefix(after, START_MARK):
                        # the mark may go on in the next burst
                        self.start_seen = ([(c, now) for c in after], now)
                        self.start_dropped = 0
                        return items
                    i += 1
                    continue
                items.append(("key", code, now))
                i += 1
                continue
            # Inside a paste.
            late = self.bursts > self.opened_in
            self.last_at = now
            if code == ESC:
                after = tuple(codes[i + 1 : i + 1 + len(END_MARK)])
                if after == END_MARK:
                    if late:
                        self._late(items, (code, *after))
                    i += 1 + len(END_MARK)
                    self._give(items, now, WAIT_AFTER_MARK)
                    continue
                if i + 1 == n:
                    if late:
                        self._late(items, (code,))
                    # an Escape that ends a burst ends the paste, then acts; a longer wait follows
                    self._give(items, now, WAIT_AFTER_ESCAPE)
                    items.append(("key", code, now))
                    return items
                if i + 1 + len(after) == n and _is_prefix(after, END_MARK):
                    if late:
                        self._late(items, (code, *after))
                    self.end_seen = ([code, *after], now)
                    return items
                if late:
                    self._late(items, (code,))
                self.left_out = True  # an Escape inside a paste is left out of its text
                i += 1
                continue
            if late:
                self._late(items, (code,))
            self.codes.append(code)
            i += 1
        return items

    def poll(self, now):
        items = []
        if self.start_seen is not None and now - self.start_seen[1] > MARK_SECONDS:
            self._release_start(items)
        self._waiting(now)
        if self.open and self.last_at is not None and now - self.last_at > PASTE_SECONDS:
            self._give(items)
        return items


LIT = "#"  # a lit cell of the big digits, the squelch bar or the busy history, in the frame's row
LIT_STYLES = ("digits", "bar", "history")
COLOR_NAMES = ("cyan", "magenta", "yellow", "blue")


class Look:
    """How the frame's marks are drawn: an attribute for each style, and whether bold is wanted.

    colors maps "cyan", "magenta", "yellow" and "blue" to their color pair's attribute; it
    is empty for mono, so a Look can be made and tested without a terminal. No theme uses
    red or green, and none sets a background: reverse video is the one exception.
    """

    def __init__(self, theme="mono", bold=True, colors=None):
        colors = colors or {}
        if theme != "mono" and not all(name in colors for name in COLOR_NAMES):
            theme = "mono"
        self.theme = theme
        self.bold = bold
        plain, bold_attr, reverse = curses.A_NORMAL, curses.A_BOLD, curses.A_REVERSE
        if theme == "dark":
            band_a, band_b = colors["cyan"], colors["magenta"]
            alarm, bar, keys = colors["yellow"], colors["cyan"], colors["cyan"]
        elif theme == "blue":
            band_a, band_b = colors["blue"], colors["yellow"]
            alarm, bar, keys = colors["yellow"] | reverse, colors["blue"], colors["blue"]
        else:
            band_a = band_b = bold_attr
            alarm, bar, keys = reverse, plain, plain
        self.styles = {
            "focus": bold_attr,
            "head_a": band_a,
            "head_b": band_b,
            "alarm": alarm | bold_attr,
            "busy": alarm,
            "digits": plain,
            "bar": bar,
            "history": bar,
            "log": bold_attr,
            "keys": keys,
        }

    def row_attrs(self, text, length, focused, marks):
        """The characters and attributes of one row's first length cells, as two lists."""
        cells = list(text[:length].ljust(length))
        attrs = [curses.A_BOLD if focused and i < len(text) else curses.A_NORMAL for i in range(length)]
        for column, span, style in marks:
            add = self.styles.get(style, curses.A_NORMAL)
            for i in range(max(0, column), min(length, column + max(0, span))):
                attr = attrs[i]
                if style in LIT_STYLES:
                    if cells[i] != LIT:
                        continue  # an unlit cell is a space, drawn plain
                    cells[i] = " "  # a lit cell is a space in reverse video, never the mark itself
                    attr |= curses.A_REVERSE
                if add & curses.A_COLOR:
                    attr &= ~curses.A_COLOR
                attrs[i] = attr | add
        if not self.bold:
            attrs = [a & ~curses.A_BOLD for a in attrs]
        return cells, attrs


def runs(cells, attrs):
    """A row as (column, text, attribute) runs, without the plain spaces at its end."""
    end = len(cells)
    while end and cells[end - 1] == " " and attrs[end - 1] == curses.A_NORMAL:
        end -= 1
    out = []
    start = 0
    for i in range(1, end + 1):
        if i == end or attrs[i] != attrs[start]:
            out.append((start, "".join(cells[start:i]), attrs[start]))
            start = i
    return out


def paint(win, model, look, last, force=False):
    """Tell the model the size, and draw its frame if it changed; leave the cursor where it says."""
    height, width = win.getmaxyx()
    model.size(width, height)
    frame = model.frame(width, height)
    if frame == last and not force:
        return last
    win.erase()
    by_row = {}
    for row, column, span, style in getattr(frame, "marks", ()) or ():
        by_row.setdefault(row, []).append((column, span, style))
    for row, text in enumerate(frame.rows[:height]):
        marks = by_row.get(row, [])
        if not text and not marks:
            continue
        length = min(width, max([len(text)] + [c + s for c, s, _ in marks]))
        cells, attrs = look.row_attrs(text, length, row == frame.focus_row, marks)
        for column, part, attr in runs(cells, attrs):
            try:
                win.addstr(row, column, part, attr)
            except curses.error:
                pass  # the bottom right cell: curses writes it and then complains
    try:
        win.move(*frame.cursor)
    except curses.error:
        pass
    win.refresh()
    return frame


def colors_for(theme):
    """Start colors for a theme that has them. The color pairs by name, or {} for mono.

    Called after curses has started. No pair sets a background: -1 keeps the terminal's own.
    A terminal with no colors, or too few, gives {}, and the theme is then mono.
    """
    if theme == "mono":
        return {}
    try:
        if not curses.has_colors():
            return {}
        curses.start_color()
        curses.use_default_colors()
        if curses.COLORS < 8 or curses.COLOR_PAIRS < len(COLOR_NAMES) + 1:
            return {}
        numbers = {"cyan": curses.COLOR_CYAN, "magenta": curses.COLOR_MAGENTA,
                   "yellow": curses.COLOR_YELLOW, "blue": curses.COLOR_BLUE}
        found = {}
        for pair, name in enumerate(COLOR_NAMES, 1):
            curses.init_pair(pair, numbers[name], -1)
            found[name] = curses.color_pair(pair)
        return found
    except curses.error:
        return {}


# --------------------------------------------------------------------------- the session


class _Stop(Exception):
    """SIGTERM, SIGHUP or SIGQUIT arrived."""

    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


def _on_signal(signum, frame):
    raise _Stop(signum)


class Signals:
    """The way out by a signal: Ctrl+C, SIGTERM, SIGHUP and SIGQUIT.

    While the screen's own loop runs (quiet()), the handler only notes the signal, and the loop
    takes the way out between keys with stop_if_asked(), never in the middle of a burst. Around
    a tool that runs in this terminal (loud()), the old handlers are back: Ctrl+C is
    KeyboardInterrupt, which the tool's runner takes, and the others raise _Stop at once.
    """

    def __init__(self):
        self.noted = []

    def note(self, signum, frame):
        self.noted.append(signum)

    def quiet(self):
        for signum in (*EXIT_SIGNALS, signal.SIGINT):
            signal.signal(signum, self.note)

    def loud(self):
        signal.signal(signal.SIGINT, signal.default_int_handler)
        for signum in EXIT_SIGNALS:
            signal.signal(signum, _on_signal)

    def stop_if_asked(self):
        """Take the way out when a signal was noted: Ctrl+C is KeyboardInterrupt, the others _Stop."""
        if self.noted:
            signum = self.noted[0]
            if signum == signal.SIGINT:
                raise KeyboardInterrupt()
            raise _Stop(signum)


def keep_typed_ahead(fd):
    """Set NOFLSH, so that Ctrl+C, Ctrl+backslash and the other signal keys no longer throw away
    the keys typed ahead of them. The terminal's settings saved before curses started are put
    back on every way out, and NOFLSH with them. curses is told, so that it keeps NOFLSH when it
    sets the program's mode again."""
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] |= termios.NOFLSH
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        curses.def_prog_mode()
    except (termios.error, curses.error):
        pass


def drain_on_signal(win, model, urgent):
    """On a way out by a signal: read every key already waiting, with no wait, at most BURST_MOST,
    and hand each to model.late(), as a key late after a paste: a key of unkey unkeys, and a key
    of lock locks when not locked; nothing else acts. A paste's marks and text are only codes
    here, and do nothing."""
    try:
        win.nodelay(True)
        for _ in range(BURST_MOST):
            code = win.getch()
            if code == -1:
                break
            name = None if code == curses.KEY_RESIZE else key_name(code)
            if name is None:
                continue
            for todo in model.late(name) or ():
                if is_urgent(todo):
                    urgent.put(todo)
    except curses.error:
        pass


ESCDELAY_MS = "100"


def set_escdelay(environ):
    """ESCDELAY at 100 milliseconds before curses starts, unless the environment sets it."""
    if not environ.get("ESCDELAY"):
        environ["ESCDELAY"] = ESCDELAY_MS


QUIET_SECONDS = 0.5


class QuietTime:
    """The quiet time after a question opens: a key that comes sooner is early. No clock inside.

    seen() is told the model's question number and the time after every call into the model;
    it says True when a new question opened, so that typed-ahead input is thrown away. key()
    is told when a key came: an early key starts the quiet time again, so a stream of keys
    never answers a question, however long it runs.
    """

    def __init__(self, seconds=QUIET_SECONDS):
        self.seconds = seconds
        self.question = 0
        self.opened_at = None

    def seen(self, question, now):
        question = question or 0
        fresh = question != 0 and question != self.question
        if fresh:
            self.opened_at = now
        elif question == 0:
            self.opened_at = None
        self.question = question
        return fresh

    def early(self, now):
        return self.opened_at is not None and now - self.opened_at < self.seconds

    def key(self, now):
        """A key came at now: whether it is early. An early key starts the quiet time again."""
        early = self.early(now)
        if early:
            self.opened_at = now
        return early


def read_burst(win, first=None):
    """The codes ready with no waiting, after first when given: at most BURST_MOST. Resize codes
    are taken out. (codes, True when a resize came). The window is left waiting POLL again."""
    codes = [] if first is None else [first]
    resized = False
    win.nodelay(True)
    try:
        while len(codes) < BURST_MOST:
            code = win.getch()
            if code == -1:
                break
            if code == curses.KEY_RESIZE:
                resized = True
                continue
            codes.append(code)
    finally:
        win.timeout(POLL)
    return codes, resized


def late(code, model, hand, guard=None, at=None):
    """A code inside or right after a paste: model.late() says what it does (unkey unkeys, lock
    locks when not locked, anything else nothing). An Escape among them, which came at at, is
    told to the key guard, so that the rest of its sequence is still dropped."""
    if code == ESC and guard is not None and at is not None:
        guard.saw_escape(at)
    return hand(model.late(key_name(code)))


def say_notes(paste, model):
    """Say what the paste guard dropped, so that nothing is dropped in silence."""
    while paste.notes:
        model.note(paste.notes.pop(0))


def drain(win, guard, model, hand, now, paste=None, items=None, at=None):
    """Drain typed-ahead keys: first the items left in the burst in hand, which came at at, then
    every key that is ready, read with no waiting through the same paste guard. A key goes
    through the key guard and key naming as usual; the model gets only those for which
    model.urgent(name) is True, as early keys, and the rest are dropped. A paste goes to
    model.paste. True when a thing to do was Quit."""
    paste = paste or PasteGuard()
    pending = items if items is not None else []
    came = [now() if at is None else at]  # when the burst in hand came

    def one(item):
        if item[0] == "paste":
            guard.forget()
            return hand(model.paste(item[1], item[2]))
        if item[0] == "late":
            return late(item[1], model, hand, guard, came[0])
        code, _broken = guard.take(item[1], item[2])  # the key guard gets the time the code came
        name = None if code is None else key_name(code)
        if name is not None and model.urgent(name):
            return hand(model.key(name, early=True))
        return False

    while True:
        while pending:
            if one(pending.pop(0)):
                return True
        codes, _resized = read_burst(win)
        if not codes:
            return False
        came[0] = now()
        pending.extend(paste.take(codes, came[0]))
        say_notes(paste, model)


URGENT_WAIT_SECONDS = 2.0  # how long a way out waits, in all, for an unkey or lock still out


class Urgent:
    """Unkey and Set("lock"), each in a short thread of its own, so that an unkey never waits
    behind a read or behind a lock that hangs. At most one unkey thread and one lock thread at
    a time: one that comes while its kind is out starts no thread, and is given that one's
    answer when it comes back. Results come back to the main thread through results.

    wait() is called on every way out, so that no unkey or lock dies with the program.
    """

    def __init__(self, ports, results, carrier=None):
        self.ports = ports
        self.results = results
        self.carrier = carrier or (lambda todo: carry(todo, None, ports))
        self.lock = threading.Lock()
        self.out = {}  # kind: (thread, the todos waiting for its answer)

    def put(self, todo):
        kind = "unkey" if isinstance(todo, sm.Unkey) else "lock"
        with self.lock:
            if kind in self.out:
                self.out[kind][1].append(todo)
                return False
            thread = threading.Thread(target=self._run, args=(kind, todo), name=f"d750ctrl-{kind}", daemon=True)
            self.out[kind] = (thread, [todo])
            thread.start()
            return True

    def _run(self, kind, todo):
        try:
            result, error = self.carrier(todo), None
        except Exception as e:  # handed to the model, which says it
            result, error = None, e
        at = time.strftime("%H:%M:%S")
        with self.lock:
            _thread, waiting = self.out.pop(kind)
        for each in waiting:
            self.results.put(("done", each, result, error, at))

    def threads(self):
        with self.lock:
            return [thread for thread, _ in self.out.values()]

    def wait(self, seconds=URGENT_WAIT_SECONDS):
        """Wait for every unkey or lock still out, at most seconds in all.
        Returns the kinds still not answered, lock first."""
        end = time.monotonic() + seconds
        for thread in self.threads():
            left = end - time.monotonic()
            if left <= 0:
                break
            thread.join(left)
        with self.lock:
            return [kind for kind in ("lock", "unkey") if kind in self.out]


class Keys:
    """The loop's work for one key that curses read, so that a test can call it with a
    pretend window and a pretend model.

    Typed-ahead keys are drained whenever model.question changes its value, to a new number
    or to 0, and whenever a key ends typing: only unkey and lock act on them.
    """

    def __init__(self, win, model, hand, quiet=None, guard=None, clock=time.monotonic, paste=None):
        self.win = win
        self.model = model
        self.hand = hand
        self.quiet = quiet or QuietTime()
        self.guard = guard or SequenceGuard()
        self.clock = clock
        self.paste = paste or PasteGuard()
        self.items = []  # what is left of the burst in hand
        self.at = None  # when the burst in hand came
        self.question = 0

    def drain(self):
        """Drain: the rest of the burst in hand first, then what curses has ready."""
        return drain(self.win, self.guard, self.model, self.hand, self.clock, self.paste, self.items, self.at)

    def burst(self, codes, now):
        """A burst the loop read, at now. True when a thing to do was Quit."""
        self.at = now
        self.items.extend(self.paste.take(codes, now))
        done = self._run()
        say_notes(self.paste, self.model)
        return done

    def poll(self, now):
        """On every pass of the loop: a mark or a paste that time has settled."""
        self.items.extend(self.paste.poll(now))
        done = self._run()
        say_notes(self.paste, self.model)
        return done

    def _run(self):
        while self.items:
            item = self.items.pop(0)
            if item[0] == "key":
                done = self.key(item[1], self.clock(), item[2])  # the quiet time asks the clock now
            elif item[0] == "paste":
                self.guard.forget()
                done = self.hand(self.model.paste(item[1], item[2])) or self.watch()
            else:
                done = late(item[1], self.model, self.hand, self.guard, self.at) or self.watch()
            if done:
                return True
        return False

    def watch(self):
        """Drain when the question changed since last seen. True when a thing to do was Quit."""
        while True:
            question = self.model.question or 0
            self.quiet.seen(question, self.clock())
            if question == self.question:
                return False
            self.question = question
            if self.drain():
                return True

    def key(self, code, now, at=None):
        """One key curses read, handled at now; at is when it came, for the key guard. True when a thing to do was Quit."""
        code, broken = self.guard.take(code, now if at is None else at)
        if broken:
            self.model.note(BROKEN)
        name = None if code is None else key_name(code)
        if name is None:
            return False
        was_typing = self.model.mode == "typing"
        if self.hand(self.model.key(name, early=self.quiet.key(now))):
            return True
        if was_typing and self.model.mode != "typing" and self.drain():
            return True
        return self.watch()


class _Ending:
    """What the loop ended with: whether the workspace is to be closed after the terminal is back."""

    def __init__(self):
        self.close_workspace = False


def _loop(win, model, common, urgent, results, look, ports, ending, signals=None):
    """Keys, results and the clock, until Quit. Returns the exit code.

    signals, the session's Signals: the loop takes the way out a signal asked for at the next
    pass, after every key it already read has acted.
    """
    signals = signals or Signals()
    redraw = True
    last = None

    def hand(todos):
        """Hand out the things to do. True when one of them is Quit."""
        nonlocal redraw
        todos = list(todos or ())
        if any(isinstance(todo, sm.CloseWorkspace) for todo in todos):
            ending.close_workspace = True
        for todo in todos:
            if isinstance(todo, sm.Quit):
                return True
            if isinstance(todo, sm.CloseWorkspace):
                continue
            if isinstance(todo, sm.Redraw):
                win.clearok(True)
                redraw = True
            elif isinstance(todo, sm.Tool) and not ports.workspace:
                result = run_here(win, todo, signals)
                redraw = True
                if hand(model.finished(todo, result, None, time.strftime("%H:%M:%S"))):
                    return True
            elif is_urgent(todo):
                urgent.put(todo)
            else:
                common.put(todo)
        return False

    keys = Keys(win, model, hand)
    watch = keys.watch

    height, width = win.getmaxyx()
    model.size(width, height)
    if hand(model.start()) or watch():
        return 0
    pasting = False
    while True:
        signals.stop_if_asked()
        last = paint(win, model, look, last, redraw)
        redraw = False
        if not pasting:
            paste_mode(True)  # after the first paint
            pasting = True
        code = win.getch()
        if code == curses.KEY_RESIZE:
            redraw = True
            code = -1
        if code != -1:
            codes, resized = read_burst(win, code)
            redraw = redraw or resized
            if codes and keys.burst(codes, time.monotonic()):
                return 0
        signals.stop_if_asked()  # between bursts: every key read has acted
        if keys.poll(time.monotonic()):
            return 0
        while True:
            try:
                item = results.get_nowait()
            except queue.Empty:
                break
            if item[0] == "done":
                _, todo, result, error, at = item
                if hand(model.finished(todo, result, error, at)):
                    return 0
            else:
                raise item[1]
            if watch():
                return 0
        if hand(model.tick(time.monotonic())) or watch():
            return 0


def _session(model, ports, theme, ending):
    """Start curses, run the loop, and put the terminal back on every way out."""
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    signals = Signals()
    handlers = {signum: signal.getsignal(signum) for signum in EXIT_SIGNALS}
    signals.quiet()  # Ctrl+C is put back to the default on the way out
    set_escdelay(os.environ)
    results = queue.Queue()
    common = Worker(Link(ports.cmd_port), ports, results, "d750ctrl-link")
    urgent = Urgent(ports, results)
    win = None
    signalled = False
    try:
        win = curses.initscr()
        curses.noecho()
        curses.cbreak()
        win.keypad(True)
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        win.timeout(POLL)
        keep_typed_ahead(fd)
        look = Look(theme, True, colors_for(theme))
        common.start()
        return _loop(win, model, common, urgent, results, look, ports, ending, signals)
    except (KeyboardInterrupt, _Stop):
        signalled = True
        raise
    finally:
        for signum in (*EXIT_SIGNALS, signal.SIGINT):
            signal.signal(signum, signal.SIG_IGN)  # nothing may cut the putting back short
        if signalled and win is not None:
            try:
                drain_on_signal(win, model, urgent)  # U typed just ahead of Ctrl+C still unkeys
            except Exception:  # noqa: BLE001  putting the terminal back comes first
                pass
        if win is not None:
            try:
                win.keypad(False)
                curses.nocbreak()
                curses.echo()
            except curses.error:
                pass
            try:
                curses.endwin()
            except curses.error:
                pass
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        except termios.error:
            pass
        paste_mode(False)  # on every way out, after the terminal is put back
        for kind in urgent.wait():  # no way out loses an unkey or a lock still out: 2 seconds at most
            print(f"Warn: {kind} not confirmed.", file=sys.stderr, flush=True)
        common.stop()
        signal.signal(signal.SIGINT, signal.default_int_handler)
        for signum, handler in handlers.items():
            signal.signal(signum, signal.SIG_DFL if handler is None else handler)


# --------------------------------------------------------------------------- options


class Options:
    """What the command line asked for. A named option not given is None."""

    def __init__(self):
        self.help = False
        self.check = False
        self.no_tmux = False
        self.inside = False
        self.step = None
        self.view = self.theme = self.digits = None
        self.given = []  # the arguments as given, for the workspace's start again


def parse_args(args):
    """The options, or the exit code after saying what was wrong. --help stops at once."""
    options = Options()
    args = list(args)
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--help":
            options.help = True
            return options
        if arg == "--check":
            options.check = True
            continue
        if arg in ("--no-tmux", "--plain"):
            options.no_tmux = True
            options.given.append(arg)
            continue
        if arg == "--inside":
            options.inside = True
            continue
        if arg == "--ascii":
            options.digits = "plain"
            options.given.append(arg)
            continue
        name, value = arg[2:].partition("=")[::2] if arg.startswith("--") else ("", "")
        if name in NAMED_OPTIONS or name == "step":
            if "=" not in arg:
                value = args[i] if i < len(args) else ""
                i += 1
            value = value.strip().lower()
            options.given.append(f"--{name}={value}")
            if name == "step":
                try:
                    options.step = float(value)
                except ValueError:
                    options.step = None
                if options.step is None or options.step != options.step:
                    print("Fail: no such step. Try: d750ctrl --help", file=sys.stderr)
                    return 2
                continue
            if value not in CHOICES[name]:
                print(f"Fail: no such {name}. Try: d750ctrl --help", file=sys.stderr)
                return 2
            setattr(options, name, value)
            continue
        print("Fail: unknown option. Try: d750ctrl --help", file=sys.stderr)
        return 2
    return options


class Chosen:
    """The settings in force: the option, else the setting, else the default.

    skipped holds a plain line for each setting whose value is not known.
    """

    def __init__(self, view, theme, digits, live_meters, announce, skipped):
        self.view = view
        self.theme = theme
        self.digits = digits
        self.live_meters = live_meters
        self.announce = announce
        self.skipped = tuple(skipped)

    def lines(self):
        """The five lines --check starts with."""
        return (
            f"View {self.view}.",
            f"Theme {self.theme}.",
            f"Digits {self.digits}.",
            f"Live meters {self.live_meters}.",
            f"Announce {self.announce}.",
        )


def _skipped_line(name, value):
    """A plain line for a setting whose value is not known."""
    head = f"Setting {name.replace('_', '-')} skipped."
    shown = lines.clean(value, 30)
    line = f"{head} {shown} is not known." if shown else f"{head} Its value is empty."
    return line if not lines.problems(line) else head


def choose(settings, options, environ):
    """The view, theme, digits, live meters and announce in force, from options, settings and NO_COLOR.

    settings is the dict read_conf() gives; a name may be written with hyphens.
    """
    settings = {str(k).replace("-", "_"): v for k, v in settings.items()}
    picked = {}
    skipped = []
    for name, words in CHOICES.items():
        picked[name] = words[0]
        if name in settings:
            value = str(settings[name]).strip().lower()
            if name == "live_meters":
                value = OLDER_LIVE.get(value, value)
            if value in words:
                picked[name] = value
            else:
                skipped.append(_skipped_line(name, settings[name]))
        given = getattr(options, name, None)
        if given is not None:
            picked[name] = given
    if options.theme is None and environ.get("NO_COLOR"):
        picked["theme"] = "mono"
    return Chosen(picked["view"], picked["theme"], picked["digits"], picked["live_meters"],
                  picked["announce"], skipped)


def check_lines(chosen, keys):
    """What --check prints: the five settings in force, a line for each skipped setting, then
    keymap.check_lines(), without its "No settings line was skipped." when a setting was."""
    said = list(keys.check_lines())
    if chosen.skipped:
        said = [line for line in said if line != NONE_SKIPPED]
    return [*chosen.lines(), *chosen.skipped, *said]


def read_settings(options=None, environ=None):
    """The settings file's settings, the settings in force, and the keymap from [keys]."""
    options = options or Options()
    environ = os.environ if environ is None else environ
    settings = read_conf(environ)
    return settings, choose(settings, options, environ), keymap.Keymap(read_keys(environ))


def step_khz(options):
    """The tuning step: --step when it is one of the radio's steps, else 10, as today."""
    for step in STEPS_KHZ:
        if options.step is not None and abs(options.step - step) < 1e-9:
            return step
    return 10


def make_model(settings, chosen, keys, options, ports):
    """The model, from what read_settings() gave."""
    status = conf_seconds(settings, "status_seconds", 2.0, 0.5) or 2.0
    return sm.ScreenModel(
        xara_port=ports.xara_port,
        announce=chosen.announce,
        live_meters=chosen.live_meters,
        step_khz=step_khz(options),
        status_seconds=status,
        busy_seconds=conf_seconds(settings, "busy_seconds", 1.0, 0.25),
        view=chosen.view,
        digits=chosen.digits,
        keymap=keys,
        skipped=bool(chosen.skipped or keys.skipped),
        workspace=ports.workspace,
        rig_key=settings.get("rig_key") or "F9",
        next_key=settings.get("next_key") or "F12",
        mycall=(settings.get("mycall") or "").upper() or "N0CALL",
        varac=(settings.get("varac") or "xarachat").strip().lower(),
    )


def _fail_line(error):
    line = lines.clean(f"Fail: a bug in d750ctrl. {type(error).__name__}: {error}", LONGEST)
    return line if not lines.problems(line) else "Fail: a bug in d750ctrl."


def main(argv=None):
    """The program d750ctrl. Returns the exit code."""
    args = sys.argv[1:] if argv is None else list(argv)
    options = parse_args(args)
    if isinstance(options, int):
        return options
    if options.help:
        for line in HELP:
            print(line)
        return 0
    settings, chosen, keys = read_settings(options)
    if options.check:
        for line in check_lines(chosen, keys):
            print(line)
        return 0
    ports = ports_from(settings, os.environ, workspace=options.inside)
    try:
        socket.create_connection(("127.0.0.1", ports.cmd_port), timeout=3).close()
    except OSError:
        print(f"Fail: d750d is not answering on 127.0.0.1:{ports.cmd_port} (systemctl --user status d750d)")
        return 1
    if not (os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno())):
        print("Fail: d750ctrl needs a terminal.", file=sys.stderr)
        return 1
    workspace_wanted = (settings.get("workspace") or "yes").lower() not in ("no", "off", "0", "false")
    if not options.inside and not options.no_tmux and workspace_wanted:
        workspace_start(settings, options.given)  # comes back only when tmux cannot be used
    model = make_model(settings, chosen, keys, options, ports)
    ending = _Ending()
    try:
        code = _session(model, ports, chosen.theme, ending)
    except KeyboardInterrupt:
        code = 0
    except _Stop as stop:
        code = 128 + stop.signum
    except Exception as e:  # a bug: the terminal is back by now; say it in one line
        print(_fail_line(e), file=sys.stderr)
        code = 1
    if ending.close_workspace and ports.workspace:
        tmux("kill-server")  # last: it ends this terminal too
    return code
