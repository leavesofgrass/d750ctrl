"""Offline tests for station: the built-in table, the settings file, order, questions, unkeying and markers.

Run: python3 -I station/station-test.py. Fake systemctl, docker and d750 programs on the PATH, in a
throwaway folder, record every call and answer from a small file of states. Nothing here touches a real
service, the radio, the network or the sound card.
"""

import json
import os
import pty
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
STATION = os.path.join(HERE, "station")
tmp = tempfile.mkdtemp(prefix="station-test-")
BIN, HOME, RUN, CONF = (os.path.join(tmp, n) for n in ("bin", "home", "run", "conf"))
for d in (BIN, HOME, RUN, CONF):
    os.makedirs(d)
STATE = os.path.join(tmp, "state.json")
CALLS = os.path.join(tmp, "calls.txt")

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


# ---- The fakes. Each appends its command line to calls.txt and reads and writes state.json.
COMMON = f"""import json, sys
STATE, CALLS = {STATE!r}, {CALLS!r}
def load():
    with open(STATE) as f:
        return json.load(f)
def save(s):
    with open(STATE, "w") as f:
        json.dump(s, f)
def record(name):
    with open(CALLS, "a") as f:
        f.write(" ".join([name] + sys.argv[1:]) + "\\n")
"""

FAKE_SYSTEMCTL = COMMON + """record("systemctl")
s = load()
args = [a for a in sys.argv[1:] if a not in ("--user", "--no-block")]
verb, unit = args[0], (args[1] if len(args) > 1 else "")
u = s["units"].setdefault(unit, {"active": "inactive", "enabled": "disabled", "since": ""})
if verb == "is-active":
    print(u["active"]); sys.exit(0 if u["active"] == "active" else 3)
if verb == "is-enabled":
    print(u["enabled"]); sys.exit(0 if u["enabled"] == "enabled" else 1)
if verb == "show":
    print(u["since"] if u["active"] == "active" else ""); sys.exit(0)
if verb in ("start", "restart"):
    u["active"] = "active"; u["since"] = "Tue 2026-11-17 09:41:00 UTC"
elif verb == "stop":
    u["active"] = "inactive"
elif verb == "enable":
    u["enabled"] = "enabled"
elif verb == "disable":
    u["enabled"] = "disabled"
save(s)
"""

FAKE_DOCKER = COMMON + """record("docker")
s = load()
a = sys.argv[1:]
if not s.get("daemon", True):
    print("Cannot connect to the Docker daemon", file=sys.stderr); sys.exit(1)
c = s["containers"]
if a[0] == "version":
    print("27.0.0"); sys.exit(0)
if a[0] == "inspect":
    name = a[-1]
    if name not in c:
        print(f"Error: No such object: {name}", file=sys.stderr); sys.exit(1)
    print(f"{c[name]}|none|2026-11-17T08:05:00.000000000Z|unless-stopped"); sys.exit(0)
if a[0] in ("start", "restart"):
    c[a[1]] = "running"
elif a[0] == "stop":
    c[a[1]] = "exited"
elif a[0] == "image":
    sys.exit(0 if a[-1] in s.get("images", []) else 1)
elif a[0] == "compose":
    compose = s["compose"][a[2]]
    if "config" in a:
        print(" ".join(compose["images"])); sys.exit(0)
    if "up" in a:
        c[compose["container"]] = "running"
save(s)
"""

FAKE_D750 = COMMON + """record("d750")
print("unkey: RPRT 0")
"""

for name, body in (("systemctl", FAKE_SYSTEMCTL), ("docker", FAKE_DOCKER), ("d750", FAKE_D750)):
    path = os.path.join(BIN, name)
    with open(path, "w") as f:
        f.write(f"#!{sys.executable}\n{body}")
    os.chmod(path, 0o755)


def states(units=None, containers=None, **extra):
    """Write the state file afresh and clear the call record."""
    base = {"units": {
        "d750d.service": {"active": "active", "enabled": "enabled", "since": "Tue 2026-11-17 08:15:02 UTC"},
        "xara.service": {"active": "inactive", "enabled": "enabled", "since": ""},
        "d750-aprs.service": {"active": "failed", "enabled": "disabled", "since": ""}},
        "containers": {}, "compose": {}, "images": []}
    base["units"].update(units or {})
    base["containers"].update(containers or {})
    base.update(extra)
    with open(STATE, "w") as f:
        json.dump(base, f)
    open(CALLS, "w").close()


def calls():
    with open(CALLS) as f:
        return [line.strip() for line in f if line.strip()]


