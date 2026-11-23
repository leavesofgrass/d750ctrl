"""d750ui.keymap: which action a key means in the screen d750ctrl.

The keymap holds the actions of the screen, their default keys, the operator's changes
from the [keys] section of the settings file, and the words for help, the bottom row's
hint and the wide face's key row. There are two families of actions: "list", for the list
view, and "face", for the face and compact. An action may have other default keys in
each family. The model asks action() what a key means and holds what each action does.
Nothing here knows curses, a socket or the model.

A key name is what the curses part gives the model: a printable ASCII character as itself,
or one of space, enter, esc, backspace, tab, up, down, left, right, pgup, pgdn, home, end,
f1 to f12, ctrl-l and ctrl-c.

GPL-2.0-or-later.
"""

from d750ui import lines

FAMILIES = ("list", "face")
VIEWS = ("list", "face", "compact")
MOST_KEYS = 4
KEEP_A_KEY = ("unkey", "lock")  # these always keep a key in each family
# y and n answer questions, so no action may have them: no double key can ask and answer.
ANSWER_KEYS = ("y", "n", "Y", "N")


def _shared(family):
    """The actions in both families, in the order of help and of --check."""
    return (
        ("other_band", ("tab",)),
        ("help", ("?",)),
        ("raw", (":",)),
        ("view_next", ("V",)),
        ("quit", ("Q", "q") if family == "face" else ("Q",)),
        ("unkey", ("U", "u") if family == "face" else ("U",)),
        ("lock", ("L",)),
        ("memory", ("C", "M")),
        ("sstv", ("S",)),
        ("rtty", ("R",)),
    )


DEFAULTS = {
    "list": (
        ("row_up", ("up",)),
        ("row_down", ("down",)),
        ("page_up", ("pgup",)),
        ("page_down", ("pgdn",)),
        ("first", ("home",)),
        ("last", ("end",)),
        ("step_down", ("left", "-")),
        ("step_up", ("right", "+", "=")),
        ("big_down", ("[",)),
        ("big_up", ("]",)),
        ("flip", ("space",)),
        ("edit", ("enter",)),
        *_shared("list"),
    ),
    "face": (
        ("tune_up", ("up",)),
        ("tune_down", ("down",)),
        ("tune_up_big", ("pgup",)),
        ("tune_down_big", ("pgdn",)),
        ("next_step", ("s",)),
        ("squelch_down", ("[",)),
        ("squelch_up", ("]",)),
        ("act_mode", ("m",)),
        ("act_power", ("p",)),
        ("act_control", ("b",)),
        ("act_source", ("v",)),
        ("act_tnc", ("t",)),
        ("act_gps", ("g",)),
        ("send_frame", ("c",)),
        ("set_clock", ("k",)),
        ("chat", ("x",)),
        ("varac_chat", ("o",)),
        ("radiogram", ("r",)),
        *_shared("face"),
    ),
}

ACTIONS = {family: tuple(name for name, _ in DEFAULTS[family]) for family in FAMILIES}
_KNOWN = frozenset(ACTIONS["list"]) | frozenset(ACTIONS["face"])

# Short words for what an action does, 21 characters or fewer, so that the longest key
# name in words (17), a colon and a space and these fit one row of 40 cells.
ACTION_WORDS = {
    "row_up": "one row up.",
    "row_down": "one row down.",
    "page_up": "one screen up.",
    "page_down": "one screen down.",
    "first": "the first row.",
    "last": "the last row.",
    "step_down": "one step down.",
    "step_up": "one step up.",
    "big_down": "ten steps down.",
    "big_up": "ten steps up.",
    "flip": "flip or next choice.",
    "edit": "type a value.",
    "other_band": "the other band.",
    "help": "this help.",
    "raw": "a raw command.",
    "view_next": "the next view.",
    "quit": "quit.",
    "unkey": "unkey now.",
    "lock": "lock or unlock PTT.",
    "memory": "memory channels.",
    "sstv": "SSTV. Asks.",
    "rtty": "RTTY. Asks.",
    "tune_up": "tune up.",
    "tune_down": "tune down.",
    "tune_up_big": "tune ten steps up.",
    "tune_down_big": "tune ten steps down.",
    "next_step": "the next step.",
    "squelch_down": "squelch down.",
    "squelch_up": "squelch up.",
    "act_mode": "the next mode.",
    "act_power": "the next power.",
    "act_control": "control here.",
    "act_source": "VFO or memory.",
    "act_tnc": "the next TNC mode.",
    "act_gps": "GPS output on, off.",
    "send_frame": "a CQ frame. Asks.",
    "set_clock": "set the clock. Asks.",
    "chat": "the chat window.",
    "varac_chat": "the VarAC chat.",
    "radiogram": "a new radiogram.",
}

