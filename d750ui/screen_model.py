"""d750ui.screen_model: every decision of the screen d750ctrl, with no curses and no socket.

The model holds what was read from the radio and the daemon, the row in focus, the active
band, the message, the tuning step and a mode: main, typing, help, memory or asking. key()
takes one key by name, tick(now) takes the monotonic time, start() begins, and each gives
back a list of things to do: small plain objects a test can compare. The curses part, or a
test, carries them out against the daemon and hands each result back with finished(),
which may give more things to do. frame(width, height) gives the rows to draw, where the
cursor goes, the row in focus and the marks; it changes nothing.

Three views: the list, the face (wide at 80 columns and more, stacked below) and compact.
The wanted view is model.view; what shows comes from the window's size. Which action a key
means comes from d750ui.keymap, for the wanted view's family.

Nothing here touches a socket, a terminal, a clock or a thread.

GPL-2.0-or-later.
"""

from dataclasses import dataclass
from typing import NamedTuple

from d750ui import keymap as km
from d750ui import lines

MAIN, TYPING, HELP, MEMORY, ASKING = "main", "typing", "help", "memory", "asking"
ANNOUNCE = ("message", "cursor")
VIEWS = ("list", "face", "compact")
LIVE = ("auto", "yes", "no")
DIGITS = ("big", "plain")

LEAST_WIDTH, LEAST_HEIGHT = 40, 8  # the list
FACE_WIDTH, FACE_HEIGHT = 80, 12  # the wide face
STACKED_HEIGHT = 10
COMPACT_HEIGHT = 6
BIG_HEIGHT = 17
TOO_SMALL = "Window too small. Need 40 by 8."
TOO_SMALL_COMPACT = "Window too small. Need 40 by 6."
TOO_SMALL_FACE = "Too small for the face. Compact."
FACE_AGAIN = "The face again."
SKIPPED_WORDS = "Settings skipped. Try d750ctrl --check"

VIEW_QUESTION = "Face? Letters change the radio. y or n"
TO_THE_FACE = "View: face. Letters change the radio."
TO_COMPACT = "View: compact. Letters change the radio."
STILL_THE_LIST = "Still the list. y goes to the face."
UNLOCK_QUESTION = "Unlock PTT? y or n"
STILL_LOCKED = "Still locked."
LOCK_GONE = "PTT is no longer locked."  # the lock went away without this screen's unlock
LOCKED_NO_RX = "Locked. The radio did not confirm RX."  # lock held, the radio did not say it is receiving
NO_RX_WORDS = "did not say it is receiving"  # in the daemon's answer to lock when the radio did not confirm
DAEMON_WORDS = ("state", "lock", "unlock", "reconnect", "quit")  # the daemon takes each only alone, in small letters
CLOCK_QUESTION = "Set the radio clock from here? y or n"
FRAME_QUESTION = "Frame: c CQ, b beacon, n no"
QUIT_QUESTION = "Close the tool windows too? y or n"
NOTHING_SENT = "Nothing sent."
LOCKED_NOTHING_SENT = "PTT is locked. Nothing sent."
UNKNOWN_NOTHING_SENT = "PTT state not read. Nothing sent."
NO_XARA_PORT = "The frame's port is not a number."
TOO_FAST = "Too fast. Answer again."
PASTE_DROPPED = "A paste was dropped."
NOTHING_PASTED = "Nothing in the paste."
VOX_REFUSED = "Refused: VOX lets the radio key itself."
NO_MYCALL = "Set mycall in the settings first."
HELP_HINT = "Help. Escape or ? goes back."
MEMORY_HINT = "Enter recalls. R rereads. Esc back"
READING_MEMORY = "Reading memory channels."
NO_MEMORY = "No memory channels found."

# What each question says when it gets any key but its yes.
NO_WORDS = {
    "unlock": STILL_LOCKED,
    "view": STILL_THE_LIST,
    "tnc": "TNC unchanged.",
    "clock": "Clock unchanged.",
    "frame": NOTHING_SENT,
    "frame_send": NOTHING_SENT,
    "quit": "Still here.",
    "sstv": "SSTV: nothing done.",
    "rtty": "RTTY: nothing done.",
    "sstv_send": NOTHING_SENT,
    "rtty_send": NOTHING_SENT,
}

STEPS_KHZ = (5, 6.25, 10, 12.5, 15, 20, 25, 50, 100)
MODES = ("FM", "NFM", "AM", "DV")
POWERS = ("high", "mid", "low", "EL")
TNCS = ("off", "APRS", "KISS")
SOURCES = ("VFO", "memory")
BANDS = ("A", "B")
ONOFF = ("off", "on")
# Raw lines whose first two characters are these can key or move the radio.
UNSAFE = ("TX", "RX", "UP", "DW", "SR", "PS", "0M", "0G", "BE")
STATE_SECONDS = 0.5
HISTORY = 30
LOG_MOST = 200
MEMORY_LAST = 199
MEMORY_BATCH = 10
TYPED_MOST = 120
XARA_PORT = 8300

RIGHT = 41  # the wide face's right panel starts at this column
PANEL = 39  # cells in each panel of the wide face
BAR_AT, BAR_CELLS = 12, 9
HISTORY_AT = 8
GLYPHS = {
    "0": ("###", "# #", "# #", "# #", "###"),
    "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"),
    "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"),
    "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"),
    "7": ("###", "  #", "  #", "  #", "  #"),
    "8": ("###", "# #", "###", "# #", "###"),
    "9": ("###", "# #", "###", "  #", "###"),
    ".": ("   ", "   ", "   ", "   ", " # "),
}

TOOL_WORDS = {"chat": "Chat", "varac": "VarAC chat", "radiogram": "Radiogram", "sstv": "SSTV", "rtty": "RTTY"}


# --------------------------------------------------------------------------- things to do


@dataclass(frozen=True)
class Ask:
    """Quiet reads: lines for the command port, in order. The result is a tuple of answers."""

    lines: tuple
    why: str = "state"  # start, state, busy, sweep or channel


@dataclass(frozen=True)
class Set:
    """One line that changes the radio or the daemon. The result is the answer."""

    line: str


@dataclass(frozen=True)
class Unkey:
    """T 0 to the PTT port. The result is the answer."""


@dataclass(frozen=True)
class Clock:
    """RT and the computer's time as yymmddHHMMSS. The result is the answer."""


@dataclass(frozen=True)
class SendFrame:
    """The CQ frame, or with beacon the beacon, to xara. The result is empty when handed over."""

    beacon: bool = False


@dataclass(frozen=True)
class MemoryRead:
    """ME nnn for each channel from first to last. The result is a tuple of (number, answer)."""

    first: int
    last: int


@dataclass(frozen=True)
class Tool:
    """Run another program. The result: missing, other, selected, opened, failed or ran."""

    name: str
    argv: tuple
    pause: bool = False
    other: str | None = None


@dataclass(frozen=True)
class Windows:
    """The names of the open tool windows, as a tuple, without rig."""


@dataclass(frozen=True)
class CloseWorkspace:
    """End the tmux server. The curses part does it last."""


@dataclass(frozen=True)
class Quit:
    """Leave the program."""


@dataclass(frozen=True)
class Redraw:
    """Draw the whole screen again."""


class Frame(NamedTuple):
    """What to draw: the rows, the cursor as (row, column), the row in focus, the marks."""

    rows: tuple
    cursor: tuple
    focus_row: int | None
    marks: tuple = ()


# --------------------------------------------------------------------------- words


def fit(text, cells=lines.CELLS):
    """Text made into one row of cells (40) or fewer that keeps the line rules, or empty."""
    text = lines.clean(text, lines.LONGEST)
    if len(text) > cells:
        cut = text[:cells]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        text = cut.rstrip(" ,;:")
    if lines.problems(text, cells):
        text = lines.clean(text, cells)
    if not text or lines.problems(text, cells):
        return ""
    return text


def _safe(row):
    """A row as it may be drawn: itself if it keeps the rules, else made to fit."""
    if not row or not lines.problems(row, lines.CELLS):
        return row
    return fit(row) or "Text not shown."


def _panel(text):
    """A wide face panel's text: 39 cells or fewer, keeping the line rules."""
    if not text or (len(text) <= PANEL and not lines.problems(text, PANEL)):
        return text
    return fit(text, PANEL) or "Text not shown."


def _put(left, right, at=RIGHT):
    """One wide face row: the left panel, then the right panel from column 41."""
    if not right:
        return left.rstrip(" ")
    return (left.ljust(at) + right).rstrip(" ")


def shows(view, width, height):
    """What a window of this size shows for a wanted view: list, wide, stacked, compact or None."""
    if view == "list":
        return "list" if width >= LEAST_WIDTH and height >= LEAST_HEIGHT else None
    if view == "face" and width >= LEAST_WIDTH and height >= STACKED_HEIGHT:
        return "wide" if width >= FACE_WIDTH and height >= FACE_HEIGHT else "stacked"
    return "compact" if width >= LEAST_WIDTH and height >= COMPACT_HEIGHT else None


def _kind(shown):
    return "face" if shown in ("wide", "stacked") else shown


def mhz_text(hz):
    """Hertz as megahertz, three decimals at least, more only when needed: 147.040, 146.52625."""
    hz = int(hz)
    whole, part = divmod(abs(hz), 1_000_000)
    decimals = f"{part:06d}".rstrip("0").ljust(3, "0")
    return f"{'-' if hz < 0 else ''}{whole}.{decimals}"


def step_words(khz):
    return f"{khz:g} kHz"


def big_digits(text):
    """Five rows of # and spaces showing text in glyphs 3 cells wide, one empty column between."""
    return [" ".join(GLYPHS[ch][row] for ch in text).rstrip() for row in range(5)]


def _visible_top(top, focus, count, height):
    """The first list row to show, near top, so that the focus row shows."""
    top = min(top, focus)
    top = max(top, focus - height + 1)
    return max(0, min(top, max(0, count - height)))


def _fields(answer, cmd):
    """The comma fields of an answer that starts with cmd, or None when it does not."""
    answer = str(answer).strip()
    if not answer.upper().startswith(cmd):
        return None
    rest = answer[len(cmd) :]
    if rest and rest[0] != " ":
        return None
    body = rest.strip()
    return body.split(",") if body else []


