"""aprschat: APRS messages from the terminal, through d750-aprs.

Over SSH or at the console. The screen works like xarachat's: the top line says who you are talking with,
the middle is the conversation, the bottom line is where you type, and the cursor rests there. Enter sends.
Line mode (--line) prints one event per line and never redraws, for a screen reader or a Braille display.

d750-aprs does the radio side: it sends with retries until acknowledged, acknowledges what comes in, and
writes every message event to its history file, which this program reads. Nothing here opens the radio.
Written Wednesday, November 11, 2026.
"""

import curses
import importlib.util
import json
import os
import socket
import sys
import textwrap
import threading
import time

HERE = os.path.dirname(os.path.realpath(__file__))
_spec = importlib.util.spec_from_file_location("d750aprs", os.path.join(HERE, "d750-aprs.py"))
aprs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aprs)

MESSAGES = os.environ.get("APRSCHAT_MESSAGES", aprs.MESSAGES)
SOCK = os.environ.get("APRSCHAT_SOCK", aprs.SOCK)
STATE = os.environ.get("APRSCHAT_STATE", os.path.expanduser("~/.local/state/d750ctrl/aprschat.json"))
TRIES = 5

HELP = [
    "Keys: Enter sends what you typed to the station named on the top line.",
    "F2 talks to another station: type its call and press Enter. Enter alone takes the last one.",
    "F3 lists the conversations; Up and Down choose, Enter opens, Escape goes back.",
    "F4 goes to the next conversation with unread messages.",
    "Page Up and Page Down scroll. Up and Down recall lines you typed. Ctrl-U clears the typing line.",
    "F1 shows this help. F10 quits. Slash commands: /to CALL, /list, /next, /status, /help, /quit.",
    "Messages longer than 67 characters go in parts. d750-aprs retries each up to 5 times until acknowledged.",
]


# ---------------------------------------------------------------- talking to d750-aprs

