"""Offline tests for notify: the curl command line, the token, and the promise never to fail the caller.

Run: python3 -I station/notify-test.py. A fake curl on the PATH records its arguments and what it was handed
on its standard input, and fails when told to. Nothing here uses the network.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
NOTIFY = os.path.join(HERE, "notify")
tmp = tempfile.mkdtemp(prefix="notify-test-")
BIN, HOME, CONF = (os.path.join(tmp, n) for n in ("bin", "home", "conf"))
for d in (BIN, HOME, CONF):
    os.makedirs(d)
ARGS, STDIN, FAIL = (os.path.join(tmp, n) for n in ("args", "stdin", "fail"))
TOKEN = "tk_testtokenfortheofflinetests"

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"Pass: {name}")
    else:
        failed += 1
        print(f"Fail: {name}")
        if detail:
            for line in str(detail).splitlines()[:12]:
                print(f"  {line}")


with open(os.path.join(BIN, "curl"), "w") as f:
    f.write(f"""#!{sys.executable}
import sys
with open({ARGS!r}, "w") as f:
    f.write("\\n".join(sys.argv[1:]))
handed = sys.stdin.read() if "-K" in sys.argv[1:] else ""
with open({STDIN!r}, "w") as f:
    f.write(handed)
try:
    sys.exit(int(open({FAIL!r}).read()))
except OSError:
    sys.exit(0)
""")
os.chmod(os.path.join(BIN, "curl"), 0o755)

ENV = dict(os.environ, PATH=BIN + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"), HOME=HOME,
           D750_CONF_DIR=CONF)
for k in ("NOTIFY_SERVER", "NOTIFY_TOKEN"):
    ENV.pop(k, None)


def notify(*args, env=None, curl_exit=0):
    for p in (ARGS, STDIN):
        if os.path.exists(p):
            os.unlink(p)
    with open(FAIL, "w") as f:
        f.write(str(curl_exit))
    p = subprocess.run(["/bin/sh", NOTIFY, *args], env=dict(ENV, **(env or {})), stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=30)
    got_args = open(ARGS).read().split("\n") if os.path.exists(ARGS) else []
    got_stdin = open(STDIN).read() if os.path.exists(STDIN) else ""
    return p.returncode, p.stdout + p.stderr, got_args, got_stdin


def after(args, flag, value):
    """True when flag is followed by value somewhere in args."""
    return any(a == flag and b == value for a, b in zip(args, args[1:]))


def settings(text):
    path = os.path.join(CONF, "notify.conf")
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o600)


# ---- No settings file: this computer's ntfy, no token
rc, out, args, stdin = notify("alerts", "Crows on the wire again", "Rain on the bridge, coffee is on", "4", "bird")
check("exit 0 when ntfy takes it", rc == 0 and out == "", out)
check("posts to the ntfy server on this computer", args[-1] == "http://127.0.0.1:2586/alerts", args)
check("the title header", after(args, "-H", "Title: Crows on the wire again"), args)
check("the priority header", after(args, "-H", "Priority: 4"), args)
check("the tags header", after(args, "-H", "Tags: bird"), args)
check("the message as raw data, never read from a file", after(args, "--data-raw", "Rain on the bridge, coffee is on"),
      args)
check("a ten second limit", after(args, "-m", "10"), args)
check("no Authorization header without a token", not any("Authorization" in a for a in args)
      and "Authorization" not in stdin and "-K" not in args, args)

rc, out, args, stdin = notify("aprs", "APRS from W7XYZ", "Meet at the food carts")
check("priority 3 and empty tags by default", after(args, "-H", "Priority: 3") and after(args, "-H", "Tags: "), args)

rc, out, args, stdin = notify("aprs", "Line one\nX-Other: two", "@/etc/hostname")
check("a line break in the title cannot start a new header",
      after(args, "-H", "Title: Line one X-Other: two"), args)
check("a message starting with @ is sent as it is", after(args, "--data-raw", "@/etc/hostname"), args)

# ---- A settings file with a server and a token
settings(f"# test settings\nserver = http://127.0.0.1:8080/\ntoken = {TOKEN}\n")
rc, out, args, stdin = notify("alerts", "Title", "Message")
check("the server comes from the settings file", "http://127.0.0.1:8080/alerts" in args, args)
check("the token is sent as an Authorization header", stdin == f'header = "Authorization: Bearer {TOKEN}"\n', stdin)
check("the token never appears on curl's command line", not any(TOKEN in a for a in args), args)

rc, out, args, stdin = notify("alerts", "Title", "Message", env={"NOTIFY_TOKEN": "tk_fromtheenvironment",
                                                                  "NOTIFY_SERVER": "http://127.0.0.1:9090"})
check("the environment overrides the settings file", "tk_fromtheenvironment" in stdin and TOKEN not in stdin
      and "http://127.0.0.1:9090/alerts" in args, args)

settings("server = http://127.0.0.1:2586\ntoken =\n")
rc, out, args, stdin = notify("alerts", "Title", "Message")
check("an empty token sends no Authorization header", "-K" not in args and stdin == "", args)

# ---- Never fails the caller
settings(f"token = {TOKEN}\n")
rc, out, args, stdin = notify("alerts", "Title", "Message", curl_exit=7)
check("exit 0 when ntfy is down", rc == 0, out)
check("one line on standard error when ntfy is down", out == "notify: ntfy did not take the message\n", out)
NOCURL = os.path.join(tmp, "nocurl")
os.makedirs(NOCURL)
for tool in ("sed", "tr", "head"):
    os.symlink(shutil.which(tool), os.path.join(NOCURL, tool))
rc, out, args, stdin = notify("alerts", "Title", "Message", env={"PATH": NOCURL})
check("exit 0 when curl is not there at all", rc == 0 and args == [], out)

shutil.rmtree(tmp, ignore_errors=True)
print(f"{passed} passed, {failed} failed.")
sys.exit(1 if failed else 0)
