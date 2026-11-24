"""fakedaemon: a pretend d750d inside the test process, and a carrier for the model's things to do.

FakeDaemon answers the command port's lines as d750d does, by d750d's rules for what a line
may hold (copied in judge, and checked against the real daemon by tests/d750d-test.py): the
state line, lock, unlock, reconnect, the refusals, and the radio's answers from the Sim class
of tests/d750-sim.py, loaded by its path. Its PTT port takes T 0 and answers RPRT 0.

Carrier carries out each thing to do the model gives, against a FakeDaemon, and records
every one. Nothing here opens a socket, a port or a terminal, and nothing transmits:
SendFrame and Tool are only recorded and answered.

Runner is a model, a FakeDaemon and a Carrier together, with a pretend clock. A key named
paste:TEXT is a paste of TEXT, as the paste guard gives one.

GPL-2.0-or-later.
"""

import collections
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
TOP = os.path.dirname(HERE)
if TOP not in sys.path:
    sys.path.insert(0, TOP)

from d750ui import screen_model as sm  # noqa: E402

_spec = importlib.util.spec_from_file_location("d750_sim", os.path.join(HERE, "d750-sim.py"))
d750_sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d750_sim)

DAEMON_WORDS = ("state", "lock", "unlock", "reconnect", "quit")
UNSAFE = {"TX", "RX", "UP", "DW", "SR", "PS", "0M", "0G", "BE"}
ARMS = ("VX", "TN", "PT")  # refused while locked: they arm the radio to send by itself
LINE_LIMIT = 512
CMD_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ,.-/+")
CLOCK_TIME = "261123120000"


def judge(line, locked):
    """d750d's rules for one command port line, copied: ("refuse", why), ("word", w), ("blank", ""),
    or ("radio", the command). The line end, a newline with one carriage return before it, is taken off first."""
    if line.endswith("\n"):
        line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
    if len(line) > LINE_LIMIT:
        return "refuse", f"the line is longer than {LINE_LIMIT} characters"
    if any(c not in CMD_CHARS for c in line):
        return "refuse", "only plain letters, digits, spaces and , . - / + are allowed"
    if line in DAEMON_WORDS:
        return "word", line
    line = line.strip(" ")
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


class FakeDaemon:
    """d750d's two ports, in the process, over the pretend radio."""

    def __init__(self):
        self.sim = d750_sim.Sim()
        self.sim.flicker = False
        self.port_open = True
        self.keyed = False
        self.locked = False
        self.answering = True  # False: every line answers ERR, as with no daemon
        self.lines = []  # every line the command port was given
        self.ptt_lines = []  # every line the PTT port was given

    def state(self):
        return (
            f"port {'open' if self.port_open else 'closed'} /dev/test-cat; "
            f"{'keyed' if self.keyed else 'not keyed'}; "
            f"{'locked' if self.locked else 'unlocked'}; "
            "last answer none; unsolicited bytes seen 0"
        )

    def command(self, line):
        """One line to the command port; its one answer line."""
        self.lines.append(line)
        if not self.answering:
            return "ERR [Errno 111] Connection refused"
        what, line = judge(line, self.locked)
        if what == "blank":
            return ""
        if what == "refuse":
            return f"ERR {line}"
        if what == "word":
            if line == "state":
                return self.state()
            if line == "lock":
                self.locked = True
                if not self.port_open:  # d750d sends RX and checks it; no radio, no answer, the lock holds
                    return "OK locked; the radio did not say it is receiving"
                self.keyed = False
                return "OK locked, PTT refused until unlock"
            if line == "unlock":
                self.locked = False
                return "OK unlocked"
            if line == "reconnect":
                return "OK port reopened"
            return "ERR closed"
        if not self.port_open:
            return "ERR radio port not available: no such device"
        answer = self.sim.answer(line)
        return answer or "ERR no answer"

    def ptt(self, line):
        self.ptt_lines.append(line)
        if not self.answering:
            return "ERR [Errno 111] Connection refused"
        if line.strip() == "T 0":
            self.keyed = False
            return "RPRT 0"
        return "RPRT -1"