def _int(text):
    try:
        return int(str(text).strip())
    except ValueError:
        return None


def _parse_mhz(text):
    """Typed megahertz as hertz, or None: digits with at most one period, 1 to 9999 MHz."""
    text = text.strip()
    if not text or text.count(".") > 1 or not all(ch.isdigit() or ch == "." for ch in text) or text == ".":
        return None
    whole, _, part = text.partition(".")
    part = (part + "000000")[:6] if len(part) <= 6 else None
    if part is None:
        return None
    hz = int(whole or "0") * 1_000_000 + int(part)
    return hz if 1_000_000 <= hz <= 9_999_999_999 else None


def _key_name(key):
    """A key named in a message: "Capital L" for a capital letter, else its words."""
    key = str(key)
    if len(key) == 1 and "A" <= key <= "Z":
        return f"Capital {key}"
    return km.key_words(key)


# --------------------------------------------------------------------------- the list's rows


class Row(NamedTuple):
    rid: str  # what the row is
    band: int | None  # 0 or 1 for a band's row
    name: str  # the start of its line, and what a letter jumps by
    kind: str  # readonly, lock, choice, number, level, channel, toggle, action


_ACTIONS = (
    ("memory", "Memory channels"),
    ("clock", "Set the radio clock"),
    ("unkey", "Unkey now"),
    ("raw", "Raw command"),
    ("frame", "Send a CQ or beacon frame"),
    ("chat", "Chat window"),
    ("varac", "VarAC chat window"),
    ("radiogram", "Radiogram"),
    ("sstv", "SSTV"),
    ("rtty", "RTTY"),
)


def _make_rows():
    rows = [
        Row("daemon", None, "Daemon", "readonly"),
        Row("ptt", None, "PTT", "lock"),
        Row("radio", None, "Radio", "readonly"),
        Row("firmware", None, "Firmware", "readonly"),
        Row("control", None, "Control band", "choice"),
        Row("transmit", None, "Transmit band", "choice"),
        Row("step", None, "Step", "choice"),
    ]
    for b, letter in enumerate(BANDS):
        rows += [
            Row("frequency", b, f"{letter} frequency", "number"),
            Row("mode", b, f"{letter} mode", "choice"),
            Row("squelch", b, f"{letter} squelch", "level"),
            Row("power", b, f"{letter} power", "choice"),
            Row("source", b, f"{letter} source", "choice"),
            Row("channel", b, f"{letter} channel", "channel"),
            Row("busy", b, f"{letter} busy", "readonly"),
        ]
    rows += [
        Row("tnc_mode", None, "TNC mode", "choice"),
        Row("tnc_band", None, "TNC band", "choice"),
        Row("gps", None, "GPS output", "toggle"),
        Row("vox", None, "VOX", "readonly"),
    ]
    rows += [Row(f"do_{rid}", None, name, "action") for rid, name in _ACTIONS]
    return tuple(rows)


ROWS = _make_rows()
VOX_WORDS = "VOX is read only here. Try: d750 vox"

_MOVES = {"row_up": "up", "row_down": "down", "page_up": "pgup", "page_down": "pgdn", "first": "home", "last": "end"}
_STEPS = {"step_down": (-1, False), "step_up": (1, False), "big_down": (-1, True), "big_up": (1, True)}
_TUNES = {"tune_up": (1, 1), "tune_down": (-1, 1), "tune_up_big": (1, 10), "tune_down_big": (-1, 10)}


class Band:
    """What was read of one band. None is not read."""

    def __init__(self):
        self.hz = None
        self.mode = None
        self.sq = None
        self.power = None
        self.vm = None
        self.mr = None
        self.busy = None
        self.history = []


# --------------------------------------------------------------------------- the model