def ask(line, timeout=5):
    """One line to d750-aprs's control socket, its answer back; None when it is not running."""
    try:
        s = socket.socket(socket.AF_UNIX)
        s.settimeout(timeout)
        s.connect(SOCK)
        s.sendall((line + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        s.close()
        return data.decode("utf-8", "replace").strip()
    except OSError:
        return None


def my_call():
    return aprs.load_conf().get("call", "N0CALL").upper()


# ---------------------------------------------------------------- the history

class History:
    """The message history from d750-aprs, as conversations by call sign, read as it grows."""

    def __init__(self, path=MESSAGES):
        self.path = path
        self.pos = 0
        self.conv = {}           # call -> list of entries, oldest first
        self.by_id = {}          # (call, message number) -> the outgoing entry

    def poll(self):
        """Read what is new: a list of (kind, call, entry), kind in, out or update."""
        changes = []
        try:
            f = open(self.path, "rb")
        except OSError:
            return changes
        with f:
            f.seek(0, 2)
            if f.tell() < self.pos:           # the file was replaced: start again
                self.pos, self.conv, self.by_id = 0, {}, {}
            f.seek(self.pos)
            for raw in f:
                if not raw.endswith(b"\n"):
                    break
                self.pos += len(raw)
                try:
                    change = self.apply(json.loads(raw))
                except (ValueError, KeyError, TypeError):
                    change = None
                if change:
                    changes.append(change)
        return changes

    def apply(self, e):
        call = str(e.get("call", "")).upper()
        if not call:
            return None
        if e["dir"] == "in":
            entry = {"t": e["t"], "dir": "in", "text": e.get("text", ""), "via": e.get("via", "rf")}
            self.conv.setdefault(call, []).append(entry)
            return ("in", call, entry)
        key = (call, str(e.get("id")))
        if e.get("state") == "queued":
            entry = {"t": e["t"], "dir": "out", "text": e.get("text", ""), "state": "queued", "tries": 0}
            self.conv.setdefault(call, []).append(entry)
            self.by_id[key] = entry
            return ("out", call, entry)
        entry = self.by_id.get(key)
        if not entry:
            return None
        entry["state"] = e.get("state", entry["state"])
        entry["tries"] = e.get("tries", entry["tries"])
        return ("update", call, entry)

    def last_time(self, call):
        c = self.conv.get(call)
        return c[-1]["t"] if c else 0


def when(t):
    lt = time.localtime(t)
    return time.strftime("%H:%M" if lt[:3] == time.localtime()[:3] else "%b %d %H:%M", lt)


STATE_WORDS = {
    "queued": "Waiting to go out.",
    "sent": "Sent, try {tries} of 5, waiting for the acknowledgement.",
    "acked": "Acknowledged.",
    "rejected": "Refused.",
    "failed": "Not acknowledged after 5 tries.",
}


def entry_line(entry, call, mine):
    """One conversation line: time, who, the text; for ours, what became of it."""
    if entry["dir"] == "in":
        return f"{when(entry['t'])} {call}: {entry['text']}" + (" (through the internet)" if entry.get("via") == "is" else "")
    state = STATE_WORDS.get(entry["state"], entry["state"]).format(tries=entry.get("tries", 0))
    return f"{when(entry['t'])} {mine}: {entry['text']}. {state}"


def update_line(entry, call):
    """A line for line mode when one of ours changes state."""
    words = {"sent": f"Sent to {call}, try {entry.get('tries', 0)} of 5", "acked": f"{call} acknowledged",
             "rejected": f"{call} refused", "failed": f"{call} did not acknowledge after 5 tries"}
    return f"{when(time.time())} {words.get(entry['state'], entry['state'])}: {entry['text']}"


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"last_read": {}, "current": ""}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(STATE + ".tmp", STATE)
    except OSError:
        pass


def valid_call(text):
    call = text.strip().upper()
    base, _, ssid = call.partition("-")
    ok = 3 <= len(base) <= 6 and base.isalnum() and any(c.isdigit() for c in base) and (not ssid or (ssid.isdigit() and int(ssid) <= 15))
    return call if ok else None


def send(call, text):
    """Hand a message to d750-aprs; its answer, or why it could not be sent."""
    reply = ask(f"send {call} {text}")
    return reply if reply is not None else "Not sent: d750-aprs is not running. Start it with: systemctl --user start d750-aprs"


def daemon_words():
    status = ask("status")
    if status is None:
        return "d750-aprs is not running"
    return "Transmit on" if "transmitting on" in status else "Transmit off, messages wait"


# ---------------------------------------------------------------- line mode

def line_mode(call):
    mine, hist, state = my_call(), History(), load_state()
    hist.poll()
    call = call or state.get("current") or ""
    out = lambda text: print(text, flush=True)
    out(f"aprschat for {mine}, line mode. {daemon_words()}. Type /help for the commands.")
    if call:
        for entry in hist.conv.get(call, [])[-10:]:
            out(entry_line(entry, call, mine))
        out(f"Talking with {call}. Type a line and press Enter to send it.")
    else:
        out("Nobody chosen yet. Type /to CALL to choose a station.")
    lines = []

    def reader():
        for raw in sys.stdin:
            lines.append(raw.rstrip("\n"))
        lines.append(None)

    threading.Thread(target=reader, daemon=True).start()
    while True:
        for kind, c, entry in hist.poll():
            if kind == "in":
                out(entry_line(entry, c, mine) if c == call else f"{when(entry['t'])} New from {c}: {entry['text']}")
            elif kind == "update":
                out(update_line(entry, c))
        while lines:
            text = lines.pop(0)
            if text is None:
                return 0
            text = text.strip()
            if not text:
                continue
            if text.startswith("/"):
                word, _, arg = text[1:].partition(" ")
                word = word.lower()
                if word in ("quit", "q", "exit"):
                    return 0
                if word == "to":
                    c = valid_call(arg)
                    if not c:
                        out("Give a call sign: /to N0CALL-7")
                        continue
                    call = c
                    state["current"] = call
                    save_state(state)
                    for entry in hist.conv.get(call, [])[-10:]:
                        out(entry_line(entry, call, mine))
                    out(f"Talking with {call}.")
                elif word == "list":
                    calls = sorted(hist.conv, key=hist.last_time, reverse=True)
                    out(f"{len(calls)} conversations" + (": " + ", ".join(calls) if calls else "."))
                elif word == "status":
                    out(ask("status") or "d750-aprs is not running.")
                else:
                    out("Commands: /to CALL, /list, /status, /quit. Anything else is sent to " + (call or "the station you choose") + ".")
                continue
            if not call:
                out("Choose a station first: /to CALL")
                continue
            out(f"{when(time.time())} {mine} to {call}: {text}. {send(call, text)}")
        time.sleep(0.3)


# ---------------------------------------------------------------- the screen

class Screen:
    def __init__(self, scr, call):
        self.scr = scr
        self.mine = my_call()
        self.hist = History()
        self.hist.poll()
        self.state = load_state()
        self.state.setdefault("last_read", {})
        self.call = call or self.state.get("current") or (max(self.hist.conv, key=self.hist.last_time) if self.hist.conv else "")
        self.buf = ""
        self.typed, self.recall = [], None
        self.notes = []              # (time, text): the program's own lines, shown in the conversation
        self.scroll = 0
        self.mode = "chat"           # chat, ask (a call sign for F2), list (F3)
        self.sel = 0
        self.daemon = daemon_words()
        self.daemon_at = time.time()
        if not self.call:
            self.note("Nobody chosen yet. Press F2 and type a call sign. F1 lists the keys.")
        self.mark_read()

    # -- state
    def note(self, text):
        self.notes.append((time.time(), text))

    def mark_read(self):
        if self.call:
            self.state["last_read"][self.call] = time.time()
            self.state["current"] = self.call
            save_state(self.state)

    def unread(self, call):
        seen = self.state["last_read"].get(call, 0)
        return sum(1 for e in self.hist.conv.get(call, []) if e["dir"] == "in" and e["t"] > seen)

    def unread_elsewhere(self):
        return [c for c in self.hist.conv if c != self.call and self.unread(c)]

    def open(self, call):
        self.call, self.scroll, self.mode = call, 0, "chat"
        self.notes = []
        self.mark_read()

    # -- what the screen shows
    def status_line(self):
        others = self.unread_elsewhere()
        unread = sum(self.unread(c) for c in others)
        who = f"with {self.call}" if self.call else "nobody chosen"
        extra = f" {unread} unread from {', '.join(others[:3])}{' and more' if len(others) > 3 else ''}, F4 goes there." if others else ""
        return f"aprschat {self.mine}, {who}.{extra} {self.daemon}. F1 help, F10 quits."

    def body(self, width):
        if self.mode == "list":
            calls = sorted(self.hist.conv, key=self.hist.last_time, reverse=True)
            if not calls:
                return ["No conversations yet. Escape goes back, F2 starts one."]
            rows = []
            for c in calls:
                last = self.hist.conv[c][-1]
                n = self.unread(c)
                rows.append(f"{c}, {n} unread, {when(last['t'])}: {last['text']}" if n else f"{c}, {when(last['t'])}: {last['text']}")
            return rows
        items = [(e["t"], entry_line(e, self.call, self.mine)) for e in self.hist.conv.get(self.call, [])]
        items += self.notes
        items.sort(key=lambda x: x[0])
        lines = []
        for _, text in items:
            lines += textwrap.wrap(text, width, subsequent_indent="  ") or [""]
        return lines

    def prompt(self):
        if self.mode == "ask":
            return "Station call sign (Enter takes the last): "
        if self.mode == "list":
            return "Up and Down choose, Enter opens, Escape goes back: "
        return f"To {self.call}: " if self.call else "Press F2 to choose a station: "

    def draw(self):
        h, w = self.scr.getmaxyx()
        if h < 4 or w < 20:
            return
        self.scr.erase()
        try:
            self.scr.addnstr(0, 0, self.status_line().ljust(w - 1), w - 1, curses.A_REVERSE)
            rows = h - 2
            if self.mode == "list":
                lines = self.body(w - 3)
                self.sel = max(0, min(self.sel, len(lines) - 1))
                top = max(0, self.sel - rows + 1)
                for i, text in enumerate(lines[top:top + rows]):
                    chosen = top + i == self.sel
                    self.scr.addnstr(1 + i, 0, ("> " if chosen else "  ") + text, w - 1, curses.A_REVERSE if chosen else 0)
                self.scr.addnstr(h - 1, 0, self.prompt(), w - 1, curses.A_BOLD)
                self.scr.move(1 + self.sel - top, 0)      # a screen reader follows the cursor to the chosen line
            else:
                lines = self.body(w - 1)
                self.scroll = max(0, min(self.scroll, max(0, len(lines) - rows)))
                end = len(lines) - self.scroll
                for i, text in enumerate(lines[max(0, end - rows):end]):
                    self.scr.addnstr(1 + i, 0, text, w - 1)
                typing = self.prompt() + self.buf
                shown = typing if len(typing) < w - 1 else typing[-(w - 2):]
                self.scr.addnstr(h - 1, 0, shown, w - 1, curses.A_BOLD)
                self.scr.move(h - 1, min(len(shown), w - 2))
        except curses.error:
            pass
        self.scr.refresh()

    # -- what comes in
    def tick(self):
        changed = False
        for kind, c, entry in self.hist.poll():
            changed = True
            if kind == "in" and c != self.call:
                self.note(f"{when(entry['t'])} New message from {c}: {entry['text']}. F4 goes there.")
            if kind == "in" and c == self.call and self.mode == "chat":
                self.mark_read()
        if time.time() - self.daemon_at > 30:
            words = daemon_words()
            changed = changed or words != self.daemon
            self.daemon, self.daemon_at = words, time.time()
        return changed

    # -- keys
    def enter(self):
        text, self.buf = self.buf.strip(), ""
        if self.mode == "ask":
            self.mode = "chat"
            call = valid_call(text) if text else self.state.get("previous", "")
            if not call:
                self.note(f"That is not a call sign: {text or 'nothing typed'}.")
                return
            self.state["previous"] = self.call or call
            self.open(call)
            self.note(f"Talking with {call}. Type and press Enter to send.")
            return
        if not text:
            return
        self.typed.append(text)
        self.recall = None
        if text.startswith("/"):
            return self.command(text[1:])
        if not self.call:
            self.note("Choose a station first: F2, then its call sign.")
            return
        reply = send(self.call, text)
        if not reply.startswith("Queued"):
            self.note(reply)
        self.scroll = 0

    def command(self, text):
        word, _, arg = text.partition(" ")
        word = word.lower()
        if word in ("quit", "q", "exit"):
            raise SystemExit(0)
        if word == "to":
            call = valid_call(arg)
            if call:
                self.state["previous"] = self.call or call
                self.open(call)
                self.note(f"Talking with {call}.")
            else:
                self.note("Give a call sign: /to N0CALL-7")
        elif word == "list":
            self.mode, self.sel = "list", 0
        elif word == "next":
            self.next_unread()
        elif word == "status":
            self.note(ask("status") or "d750-aprs is not running.")
        else:
            for line in HELP:
                self.note(line)

    def next_unread(self):
        others = sorted(self.unread_elsewhere(), key=self.hist.last_time, reverse=True)
        if others:
            self.state["previous"] = self.call
            self.open(others[0])
        else:
            self.note("No unread messages from other stations.")

    def key(self, k):
        if k in (curses.KEY_F10,):
            raise SystemExit(0)
        if self.mode == "list":
            calls = sorted(self.hist.conv, key=self.hist.last_time, reverse=True)
            if k == curses.KEY_UP:
                self.sel = max(0, self.sel - 1)
            elif k == curses.KEY_DOWN:
                self.sel = min(len(calls) - 1, self.sel + 1)
            elif k in ("\n", "\r", curses.KEY_ENTER) and calls:
                self.state["previous"] = self.call
                self.open(calls[self.sel])
            elif k in ("\x1b", curses.KEY_F3):
                self.mode = "chat"
            return
        if k == curses.KEY_F1:
            for line in HELP:
                self.note(line)
        elif k == curses.KEY_F2:
            self.mode, self.buf = "ask", ""
        elif k == curses.KEY_F3:
            self.mode, self.sel = "list", 0
        elif k == curses.KEY_F4:
            self.next_unread()
        elif k in ("\n", "\r", curses.KEY_ENTER):
            self.enter()
        elif k == "\x1b" and self.mode == "ask":
            self.mode, self.buf = "chat", ""
        elif k in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            self.buf = self.buf[:-1]
        elif k == "\x15":                                  # Ctrl-U
            self.buf = ""
        elif k == curses.KEY_PPAGE:
            self.scroll += max(1, self.scr.getmaxyx()[0] - 4)
        elif k == curses.KEY_NPAGE:
            self.scroll = max(0, self.scroll - max(1, self.scr.getmaxyx()[0] - 4))
        elif k == curses.KEY_UP and self.typed and self.mode == "chat":
            self.recall = len(self.typed) - 1 if self.recall is None else max(0, self.recall - 1)
            self.buf = self.typed[self.recall]
        elif k == curses.KEY_DOWN and self.recall is not None:
            self.recall += 1
            self.buf = self.typed[self.recall] if self.recall < len(self.typed) else ""
            if self.recall >= len(self.typed):
                self.recall = None
        elif isinstance(k, str) and k.isprintable():
            self.buf += k

    def run(self):
        curses.curs_set(1)
        self.scr.keypad(True)
        self.scr.timeout(500)
        self.draw()
        while True:
            try:
                k = self.scr.get_wch()
            except curses.error:
                k = None
            if k is None:
                if self.tick():
                    self.draw()
                continue
            if k == curses.KEY_RESIZE:
                self.draw()
                continue
            self.key(k)
            self.tick()
            self.draw()


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip())
        print("\nUsage: aprschat [CALL]          the screen; aprschat --line [CALL]   one event per line")
        return 0
    call = valid_call(args[0]) if args else ""
    if args and not call:
        print(f"Not a call sign: {args[0]}")
        return 2
    if "--line" in argv or not sys.stdout.isatty():
        return line_mode(call)
    os.environ.setdefault("ESCDELAY", "50")
    try:
        curses.wrapper(lambda scr: Screen(scr, call).run())
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass
    print("aprschat closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