# Help rows: (the actions, what they do). A row with no actions is fixed and given whole.
# A row's keys are always the keys in force.
_SHARED_ROWS = (
    (("quit",), "quit."),
    (("unkey",), "unkey now."),
    (("lock",), "lock PTT, or ask to unlock it."),
    (("memory",), "memory channels."),
    (("sstv",), "SSTV, receive or send. Asks."),
    (("rtty",), "RTTY, receive or send. Asks."),
    (("view_next",), "the next view."),
    (("help",), "this help."),
    (("raw",), "a raw radio command."),
    ((), "Ctrl+L: draw the screen again."),
    ((), "Ctrl+C: quit."),
    ((), "Typing: Enter sets it, Escape cancels."),
    ((), "Questions: only y says yes."),
    ((), "Escape or question mark: back."),
)

_ROWS = {
    "list": (
        (("row_up", "row_down"), "one row."),
        (("page_up", "page_down"), "one screen."),
        (("first", "last"), "the first row, the last."),
        ((), "A small letter: jump to a row."),
        (("step_down",), "one step down."),
        (("step_up",), "one step up."),
        (("big_down", "big_up"), "ten steps."),
        (("flip",), "flip, or the next choice."),
        (("edit",), "type a value, or do an action."),
        (("other_band",), "the same row of the other band."),
        ((), "A digit or period: type a frequency."),
        *_SHARED_ROWS,
    ),
    "face": (
        (("other_band",), "the other band."),
        (("tune_up", "tune_down"), "tune one step."),
        (("tune_up_big", "tune_down_big"), "tune ten steps."),
        ((), "A digit or period: type a frequency."),
        (("next_step",), "the next tuning step."),
        (("squelch_down", "squelch_up"), "squelch."),
        (("act_mode",), "the next mode."),
        (("act_power",), "the next power."),
        (("act_control",), "control and transmit here."),
        (("act_source",), "VFO or memory."),
        (("act_tnc",), "the next TNC mode. Asks."),
        (("act_gps",), "GPS output on or off."),
        (("send_frame",), "send a CQ or beacon frame. Asks."),
        (("set_clock",), "set the radio clock. Asks."),
        (("chat",), "the chat window."),
        (("varac_chat",), "the VarAC chat window."),
        (("radiogram",), "a new radiogram."),
        *_SHARED_ROWS,
    ),
}

# The wide face's key row: (actions, words, the key shown when it is in force).
_KEY_ROW = (
    (("other_band",), "band.", "tab"),
    (("tune_up", "tune_down"), "tune.", None),
    (("help",), "help.", None),
    (("unkey",), "unkey.", "u"),
    (("lock",), "lock.", None),
    (("view_next",), "view.", None),
    (("quit",), "quit.", "q"),
    (("next_step",), "step.", None),
    (("act_mode",), "mode.", None),
    (("act_power",), "power.", None),
    (("act_control",), "control.", None),
    (("act_source",), "source.", None),
    (("memory",), "memory.", "M"),
    (("act_tnc",), "TNC.", None),
    (("act_gps",), "GPS.", None),
    (("send_frame",), "frame.", None),
    (("set_clock",), "clock.", None),
    (("chat",), "chat.", None),
    (("varac_chat",), "VarAC.", None),
    (("radiogram",), "radiogram.", None),
    (("sstv",), "SSTV.", None),
    (("rtty",), "RTTY.", None),
)
_ROW_KEEPS = ("unkey", "lock")  # these entries never drop from the key row