class Carrier:
    """Carries out the model's things to do against a FakeDaemon, and records each."""

    def __init__(self, daemon, installed=("xarachat", "openslot", "radiogram", "d750-sstv", "d750-rtty"),
                 workspace=False, windows=(), xara_answers=True):
        self.daemon = daemon
        self.installed = set(installed)
        self.workspace = workspace
        self.windows = list(windows)
        self.xara_answers = xara_answers
        self.done = []
        self.frames = []  # SendFrame things to do, recorded and never sent anywhere
        self.tools = []  # Tool things to do, recorded and never run

    def carry(self, todo):
        self.done.append(todo)
        if isinstance(todo, sm.Ask):
            return tuple(self.daemon.command(line) for line in todo.lines)
        if isinstance(todo, sm.Set):
            return self.daemon.command(todo.line)
        if isinstance(todo, sm.Unkey):
            return self.daemon.ptt("T 0")
        if isinstance(todo, sm.Clock):
            return self.daemon.command("RT " + CLOCK_TIME)
        if isinstance(todo, sm.SendFrame):
            self.frames.append(todo)
            return "" if self.xara_answers else "ERR [Errno 111] Connection refused"
        if isinstance(todo, sm.MemoryRead):
            return tuple((n, self.daemon.command(f"ME {n:03d}")) for n in range(todo.first, todo.last + 1))
        if isinstance(todo, sm.Tool):
            self.tools.append(todo)
            return self._tool(todo)
        if isinstance(todo, sm.Windows):
            return tuple(self.windows) if self.workspace else ()
        return None

    def _tool(self, todo):
        if todo.argv[0] not in self.installed:
            return "missing"
        if not self.workspace:
            return "ran"
        if todo.other and todo.other in self.windows:
            return "other"
        if todo.name in self.windows:
            return "selected"
        self.windows.append(todo.name)
        return "opened"


class Runner:
    """A model, a pretend daemon and a carrier that does what the model asks, in order."""

    def __init__(self, start=True, workspace=False, windows=(), installed=None, xara_answers=True, **settings):
        self.daemon = FakeDaemon()
        kw = {} if installed is None else {"installed": installed}
        self.carrier = Carrier(self.daemon, workspace=workspace, windows=windows, xara_answers=xara_answers, **kw)
        settings.setdefault("mycall", "W9XYZ")
        self.model = sm.ScreenModel(workspace=workspace, **settings)
        self.now = 1000.0
        self.clock = 0  # counts finished things, for the command log's times
        if start:
            self.run(self.model.start())

    @property
    def done(self):
        return self.carrier.done

    def run(self, todos):
        waiting = collections.deque(todos)
        while waiting:
            todo = waiting.popleft()
            if isinstance(todo, (sm.Quit, sm.Redraw, sm.CloseWorkspace)):
                self.carrier.done.append(todo)
                continue
            try:
                result, error = self.carrier.carry(todo), None
            except Exception as e:  # the model says what a failure means
                result, error = None, e
            self.clock += 1
            at = f"12:{(self.clock // 60) % 60:02d}:{self.clock % 60:02d}"
            waiting.extend(self.model.finished(todo, result, error, at))

    def press(self, *names):
        """Press keys; returns every thing to do they led to, in order."""
        start = len(self.done)
        for name in names:
            if name.startswith("paste:"):  # a paste with its marks, as the paste guard gives it
                self.run(self.model.paste(name[len("paste:") :]))
            else:
                self.run(self.model.key(name))
        return self.done[start:]

    def type(self, text):
        return self.press(*["space" if ch == " " else ch for ch in text])

    def tick(self, seconds=0.1):
        """Time passes by seconds, in steps of 0.1 seconds or less."""
        start = len(self.done)
        end = self.now + seconds
        while self.now < end - 1e-9:
            self.now = min(end, self.now + 0.1)
            self.run(self.model.tick(self.now))
        return self.done[start:]

    def frame(self, width=40, height=12):
        self.model.size(width, height)
        return self.model.frame(width, height)
