#!/usr/bin/env python3
"""d750ctrl-tmux-test: the tmux workspace, for real. d750ctrl runs without --no-tmux on a pseudo
terminal, against the test bed (tests/test-env.sh: the simulator and a d750d on ports 4542 and
4543), and the test reads the workspace through tmux itself, on the socket d750 only.

The tools on PATH are stubs that only write down their arguments; the chat stubs then wait, so
that their windows stay open. D750_XARA_PORT is a port this test picked, where only the test
listens. Nothing transmits: no send question is ever answered, and no real tool is run. The test
ends only the tmux servers it started, and the test bed it started, by its process group.

When tmux is not installed it says so and passes. Exit 0 when every check passes.
GPL-2.0-or-later.
"""
import fcntl
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
sys.path.insert(0, TOP)

SCREEN = os.path.join(TOP, "d750ctrl")
CMD_PORT = 4543
SOCKET = "d750"  # the workspace's own tmux socket; the only one this test drives
OPERATOR = "d750-test-operator"  # a stand-in for the operator's own tmux, which must stay untouched
RIG_KEY, NEXT_KEY = "F5", "F6"  # not the defaults, so the test sees the settings read
F5, F6 = "\x1b[15~", "\x1b[17~"  # what an xterm sends for them
COLS, ROWS = 100, 30
WAIT = 15.0

WORK = tempfile.mkdtemp(prefix="d750ctrl-tmux-test-")
STUBS = os.path.join(WORK, "stubs")
STUB_LOG = os.path.join(WORK, "stub-log.txt")
STUB = (
    "#!/bin/sh\n"
    'echo "$(basename "$0") $*" >> "$STUB_LOG"\n'
    'case "$(basename "$0")" in xarachat|openslot) exec sleep 600;; esac\n'
)
ARGDUMP = '#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done >> "$ARGDUMP"\n'

TOTAL = [0]
FAILED = []


def check(desc, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        FAILED.append(desc)
        print(f"Fail: {desc}" + (f"\n{detail}" if detail else ""), flush=True)
    return cond


def wait_until(test, limit=WAIT, step=0.1):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        try:
            if test():
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(step)
    try:
        return bool(test())
    except (OSError, subprocess.SubprocessError):
        return False


# --------------------------------------------------------------------------- tmux, on its own socket


def tmux(*args, sock=SOCKET):
    return subprocess.run(["tmux", "-L", sock, *args], capture_output=True, text=True, timeout=10)


def server_up(sock=SOCKET):
    return tmux("list-sessions", sock=sock).returncode == 0


def windows():
    done = tmux("list-windows", "-t", "d750", "-F", "#W")
    return done.stdout.split() if done.returncode == 0 else []


def active():
    return tmux("display-message", "-p", "-t", "d750", "#W").stdout.strip()


def pane(target="d750:rig"):
    done = tmux("capture-pane", "-p", "-t", target)
    return done.stdout.rstrip("\n").split("\n") if done.returncode == 0 else []


def shows(text, target="d750:rig"):
    return any(text in row for row in pane(target))


def message_row():
    rows = pane()
    return rows[-2] if len(rows) >= 2 else ""


def bottom_row():
    rows = pane()
    return rows[-1] if rows else ""


def default_socket_up():
    return subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True, timeout=10).returncode == 0


# --------------------------------------------------------------------------- the test bed


def ask(line):
    with socket.create_connection(("127.0.0.1", CMD_PORT), timeout=5) as s:
        f = s.makefile("rwb", buffering=0)
        f.write((line + "\n").encode())
        return f.readline().decode().strip()


def start_test_bed():
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


class Listener:
    """Listens on a port this test picked, never 8300, and counts connections: a frame sent by
    mistake would be seen here, and nothing transmits."""

    def __init__(self):
        self.count = 0
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            self.count += 1
            c.close()


def make_stubs():
    os.makedirs(STUBS, exist_ok=True)
    for name in ("xarachat", "openslot", "radiogram", "d750-sstv", "d750-rtty"):
        with open(os.path.join(STUBS, name), "w", encoding="ascii") as f:
            f.write(STUB)
        os.chmod(os.path.join(STUBS, name), 0o755)
    with open(os.path.join(STUBS, "argdump"), "w", encoding="ascii") as f:
        f.write(ARGDUMP)
    os.chmod(os.path.join(STUBS, "argdump"), 0o755)


def stub_log():
    try:
        with open(STUB_LOG, encoding="ascii") as f:
            return f.read().splitlines()
    except OSError:
        return []