# Key names in words. A letter is itself; every other printable mark is named here.
_NAMED = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "pgup": "Page Up",
    "pgdn": "Page Down",
    "home": "Home",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "backspace": "Backspace",
    "space": "Space",
    "tab": "Tab",
    "ctrl-l": "Ctrl+L",
    "ctrl-c": "Ctrl+C",
    **{f"f{n}": f"F{n}" for n in range(1, 13)},
}
_MARK_WORDS = {
    "!": "Exclamation mark",
    '"': "Double quote",
    "#": "Number sign",
    "$": "Dollar sign",
    "%": "Percent",
    "&": "Ampersand",
    "'": "Apostrophe",
    "(": "Left parenthesis",
    ")": "Right parenthesis",
    "*": "Star",
    "+": "Plus",
    ",": "Comma",
    "-": "Minus",
    ".": "Period",
    "/": "Slash",
    ":": "Colon",
    ";": "Semicolon",
    "<": "Less than",
    "=": "Equals",
    ">": "Greater than",
    "?": "Question mark",
    "@": "At sign",
    "[": "Left bracket",
    "\\": "Backslash",
    "]": "Right bracket",
    "^": "Caret",
    "_": "Underscore",
    "`": "Backtick",
    "{": "Left brace",
    "|": "Vertical bar",
    "}": "Right brace",
    "~": "Tilde",
}

# Key names the settings file takes besides a single character, as the model's key names.
_FILE_NAMES = {
    **{name: name for name in ("tab", "space", "enter", "up", "down", "left", "right")},
    **{name: name for name in ("pgup", "pgdn", "home", "end", "backspace")},
    "comma": ",",
    **{f"f{n}": f"f{n}" for n in range(1, 13)},
}
# Names that are keys but can never be changed: they keep their meaning in every mode.
_FIXED_NAMES = frozenset(("esc", "escape", "ctrl-c", "ctrl-l", "ctrl+c", "ctrl+l", "period"))


def key_words(key):
    """A key's name in words: "Up", "Page Up", "Question mark", "F5", a letter as itself."""
    key = str(key)
    if key in _NAMED:
        return _NAMED[key]
    if len(key) == 1:
        if key in _MARK_WORDS:
            return _MARK_WORDS[key]
        if key.isalnum() and key.isascii():
            return key
    return lines.clean(key, 20) or "a key"


def spoken_words(key):
    """A key as help and --check name it: a capital letter is "capital Q", so Q and q do not sound alike."""
    key = str(key)
    if len(key) == 1 and "A" <= key <= "Z":
        return f"capital {key}"
    return key_words(key)


def short_words(key):
    """A key as a hint names it: the character itself when a line may hold it, else in words."""
    key = str(key)
    if len(key) == 1 and " " < key < "\x7f" and not lines.problems(key, lines.CELLS):
        return key
    return key_words(key)


def _shown_name(text):
    """A typed name for a skipped line: underscores as hyphens, made safe."""
    return lines.clean(str(text).replace("_", "-"), 24)


def _file_key(typed):
    """A key name from the settings file: (the model's key name, None) or (None, why not)."""
    typed = typed.strip()
    if len(typed) == 1:
        if typed.isdigit() or typed == ".":
            return None, "fixed"
        if " " < typed < "\x7f" and typed != ",":
            return typed, None
        return None, "unknown"
    low = typed.lower()
    if low in _FILE_NAMES:
        return _FILE_NAMES[low], None
    if low in _FIXED_NAMES or low.startswith("ctrl"):
        return None, "fixed"
    return None, "unknown"


