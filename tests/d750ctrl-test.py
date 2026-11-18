#!/usr/bin/env python3
"""d750ctrl-test: drive d750ctrl under a pseudo terminal against the simulator (tests/test-env.sh: ports 4542/4543),
press the keys, and check what the simulated radio ended up with and what the screen showed. Exit 0 on Pass.
The screen reaches d750d through a counting relay here, so the test also checks how often it reads the radio."""
import fcntl, os, pty, tempfile, re, select, socket, struct, subprocess, sys, termios, threading, time

here = os.path.dirname(os.path.abspath(__file__))
top = os.path.dirname(here)
env_proc = subprocess.Popen(["sh", os.path.join(here, "test-env.sh")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

def ask(line):
    s = socket.create_connection(("127.0.0.1", 4543), timeout=5); f = s.makefile("rwb", buffering=0)
    f.write((line + "\n").encode()); r = f.readline().decode().strip(); s.close(); return r

sent = []   # (time, line) for every line the screen sent to d750d
def relay():
    """Listen on a free port; pass each line on to d750d's command port 4543 and its one answer line back."""
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0)); srv.listen(4)
    def serve(c):
        try:
            up = socket.create_connection(("127.0.0.1", 4543), timeout=5)
            cf, uf = c.makefile("rwb", buffering=0), up.makefile("rwb", buffering=0)
            for raw in cf:
                if not raw.strip(): continue
                sent.append((time.monotonic(), raw.decode(errors="replace").strip()))
                uf.write(raw); cf.write(uf.readline())
        except OSError:
            pass
    def accept():
        while True:
            c, _ = srv.accept(); threading.Thread(target=serve, args=(c,), daemon=True).start()
    threading.Thread(target=accept, daemon=True).start()
    return srv.getsockname()[1]

STATUS, BUSY = 3, 0.75   # not the defaults (2 and 1), so the test sees the settings read
conf_dir = tempfile.mkdtemp(prefix="d750ctrl-test-")   # the operator's settings stay out of the test
with open(os.path.join(conf_dir, "d750ctrl.conf"), "w", encoding="utf-8") as f:
    f.write(f"status_seconds = {STATUS}\nbusy_seconds = {BUSY}\n")
env = dict(os.environ, TERM="xterm", D750_CMD_PORT=str(relay()), D750_PTT_PORT="4542", D750_CONF_DIR=conf_dir)
pid, fd = pty.fork()
if pid == 0:
    os.execvpe(sys.executable, [sys.executable, os.path.join(top, "d750ctrl"), "--ascii", "--theme", "mono", "--plain"], env)
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
steps = 0
def step(desc, cond):
    global ok, steps
    steps += 1
    print(f"{steps}. {'Pass' if cond else 'Fail'}: {desc}", flush=True); ok = ok and cond

pump(2.5)
step("both band panels and the CAT log drawn", seen("BAND A") and seen("BAND B") and seen("CAT log"))
step("frequency shown in the panel", seen("144.390") or seen("147.040"))
# how often the screen reads the radio with no keys pressed; d750d's own words (state) cost the radio nothing
WINDOW = 7.5
t0 = time.monotonic(); pump(WINDOW)
quiet = [l for t, l in list(sent) if t0 <= t < t0 + WINDOW]
cat = [l for l in quiet if l.split()[0].lower() not in ("state", "lock", "unlock")]
n_fq, n_by0, n_by1 = quiet.count("FQ 0"), quiet.count("BY 0"), quiet.count("BY 1")
step(f"full sweep every {STATUS} s from the settings: FQ 0 read {n_fq} times in {WINDOW:g} s", 2 <= n_fq <= 3)
step(f"busy flags every {BUSY:g} s from the settings: BY 0 read {n_by0} times, BY 1 {n_by1} times",
     9 <= n_by0 <= 11 and 9 <= n_by1 <= 11)
step(f"{len(cat) / WINDOW:.1f} CAT commands a second, under 10 (about 29 before November 11)", len(cat) / WINDOW < 10)
send("\t", 0.8)                                            # active band B
send("\x1bOA", 1.2)                                        # Up in keypad mode: one step of 10 kHz
step("Up tunes the active band one step", ask("FQ 1") == "FQ 1,0144400000")
send("]", 1.0); step("] raises the squelch", ask("SQ 1") == "SQ 1,4")
log = list(sent)
t_set = next((t for t, l in log if l == "SQ 1,4"), None)
t_back = next((t for t, l in log if t_set is not None and t > t_set and l == "SQ 1"), None)
step("a change is read back at once, not at the next sweep",
     t_set is not None and t_back is not None and t_back - t_set < 0.6)
send("p", 1.0); step("p cycles the power", ask("PC 1") == "PC 1,2")
send("m", 1.0); step("m cycles the mode to NFM (code 1 on the TM-D750)", ask("MD 1") == "MD 1,1")
send("b", 1.0); step("b makes the band control and transmit", ask("BC") == "BC 1,1")
send("146.520\r", 1.2); step("a typed frequency tunes", ask("FQ 1") == "FQ 1,0146520000")
send("M", 2.0)
for _ in range(60):
    if seen("memory channels in 000 to 199"): break
    pump(0.5)
step("memory browser lists channels", seen("146.520 MHz") or seen("000  "))
send("\r", 1.0); step("Enter recalls a channel into memory mode", ask("VM 1") == "VM 1,1")
tn_before = ask("TN"); send("t", 0.6); send("n", 0.8); step("t asks before changing the TNC and n leaves it", tn_before.startswith("TN") and ask("TN") == tn_before)
send("L", 1.0); step("L locks PTT in the daemon", "locked" in ask("state") and "unlocked" not in ask("state"))
send("L", 1.0); step("L again unlocks", "unlocked" in ask("state"))
send(":", 0.5); send("ID\r", 1.0); step("a raw CAT command shows its answer", seen("ID -> ID TM-D750"))
send("?", 0.8); step("help screen", seen("any key returns")); send(" ", 0.5)
send("S", 0.8); step("S offers the SSTV menu", seen("SSTV: r receive, s send")); send("\x1b", 0.8)
send("R", 0.8); step("R offers the RTTY menu", seen("RTTY: r receive, s send")); send("\x1b", 0.8)
send("q", 1.0)
try:
    os.waitpid(pid, 0); exited = True
except ChildProcessError:
    exited = False
step("q quits", exited)
env_proc.terminate()
for p in open(os.path.expanduser("~/.local/share/d750ctrl/log/test/pids")).read().split():
    try: os.kill(int(p), 15)
    except (ProcessLookupError, ValueError): pass
print("Pass: d750ctrl" if ok else "Fail: d750ctrl")
if not ok:
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][B0]|\x1b[=>]", " ", screen.decode(errors="replace"))
    print("--- screen tail ---"); print(" ".join(text.split())[-1200:])
sys.exit(0 if ok else 1)