def child_env(xara_port):
    conf = os.path.join(WORK, "conf")
    os.makedirs(conf, exist_ok=True)
    with open(os.path.join(conf, "d750ctrl.conf"), "w", encoding="ascii") as f:
        f.write(f"mycall = W9XYZ\nrig_key = {RIG_KEY}\nnext_key = {NEXT_KEY}\nstatus_seconds = 1\n")
    env = {k: v for k, v in os.environ.items() if k not in ("LINES", "COLUMNS", "NO_COLOR", "TMUX", "TMUX_PANE")}
    env.update(TERM="xterm", D750_CONF_DIR=conf, D750_CMD_PORT=str(CMD_PORT), D750_PTT_PORT="4542",
               D750_XARA_PORT=str(xara_port), STUB_LOG=STUB_LOG, PYTHONUNBUFFERED="1",
               PATH=STUBS + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"))
    return env


# --------------------------------------------------------------------------- a client on a pseudo terminal


def _take_terminal():
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class Client:
    """d750ctrl on a pseudo terminal; once it is in the workspace, this is the tmux client."""

    def __init__(self, args, env):
        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
        self.before = termios.tcgetattr(self.slave)
        self.out = bytearray()
        self.proc = subprocess.Popen([sys.executable, SCREEN, *args], stdin=self.slave, stdout=self.slave,
                                     stderr=self.slave, cwd=TOP, env=env, start_new_session=True,
                                     preexec_fn=_take_terminal, close_fds=True)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            try:
                data = os.read(self.master, 65536)
            except OSError:
                return
            if not data:
                return
            self.out += data

    def press(self, keys):
        os.write(self.master, keys.encode("ascii"))

    def ended(self, limit=WAIT):
        try:
            return self.proc.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            return None

    def settings_back(self):
        return termios.tcgetattr(self.slave) == self.before

    def end(self):
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
        finally:
            for fd in (self.master, self.slave):
                try:
                    os.close(fd)
                except OSError:
                    pass


def rig_ready():
    return wait_until(lambda: "rig" in windows() and any(r.startswith("d750ctrl. Receiving.") for r in pane()))


def dump():
    return "\n".join(f"  {i}: {row!r}" for i, row in enumerate(pane())) + f"\n  windows {windows()}, active {active()!r}"


# --------------------------------------------------------------------------- the checks


def the_workspace_starts_and_options_reach_the_inner_program(env):
    client = Client(["--view", "list"], env)
    try:
        started = wait_until(lambda: "rig" in windows())
        check("the workspace starts: a session on the socket d750 with a window named rig", started,
              f"windows {windows()}")
        command = tmux("list-panes", "-t", "d750:rig", "-F", "#{pane_start_command}").stdout
        check("the rig window runs d750ctrl started with --inside", "--inside" in command and "d750ctrl" in command,
              command)
        check("an option given at start reaches the inner program", "--view=list" in command, command)
        check("the rig screen shows in the rig window, in the list view",
              wait_until(lambda: shows("d750ctrl. Receiving.") and shows("Daemon port open")), dump())
        check("the client on this terminal is attached to the workspace", client.proc.poll() is None)
        client.press("Q")
        check("Q with no tool windows ends the session, and the server with it", wait_until(lambda: not server_up()))
        check("the client ends and the terminal is back", client.ended() is not None and client.settings_back())
    finally:
        client.end()
        tmux("kill-server")


def the_tools_and_the_keys(env, xara):
    client = Client([], env)
    second = None
    try:
        if not check("the face shows in the rig window", rig_ready() and wait_until(lambda: shows("Unlocked.")), dump()):
            return
        time.sleep(0.5)
        # A tool with no pause: chat.
        client.press("x")
        check("x opens a window named chat", wait_until(lambda: "chat" in windows()), dump())
        check("the chat window runs the stub with its arguments", wait_until(lambda: "xarachat --tui" in stub_log()),
              str(stub_log()))
        check("the chat window is the one in front", wait_until(lambda: active() == "chat"), dump())
        check(f"the message row says chat opened, and {RIG_KEY} comes back",
              wait_until(lambda: message_row().startswith("Chat opened.") and RIG_KEY in message_row()), dump())
        # The rig key from the settings.
        client.press(F5)
        check(f"{RIG_KEY}, the rig key from the settings, brings the rig window back",
              wait_until(lambda: active() == "rig"), dump())
        time.sleep(0.3)
        client.press("x")
        check("x again goes to the open chat window, and opens no second one",
              wait_until(lambda: active() == "chat") and windows().count("chat") == 1
              and stub_log().count("xarachat --tui") == 1, dump() + f"\n{stub_log()}")
        check("the message row says the chat window was selected",
              wait_until(lambda: message_row().startswith("Chat window.")), dump())
        client.press(F5)
        wait_until(lambda: active() == "rig")
        time.sleep(0.3)
        before = message_row()
        client.press("o")
        check("o with chat open goes to the chat window, and opens no varac window",
              wait_until(lambda: active() == "chat") and "varac" not in windows()
              and not any("--varac" in line for line in stub_log()), dump() + f"\n{stub_log()}")
        check("the message row says how to switch", wait_until(
            lambda: message_row() != before and "chat" in message_row().lower()), dump())
        client.press(F5)
        wait_until(lambda: active() == "rig")
        # The screen learns the open windows.
        check("the face learns the open windows: Windows open: chat.",
              wait_until(lambda: shows("Windows open: chat.")), dump())
        # The next-window key.
        client.press(F6)
        check(f"{NEXT_KEY}, the next-window key from the settings, steps to the next window",
              wait_until(lambda: active() == "chat"), dump())
        client.press(F5)
        wait_until(lambda: active() == "rig")
        time.sleep(0.3)
        # A tool with a pause: radiogram.
        client.press("r")
        check("r opens a window named radiogram, which runs the stub",
              wait_until(lambda: "radiogram" in windows() or "radiogram new" in stub_log())
              and wait_until(lambda: "radiogram new" in stub_log()), dump() + f"\n{stub_log()}")
        check("after the tool, its window says Done. Enter closes this window.",
              wait_until(lambda: shows("Done. Enter closes this window.", "d750:radiogram")),
              "\n".join(pane("d750:radiogram")))
        check(f"the pause names the rig key {RIG_KEY}",
              shows(f"{RIG_KEY} is the rig screen.", "d750:radiogram"), "\n".join(pane("d750:radiogram")))
        wait_until(lambda: active() == "radiogram", 3)
        client.press("\r")
        check("Enter closes the radiogram window", wait_until(lambda: "radiogram" not in windows()), dump())
        client.press(F5)
        wait_until(lambda: active() == "rig")
        # The windows are read with each full sweep (every second here). This test closes the radiogram
        # window within a tenth of a second, so a read made while it was open can come back after it
        # closed; the next sweep puts it right. So: wait past two sweeps, then the list must hold.
        time.sleep(2.5)
        seen = []
        end = time.monotonic() + 3.0
        while time.monotonic() < end:
            row = next((r[41:] for r in pane() if r[41:].startswith("Windows open")), "")
            if row not in seen:
                seen.append(row)
            time.sleep(0.1)
        check("the face learns a window closed, and the list holds over three sweeps",
              seen == ["Windows open: chat."], repr(seen))
        # Quit with windows open asks; n quits this screen only.
        client.press("q")
        asked = wait_until(lambda: bottom_row() == "Close the tool windows too? y or n")
        check("q with a tool window open asks, and names the windows",
              asked and message_row() == "Windows open: chat.", dump())
        time.sleep(0.7)
        client.press("n")
        check("n quits this screen only: the rig window goes, the chat window and the server stay",
              wait_until(lambda: windows() == ["chat"]) and server_up(), dump())
        # Start again: the workspace is found and a rig window added.
        second = Client([], env)
        check("starting again adds a rig window to the workspace that is there",
              rig_ready() and windows().count("chat") == 1, dump())
        check("the screen started again learns the chat window", wait_until(lambda: shows("Windows open: chat.")),
              dump())
        time.sleep(0.5)
        second.press("q")
        asked = wait_until(lambda: bottom_row() == "Close the tool windows too? y or n")
        check("q asks again", asked, dump())
        time.sleep(0.7)
        second.press("y")
        check("y ends the workspace: the tmux server on the socket d750 is gone", wait_until(lambda: not server_up()))
        check("both clients end", second.ended() is not None and client.ended() is not None)
        check("the terminal of the screen that asked is back", second.settings_back())
        check("no frame was sent", xara.count == 0)
    finally:
        if second is not None:
            second.end()
        client.end()
        tmux("kill-server")


def pastes_through_tmux(env):
    """tmux's own paste command with marks (paste-buffer -p), into the rig screen's main mode and
    into a typing line."""
    client = Client([], env)
    try:
        if not check("the face shows for the paste checks", rig_ready() and wait_until(lambda: shows("Unlocked.")),
                     dump()):
            return
        time.sleep(0.5)
        radio = [ask(line) for line in ("FQ 0", "MD 0", "PC 0", "BC")]
        tmux("set-buffer", "-b", "t750", "mpb146.52")
        tmux("paste-buffer", "-p", "-b", "t750", "-t", "d750:rig")
        check("tmux's paste into main mode is dropped", wait_until(lambda: message_row() == "A paste was dropped."),
              dump())
        time.sleep(1.5)
        check("tmux's paste into main mode sets nothing",
              [ask(line) for line in ("FQ 0", "MD 0", "PC 0", "BC")] == radio)
        client.press("1")
        typing = wait_until(lambda: bottom_row().endswith("1"))
        tmux("set-buffer", "-b", "t750", "46.52")
        tmux("paste-buffer", "-p", "-b", "t750", "-t", "d750:rig")
        check("tmux's paste into a typing line is text in the line",
              typing and wait_until(lambda: bottom_row().endswith("146.52"))
              and wait_until(lambda: message_row() == "Pasted 5 characters. Enter applies."), dump())
        time.sleep(0.7)
        client.press("\x1b")
        wait_until(lambda: not bottom_row().endswith("146.52"))
        time.sleep(1.0)
        check("the pasted frequency was never applied", ask("FQ 0") == radio[0], ask("FQ 0"))
        # The blocker: tmux's paste of text that holds an end mark and a y, at the unlock question.
        client.press("L")
        locked = wait_until(lambda: "; locked" in ask("state")) and wait_until(lambda: shows("PTT locked."))
        time.sleep(1.5)
        client.press("L")
        asked = wait_until(lambda: bottom_row() == "Unlock PTT? y or n")
        time.sleep(0.7)
        tmux("set-buffer", "-b", "t750", "hi\x1b[201~y")
        tmux("paste-buffer", "-p", "-b", "t750", "-t", "d750:rig")
        time.sleep(1.5)
        check("tmux's paste of an end mark and a y at the unlock question unlocks nothing",
              locked and asked and "; locked" in ask("state") and bottom_row() == "Unlock PTT? y or n", dump())
        time.sleep(0.7)
        client.press("n")
        wait_until(lambda: message_row() == "Still locked.")
        time.sleep(0.7)
        client.press("L")
        wait_until(lambda: bottom_row() == "Unlock PTT? y or n")
        time.sleep(0.7)
        client.press("y")
        check("the lock is taken off again", wait_until(lambda: "; unlocked" in ask("state")))
        client.press("Q")
        check("the screen quits after the pastes", wait_until(lambda: not server_up()))
    finally:
        if "; locked" in ask("state"):
            ask("unlock")
        client.end()
        tmux("kill-server")


def what_tmux_marks():
    """Does tmux mark a paste only for a program that asked for it? Said as a note, and the case
    the screen relies on, a program that asked, is a check."""
    made = tmux("new-session", "-d", "-s", "d750", "-n", "rig", "-x", "80", "-y", "24", "sleep 600")
    if not check("a server for the marks probe starts", made.returncode == 0, made.stderr):
        return
    try:
        seen = {}
        for name, asks in (("unasked", False), ("asked", True)):
            out = os.path.join(WORK, f"marks-{name}.txt")
            ask_bytes = "printf '\\033[?2004h'; " if asks else ""
            tmux("new-window", "-d", "-t", "d750", "-n", name, f"{ask_bytes}stty -echo; cat -v > {out}")
            time.sleep(0.5)
            tmux("set-buffer", "-b", "probe", "abc")
            tmux("paste-buffer", "-p", "-b", "probe", "-t", f"d750:{name}")
            time.sleep(0.3)
            tmux("send-keys", "-t", f"d750:{name}", "Enter")
            time.sleep(0.2)
            tmux("send-keys", "-t", f"d750:{name}", "C-d")
            wait_until(lambda: name not in windows(), 5)
            try:
                with open(out, encoding="latin-1") as f:
                    seen[name] = f.read()
            except OSError:
                seen[name] = ""
        unasked, asked = "^[[200~" in seen["unasked"], "^[[200~" in seen["asked"]
        print(f"Note: tmux marked a paste for a program that did not ask: {'yes' if unasked else 'no'}. "
              f"Saw {seen['unasked'].strip()!r}.")
        print(f"Note: tmux marked a paste for a program that asked: {'yes' if asked else 'no'}. "
              f"Saw {seen['asked'].strip()!r}.")
        check("tmux marks a paste for a program that asked for bracketed paste", asked, repr(seen))
    finally:
        tmux("kill-server")


ARGS = (
    "$(touch {work}/pwned1)",
    "'; touch {work}/pwned2; '",
    "`touch {work}/pwned3`",
    "two words  and spaces",
    "-n",
    "--help",
    "a;b|c&d>e",
    '"quoted"',
)


def typed_text_never_reaches_a_shell():
    from d750ui import screen as scr
    from d750ui import screen_model as sm

    os.environ["PATH"] = STUBS + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
    args = tuple(a.format(work=WORK) for a in ARGS)
    ports = scr.Ports(rig_key=RIG_KEY, workspace=True)
    shells = ["/bin/sh"] + [s for s in ("/bin/bash",) if os.path.exists(s)]
    try:
        made = tmux("new-session", "-d", "-s", "d750", "-n", "rig", "-x", "80", "-y", "24", "sleep 600")
        if not check("a workspace for the direct calls starts", made.returncode == 0, made.stderr):
            return
        for round_, shell in enumerate(shells, 1):
            tmux("set-option", "-g", "default-shell", shell)
            for pause in (False, True):
                name = f"probe{round_}{'p' if pause else ''}"
                dumpfile = os.path.join(WORK, f"argdump-{name}.txt")
                tmux("set-environment", "-g", "ARGDUMP", dumpfile)
                result = scr.tool_in_workspace(sm.Tool(name, ("argdump", *args), pause, None), ports)
                check(f"with default-shell {shell}, pause {pause}: the window opens", result == "opened", result)

                def lines_in():
                    try:
                        with open(dumpfile, encoding="utf-8") as f:
                            return f.read().split("\n")[:-1]
                    except OSError:
                        return []

                wait_until(lambda: len(lines_in()) >= len(args), 10)
                check(f"with default-shell {shell}, pause {pause}: every argument arrives whole",
                      tuple(lines_in()) == args, f"{lines_in()!r}")
                if pause:
                    check(f"with default-shell {shell}: the pause shows, and Enter closes the window",
                          wait_until(lambda: shows("Done. Enter closes this window.", f"d750:{name}"))
                          and tmux("send-keys", "-t", f"d750:{name}", "Enter").returncode == 0
                          and wait_until(lambda: name not in windows()), "\n".join(pane(f"d750:{name}")))
                else:
                    check(f"with default-shell {shell}: the window closes when the program ends",
                          wait_until(lambda: name not in windows()), str(windows()))
        made = [n for n in ("pwned1", "pwned2", "pwned3") if os.path.exists(os.path.join(WORK, n))]
        check("no typed text ran as a command: no pwned file exists", made == [], str(made))
        before = windows()
        result = scr.tool_in_workspace(sm.Tool("nothere", ("no-such-program-d750",), False, None), ports)
        check("a missing program gives missing", result == "missing", result)
        check("a missing program opens no window", windows() == before, f"{before} then {windows()}")
        result = scr.tool_in_workspace(sm.Tool("rig", ("argdump", "x"), False, None), ports)
        check("a tool whose window is open gives selected", result == "selected", result)
        tmux("new-window", "-d", "-t", "d750", "-n", "chat", "sleep 600")
        result = scr.tool_in_workspace(sm.Tool("varac", ("argdump", "y"), False, "chat"), ports)
        check("a tool whose other window is open gives other, and opens nothing",
              result == "other" and "varac" not in windows() and active() == "chat", f"{result} {windows()}")
        check("Windows() names the open tool windows, without rig",
              scr.carry(sm.Windows(), None, ports) == ("chat",), str(scr.carry(sm.Windows(), None, ports)))
    finally:
        tmux("kill-server")


def main():
    if shutil.which("tmux") is None:
        print("Note: tmux is not installed. Nothing tested.")
        return 0
    make_stubs()
    xara = Listener()
    env = child_env(xara.port)
    default_before = default_socket_up()
    tmux("kill-server")  # only the workspace socket, and only in case an earlier run left it
    operator = tmux("new-session", "-d", "-s", "mine", "sleep 600", sock=OPERATOR)
    bed = start_test_bed()
    try:
        for part in (lambda: the_workspace_starts_and_options_reach_the_inner_program(env),
                     lambda: the_tools_and_the_keys(env, xara),
                     lambda: pastes_through_tmux(env),
                     what_tmux_marks,
                     typed_text_never_reaches_a_shell):
            try:
                part()
            except Exception as e:  # noqa: BLE001
                check(f"no error in the test: {type(e).__name__}: {e}", False)
    finally:
        tmux("kill-server")
        stop_test_bed(bed)
    check("the test's tmux server on the socket d750 is ended", not server_up())
    check("another tmux server, standing for the operator's own, is untouched",
          operator.returncode == 0 and server_up(OPERATOR))
    check("no tmux server on the default socket was started", default_socket_up() == default_before)
    tmux("kill-server", sock=OPERATOR)  # the stand-in is this test's own
    if FAILED:
        print(f"Fail: d750ctrl-tmux, {len(FAILED)} of {TOTAL[0]} tests.")
        return 1
    print(f"Pass: d750ctrl-tmux, {TOTAL[0]} tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