def changes():
    """The calls that change something: everything but the questions about state."""
    quiet = (" is-active ", " is-enabled ", " show ", "docker inspect ", "docker version ")
    return [c for c in calls() if not any(q in c + " " for q in quiet)]


ENV = dict(os.environ, PATH=BIN + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"), HOME=HOME,
           XDG_RUNTIME_DIR=RUN, D750_CONF_DIR=CONF, STATION_SETTLE="0", TZ="UTC")
ENV.pop("STATION_DRY_RUN", None)


def station(*args, stdin=subprocess.DEVNULL):
    p = subprocess.run([sys.executable, "-I", STATION, *args], env=ENV, stdin=stdin,
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout + p.stderr


def station_tty(*args, answer="\n"):
    """Run station with a terminal on its standard input, and type answer into it."""
    master, slave = pty.openpty()
    p = subprocess.Popen([sys.executable, "-I", STATION, *args], env=ENV, stdin=slave,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    os.close(slave)
    os.write(master, answer.encode())
    out, _ = p.communicate(timeout=60)
    os.close(master)
    return p.returncode, out


def settings(text):
    with open(os.path.join(CONF, "station.conf"), "w") as f:
        f.write(text)


def no_settings():
    path = os.path.join(CONF, "station.conf")
    if os.path.exists(path):
        os.unlink(path)


# ---- The built-in table, with no settings file
no_settings()
states()
rc, out = station("help")
check("help exits 0", rc == 0, out)
check("help starts with what station is", out.startswith("station: raise and lower services.\n"), out)
check("help lists the three radio pieces",
      "radio: Radio service\nxara: xara\naprs: APRS\nall: the three above\n" in out, out)
check("help has no network group without a settings file", "Network names:" not in out, out)
check("help names the APRS question", "Questions: start APRS.\n" in out, out)
check("help ends with examples", out.endswith("Examples:\nstation status\nstation stop xara\n"), out)

rc, out = station()
check("no words is a usage error", rc == 2 and out.startswith("Say what to do.\n"), out)
rc, out = station("frob", "radio")
check("an unknown word is a usage error", rc == 2 and "Not a known word: frob" in out, out)
rc, out = station("--loud")
check("an unknown option is a usage error", rc == 2 and "Not a known option: --loud" in out, out)
rc, out = station("restart", "all")
check("restart works on one name only", rc == 2 and "restart works on one name, not all." in out, out)

states()
rc, out = station("status")
check("status of a running unit says since when", "Radio service: running since 08:15.\n" in out, out)
check("status of a stopped unit", "xara: stopped.\n" in out, out)
check("status of a failed unit", "APRS: failed.\n" in out, out)
check("status has the station heading only", out.startswith("Station:\n") and "Network:" not in out, out)
check("status changes nothing", changes() == [], calls())
rc, out = station("status", "network")
check("network is not a name without a network group", rc == 2 and "Not a known name: network" in out, out)
rc, out = station("status", "sshd")
check("sshd is only an unknown name without a settings file", rc == 2 and "Not a known name: sshd" in out, out)

# ---- Start in table order, stop backwards, unkeying before the radio service stops
states(units={"d750d.service": {"active": "inactive", "enabled": "enabled", "since": ""},
              "d750-aprs.service": {"active": "inactive", "enabled": "enabled", "since": ""}})
rc, out = station("--yes", "start", "all")
want = ["systemctl --user start d750d.service", "systemctl --user start --no-block xara.service",
        "systemctl --user start d750-aprs.service"]
check("start all runs in table order", changes() == want, "\n".join(changes()))
check("start all says the APRS warning even with --yes", "Starting APRS can transmit.\n" in out, out)
check("start all exits 0 when all run", rc == 0, out)
check("start all says what is running", "Radio service: running since 09:41.\n" in out
      and "APRS: running since 09:41.\n" in out, out)

states(units={"xara.service": {"active": "active", "enabled": "enabled", "since": "x 08:16:00"},
              "d750-aprs.service": {"active": "active", "enabled": "enabled", "since": "x 08:17:00"}})
rc, out = station("stop", "all")
want = ["systemctl --user stop d750-aprs.service", "systemctl --user stop xara.service", "d750 ptt off",
        "systemctl --user stop d750d.service"]
check("stop all runs backwards, unkeying before the radio service", changes() == want, "\n".join(changes()))
check("stop all says the unkeying", "Radio service: unkeying first.\n" in out, out)
check("stop all exits 0", rc == 0, out)

states(units={"xara.service": {"active": "active", "enabled": "enabled", "since": "x 08:16:00"}})
rc, out = station("stop", "radio")
check("stop radio unkeys first", changes() == ["d750 ptt off", "systemctl --user stop d750d.service"],
      "\n".join(changes()))
check("stop radio says xara's note while xara runs", out.rstrip().endswith("xara cannot key until it is back."), out)

states(units={"d750d.service": {"active": "inactive", "enabled": "enabled", "since": ""}})
rc, out = station("stop", "radio")
check("a radio service already stopped is not unkeyed", "d750" not in " ".join(c.split()[0] for c in changes())
      and "Radio service: not running. Nothing to unkey.\n" in out, out)

states()
rc, out = station("--dry-run", "stop", "radio")
check("a dry run prints the commands and runs none",
      out == "d750 ptt off\nsystemctl --user stop d750d.service\n" and changes() == [], out)

# ---- The APRS question, whose default is No
states(units={"d750-aprs.service": {"active": "inactive", "enabled": "enabled", "since": ""}})
rc, out = station_tty("start", "aprs", answer="\n")
check("Enter at the APRS question starts nothing", rc == 1 and "Not started." in out and changes() == [],
      out + "\n" + "\n".join(changes()))
check("the APRS question is asked", "Starting APRS can transmit." in out
      and "Start APRS? No is the default" in out, out)
states(units={"d750-aprs.service": {"active": "inactive", "enabled": "enabled", "since": ""}})
rc, out = station_tty("start", "aprs", answer="yes\n")
check("yes at the APRS question starts it", rc == 0 and changes() == ["systemctl --user start d750-aprs.service"],
      out + "\n" + "\n".join(changes()))
states()
rc, out = station("start", "aprs")
check("with no terminal the question is not guessed",
      rc == 1 and "No terminal to ask on. Use --yes.\nNot started.\n" in out and changes() == [], out)

# ---- on and off
states(units={"xara.service": {"active": "inactive", "enabled": "disabled", "since": ""}})
rc, out = station("on", "xara")
check("on enables, then starts", changes() == ["systemctl --user enable xara.service",
                                               "systemctl --user start --no-block xara.service"], "\n".join(changes()))
check("on says on at boot", "xara: on at boot.\n" in out, out)
rc, out = station("off", "xara")
check("off stops, then disables", changes()[-2:] == ["systemctl --user stop xara.service",
                                                     "systemctl --user disable xara.service"], "\n".join(changes()))
check("off says off at boot", "xara: stopped.\nxara: off at boot.\n" in out, out)

# ---- A settings file replaces the built-in table
settings("""# a test table
[service web]
kind = unit
unit = web.service
label = Web
""")
states(units={"web.service": {"active": "active", "enabled": "enabled", "since": "x 07:30:00"}})
rc, out = station("help")
check("a settings file replaces the table", "web: Web\nall: the one above\n" in out and "radio:" not in out, out)
check("with no question, help has no Questions line", "Questions:" not in out, out)
rc, out = station("status", "radio")
check("a name the file leaves out is unknown", rc == 2 and "Not a known name: radio" in out, out)
rc, out = station("status", "web")
check("status of a unit from the file", out == "Web: running since 07:30.\n", out)

settings("[service web]\nkind = vm\nunit = web.service\n")
rc, out = station("status")
check("a bad settings file is refused with its reason",
      rc == 2 and out.startswith("Settings: ") and "kind is unit or container." in out, out)
settings("[service web]\nunit = web.service\nwarn = It can transmit.\n")
rc, out = station("status")
check("warn without ask is refused", rc == 2 and "warn and ask go together." in out, out)
settings("[service web]\nunit = web.service\ncolour = blue\n")
rc, out = station("status")
check("an unknown field is refused", rc == 2 and "not a known field: colour" in out, out)

# ---- A network group: a container with a marker, a protected name, a watched timer
compose = os.path.join(HOME, "containers", "web", "compose.yml")
settings(f"""[service radio]
unit = d750d.service
label = Radio service
unkey = yes

[service web]
group = network
kind = container
container = web
compose = ~/containers/web/compose.yml
label = Web server
no_block = yes
waiting = Its health check is running.
marker = web
stop_note = Web server: the pages are gone until it is back.

[service sync]
group = network
unit = sync.service
label = Sync
stop_warn = Stopping Sync ends file sharing.
stop_ask = Stop Sync? No is the default

[watch]
name = web-up
unit = web-up.timer
label = web-up timer

[protect]
sshd = sshd stays up. You reach this computer by it.
docker = Docker stays up. The containers use it.

[help]
never_touched = sshd, docker
examples = station status
    station off web
""")
OFF = os.path.join(HOME, ".config", "station", "off-web")
STOP = os.path.join(RUN, "station", "stop-web")
states(units={"sync.service": {"active": "active", "enabled": "enabled", "since": "x 06:00:00"},
              "web-up.timer": {"active": "inactive", "enabled": "enabled", "since": ""}},
       containers={"web": "running"})
rc, out = station("help")
check("help lists the network group", "Network names:\nweb: Web server\nsync: Sync\nnetwork: the two above\n"
      "all and network: start, stop,\nstatus only. all never touches\nthe network group.\n" in out, out)
check("help names both questions and the timer",
      "Questions: stop Sync.\nweb-up skips what you lowered.\n" in out, out)
check("help says what is never touched", "Never touched: sshd, docker.\n" in out, out)
check("help takes the examples from the file", out.endswith("Examples:\nstation status\nstation off web\n"), out)

rc, out = station("stop", "sshd")
check("a protected name is refused with its reason", rc == 2 and out == "sshd stays up. You reach this computer by it.\n"
      and changes() == [], out)

rc, out = station("status")
check("status has both headings, the container, and the stopped timer",
      out == "Station:\nRadio service: running since 08:15.\nNetwork:\nWeb server: running since 08:05.\n"
             "Sync: running since 06:00.\nweb-up timer: stopped.\n", out)

rc, out = station("stop", "web")
check("stop of a container writes its stop marker", os.path.exists(STOP) and not os.path.exists(OFF), out)
check("the stop marker is written, then the container stopped", changes() == ["docker stop web"], calls())
check("stop of a container says its note", out == "Web server: stopped.\nWeb server: the pages are gone until "
                                                  "it is back.\n", out)
rc, out = station("off", "web")
check("off of a container writes its off marker", os.path.exists(OFF), out)
rc, out = station("status", "web")
check("the off marker reads as off at boot", out == "Web server: stopped.\nWeb server: off at boot.\n", out)
rc, out = station("start", "web")
check("start of a container removes both markers", not os.path.exists(OFF) and not os.path.exists(STOP), out)
check("start of a container runs docker start", "docker start web" in changes(), calls())

states(containers={}, compose={compose: {"images": ["example/web:1"], "container": "web"}}, images=[])
rc, out = station("start", "web")
check("a container whose image is missing is not pulled",
      rc == 1 and "Web server: image example/web:1 is not on this disk.\nNothing is pulled without internet.\n" in out
      and not any(" up " in c for c in changes()), out)
states(containers={}, compose={compose: {"images": ["example/web:1"], "container": "web"}}, images=["example/web:1"])
rc, out = station("start", "web")
check("a container not yet created is made from its compose file, never pulling",
      rc == 0 and f"docker compose -f {compose} up -d --pull never" in changes(), "\n".join(changes()))

states(units={"sync.service": {"active": "active", "enabled": "enabled", "since": "x 06:00:00"}},
       containers={"web": "running"})
rc, out = station("stop", "network")
check("stop network asks before Sync and, with no terminal, stops nothing",
      rc == 1 and "Stopping Sync ends file sharing.\nNo terminal to ask on. Use --yes.\nNot stopped.\n" in out
      and changes() == [], out)
rc, out = station("--yes", "stop", "network")
check("stop network runs backwards", changes() == ["systemctl --user stop sync.service", "docker stop web"],
      "\n".join(changes()))
states(containers={"web": "exited"})
rc, out = station("stop", "all")
check("all never touches the network group", all("web" not in c and "sync" not in c for c in changes()),
      "\n".join(changes()))

states(containers={"web": "running"}, daemon=False)
for marker in (OFF, STOP):
    if os.path.exists(marker):
        os.unlink(marker)
rc, out = station("stop", "web")
check("with docker not answering nothing is changed",
      rc == 1 and out == "Docker is not answering.\n" and not os.path.exists(STOP), out)

# ---- No settings file again: the defaults come back
no_settings()
states()
rc, out = station("status")
check("a missing settings file falls back to the defaults",
      out == "Station:\nRadio service: running since 08:15.\nxara: stopped.\nAPRS: failed.\nAPRS: off at boot.\n", out)

shutil.rmtree(tmp, ignore_errors=True)
print(f"{passed} passed, {failed} failed.")
sys.exit(1 if failed else 0)