class Keymap:
    """The keys in force: the defaults with the operator's changes."""

    def __init__(self, changes=()):
        self._bound = {family: {name: list(keys) for name, keys in DEFAULTS[family]} for family in FAMILIES}
        skipped = []
        given = {family: {} for family in FAMILIES}  # key to the action a change gave it
        for change in changes:
            why = self._change(change, given)
            if why:
                skipped.append(why)
        self.skipped = tuple(skipped)
        self._by_key = {
            family: {key: name for name, keys in self._bound[family].items() for key in keys}
            for family in FAMILIES
        }
        self._help = {}

    def _change(self, change, given):
        """Use one change; None when used, else its skipped line."""
        try:
            number, name, value = change
            number = int(number)
        except (TypeError, ValueError):
            return "A settings line was skipped: it could not be read."
        head = f"Line {number} skipped:"
        if value is None:
            return f"{head} no equals sign."
        action = str(name).strip().lower().replace("-", "_")
        if action not in _KNOWN:
            return _skip_line(head, "no such action", name)
        value = str(value).strip()
        if value.lower() == "none":
            if action in KEEP_A_KEY:
                return f"{head} {action} must keep a key."
            keys = []
        else:
            parts = value.split(",")
            if len(parts) > MOST_KEYS:
                return f"{head} more than {MOST_KEYS} keys."
            keys = []
            for part in parts:
                if not part.strip():
                    return f"{head} a key name is missing."
                key, why = _file_key(part)
                if why == "fixed":
                    return _skip_line(head, "that key cannot be changed", part)
                if why:
                    return _skip_line(head, "no such key", part)
                if key not in keys:
                    keys.append(key)
            if any(k in ANSWER_KEYS for k in keys):
                return f"{head} y and n answer questions. Not for {action.replace('_', '-')}."
        families = [family for family in FAMILIES if action in self._bound[family]]
        for family in families:
            for key in keys:
                holder, line = given[family].get(key, (None, None))
                if holder is not None and holder != action:
                    where = f"is already given to {holder.replace('_', '-')} on line {line}."
                    said = f"{head} {key_words(key)} {where}"
                    return said if not lines.problems(said, 80) else f"{head} {short_words(key)} {where}"
        for family in families:
            for keep in KEEP_A_KEY:
                if keep != action and not [k for k in self._bound[family][keep] if k not in keys]:
                    return f"{head} it would leave {keep} with no key."
        for family in families:
            for key, (holder, _line) in list(given[family].items()):
                if holder == action:
                    del given[family][key]
            for other, held in self._bound[family].items():
                if other != action:
                    held[:] = [k for k in held if k not in keys]
            self._bound[family][action] = list(keys)
            for key in keys:
                given[family][key] = (action, number)
        return None

    # ----------------------------------------------------------------- asking

    def action(self, family, key):
        """The action's name for a key name in a family, or None."""
        return self._by_key.get(family, {}).get(str(key))

    def keys(self, family, action):
        """The key names bound to an action in a family, in order; empty when none."""
        return tuple(self._bound.get(family, {}).get(action, ()))

    def first(self, family, action):
        """The first key in force of an action, or None."""
        keys = self.keys(family, action)
        return keys[0] if keys else None

    # ----------------------------------------------------------------- words

    def help_rows(self, view):
        """The help rows for a view: list, face or compact. Each passes the rules for 40 cells."""
        family = "list" if view == "list" else "face"
        if family not in self._help:
            rows = []
            for actions, words in _ROWS[family]:
                if not actions:
                    rows.append(words)
                else:
                    rows.extend(self._built_rows(family, actions, words))
            self._help[family] = tuple(rows)
        return self._help[family]

    def _built_rows(self, family, actions, words):
        if not any(self.keys(family, a) for a in actions):
            return []
        for most in (2, 1):
            named = [spoken_words(k) for a in actions for k in self.keys(family, a)[:most]]
            for what in (words, ACTION_WORDS[actions[0]] if len(actions) == 1 else None):
                if what:
                    row = _row_start(f"{', '.join(named)}: {what}")
                    if _fits(row):
                        return [row]
        rows = []
        for a in actions:
            key = self.first(family, a)
            if key is not None:
                row = _row_start(f"{spoken_words(key)}: {ACTION_WORDS[a]}")
                rows.append(row if _fits(row) else f"{short_words(key)}: {ACTION_WORDS[a]}")
        return rows

    def _pair_words(self, family, actions):
        """The first keys in force of one or two actions, as a hint names them, or None."""
        named = [short_words(self.first(family, a)) for a in actions if self.first(family, a) is not None]
        return ", ".join(named) if named else None

    def hint(self, view):
        """The bottom row in main mode, 40 cells or fewer. It may be empty."""
        parts = []
        if view == "list":
            family = "list"
            parts.append("Letters jump.")
            down, up = self.first("list", "step_down"), self.first("list", "step_up")
            if (down, up) == ("left", "right"):
                parts.append("Arrows change.")
            elif self._pair_words("list", ("step_down", "step_up")):
                parts.append(f"{self._pair_words('list', ('step_down', 'step_up'))} change.")
        else:
            family = "face"
            band = self.first(family, "other_band")
            if band is not None:
                parts.append(f"{short_words(band)} band.")
            tune = self._pair_words(family, ("tune_up", "tune_down"))
            if tune:
                parts.append(f"{tune} tune.")
            view_key = self.first(family, "view_next")
            if view_key is not None:
                parts.append(f"{short_words(view_key)} view.")
        help_key = self.first(family, "help")
        if help_key is not None:
            parts.append(f"{short_words(help_key)} help")
        while parts and not _fits(" ".join(parts)):
            parts.pop(0)
        return " ".join(parts)

    def _shown_key(self, action, preferred):
        keys = self.keys("face", action)
        if preferred is not None and preferred in keys:
            return short_words(preferred)
        return short_words(keys[0]) if keys else None

    def key_row(self, width=80):
        """The wide face's key row: width - 1 cells or fewer, keeping every line rule but the length.

        Entries drop from the end, but for unkey and lock, which always show.
        """
        most = max(1, int(width) - 1)
        entries = []
        for actions, words, preferred in _KEY_ROW:
            if len(actions) == 1:
                named = self._shown_key(actions[0], preferred)
            else:
                named = self._pair_words("face", actions)
            if named:
                entries.append((actions[0] in _ROW_KEEPS, f"{named} {words}"))
        while entries:
            row = " ".join(text for _, text in entries)
            if len(row) <= most and not row_problems(row):
                return row
            droppable = [i for i, (keep, _) in enumerate(entries) if not keep]
            if not droppable:
                break
            del entries[droppable[-1]]
        return ""

    def check_lines(self):
        """Plain lines for d750ctrl --check: each family's keys, then what was skipped."""
        shared = [a for a in ACTIONS["list"] if a in ACTIONS["face"]]
        out = list(self.skipped or ("No settings line was skipped.",))  # what went wrong is heard first
        out.append("Keys in every view:")
        for action in shared:
            name = action.replace("_", "-")
            here, there = self.keys("list", action), self.keys("face", action)
            if here == there:
                out.append(_action_line(name, here))
            else:  # other keys in each family: say each
                out.append(_action_line(f"{name} in the list", here))
                out.append(_action_line(f"{name} in the face", there))
        for family, heading in (
            ("list", "Keys in the list view:"),
            ("face", "Keys in the face and compact views:"),
        ):
            out.append(heading)
            for action in ACTIONS[family]:
                if action not in shared:
                    out.append(_action_line(action.replace("_", "-"), self.keys(family, action)))
        return out