class ScreenModel:
    """Every decision of the screen. Used from one thread only."""

    def __init__(
        self,
        announce="message",
        live_meters="auto",
        step_khz=10,
        status_seconds=2.0,
        busy_seconds=1.0,
        view="face",
        digits="big",
        keymap=None,
        skipped=False,
        workspace=False,
        rig_key="F9",
        next_key="F12",
        mycall="N0CALL",
        varac="xarachat",
        xara_port=XARA_PORT,
    ):
        self.announce = announce if announce in ANNOUNCE else "message"
        self.live_meters = _live_words(live_meters)
        self.view = view if view in VIEWS else "face"
        self.digits = digits if digits in DIGITS else "big"
        self.keymap = km.Keymap() if keymap is None else keymap
        self.skipped = bool(skipped)
        self.step_index = STEPS_KHZ.index(step_khz) if step_khz in STEPS_KHZ else STEPS_KHZ.index(10)
        self.status_seconds = _seconds(status_seconds, 2.0, 0.5) or 2.0
        self.busy_seconds = _seconds(busy_seconds, 1.0, 0.25)
        self.workspace = bool(workspace)
        self.rig_key = str(rig_key or "F9")
        self.next_key = str(next_key or "F12")
        self.mycall = str(mycall or "").strip().upper()
        self.varac = str(varac or "xarachat").strip().lower()
        self.xara_port = None if xara_port is None else int(xara_port)  # None: it could not be read

        # The radio and the daemon, as last read. None is not read.
        self.bands = [Band(), Band()]
        self.ctrl = None
        self.tx = None
        self.tnc = None  # (mode, band)
        self.gps = None
        self.vox = None
        self.ident = None
        self.firmware = None
        self.no_daemon = False
        self.port_open = None
        self.keyed = False
        self.locked = None
        self.windows = ()
        self.log = []  # (at, line, answer), the newest last

        # What the screen is doing.
        self.mode = MAIN
        self.question = 0  # 0, or the number of the question open now; each new one is larger
        self.asked = None  # the kind of the question open now
        self._questions = 0
        self._too_fast_said = False
        self.active = 0
        self.focus = 0
        self.top = 0
        self.message = SKIPPED_WORDS if self.skipped else ""
        self.typing = None  # (target, band or row index)
        self.typed = ""
        self.help_focus = 0
        self.help_top = 0
        self.channels = []  # (number, hz, mode, offset)
        self.mem_focus = 0
        self.mem_top = 0
        self.width, self.height = 80, 24
        self.showing = shows(self.view, self.width, self.height)
        self.seen = self.showing
        self._send = {}  # what a send question would send
        self._origins = {}  # id of a Set or Tool sent, to (where it came from, the thing itself, more)

        # Reading.
        self._now = None
        self._out = None  # the Ask or MemoryRead out now; never two
        self._next_state = self._next_sweep = self._next_busy = None
        self._sweep_now = False
        self._state_now = False
        self._mem_started = False
        self._mem_reading = False
        self._mem_wanted = False
        self._mem_next = 0
        self._mem_restart = False
        self._mem_last_turn = False
        # Lock answers come from the lock and unlock Sets; a state read sent before one came back
        # keeps its other words but not its lock words.
        self._lock_answers = 0  # lock and unlock answers taken so far
        self._ask_locks = {}  # id of an Ask out, to (the Ask, lock answers when it went out)
        self._unlocking = 0  # this screen's unlocks out, not yet answered

    # ----------------------------------------------------------------- what is held

    @property
    def family(self):
        """The keymap's family for the wanted view: list, or face for the face and compact."""
        return "list" if self.view == "list" else "face"

    @property
    def step_khz(self):
        return STEPS_KHZ[self.step_index]

    def _step_hz(self):
        return int(round(self.step_khz * 1000))

    def focused(self):
        return ROWS[self.focus]

    def status(self):
        """Row 0."""
        if self.no_daemon:
            return "d750ctrl. No daemon."
        if self.port_open is False:
            return "d750ctrl. No radio."
        if self.keyed:
            return "d750ctrl. TRANSMITTING."
        if self.locked is None:
            return "d750ctrl. Starting."
        return "d750ctrl. Receiving. PTT locked." if self.locked else "d750ctrl. Receiving. Unlocked."

    def size(self, width, height):
        """The window's size: for Page Up and Page Down, the busy reads and the size messages."""
        self.width, self.height = int(width), int(height)
        new = shows(self.view, self.width, self.height)
        self.showing = new
        if new is None:
            # A question cannot be answered on a window that cannot show it: it is cancelled.
            if self.mode == ASKING:
                words = NO_WORDS.get(self.asked, NOTHING_SENT)
                self._end_question()
                self._tell(words)
            return
        seen, self.seen = self.seen, new
        if self.view != "face" or _kind(new) == _kind(seen):
            return
        if new == "compact":
            self._tell(TOO_SMALL_FACE)
        elif seen == "compact":
            self._tell(FACE_AGAIN)

    def help_rows(self):
        return self.keymap.help_rows(self.view)

    # ----------------------------------------------------------------- words for values

    def _freq(self, b):
        hz = self.bands[b].hz
        return None if hz is None else f"{mhz_text(hz)} MHz"

    def _mode_word(self, b):
        m = self.bands[b].mode
        return None if m is None else (MODES[m] if 0 <= m < len(MODES) else f"mode {m}")

    def _power_word(self, b):
        p = self.bands[b].power
        return None if p is None else (POWERS[p] if 0 <= p < len(POWERS) else f"power {p}")

    def _source_word(self, b):
        band = self.bands[b]
        if band.vm is None:
            return None
        if band.vm == 1:
            return f"memory {band.mr}" if band.mr else "memory"
        return "VFO"

    def _busy_word(self, b):
        busy = self.bands[b].busy
        return None if busy is None else ("BUSY" if busy else "quiet")

    def _tnc_words(self):
        """"KISS on B", or None."""
        if self.tnc is None:
            return None
        mode, band = self.tnc
        word = TNCS[mode] if 0 <= mode < len(TNCS) else f"mode {mode}"
        return f"{word} on {BANDS[band] if band in (0, 1) else band}"

    def row_line(self, row):
        """The list row for a control."""
        b, name = row.band, row.name
        letter = BANDS[b] if b is not None else ""
        rid = row.rid
        if rid == "daemon":
            if self.no_daemon:
                return "Daemon not answering"
            if self.port_open is None:
                return "Daemon not read"
            return "Daemon port open" if self.port_open else "Daemon port closed"
        if rid == "ptt":
            return "PTT not read" if self.locked is None else ("PTT locked" if self.locked else "PTT unlocked")
        if rid == "radio":
            return f"Radio {lines.clean(self.ident, 30)}" if self.ident else "Radio not read"
        if rid == "firmware":
            return f"Firmware {lines.clean(self.firmware, 28)}" if self.firmware else "Firmware not read"
        if rid in ("control", "transmit"):
            v = self.ctrl if rid == "control" else self.tx
            return f"{name} not read" if v is None else f"{name} {BANDS[v]}"
        if rid == "step":
            return f"Step {step_words(self.step_khz)}"
        value = {
            "frequency": lambda: self._freq(b),
            "mode": lambda: self._mode_word(b),
            "squelch": lambda: None if self.bands[b].sq is None else str(self.bands[b].sq),
            "power": lambda: self._power_word(b),
            "source": lambda: None if self.bands[b].vm is None else SOURCES[1 if self.bands[b].vm == 1 else 0],
            "tnc_mode": lambda: None if self.tnc is None else self._choice_word(TNCS, self.tnc[0]),
            "tnc_band": lambda: None if self.tnc is None else self._choice_word(BANDS, self.tnc[1]),
            "gps": lambda: None if self.gps is None else ONOFF[1 if self.gps else 0],
            "vox": lambda: None if self.vox is None else ONOFF[1 if self.vox else 0],
        }
        if rid == "channel":
            band = self.bands[b]
            if band.vm is None:
                return f"{name} not read"
            return f"{name} {band.mr}" if band.vm == 1 and band.mr else f"{name} none"
        if rid == "busy":
            word = self._busy_word(b)
            return f"{letter} busy not read" if word is None else f"{letter} {word}"
        if rid in value:
            v = value[rid]()
            return f"{name} not read" if v is None else f"{name} {v}"
        return name

    @staticmethod
    def _choice_word(words, index):
        return words[index] if 0 <= index < len(words) else str(index)

    def band_line(self, b):
        """What Tab says: "Band B. 144.390 MHz FM, power mid."."""
        freq = self._freq(b)
        if freq is None:
            return f"Band {BANDS[b]}. Not read."
        head = freq + (f" {self._mode_word(b)}" if self._mode_word(b) else "")
        power = self._power_word(b)
        return f"Band {BANDS[b]}. {head}" + (f", power {power}." if power else ".")

    # ----------------------------------------------------------------- saying

    def note(self, text):
        """Set the message row."""
        self.message = fit(text)

    def _say(self, text):
        """Focus moves and value changes in the list: the message row only with announce message."""
        if self.announce == "message":
            self.note(text)

    def _tell(self, text):
        """Refusals, errors, events: always the message row."""
        self.note(text)

    def _back_words(self):
        """What a way back to main mode says: the line in focus, or the active band's line."""
        if self.view == "list":
            return self.row_line(self.focused())
        return self.band_line(self.active)

    # ----------------------------------------------------------------- reading

    def _sweep_lines(self):
        out = ["state"]
        if self.ident is None:
            out.append("ID")
        if self.firmware is None:
            out.append("FV")
        out.append("BC")
        for b in (0, 1):
            out += [f"FQ {b}", f"MD {b}", f"SQ {b}", f"PC {b}", f"VM {b}"]
        out += ["BY 0", "BY 1", "TN", "GP", "VX"]
        return tuple(out)

    def _fast_busy(self):
        """Busy read by itself every busy_seconds: by live_meters, the view shown and the mode."""
        if self.busy_seconds <= 0 or self.mode != MAIN or self.showing is None:
            return False
        if self.live_meters == "yes":
            return True
        if self.live_meters == "no":
            return False
        return self.showing == "wide"

    def _issue(self, ask):
        """An Ask goes out: it is the read out now, and it notes how many lock answers came back
        before it, so that its state answer cannot undo a lock answered after it went out."""
        self._out = ask
        self._ask_locks[id(ask)] = (ask, self._lock_answers)

    def start(self):
        """What to do first: the state, then a full sweep, in one read."""
        ask = Ask(self._sweep_lines(), "start")
        self._issue(ask)
        return [ask] + ([Windows()] if self.workspace else [])

    def tick(self, now):
        """The monotonic time in seconds: what is due."""
        self._now = now
        if self._next_state is None:
            self._next_state = now + STATE_SECONDS
            self._next_sweep = now + self.status_seconds
            self._next_busy = now + self.busy_seconds
        return self._next_read()

    def _due(self):
        now = self._now
        timed = now is not None and self._next_state is not None
        sweep = self._sweep_now or (timed and now >= self._next_sweep)
        state = self._state_now or (timed and now >= self._next_state)
        busy = timed and self._fast_busy() and now >= self._next_busy
        return sweep, busy, state

    def _next_read(self):
        """At most one read, when none is out: a memory batch or the reads that are due."""
        if self._out is not None:
            return []
        sweep, busy, state = self._due()
        reads = sweep or busy or state
        if self._mem_wanted and (not reads or not self._mem_last_turn):
            self._mem_last_turn = True
            return [self._memory_batch()]
        self._mem_last_turn = False
        now = self._now
        if sweep:
            self._sweep_now = self._state_now = False
            if now is not None and self._next_state is not None:
                self._next_sweep = now + self.status_seconds
                self._next_busy = now + self.busy_seconds
                self._next_state = now + STATE_SECONDS
            ask = Ask(self._sweep_lines(), "sweep")
            self._issue(ask)
            return [ask] + ([Windows()] if self.workspace else [])
        if busy:
            self._next_busy = now + self.busy_seconds
            head = ()
            if state:
                head = ("state",)
                self._state_now = False
                self._next_state = now + STATE_SECONDS
            ask = Ask(head + ("BY 0", "BY 1"), "busy")
            self._issue(ask)
            return [ask]
        if state:
            self._state_now = False
            if now is not None and self._next_state is not None:
                self._next_state = now + STATE_SECONDS
            ask = Ask(("state",), "state")
            self._issue(ask)
            return [ask]
        return []

    def _sweep_soon(self):
        """A full sweep at once, or as soon as the read out now is back."""
        self._sweep_now = True
        return self._next_read()

    def _take(self, line, answer, read=False, lock_words=True):
        """An answer to a line: the value it holds is taken. True when it was taken.

        lock_words False: a state answer's locked or unlocked is not taken, because a lock or
        unlock was answered after its read went out.
        """
        parts = str(line).strip().split(None, 1)
        if not parts:
            return False
        cmd = parts[0].upper()
        args = parts[1].split(",") if len(parts) > 1 else []
        band = _int(args[0]) if args else None
        band = band if band in (0, 1) else None
        answer = str(answer).strip()
        if cmd == "STATE":
            if answer.startswith("ERR") or not answer:
                self.no_daemon = True
                return False
            if answer.startswith("port "):
                self.no_daemon = False
                self.port_open = answer.startswith("port open")
                self.keyed = "; keyed" in answer
                if lock_words:
                    locked = "; locked" in answer
                    if self.locked is True and not locked and not self._unlocking:
                        # The lock went away without this screen's unlock: the daemon started
                        # again, or another program unlocked. Said once, in both announce modes.
                        self._tell(LOCK_GONE)
                    self.locked = locked
                return True
            return False
        if cmd == "BY":
            if band is None:
                return False
            f = _fields(answer, "BY")
            busy = 1 if f is not None and len(f) >= 2 and f[1].strip() == "1" else 0
            if read:
                b = self.bands[band]
                b.busy = busy
                b.history = (b.history + [busy])[-HISTORY:]
            return f is not None
        f = _fields(answer, cmd)
        if f is None:
            return False
        if cmd == "ID":
            if not f:
                return False
            self.ident = ",".join(f).strip()
            return True
        if cmd == "FV":
            if not f:
                return False
            self.firmware = ",".join(f).strip()
            return True
        if cmd == "BC":
            if len(f) < 2 or _int(f[0]) not in (0, 1) or _int(f[1]) not in (0, 1):
                return False
            self.ctrl, self.tx = _int(f[0]), _int(f[1])
            return True
        if cmd == "TN":
            if len(f) < 2 or _int(f[0]) is None or _int(f[1]) is None:
                return False
            self.tnc = (_int(f[0]), _int(f[1]))
            return True
        if cmd == "GP":
            if len(f) < 2 or _int(f[1]) is None:
                return False
            self.gps = _int(f[1])
            return True
        if cmd == "VX":
            if not f or _int(f[0]) is None:
                return False
            self.vox = _int(f[0])
            return True
        if band is None:
            return False
        b = self.bands[band]
        if cmd == "MR":
            channel = f[-1].strip() if f else ""
            if not channel.isdigit():
                return False
            b.mr = f"{int(channel):03d}"
            b.vm = 1
            return True
        if len(f) < 2 or _int(f[1]) is None:
            return False
        value = _int(f[1])
        if cmd == "FQ":
            b.hz = value
        elif cmd == "MD":
            b.mode = value
        elif cmd == "SQ":
            b.sq = value
        elif cmd == "PC":
            b.power = value
        elif cmd == "VM":
            b.vm = value
            if value != 1:
                b.mr = None
        else:
            return False
        return True

    # ----------------------------------------------------------------- keys

    def key(self, name, early=False):
        """One key by name; returns the things to do.

        early: the key came within the quiet time of a question opening. In a question it
        answers nothing, but for the keys of unkey and lock, and Ctrl+C.
        """
        name = str(name)
        if name == "ctrl-l":
            return [Redraw()]
        if name == "ctrl-c":
            return [Quit()]
        if shows(self.view, self.width, self.height) is None:
            return self._key_too_small(name)
        if self.mode in (HELP, MEMORY, ASKING):
            action = self.keymap.action(self.family, name)
            if action in ("unkey", "lock"):
                return self._unkey_or_lock_anywhere(action)
        if self.mode == ASKING and early:
            if not self._too_fast_said:
                self._too_fast_said = True
                self._tell(TOO_FAST)
            return []
        handler = {
            MAIN: self._key_main,
            TYPING: self._key_typing,
            HELP: self._key_help,
            MEMORY: self._key_memory,
            ASKING: self._key_asking,
        }[self.mode]
        return handler(name)

    def urgent(self, name):
        """True when the key is a key of unkey or lock in the wanted view's family, in any mode."""
        return self.keymap.action(self.family, str(name)) in ("unkey", "lock")

    def _unkey_or_lock_anywhere(self, action):
        """The keys of unkey and lock in help, memory and a question: unkey is sent, and lock
        locks when the daemon is not locked. In a question they also answer no."""
        if self.mode == ASKING:
            words = NO_WORDS.get(self.asked, NOTHING_SENT)
            self._end_question()
            self._tell(words)
        if action == "unkey":
            return [Unkey()]
        if not self.locked:
            return self._send_set("lock", "lock")
        return []

    def _key_too_small(self, name):
        """Nothing shows. The keys of unkey and lock act as in a window big enough for a view, in
        every mode but typing; quit acts in main mode only; nothing else acts, so a letter typed as
        part of a value never acts. One difference: a question cannot be shown here, so lock while
        locked in main mode opens none, and says what a question cancelled by the size says."""
        if self.mode == TYPING:
            return []
        action = self.keymap.action(self.family, name)
        if action in ("unkey", "lock"):
            if self.mode != MAIN:
                return self._unkey_or_lock_anywhere(action)
            if action == "unkey":
                return [Unkey()]
            if self.locked:
                self._tell(NO_WORDS["unlock"])
                return []
            return self._send_set("lock", "lock")
        if action == "quit" and self.mode == MAIN:
            return [Quit()]
        return []

    def _key_main(self, name):
        # Fixed first: a digit or a period starts a frequency, whatever the keymap says.
        if len(name) == 1 and (name.isdigit() or name == "."):
            self._start_typing(("frequency", self.active), name)
            return []
        action = self.keymap.action(self.family, name)
        if action is not None:
            return self._do(action)
        if len(name) == 1 and "a" <= name <= "z":
            if self.view == "list":
                return self._jump(name)
            self._tell(self._nothing_on(name))
            return []
        if len(name) == 1 and "A" <= name <= "Z":
            self._tell(f"Nothing on capital {name}. Is Caps Lock on?")
            return []
        return []

    def _nothing_on(self, letter):
        key = self.keymap.first("face", "help")
        if key is not None:
            line = f"Nothing on {letter}. {km.short_words(key)} lists the keys."
            if len(line) <= lines.CELLS and not lines.problems(line, lines.CELLS):
                return line
        return f"Nothing on {letter}."

    def _do(self, action):
        """Carry out one action of the keymap in main mode."""
        if action in _MOVES:
            new = self._paged(self.focus, len(ROWS), _MOVES[action])
            if new == self.focus:
                return []
            self.focus = new
            self._keep_main()
            return self._landed()
        if action in _STEPS:
            return self._row_step(*_STEPS[action])
        if action in _TUNES:
            direction, count = _TUNES[action]
            return self._tune(self.active, direction * count, "face")
        simple = {
            "flip": self._flip,
            "edit": self._edit,
            "other_band": self._other_band,
            "help": self._open_help,
            "raw": self._open_raw,
            "view_next": self._view_next,
            "quit": self._quit,
            "unkey": lambda: [Unkey()],
            "lock": self._lock,
            "memory": self._open_memory,
            "sstv": lambda: self._ask("sstv"),
            "rtty": lambda: self._ask("rtty"),
            "next_step": self._next_step,
            "squelch_down": lambda: self._squelch(self.active, -1, "face"),
            "squelch_up": lambda: self._squelch(self.active, 1, "face"),
            "act_mode": lambda: self._next_choice(("mode", self.active), "face"),
            "act_power": lambda: self._next_choice(("power", self.active), "face"),
            "act_control": self._control_here,
            "act_source": lambda: self._next_choice(("source", self.active), "face"),
            "act_tnc": lambda: self._next_choice(("tnc_mode", None), "face"),
            "act_gps": lambda: self._next_choice(("gps", None), "face"),
            "set_clock": lambda: self._ask("clock"),
            "send_frame": self._frame,
            "chat": lambda: self._chat("chat"),
            "varac_chat": lambda: self._chat("varac"),
            "radiogram": lambda: self._tool("radiogram", ("radiogram", "new"), True, None),
        }
        if action in simple:
            return simple[action]()
        return []

    # ----------------------------------------------------------------- the list's moves

    def _page(self):
        return max(1, self.height - 3)

    def _paged(self, index, count, name):
        moves = {"up": index - 1, "down": index + 1, "home": 0, "end": count - 1}
        moves.update({"pgup": index - self._page(), "pgdn": index + self._page()})
        return max(0, min(count - 1, moves[name]))

    def _keep_main(self):
        self.top = _visible_top(self.top, self.focus, len(ROWS), self._page())

    def _landed(self):
        row = self.focused()
        if row.band is not None:
            self.active = row.band
        self._say(self.row_line(row))
        return []

    def _jump(self, letter):
        count = len(ROWS)
        for i in range(1, count + 1):
            j = (self.focus + i) % count
            if ROWS[j].name.lower().startswith(letter):
                self.focus = j
                self._keep_main()
                return self._landed()
        self._tell(f"No control starts with {letter}.")
        return []

    def _other_band(self):
        if self.view != "list":
            self.active ^= 1
            self._tell(self.band_line(self.active))
            return []
        row = self.focused()
        if row.band is None:
            self._tell("Tab works on a band's row.")
            return []
        for i, other in enumerate(ROWS):
            if other.rid == row.rid and other.band == 1 - row.band:
                self.focus = i
                self._keep_main()
                return self._landed()
        return []

    # ----------------------------------------------------------------- choices and steps

    def _choice(self, rid, band):
        """(the words, the index held, a function of the new index giving things to do), or None."""
        b = self.bands[band] if band is not None else None
        if rid == "control":
            if self.ctrl is None or self.tx is None:
                return None
            return BANDS, self.ctrl, lambda i: self._send_set(f"BC {i},{self.tx}", "row")
        if rid == "transmit":
            if self.ctrl is None or self.tx is None:
                return None
            return BANDS, self.tx, lambda i: self._send_set(f"BC {self.ctrl},{i}", "row")
        if rid == "step":
            return tuple(step_words(k) for k in STEPS_KHZ), self.step_index, self._set_step
        if rid == "mode":
            if b.mode is None:
                return None
            return MODES, b.mode, lambda i: self._send_set(f"MD {band},{i}", self._origin())
        if rid == "power":
            if b.power is None:
                return None
            return POWERS, b.power, lambda i: self._send_set(f"PC {band},{i}", self._origin())
        if rid == "source":
            if b.vm is None:
                return None
            return SOURCES, 1 if b.vm == 1 else 0, lambda i: self._send_set(f"VM {band},{i}", self._origin())
        if rid == "tnc_mode":
            if self.tnc is None:
                return None
            return TNCS, self.tnc[0], lambda i: self._tnc_question(i, self.tnc[1])
        if rid == "tnc_band":
            if self.tnc is None:
                return None
            return BANDS, self.tnc[1], lambda i: self._tnc_question(self.tnc[0], i)
        if rid == "gps":
            if self.gps is None:
                return None
            return ONOFF, 1 if self.gps else 0, lambda i: self._send_set(f"GP 1,{i}", self._origin())
        return None

    def _not_read(self, rid, band):
        names = {"tnc_mode": "TNC", "tnc_band": "TNC", "gps": "GPS output", "control": "Control band"}
        names.update({"transmit": "Transmit band"})
        if rid in names:
            return f"{names[rid]} not read."
        return f"{BANDS[band]} {rid} not read." if band is not None else f"{rid} not read."

    def _origin(self):
        return "row" if self.view == "list" else "face"

    def _next_choice(self, what, origin):
        """The next choice, going round: the face's acts and the list's flip."""
        rid, band = what
        held = self._choice(rid, band)
        if held is None:
            self._tell(self._not_read(rid, band))
            return []
        words, at, apply = held
        at = at if 0 <= at < len(words) else -1
        return apply((at + 1) % len(words))

    def _set_step(self, index):
        self.step_index = index
        if self.view == "list":
            self._say(self.row_line(self.focused()))
        else:
            self._tell(f"Step {step_words(self.step_khz)}.")
        return []

    def _next_step(self):
        return self._set_step((self.step_index + 1) % len(STEPS_KHZ))

    def _vox_or_readonly(self, row):
        if row.rid == "vox":
            self._tell(VOX_WORDS)
        else:
            self._tell(f"{row.name} cannot be set here.")
        return []

    def _row_step(self, direction, big):
        """One step or ten of the row in focus in the list."""
        row = self.focused()
        if row.kind == "lock":
            return self._lock()
        if row.kind == "readonly":
            return self._vox_or_readonly(row)
        if row.kind == "action":
            self._tell("Enter does what this row says.")
            return []
        if row.kind == "channel":
            self._tell("Enter types a channel number.")
            return []
        if row.kind == "number":
            return self._tune(row.band, direction * (10 if big else 1), "row")
        if row.kind == "level":
            return self._squelch(row.band, direction, "row")
        held = self._choice(row.rid, row.band)
        if held is None:
            self._tell(self._not_read(row.rid, row.band))
            return []
        words, at, apply = held
        new = at + direction
        if row.kind == "toggle":
            new = 1 if direction > 0 else 0
            if new == at:
                self._tell(f"{row.name} is already {words[at]}.")
                return []
            return apply(new)
        if not 0 <= new < len(words):
            self._tell(f"{row.name} is at its end.")
            return []
        return apply(new)

    def _flip(self):
        row = self.focused()
        if row.kind == "lock":
            return self._lock()
        if row.kind == "readonly":
            return self._vox_or_readonly(row)
        if row.kind == "action":
            self._tell("Enter does what this row says.")
            return []
        if row.kind == "channel":
            self._tell("Enter types a channel number.")
            return []
        if row.kind in ("number", "level"):
            self._tell("Enter types a value here.")
            return []
        return self._next_choice((row.rid, row.band), "row")

    def _edit(self):
        row = self.focused()
        if row.kind == "lock":
            return self._lock()
        if row.kind == "readonly":
            return self._vox_or_readonly(row)
        if row.kind == "action":
            return self._row_action(row.rid[3:])
        if row.kind == "number":
            self._start_typing(("frequency", row.band), "")
            return []
        if row.kind == "level":
            self._start_typing(("squelch", row.band), "")
            return []
        if row.kind == "channel":
            self._start_typing(("channel", row.band), "")
            return []
        held = self._choice(row.rid, row.band)
        if held is None:
            self._tell(self._not_read(row.rid, row.band))
            return []
        self._start_typing(("choice", self.focus), "")
        if row.rid == "step":
            self._tell("Type a step in kHz, such as 12.5.")
        else:
            self._tell(fit("Choices: " + ", ".join(held[0])) or "Type the start of a choice.")
        return []

    def _row_action(self, rid):
        return {
            "memory": self._open_memory,
            "clock": lambda: self._ask("clock"),
            "unkey": lambda: [Unkey()],
            "raw": self._open_raw,
            "frame": self._frame,
            "chat": lambda: self._chat("chat"),
            "varac": lambda: self._chat("varac"),
            "radiogram": lambda: self._tool("radiogram", ("radiogram", "new"), True, None),
            "sstv": lambda: self._ask("sstv"),
            "rtty": lambda: self._ask("rtty"),
        }[rid]()

    # ----------------------------------------------------------------- setting the radio

    def _send_set(self, line, origin, more=None):
        todo = Set(line)
        self._origins[id(todo)] = (origin, todo, more)
        return [todo]

    def _tune(self, band, steps, origin):
        hz = self.bands[band].hz
        if hz is None:
            self._tell(f"{BANDS[band]} frequency not read.")
            return []
        new = hz + steps * self._step_hz()
        if not 0 < new <= 9_999_999_999:
            self._tell(f"{BANDS[band]} frequency is at its end.")
            return []
        return self._send_set(f"FQ {band},{new:010d}", origin)

    def _squelch(self, band, direction, origin):
        sq = self.bands[band].sq
        if sq is None:
            self._tell(f"{BANDS[band]} squelch not read.")
            return []
        new = sq + direction
        if not 0 <= new <= 9:
            self._tell(f"{BANDS[band]} squelch is at its end.")
            return []
        return self._send_set(f"SQ {band},{new}", origin)

    def _control_here(self):
        a = self.active
        return self._send_set(f"BC {a},{a}", "face")

    def _lock(self):
        """lock: locks at once, or asks to unlock when locked."""
        if self.locked:
            return self._ask("unlock")
        return self._send_set("lock", "lock")

    def _tnc_question(self, mode, band):
        self._send = {"tnc": (mode, band)}
        return self._ask("tnc")

    # ----------------------------------------------------------------- questions

    def _ask(self, kind):
        """Open a question: asking mode, a new and larger question number, and its kind."""
        self.mode = ASKING
        self.asked = kind
        self._questions += 1
        self.question = self._questions
        self._too_fast_said = False
        return []

    def _end_question(self):
        self.mode = MAIN
        self.asked = None
        self.question = 0

    def question_text(self):
        q = self.asked
        if q == "unlock":
            return UNLOCK_QUESTION
        if q == "view":
            return VIEW_QUESTION
        if q == "tnc":
            mode, band = self._send.get("tnc", (0, 0))
            word = TNCS[mode] if 0 <= mode < len(TNCS) else str(mode)
            return f"TNC to {word} on band {self._band_letter(band)}? y or n"
        if q == "clock":
            return CLOCK_QUESTION
        if q == "frame":
            return FRAME_QUESTION
        if q == "frame_send":
            what = "one beacon" if self._send.get("beacon") else "one CQ frame"
            return f"Send {what}{self._on_band()}? y or n"
        if q == "quit":
            return QUIT_QUESTION
        if q == "sstv":
            return "SSTV: r receive, s send"
        if q == "rtty":
            return "RTTY: r receive, s send"
        if q == "sstv_send":
            return f"Send the picture{self._on_band()}? y or n"
        if q == "rtty_send":
            return f"Send this text{self._on_band()}? y or n"
        return ""

    @staticmethod
    def _band_letter(band):
        return BANDS[band] if band in (0, 1) else str(band)

    def _on_band(self):
        """" on band B", naming the transmit band, or nothing when it is not read."""
        return f" on band {BANDS[self.tx]}" if self.tx in (0, 1) else ""

    def _key_asking(self, name):
        q = self.asked
        self._end_question()
        if q == "view":
            return self._view_answer(name)
        if q == "quit":
            if name == "y":
                return [Quit(), CloseWorkspace()]
            if name == "n":
                return [Quit()]
            self._tell(NO_WORDS["quit"])
            return []
        if q in ("sstv", "rtty"):
            if name == "r":
                default = "150" if q == "sstv" else "60"
                self._start_typing((f"{q}_seconds", None), "")
                self._send = {"default": default}
                return []
            if name == "s":
                refused = self._send_refused()
                if refused:
                    self._tell(refused)
                    return []
                self._send = {}
                self._start_typing(("sstv_picture" if q == "sstv" else "rtty_text", None), "")
                return []
            self._tell(NO_WORDS[q])
            return []
        if q == "frame":
            if name in ("c", "b"):
                self._send = {"beacon": name == "b"}
                return self._ask("frame_send")
            self._tell(NOTHING_SENT)
            return []
        if name != "y":
            self._tell(NO_WORDS.get(q, NOTHING_SENT))
            return []
        # Only the small letter y comes here.
        if q == "unlock":
            self._unlocking += 1  # until its answer comes, an unlocked state is this screen's own
            return self._send_set("unlock", "lock")
        if q == "tnc":
            mode, band = self._send.get("tnc", (None, None))
            if mode is None:
                return []
            return self._send_set(f"TN {mode},{band}", self._origin())
        if q == "clock":
            return [Clock()]
        if q in ("frame_send", "sstv_send", "rtty_send"):
            refused = self._send_refused()
            if refused:
                self._tell(refused)
                return []
            if q == "frame_send":
                return [SendFrame(bool(self._send.get("beacon")))]
            argv = self._send.get("argv")
            if not argv:
                return []
            return self._tool(q[:4], argv, True, None)
        return []

    def _send_refused(self):
        """The words refusing a frame or a send, or None: the lock must be known and off."""
        if self.locked is None or self.no_daemon:
            return UNKNOWN_NOTHING_SENT
        if self.locked:
            return LOCKED_NOTHING_SENT
        return None

    def _frame(self):
        refused = self._send_refused()
        if refused:
            self._tell(refused)
            return []
        if self.xara_port is None:
            self._tell(NO_XARA_PORT)
            return []
        if not self.mycall or self.mycall == "N0CALL":
            self._tell(NO_MYCALL)
            return []
        return self._ask("frame")

    def _quit(self):
        if self.workspace and self.windows:
            self._tell("Windows open: " + ", ".join(lines.clean(w, 20) for w in self.windows) + ".")
            return self._ask("quit")
        return [Quit()]

    # ----------------------------------------------------------------- views

    def _view_next(self):
        if self.view == "list":
            return self._ask("view")
        self._change_view(VIEWS[(VIEWS.index(self.view) + 1) % len(VIEWS)])
        return []

    def _change_view(self, view):
        self.view = view
        new = shows(self.view, self.width, self.height)
        self.showing = new
        if new is None:
            return
        self.seen = new
        if self.view == "face" and new == "compact":
            self._tell(TOO_SMALL_FACE)
        else:
            self._tell(f"View: {self.view}.")

    def _view_answer(self, name):
        if name != "y":
            self._tell(STILL_THE_LIST)
            return []
        self._change_view("face")
        if self.showing == "compact":
            self._tell(TO_COMPACT)
        elif self.showing is not None:
            self._tell(TO_THE_FACE)
        return []

    # ----------------------------------------------------------------- tools

    def _tool(self, name, argv, pause, other):
        todo = Tool(name, tuple(argv), pause, other)
        self._origins[id(todo)] = ("tool", todo, None)
        return [todo]

    def _chat(self, which):
        if which == "varac" and self.varac == "openslot":
            return self._tool("varac", ("openslot", "--tui"), False, None)
        other = "varac" if which == "chat" else "chat"
        argv = ("xarachat", "--tui") + (("--varac", "yes") if which == "varac" else ())
        return self._tool(which, argv, False, other)

    def _tool_words(self, todo, result):
        name = todo.name
        words = TOOL_WORDS.get(name, lines.clean(name, 20) or "The tool")
        sends = "tx" in todo.argv
        if result == "missing":
            return f"{words} is not installed."
        if result in ("selected", "other") and sends:
            return f"{words} window is open. {NOTHING_SENT}"
        if result == "other":
            if name == "chat":
                return "Xarachat is in varac. /varac off there."
            if name == "varac":
                return "Xarachat is in chat. /varac on there."
            return f"{words} is in another window."
        if result == "selected":
            return f"{words} window. {self.rig_key} comes back here."
        if result == "opened":
            return f"{words} opened. {self.rig_key} comes back here."
        if result == "failed":
            return f"No window for {lines.clean(name, 20)}."
        if result == "ran":
            return f"{words} ended."
        return f"{words}: {lines.clean(result, 30)}"

    # ----------------------------------------------------------------- help, raw, memory

    def _open_help(self):
        self.mode = HELP
        rows = self.help_rows()
        self.help_focus = max(0, min(self.help_focus, len(rows) - 1))
        if rows:
            self._say(rows[self.help_focus])
        return []

    def _key_help(self, name):
        if name in ("esc", "?", self.keymap.first(self.family, "help")):
            self.mode = MAIN
            self._say(self._back_words())
            return []
        if name in ("up", "down", "pgup", "pgdn", "home", "end"):
            rows = self.help_rows()
            if not rows:
                return []
            self.help_focus = max(0, min(self.help_focus, len(rows) - 1))
            new = self._paged(self.help_focus, len(rows), name)
            if new != self.help_focus:
                self.help_focus = new
                self.help_top = _visible_top(self.help_top, new, len(rows), self._page())
                self._say(rows[new])
        return []

    def _open_raw(self):
        self._start_typing(("raw", None), "")
        return []

    def _open_memory(self):
        self.mode = MEMORY
        if not self._mem_started:
            self._mem_started = True
            return self._read_memory()
        if self._mem_reading:
            self._tell(READING_MEMORY)
        else:
            rows = self.memory_rows()
            self.mem_focus = max(0, min(self.mem_focus, len(rows) - 1))
            self._say(rows[self.mem_focus])
        return []

    def _read_memory(self):
        """Read channels 000 to 199 again, ten at a time."""
        self.channels = []
        self.mem_focus = self.mem_top = 0
        self._mem_reading = True
        self._mem_next = 0
        if isinstance(self._out, MemoryRead):
            self._mem_restart = True
        else:
            self._mem_wanted = True
        self._tell(READING_MEMORY)
        return self._next_read()

    def _memory_batch(self):
        first = self._mem_next
        todo = MemoryRead(first, min(MEMORY_LAST, first + MEMORY_BATCH - 1))
        self._mem_wanted = False
        self._out = todo
        return todo

    def memory_rows(self):
        if not self.channels:
            return [READING_MEMORY if self._mem_reading else NO_MEMORY]
        return [self._memory_line(*ch) for ch in self.channels]

    def _memory_line(self, number, hz, mode, offset):
        word = MODES[mode] if mode is not None and 0 <= mode < len(MODES) else "mode unknown"
        line = f"{number:03d} {mhz_text(hz)} MHz {word}"
        if offset is not None:
            line += f", offset {mhz_text(offset)} MHz"
        return line

    def _key_memory(self, name):
        if name == "esc" or self.keymap.action(self.family, name) == "memory":
            self.mode = MAIN
            self._say(self._back_words())
            return []
        if name in ("up", "down", "pgup", "pgdn", "home", "end"):
            rows = self.memory_rows()
            new = self._paged(self.mem_focus, len(rows), name)
            if new != self.mem_focus:
                self.mem_focus = new
                self.mem_top = _visible_top(self.mem_top, new, len(rows), self._page())
                self._say(rows[new])
            return []
        if name == "R":
            return self._read_memory()
        if name == "enter":
            if not self.channels:
                self._tell(READING_MEMORY if self._mem_reading else NO_MEMORY)
                return []
            number = self.channels[min(self.mem_focus, len(self.channels) - 1)][0]
            self.mode = MAIN
            return self._send_set(f"MR {self.active},{number:03d}", "memory")
        return []

    # ----------------------------------------------------------------- typing

    def _start_typing(self, target, first):
        """Typing starts with an empty message row: an old message must not sit above it."""
        self.mode = TYPING
        self.typing = target
        self.typed = first
        self.message = ""

    def typing_prompt(self):
        target, where = self.typing if self.typing else (None, None)
        if target == "frequency":
            return f"Band {BANDS[where]} frequency in MHz"
        if target == "squelch":
            return f"Band {BANDS[where]} squelch, 0 to 9"
        if target == "channel":
            return f"Band {BANDS[where]} channel, 000 to 199"
        if target == "raw":
            return "Raw command"
        if target == "choice":
            return ROWS[where].name
        prompts = {
            "sstv_seconds": "Seconds to listen, 150",
            "rtty_seconds": "Seconds to listen, 60",
            "sstv_picture": "Picture file to send",
            "sstv_mode": "SSTV mode, ROBOT 36",
            "rtty_text": "Text to send",
        }
        return prompts.get(target, "Type")

    def _typing_row(self):
        """The bottom row while typing, and the column just after its last character.

        The shown copy is the typed text through lines.clean; its end shows. The row is 39
        cells or fewer, so the cursor fits after it.
        """
        prefix = self.typing_prompt() + ":"
        room = lines.CELLS - 1 - len(prefix) - 1
        shown = lines.clean(self.typed, TYPED_MOST + 10)
        if len(shown) > room:
            shown = shown[-room:] if room > 0 else ""
        shown = shown.lstrip(" ")
        row = (prefix + " " + shown).rstrip(" ")
        while shown and lines.problems(row, lines.CELLS):
            shown = shown[1:].lstrip(" ")
            row = (prefix + " " + shown).rstrip(" ")
        return row, len(row)

    def _key_typing(self, name):
        if name == "esc":
            self.mode = MAIN
            self.typing = None
            self.typed = ""
            self._say(self._back_words())
            return []
        if name == "enter":
            return self._apply_typed()
        if name == "backspace":
            self.typed = self.typed[:-1]
            return []
        ch = " " if name == "space" else name
        refusal = self._typing_refusal(ch)
        if refusal is not None:
            if refusal:
                self._tell(refusal)
            return []
        self.typed += ch
        return []

    def _typing_refusal(self, ch):
        """None when a typed character may be added; else its words, empty when it says nothing."""
        if len(ch) != 1 or not " " <= ch <= "~":
            return ""
        if len(self.typed) >= TYPED_MOST:
            return "That is as long as it can be."
        return None

    # ----------------------------------------------------------------- pastes

    def paste(self, text, left_out=False):
        """A paste, known by its marks. In typing mode its text is added, each character by the
        test a typed character passes, and nothing is applied. Anywhere else, and when the window
        is too small, nothing changes but the message row. Always returns an empty list."""
        text = str(text)
        if self.mode != TYPING or shows(self.view, self.width, self.height) is None:
            self._tell(PASTE_DROPPED)
            return []
        kept = 0
        turned_away = bool(left_out)
        for ch in text:
            if self._typing_refusal(ch) is None:
                self.typed += ch
                kept += 1
            else:
                turned_away = True
        if kept == 0:
            self._tell(NOTHING_PASTED)
        else:
            count = f"{kept} character" + ("" if kept == 1 else "s")
            self._tell(f"Pasted {count}, some left out." if turned_away else f"Pasted {count}. Enter applies.")
        return []

    def unkeys(self, name):
        """True when the key is a key of unkey in the wanted view's family, in any mode."""
        return self.keymap.action(self.family, str(name)) == "unkey"

    def unkey_now(self):
        """What unkey does in main mode, in any mode: what was typed, a question or a mode stay."""
        return [Unkey()]

    def late(self, name):
        """A key that came inside or right after a paste. A key of unkey unkeys; a key of lock locks
        when the daemon says it is not locked; anything else does nothing. Nothing else changes."""
        action = self.keymap.action(self.family, str(name))
        if action == "unkey":
            return [Unkey()]
        if action == "lock" and self.locked is False and not self.no_daemon:
            return self._send_set("lock", "lock")
        return []

    def _finish_typing(self):
        self.mode = MAIN
        target = self.typing
        self.typing = None
        text = self.typed
        self.typed = ""
        return target, text

    def _apply_typed(self):
        """Enter while typing. A value that cannot be used keeps typing mode, with its words."""
        target, where = self.typing
        text = self.typed
        if target in ("sstv_seconds", "rtty_seconds"):
            seconds = text.strip() or self._send.get("default", "60")
            if not seconds.isdigit() or int(seconds) <= 0:
                self._tell("Seconds are a whole number.")
                return []
            self._finish_typing()
            tool = "d750-sstv" if target == "sstv_seconds" else "d750-rtty"
            return self._tool(target[:4], (tool, "rx", seconds), True, None)
        if target == "sstv_picture":
            self._finish_typing()
            if not text.strip():
                self._tell(f"No picture. {NOTHING_SENT}")
                return []
            self._send = {"picture": text.strip()}
            self._start_typing(("sstv_mode", None), "")
            return []
        if target == "sstv_mode":
            self._finish_typing()
            mode = text.strip().upper().replace(" ", "_") or "ROBOT_36"
            picture = self._send.get("picture", "")
            self._send = {"argv": ("d750-sstv", "tx", picture, mode)}
            name = picture.rstrip("/").rsplit("/", 1)[-1]
            self._tell(fit(f"Picture {lines.clean(name, 30)}, mode {lines.clean(mode.replace('_', ' '), 20)}."))
            return self._ask("sstv_send")
        if target == "rtty_text":
            self._finish_typing()
            if not text.strip():
                self._tell(f"No text. {NOTHING_SENT}")
                return []
            self._send = {"argv": ("d750-rtty", "tx", text)}
            self._tell(fit("Text: " + lines.clean(text, 60)) or "Text to send.")
            return self._ask("rtty_send")
        if not text.strip():
            self._finish_typing()
            self._tell("Nothing typed, nothing changed.")
            return []
        if target == "raw":
            return self._raw(text)
        if target == "frequency":
            hz = _parse_mhz(text)
            if hz is None:
                self._tell(fit(f"Not a frequency: {lines.clean(text, 20)}") or "Not a frequency.")
                return []
            self._finish_typing()
            return self._send_set(f"FQ {where},{hz:010d}", self._origin())
        if target == "squelch":
            v = _int(text)
            if v is None or not 0 <= v <= 9:
                self._tell("Squelch is 0 to 9.")
                return []
            self._finish_typing()
            return self._send_set(f"SQ {where},{v}", "row")
        if target == "channel":
            v = _int(text)
            if v is None or not 0 <= v <= MEMORY_LAST:
                self._tell("A channel is 000 to 199.")
                return []
            self._finish_typing()
            return self._send_set(f"MR {where},{v:03d}", "memory")
        if target == "choice":
            row = ROWS[where]
            held = self._choice(row.rid, row.band)
            if held is None:
                self._finish_typing()
                self._tell(self._not_read(row.rid, row.band))
                return []
            words, _at, apply = held
            index = self._typed_choice(row, words, text)
            if index is None:
                self._tell("Type the start of a choice.")
                return []
            self._finish_typing()
            return apply(index)
        self._finish_typing()
        return []

    @staticmethod
    def _typed_choice(row, words, text):
        typed = text.strip().lower()
        if row.rid == "step":
            typed = typed.removesuffix("khz").strip()
            for i, khz in enumerate(STEPS_KHZ):
                if typed == f"{khz:g}":
                    return i
            return None
        exact = [i for i, w in enumerate(words) if w.lower() == typed]
        if exact:
            return exact[0]
        starts = [i for i, w in enumerate(words) if w.lower().startswith(typed)]
        return starts[0] if len(starts) == 1 else None

    def _tnc_refused(self):
        """A raw TN with a value: the TNC changes only through its question."""
        key = self.keymap.first("face", "act_tnc") if self.family == "face" else None
        if key is not None:
            for named in (km.spoken_words(key), km.short_words(key)):
                said = f"Refused. The {named} key changes the TNC."
                if len(said) <= lines.CELLS and not lines.problems(said, lines.CELLS):
                    return said
        return "Refused. The TNC mode row changes it."

    def _raw(self, text):
        """A raw command: refused when it can key or move the radio, or is a daemon word."""
        self._finish_typing()
        stripped = text.strip()
        head = stripped[:2].upper()
        if head in UNSAFE:
            self._tell(f"Refused: {head} can key or move the radio.")
            return []
        upper = stripped.upper()
        if upper.startswith("VX") and upper[2:].strip() not in ("", "0"):
            self._tell(VOX_REFUSED)
            return []
        if upper.startswith("TN") and upper[2:].strip():
            self._tell(self._tnc_refused())
            return []
        word = stripped.split()[0].lower()
        if word in ("lock", "unlock"):
            key = self.keymap.first(self.family, "lock")
            said = f"Refused. {_key_name(key)} locks and unlocks."
            self._tell(said if len(said) <= lines.CELLS else "Refused. The lock key locks and unlocks.")
            return []
        if word in ("quit", "reconnect"):
            said = f"Refused: {word} is the daemon's own word."
            self._tell(said if len(said) <= lines.CELLS else f"Refused: {word} is a daemon word.")
            return []
        if stripped.lower() in DAEMON_WORDS:
            # The daemon takes its words only alone and in small letters: STATE goes as state.
            return self._send_set(stripped.lower(), "raw")
        return self._send_set(text, "raw")

    # ----------------------------------------------------------------- results

    def _log(self, at, line, answer):
        self.log.append((str(at), str(line), str(answer)))
        del self.log[:-LOG_MOST]

    def finished(self, todo, result=None, error=None, at=""):
        """A thing to do was carried out: its result, or the error it raised. Gives more to do."""
        origin = self._origins.pop(id(todo), None)
        if isinstance(todo, Set) and str(todo.line).strip() == "unlock" and self._unlocking:
            self._unlocking -= 1  # answered, or failed: no longer out
        if isinstance(todo, (Ask, MemoryRead)) and (self._out is todo or self._out == todo):
            self._out = None
        if isinstance(todo, Ask) and error is not None:
            self._ask_locks.pop(id(todo), None)
        if error is not None:
            if isinstance(todo, MemoryRead):
                self._mem_reading = False
                self._mem_restart = False
            self._tell(fit(f"Fail: {error}") or "Fail: an error with no words.")
            return self._next_read() if isinstance(todo, (Ask, MemoryRead)) else []
        if isinstance(todo, Ask):
            return self._read_back(todo, result, at)
        if isinstance(todo, Set):
            return self._set_back(todo, result, at, origin)
        if isinstance(todo, Unkey):
            answer = str(result if result is not None else "").strip()
            self._log(at, "T 0", answer)
            if answer == "RPRT 0":
                self._tell("Unkey sent.")
            else:
                self._tell(fit(f"Unkey failed: {lines.clean(answer, 40) or 'no answer'}"))
            self._state_now = True
            return self._next_read()
        if isinstance(todo, Clock):
            answer = str(result if result is not None else "").strip()
            self._log(at, "RT", answer)
            if _fields(answer, "RT") is not None:
                self._tell("Radio clock set.")
            elif answer.startswith("ERR") or not answer:
                self._tell("No answer: the clock.")
            else:
                self._tell("Radio refused: the clock.")
            return self._sweep_soon()
        if isinstance(todo, SendFrame):
            what = "Beacon" if todo.beacon else "CQ frame"
            if result is None or str(result) == "":
                self._tell(f"{what} handed to xara.")
            else:
                self._tell(f"Xara does not answer on port {self.xara_port}.")
            return []
        if isinstance(todo, MemoryRead):
            return self._memory_back(todo, result)
        if isinstance(todo, Tool):
            self._tell(fit(self._tool_words(todo, str(result))))
            return [Windows()] if self.workspace else []
        if isinstance(todo, Windows):
            self.windows = tuple(str(w) for w in (result or ()) if str(w) and str(w) != "rig")
            return []
        return []

    def _read_back(self, todo, result, at):
        answers = tuple(result) if result is not None else ()
        entry = self._ask_locks.pop(id(todo), None)
        if entry is None:  # handed back as an equal copy: the oldest equal Ask out
            key = next((k for k, (ask, _n) in self._ask_locks.items() if ask == todo), None)
            entry = self._ask_locks.pop(key) if key is not None else None
        lock_words = entry is None or entry[1] == self._lock_answers
        for i, line in enumerate(todo.lines):
            answer = str(answers[i]).strip() if i < len(answers) else "ERR no answer"
            if answer.startswith("ERR"):
                self._log(at, line, answer)
            self._take(line, answer, read=True, lock_words=lock_words)
        if todo.why in ("start", "sweep"):
            memory = tuple(f"MR {b}" for b in (0, 1) if self.bands[b].vm == 1)
            if memory:
                ask = Ask(memory, "channel")
                self._issue(ask)
                return [ask]
        return self._next_read()

    def _set_back(self, todo, result, at, origin):
        answer = str(result if result is not None else "").strip()
        self._log(at, todo.line, answer)
        where, _todo, _more = origin if origin else (None, None, None)
        line = todo.line.strip()
        cmd = line.split()[0].upper() if line else ""
        if where is None:
            where = "lock" if cmd in ("LOCK", "UNLOCK") else self._origin()
        if where == "lock":
            if cmd == "LOCK" and NO_RX_WORDS in answer:
                # The lock holds, but the radio did not say it is receiving: locked, and said.
                self.locked = True
                self._lock_answers += 1
                self._tell(LOCKED_NO_RX)
            elif answer.startswith("OK"):
                self.locked = cmd == "LOCK"
                self._lock_answers += 1
                self._tell("PTT locked." if self.locked else "PTT unlocked.")
            elif answer.startswith("ERR") or not answer:
                self._tell(f"No answer: PTT {cmd.lower()}.")
            else:
                self._tell(fit(f"Daemon said: {lines.clean(answer, 40)}"))
            return self._sweep_soon()
        taken = self._take(line, answer, lock_words=False)  # a raw state line never sets the lock
        if where == "raw":
            self._tell(fit(f"Answer: {lines.clean(answer, 60)}") if answer else "Answer: none.")
            return self._sweep_soon()
        what, band = self._what(line)
        if not taken:
            if answer.startswith("ERR") or not answer:
                self._tell(f"No answer: {what}.")
            else:
                self._tell(f"Radio refused: {what}.")
            return self._sweep_soon()
        if where == "memory":
            b = self.bands[band] if band is not None else None
            channel = b.mr if b is not None and b.mr else line.rsplit(",", 1)[-1]
            self._tell(f"Band {self._band_letter(band)} on channel {channel}.")
        elif where == "row" and self.view == "list":
            self._say(self.row_line(self.focused()))
        else:
            self._said(cmd, band)
        return self._sweep_soon()

    def _what(self, line):
        """What a set line changes, in words for a refusal: "A squelch", "TNC"."""
        parts = line.split(None, 1)
        cmd = parts[0].upper()
        args = parts[1].split(",") if len(parts) > 1 else []
        band = _int(args[0]) if args else None
        band = band if band in (0, 1) else None
        names = {"FQ": "frequency", "MD": "mode", "SQ": "squelch", "PC": "power", "VM": "source", "MR": "channel"}
        if cmd in names and band is not None:
            return f"{BANDS[band]} {names[cmd]}", band
        others = {"BC": "control band", "TN": "TNC", "GP": "GPS output"}
        return others.get(cmd, lines.clean(cmd, 10) or "that"), band

    def _said(self, cmd, band):
        """The face's words for a change the radio took."""
        if cmd == "FQ" and band is not None:
            # Tuning follows announce: the frequency is where the cursor is.
            self._say(f"Band {BANDS[band]} {self._freq(band)}.")
            return
        if cmd == "SQ" and band is not None:
            self._tell(f"Band {BANDS[band]} squelch {self.bands[band].sq}.")
        elif cmd == "PC" and band is not None:
            self._tell(f"Band {BANDS[band]} power {self._power_word(band)}.")
        elif cmd == "MD" and band is not None:
            self._tell(f"Band {BANDS[band]} mode {self._mode_word(band)}.")
        elif cmd == "VM" and band is not None:
            self._tell(f"Band {BANDS[band]} source {SOURCES[1 if self.bands[band].vm == 1 else 0]}.")
        elif cmd == "BC":
            if self.ctrl == self.tx and self.ctrl in (0, 1):
                self._tell(f"Band {BANDS[self.ctrl]} controls and transmits.")
            else:
                self._tell(f"Control band {self._band_letter(self.ctrl)}. Transmit band {self._band_letter(self.tx)}.")
        elif cmd == "GP":
            self._tell(f"GPS output {'on' if self.gps else 'off'}.")
        elif cmd == "TN" and self.tnc is not None:
            mode, tband = self.tnc
            word = TNCS[mode] if 0 <= mode < len(TNCS) else str(mode)
            self._tell(f"TNC {word} on band {self._band_letter(tband)}.")
        elif cmd == "MR" and band is not None:
            self._tell(f"Band {BANDS[band]} on channel {self.bands[band].mr}.")

    def _memory_back(self, todo, result):
        if self._mem_restart:
            self._mem_restart = False
            self._mem_wanted = True
            return self._next_read()
        for item in result or ():
            try:
                number, answer = item
            except (TypeError, ValueError):
                continue
            f = _fields(answer, "ME")
            if f is None or len(f) < 2 or _int(f[1]) is None:
                continue
            mode = _int(f[5]) if len(f) > 5 else None
            offset = _int(f[2]) if len(f) > 2 else None
            self.channels.append((int(number), _int(f[1]), mode, offset))
        self._mem_next = todo.last + 1
        if self._mem_next > MEMORY_LAST:
            self._mem_reading = False
            count = len(self.channels)
            if count == 0:
                self._tell(NO_MEMORY)
            else:
                plural = "channel" if count == 1 else "channels"
                self._tell(f"{count} memory {plural} in 000 to {MEMORY_LAST:03d}.")
            return self._next_read()
        self._mem_wanted = True
        return self._next_read()

    # ----------------------------------------------------------------- the frame

    def _bottom(self):
        """The bottom row, and the cursor's column when the cursor goes there, else None."""
        if self.mode == TYPING:
            return self._typing_row()
        if self.mode == ASKING:
            text = _safe(self.question_text())
            return text, min(len(text), lines.CELLS - 1)
        if self.mode == HELP:
            return HELP_HINT, None
        if self.mode == MEMORY:
            return MEMORY_HINT, None
        return self.keymap.hint(self.view), None

    def frame(self, width, height):
        """The rows to draw, where the cursor goes, the row in focus and the marks. Changes nothing."""
        shown = shows(self.view, width, height)
        if shown is None:
            text = TOO_SMALL if self.view == "list" else TOO_SMALL_COMPACT
            rows = ((text,) + ("",) * max(0, height - 1))[: max(0, height)]
            return Frame(rows, (0, 0), None)
        if shown == "list" or self.mode in (HELP, MEMORY):
            return self._list_frame(height)
        if shown == "compact":
            return self._compact_frame(height)
        if shown == "stacked":
            return self._stacked_frame(height)
        return self._wide_frame(width, height)

    def _cursor(self, height, row, column=0):
        _, at = self._bottom()
        return (height - 1, at) if at is not None else (row, column)

    def _ends(self, height, body):
        middle = [""] * max(0, height - 2 - len(body))
        return [*body, *middle, self.message, self._bottom()[0]][:height]

    def _list_items(self):
        if self.mode == HELP:
            rows = list(self.help_rows()) or [""]
            return rows, max(0, min(self.help_focus, len(rows) - 1)), self.help_top
        if self.mode == MEMORY:
            rows = self.memory_rows()
            return rows, max(0, min(self.mem_focus, len(rows) - 1)), self.mem_top
        return [self.row_line(r) for r in ROWS], self.focus, self.top

    def _list_frame(self, height):
        page = height - 3
        items, focus, top = self._list_items()
        top = _visible_top(top, focus, len(items), page)
        shown = [items[top + i] if top + i < len(items) else "" for i in range(page)]
        bottom, column = self._bottom()
        rows = tuple(_safe(row) for row in [self.status(), *shown, self.message, bottom])
        focus_row = 1 + focus - top
        cursor = (height - 1, column) if column is not None else (focus_row, 0)
        return Frame(rows, cursor, focus_row)

    def _band_rows(self, b):
        """The stacked face's three rows for a band."""
        letter = BANDS[b]
        freq = self._freq(b)
        tags = [t for t, on in (("Control.", self.ctrl == b), ("Transmit.", self.tx == b)) if on]
        first = f"{letter} {freq}" if freq else f"{letter} not read"
        if tags:
            first += ". " + " ".join(tags)
        second = f"{letter} {self._source_row(b)}" + (". Active." if b == self.active else "")
        sq = self.bands[b].sq
        parts = [f"squelch {sq}" if sq is not None else "squelch not read"]
        if self._busy_word(b):
            parts.append(self._busy_word(b))
        return [first, second, f"{letter} " + ", ".join(parts)]

    def _source_row(self, b):
        """"FM, power high, VFO"; a part not read is left out."""
        parts = [w for w in (self._mode_word(b),) if w]
        if self._power_word(b):
            parts.append(f"power {self._power_word(b)}")
        if self._source_word(b):
            parts.append(self._source_word(b))
        return ", ".join(parts) if parts else "mode not read"

    def _facts_row(self):
        parts = []
        if self._tnc_words():
            parts.append(f"TNC {self._tnc_words()}.")
        if self.gps is not None:
            parts.append(f"GPS out {'on' if self.gps else 'off'}.")
        if self.vox is not None:
            parts.append(f"VOX {'on' if self.vox else 'off'}.")
        return " ".join(parts)

    def _status_marks(self, rows):
        at = rows[0].find("TRANSMITTING")
        return [(0, at, len("TRANSMITTING"), "alarm")] if 0 <= at < PANEL else []

    def _stacked_frame(self, height):
        body = [self.status(), *self._band_rows(0), *self._band_rows(1), self._facts_row()]
        rows = tuple(_safe(row) for row in self._ends(height, body))
        marks = self._status_marks(rows)
        for b, top in ((0, 1), (1, 4)):
            style = "head_a" if b == 0 else "head_b"
            for r in range(top, top + 3):
                if rows[r][:1] == BANDS[b]:
                    marks.append((r, 0, 1, style))
            at = rows[top + 2].find("BUSY")
            if at >= 0:
                marks.append((top + 2, at, 4, "busy"))
        first = 1 if self.active == 0 else 4
        freq = self._freq(self.active) or "not read"
        if rows[first][2 : 2 + len(freq)] == freq:
            marks.append((first, 2, len(freq), "focus"))
        return Frame(rows, self._cursor(height, first), None, tuple(marks))

    def _compact_frame(self, height):
        body = [self.status()]
        for b in (0, 1):
            freq = self._freq(b)
            active = ". Active." if b == self.active else ""
            if freq is None:
                body.append(f"{BANDS[b]} not read{active}")
                continue
            head = f"{BANDS[b]} {freq}" + (f" {self._mode_word(b)}" if self._mode_word(b) else "")
            rest = [w for w in (self._power_word(b), self._busy_word(b)) if w]
            body.append(", ".join([head, *rest]) + active)
        parts = []
        if self.ctrl is not None:
            parts.append(f"Control {BANDS[self.ctrl]}.")
        if self.tx is not None:
            parts.append(f"Transmit {BANDS[self.tx]}.")
        if self._tnc_words():
            parts.append(f"TNC {self._tnc_words()}.")
        body.append(" ".join(parts))
        rows = tuple(_safe(row) for row in self._ends(height, body))
        first = 1 + self.active
        return Frame(rows, self._cursor(height, first), first)

    def digit_text(self, height):
        """The active band's frequency for big digits, or None when they do not show."""
        hz = self.bands[self.active].hz
        if self.digits != "big" or height < BIG_HEIGHT or hz is None:
            return None
        text = mhz_text(hz)
        return text if all(ch in GLYPHS for ch in text) and len(text) * 4 - 1 <= PANEL else None

    def _wide_frame(self, width, height):
        text = self.digit_text(height)
        glyphs = big_digits(text) if text else []
        d = len(glyphs)
        at = (0, RIGHT)
        rows = [""] * height
        marks = []
        right0 = [f"Step {step_words(self.step_khz)}."]
        if self._tnc_words():
            right0.append(f"TNC {self._tnc_words()}.")
        rows[0] = _put(_panel(self.status()), _panel(" ".join(right0)))
        marks += self._status_marks(rows)
        heads, freqs, sources, squelch, busy = [], [], [], [], []
        for b in (0, 1):
            tags = [t for t, on in (("Active.", self.active == b), ("Control.", self.ctrl == b)) if on]
            if self.tx == b:
                tags.append("Transmit.")
            heads.append(_panel(" ".join([f"Band {BANDS[b]}.", *tags])))
            freqs.append(_panel(self._freq(b) or "Not read"))
            sources.append(_panel(self._source_row(b)[:1].upper() + self._source_row(b)[1:]))
            sq = self.bands[b].sq
            squelch.append(("Squelch not read", None) if sq is None else (f"Squelch {sq}", sq))
            busy.append((self._busy_word(b) or "Busy not read", self.bands[b].history))
        rows[1] = _put(heads[0], heads[1])
        rows[2] = _put(freqs[0], freqs[1])
        for b in (0, 1):
            marks.append((1, at[b], 6, "head_a" if b == 0 else "head_b"))
        marks.append((2, at[self.active], len(freqs[self.active]), "focus"))
        for i, glyph in enumerate(glyphs):
            rows[3 + i] = (" " * at[self.active] + glyph).rstrip(" ")
            if glyph.strip():
                marks.append((3 + i, at[self.active], len(glyph), "digits"))
        rows[3 + d] = _put(sources[0], sources[1])
        sq_parts, busy_parts = [], []
        for b in (0, 1):
            words, sq = squelch[b]
            if sq is not None and 0 <= sq <= BAR_CELLS:
                sq_parts.append(words.ljust(BAR_AT) + "#" * sq + " " * (BAR_CELLS - sq))
                marks.append((4 + d, at[b] + BAR_AT, BAR_CELLS, "bar"))
            else:
                sq_parts.append(words)
            word, history = busy[b]
            if history and len(word) < HISTORY_AT:
                hist = "".join("#" if v else "." for v in history[-HISTORY:])
                busy_parts.append(word.ljust(HISTORY_AT) + hist)
                marks.append((5 + d, at[b] + HISTORY_AT, len(hist), "history"))
            else:
                busy_parts.append(word)
            if word == "BUSY":
                marks.append((5 + d, at[b], 4, "busy"))
        rows[4 + d] = _put(sq_parts[0], sq_parts[1])
        rows[5 + d] = _put(busy_parts[0], busy_parts[1])
        facts = [lines.clean(self.ident, 20) + "." if self.ident else ""]
        if self.gps is not None:
            facts.append(f"GPS out {'on' if self.gps else 'off'}.")
        if self.vox is not None:
            facts.append(f"VOX {'on' if self.vox else 'off'}.")
        windows = ""
        if self.windows:
            windows = "Windows open: " + ", ".join(lines.clean(w, 20) for w in self.windows) + "."
        rows[6 + d] = _put(_panel(" ".join(f for f in facts if f)), _panel(windows))
        key_row = self.keymap.key_row(width)
        if height >= 13 + d:
            rows[8 + d] = "Command log"
            marks.append((8 + d, 0, len("Command log"), "log"))
            room = (height - 4) - (8 + d)
            entries = self.log[-room:] if room > 0 else []
            for i, (when, line, answer) in enumerate(entries):
                text = f"{when} sent {lines.clean(line, 40)}. Answer: {lines.clean(answer, 80)}"
                rows[9 + d + i] = lines.clean(text.strip(), width)[:width].rstrip(" ")
        rows[height - 3] = key_row
        if key_row:
            marks.append((height - 3, 0, len(key_row), "keys"))
        rows[height - 2] = _safe(self.message)
        rows[height - 1] = _safe(self._bottom()[0])
        cursor = self._cursor(height, 2, at[self.active])
        return Frame(tuple(rows), cursor, None, tuple(marks))


def _live_words(value):
    """live_meters: auto, yes or no; on, true and 1 count as yes, off, false and 0 as no."""
    if value is True:
        return "yes"
    if value is False:
        return "no"
    word = str(value).strip().lower()
    if word in ("yes", "on", "true", "1"):
        return "yes"
    if word in ("no", "off", "false", "0"):
        return "no"
    return "auto"


def _seconds(value, default, least):
    """A time in seconds, no shorter than least; 0 or less stays 0 (off). A bad value is the default."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return 0.0 if v <= 0 else max(least, v)
