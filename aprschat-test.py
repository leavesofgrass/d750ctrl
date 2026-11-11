"""Offline tests for aprschat: the history, line mode, and the screen under a pseudo terminal.

Run: python3 -I aprschat-test.py. A stand-in for d750-aprs answers on a throwaway control socket and
writes the history events the real one would. Nothing here opens the radio or transmits.
"""

import fcntl
import importlib.util
import json
import os
import pty
import select
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time

HERE = os.path.dirname(os.path.realpath(__file__))
tmp = tempfile.mkdtemp(prefix="aprschat-test-")
MSG, SOCK, STATE = (os.path.join(tmp, n) for n in ("messages.jsonl", "ctl.sock", "state.json"))
os.environ.update(APRSCHAT_MESSAGES=MSG, APRSCHAT_SOCK=SOCK, APRSCHAT_STATE=STATE)
spec = importlib.util.spec_from_file_location("aprschat", os.path.join(HERE, "aprschat.py"))
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)

passed = failed = 0


def check(name, got, want):
    global passed, failed
    if got == want:
        passed += 1
    else:
        failed += 1
        print(f"Fail: {name}\n  got:  {got!r}\n  want: {want!r}")


def event(**e):
    with open(MSG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), **e}) + "\n")


# A stand-in for d750-aprs: answers status and send, and acknowledges each message a moment later.
sent = []


def fake_daemon():
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(SOCK)
    srv.listen(4)
    n = 0
    while True:
        c, _ = srv.accept()
        line = c.makefile().readline().strip()
        if line == "status":
            c.sendall(b"N0CALL-2: TNC connected, transmitting on.\n")
        elif line.startswith("send "):
            _, call, text = line.split(" ", 2)
            n += 1
            sent.append((call, text))
            event(dir="out", call=call.upper(), id=str(n), text=text, state="queued")
            c.sendall(f"Queued as {n}.\n".encode())
            threading.Timer(0.3, event, kwargs=dict(dir="out", call=call.upper(), id=str(n), state="acked")).start()
        c.close()


threading.Thread(target=fake_daemon, daemon=True).start()
time.sleep(0.2)

# The history: conversations, our messages with their state, a part that is not ours ignored.
event(dir="in", call="KD7SWH-7", id="1", text="hello from the window", via="rf")
event(dir="out", call="KD7SWH-7", id="5", text="hi back", state="queued")
event(dir="out", call="KD7SWH-7", id="5", state="sent", tries=1)
event(dir="in", call="W7XYZ", id="2", text="from the web", via="is")
event(dir="out", call="NOBODY", id="99", state="acked")
h = chat.History(MSG)
h.poll()
check("two conversations", sorted(h.conv), ["KD7SWH-7", "W7XYZ"])
check("our message, sent once", (h.conv["KD7SWH-7"][1]["state"], h.conv["KD7SWH-7"][1]["tries"]), ("sent", 1))
line = chat.entry_line(h.conv["KD7SWH-7"][1], "KD7SWH-7", "N0CALL-2")
check("our line says what became of it", line.split(" ", 1)[1], "N0CALL-2: hi back. Sent, try 1 of 5, waiting for the acknowledgement.")
check("an internet message says so", chat.entry_line(h.conv["W7XYZ"][0], "W7XYZ", "X").split(" ", 1)[1],
      "W7XYZ: from the web (through the internet)")
event(dir="out", call="KD7SWH-7", id="5", state="acked")
check("an update comes back as one change", [(k, c) for k, c, _ in h.poll()], [("update", "KD7SWH-7")])
check("acknowledged in words", chat.entry_line(h.conv["KD7SWH-7"][1], "KD7SWH-7", "X").endswith("hi back. Acknowledged."), True)
check("call signs", [chat.valid_call(x) for x in ("kd7swh-7", "N0CALL", "hello", "W7X-16", "AB")],
      ["KD7SWH-7", "N0CALL", None, None, None])

# Line mode, as a screen reader would use it.
env = dict(os.environ, HOME=tmp)
p = subprocess.Popen([sys.executable, "-I", os.path.join(HERE, "aprschat.py"), "--line", "kd7swh-7"], env=env,
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
p.stdin.write("line mode test\n")
p.stdin.flush()
time.sleep(1.5)
p.stdin.write("/quit\n")
p.stdin.flush()
out = p.communicate(timeout=10)[0]
check("line mode shows the conversation", "KD7SWH-7: hello from the window" in out, True)
check("line mode sends", sent[-1], ("KD7SWH-7", "line mode test"))
check("line mode says it was queued", "to KD7SWH-7: line mode test. Queued as" in out, True)
check("line mode says the acknowledgement", "KD7SWH-7 acknowledged: line mode test" in out, True)

# The screen, in a pseudo terminal: F2 and a call sign, a typed line, Enter, F10.
pid, fd = pty.fork()
if pid == 0:
    os.execvpe(sys.executable, [sys.executable, "-I", os.path.join(HERE, "aprschat.py")],
               dict(env, TERM="xterm", LINES="24", COLUMNS="100"))
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
screen = b""


def pump(seconds):
    global screen
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                screen += os.read(fd, 65536)
            except OSError:
                return


def keys(text, wait=0.8):
    os.write(fd, text.encode())
    pump(wait)


pump(1.5)
check("screen opens on the last conversation", b"with KD7SWH-7" in screen, True)
keys("\x1bOQ")                      # F2
check("F2 asks for a call sign", b"Station call sign" in screen, True)
keys("w7xyz\r")
check("talking with W7XYZ", b"To W7XYZ:" in screen, True)
keys("screen test\r", 1.5)
check("the screen sends", sent[-1], ("W7XYZ", "screen test"))
# curses writes only what changes: "Waiting to go out." first, then "Acknowledged." over it.
at = screen.find(b"screen test. Waiting to go out.")
check("the screen shows it waiting, then acknowledged", at >= 0 and b"Acknowledged." in screen[at:], True)
event(dir="in", call="KD7SWH-7", id="3", text="are you there", via="rf")
pump(1.5)
check("a message from another station is said", b"New message from KD7SWH-7: are you there" in screen, True)
keys("\x1b[21~", 1.0)               # F10
try:
    os.waitpid(pid, 0)
    check("F10 quits", True, True)
except ChildProcessError:
    check("F10 quits", True, True)

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print(f"{passed} passed, {failed} failed.")
sys.exit(1 if failed else 0)