def _action_line(name, keys):
    """One --check line: an action and its keys in words, its meaning within 40 cells."""
    if not keys:
        return f"{name}: no key."
    count = f"{len(keys)} key" if len(keys) == 1 else f"{len(keys)} keys"
    named = ", ".join(spoken_words(k) for k in keys)
    short = ", ".join(short_words(k) for k in keys)
    tries = (f"{name}: {named}.", f"{name} has {count}: {named}.", f"{name} has {count}: {short}.")
    for line in tries:
        if not lines.problems(line, 80):
            return line
    return f"{name}: {short}."


def _row_start(row):
    """A help row starts with a capital: "Capital Q, q: quit."."""
    return row[:1].upper() + row[1:] if row.startswith("capital ") else row


def row_problems(row):
    """What breaks the line rules in a key row, its length aside: the meaning still ends by cell 40."""
    found = [p for p in lines.problems(row, lines.LONGEST) if not p.startswith("longer than")]
    if len(row) > lines.LONGEST and not lines._clause_ends_by_cell_40(row) and lines.NO_CLAUSE not in found:
        found.append(lines.NO_CLAUSE)
    return found


def _fits(row):
    return bool(row) and len(row) <= lines.CELLS and not lines.problems(row, lines.CELLS)


def _skip_line(head, why, typed):
    """A skipped line naming what was typed, or without it when that would break the rules."""
    shown = _shown_name(typed)
    line = f"{head} {why}, {shown}." if shown else f"{head} {why}."
    if lines.problems(line, 80):
        line = f"{head} {why}."
    return line
