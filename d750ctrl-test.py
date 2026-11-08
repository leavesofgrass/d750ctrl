#!/usr/bin/env python3
"""d750ctrl-test: drive d750ctrl under a pseudo terminal against the simulator (test-env.sh: ports 4542/4543),
press the keys, and check what the simulated radio ended up with and what the screen showed. Exit 0 on Pass."""
import fcntl, os, pty, re, select, socket, struct, subprocess, sys, termios, time

here = os.path.dirname(os.path.abspath(__file__))
env_proc = subprocess.Popen(["sh", os.path.join(here, "test-env.sh")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

def ask(line):
    s = socket.create_connection(("127.0.0.1", 4543), timeout=5); f = s.makefile("rwb", buffering=0)
    f.write((line + "\n").encode()); r = f.readline().decode().strip(); s.close(); return r

env = dict(os.environ, TERM="xterm", D750_CMD_PORT="4543", D750_PTT_PORT="4542")
pid, fd = pty.fork()
if pid == 0:
    os.execvpe(sys.executable, [sys.executable, os.path.join(here, "d750ctrl"), "--ascii", "--theme", "mono", "--plain"], env)
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
screen = b""
def pump(seconds):
    global screen
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try: screen += os.read(fd, 65536)
            except OSError: return
def send(keys, wait=0.7):
    os.write(fd, keys.encode()); pump(wait)
def seen(text): return text.encode() in screen
ok = True
def step(n, desc, cond):
    global ok
    print(f"{n}. {'Pass' if cond else 'Fail'}: {desc}", flush=True); ok = ok and cond

pump(2.5)
step(1, "both band panels and the CAT log drawn", seen("BAND A") and seen("BAND B") and seen("CAT log"))
step(2, "frequency shown in the panel", seen("144.390") or seen("147.040"))
send("\t", 0.8)                                            # active band B
send("\x1bOA", 1.2)                                        # Up in keypad mode: one step of 10 kHz
step(3, "Up tunes the active band one step", ask("FQ 1") == "FQ 1,0144400000")
send("]", 1.0); step(4, "] raises the squelch", ask("SQ 1") == "SQ 1,4")
send("p", 1.0); step(5, "p cycles the power", ask("PC 1") == "PC 1,2")
send("m", 1.0); step(6, "m cycles the mode to NFM", ask("MD 1") == "MD 1,6")
send("b", 1.0); step(7, "b makes the band control and transmit", ask("BC") == "BC 1,1")
send("146.520\r", 1.2); step(8, "a typed frequency tunes", ask("FQ 1") == "FQ 1,0146520000")
send("M", 2.0)
for _ in range(60):
    if seen("memory channels in 000 to 199"): break
    pump(0.5)
step(9, "memory browser lists channels", seen("146.520 MHz") or seen("000  "))
send("\r", 1.0); step(10, "Enter recalls a channel into memory mode", ask("VM 1") == "VM 1,1")
send("t", 0.6); send("n", 0.8); step(11, "t asks before changing the TNC and n leaves it", ask("TN") == "TN 2,1")
send("L", 1.0); step(12, "L locks PTT in the daemon", "locked" in ask("state") and "unlocked" not in ask("state"))
send("L", 1.0); step(13, "L again unlocks", "unlocked" in ask("state"))
send(":", 0.5); send("ID\r", 1.0); step(14, "a raw CAT command shows its answer", seen("ID -> ID TM-D750"))
send("?", 0.8); step(15, "help screen", seen("any key returns")); send(" ", 0.5)
send("S", 0.8); step(16, "S offers the SSTV menu", seen("SSTV: r receive, s send")); send("\x1b", 0.8)
send("R", 0.8); step(17, "R offers the RTTY menu", seen("RTTY: r receive, s send")); send("\x1b", 0.8)
send("q", 1.0)
try:
    os.waitpid(pid, 0); exited = True
except ChildProcessError:
    exited = False
step(18, "q quits", exited)
env_proc.terminate()
for p in open(os.path.expanduser("~/.local/share/d750ctrl/log/test/pids")).read().split(): 
    try: os.kill(int(p), 15)
    except (ProcessLookupError, ValueError): pass
print("Pass: d750ctrl" if ok else "Fail: d750ctrl")
if not ok:
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][B0]|\x1b[=>]", " ", screen.decode(errors="replace"))
    print("--- screen tail ---"); print(" ".join(text.split())[-1200:])
sys.exit(0 if ok else 1)
