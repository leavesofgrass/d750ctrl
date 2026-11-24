"""Output rules for d750: every line a verb prints, checked against the project's written rules.

Run: python3 -I tests/output-rules-test.py, with the test bed running first (tests/test-env.sh: the
simulator and a second d750d on ports 4542 and 4543). It runs a fixed list of d750 verbs, using the d750
one folder up, never the one on the PATH, with a settings folder of its own, exactly as tests.sh does.
It never keys:
the only PTT word it sends is ptt off, VarAC frames only as dry runs, and it puts back every value it
changes on the pretend radio. One line per verb run, Pass or Fail, then the count.
Written Tuesday, November 17, 2026.
"""

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
TOP = os.path.dirname(HERE)
D750 = os.path.join(TOP, "d750")
HOST, PTT_PORT, CMD_PORT = "127.0.0.1", 4542, 4543
LIMIT = 80
# The project's words for a line that says something went wrong: d750's Fail: and usage:, the daemon's
# ERR, and d750's answer to a verb it does not know.
FAIL_WORDS = ("Fail:", "usage:", "ERR", "unknown verb:")
# Lines known to be longer than LIMIT, left as they are on purpose: other programs may read them, and
# the owner tuned them. Each is printed as a note, not a failure. (verb, start of the line, why)
KNOWN_LONG = [
    ("status", "daemon: ", "the daemon's state line, as d750d words it"),
    ("state", "port ", "the daemon's own state line"),
    ("doctor", "Pass: daemon: ", "the same state line inside doctor"),
    ("fixup", "note: no bluetooth address in ", "names the settings file, and its path can be long"),
    ("log", "", "the daemon's log lines, shown as d750d wrote them"),
]
# Kenwood commands that key or move the radio; d750d refuses them on the command port, and so does this test.
UNSAFE = {"TX", "RX", "UP", "DW", "SR", "PS", "0M", "0G"}


def bed_running():
    for port in (PTT_PORT, CMD_PORT):
        try:
            socket.create_connection((HOST, port), timeout=2).close()
        except OSError:
            return False
    return True


def ask(line):
    """One line to the test daemon's command port, its answer back."""
    with socket.create_connection((HOST, CMD_PORT), timeout=8) as s:
        s.sendall(line.encode("ascii") + b"\n")
        return s.makefile("rb").readline().decode(errors="replace").strip()


def guard(args):
    """Refuse, before anything runs, a command that could key the radio or touch xara."""
    words = [a.lower() for a in args if a != "-n"]
    dry = "-n" in args
    ok = True
    if words[:1] == ["ptt"] and words[1:] != ["off"]:
        ok = False
    if words[:1] == ["vara"] and not (words[1:] in (["cq"], ["beacon"]) and dry):
        ok = False
    if words[:1] == ["raw"] and (len(words) < 2 or words[1].split()[0].upper() in UNSAFE):
        ok = False
    if words[:1] in (["level"], ["record"], ["probe"]):
        ok = False
    if not ok:
        raise SystemExit("Fail: this test refuses to run: d750 " + " ".join(args))


def split_lines(data):
    text = data.decode("ascii", errors="replace")
    out = text.split("\n")
    return out[:-1] if out and out[-1] == "" else out


class Run:
    def __init__(self, args, rc, out, err, want_rc=(0,)):
        self.args, self.rc, self.out, self.err, self.want_rc = list(args), rc, out, err, want_rc
        self.name = " ".join(self.args)
        self.verb = next((a for a in self.args if a != "-n"), "")
        self.out_lines, self.err_lines = split_lines(out), split_lines(err)
        self.changed = []           # reads that differ after a run that must change nothing


def d750(args, want_rc=(0,)):
    guard(args)
    try:
        p = subprocess.run(["bash", D750, *args], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        return Run(args, p.returncode, p.stdout, p.stderr, want_rc)
    except subprocess.TimeoutExpired:
        return Run(args, None, b"", b"", want_rc)


# The rules. Each takes a Run and returns (problems, notes); no problems is a pass.

def plain_text(run):
    """printable ASCII and newlines only; no tabs, no trailing spaces"""
    bad = []
    for stream, data, lines in (("output", run.out, run.out_lines), ("errors", run.err, run.err_lines)):
        odd = [c for c in data if c != 10 and not 32 <= c < 127]
        if odd:
            bad.append(f"byte 0x{odd[0]:02x} in its {stream}")
        trailing = [n for n, line in enumerate(lines, 1) if line != line.rstrip(" ")]
        if trailing:
            bad.append(f"trailing space, {stream} line {trailing[0]}")
    return bad, []


def known_long(run, line):
    for verb, start, _why in KNOWN_LONG:
        if run.verb == verb and line.startswith(start):
            return True
    return False


def line_length(run):
    """no line longer than 80 characters, but KNOWN_LONG"""
    bad, notes = [], []
    for stream, lines in (("output", run.out_lines), ("errors", run.err_lines)):
        for n, line in enumerate(lines, 1):
            if len(line) <= LIMIT:
                continue
            if known_long(run, line):
                note = f"note: d750 {run.verb}: a known long line, {len(line)} characters"
                if note not in notes:
                    notes.append(note)
            else:
                bad.append(f"{stream} line {n} is {len(line)} characters")
    return bad, notes


def exit_code(run):
    """0 when it works, 1 for a refusal, 2 for usage"""
    if run.rc is None:
        return ["no exit in 60 seconds"], []
    if run.rc not in run.want_rc:
        return [f"exit {run.rc}, wanted {' or '.join(map(str, run.want_rc))}"], []
    return [], []


def failures_say_so(run):
    """a nonzero exit says why: Fail:, usage:, ERR, unknown verb:"""
    if not run.rc:
        return [], []
    # d750's fail and usage write to standard error, so the reason is the first line there. A verb whose
    # error output is empty (doctor, raw, an unknown verb) must say it on a line of its output.
    if run.err_lines:
        if not run.err_lines[0].startswith(FAIL_WORDS):
            return [f"its first error line does not say why: {run.err_lines[0][:70]!r}"], []
        return [], []
    if not any(line.startswith(FAIL_WORDS) for line in run.out_lines):
        return ["no line says why it failed"], []
    return [], []


def answer_first(run):
    """a verb that works prints a first line, not empty"""
    if run.rc != 0:
        return [], []
    lines = run.out_lines or run.err_lines
    if not lines:
        return ["printed nothing"], []
    if not lines[0].strip():
        return ["its first line is empty"], []
    return [], []


STATE_WORD = re.compile(r"\b(VOX|GPS(?! PC)|PC output):?\s+(\w+)")


def on_and_off(run):
    """VOX and GPS states are on or off, never 1, 0, true, false"""
    if run.verb not in ("vox", "gps"):
        return [], []
    bad = []
    for line in run.out_lines + run.err_lines:
        for m in STATE_WORD.finditer(line):
            if m.group(2) not in ("on", "off"):
                bad.append(f"{m.group(1)} said as {m.group(2)}")
    return bad, []


def dry_runs(run):
    """with -n: would send, and the radio is left as it was"""
    if "-n" not in run.args:
        return [], []
    bad = []
    lines = run.out_lines + run.err_lines
    if not any(line.startswith("would send") for line in lines):
        bad.append("no line starts with would send")
    done = [line for line in lines if line.startswith(("after:", "Fixed:", "radio clock set:"))]
    if done:
        bad.append(f"says it was done: {done[0][:30]}")
    bad += [f"changed {c}" for c in run.changed]
    return bad, []


RULES = [plain_text, line_length, exit_code, failures_say_so, answer_first, on_and_off, dry_runs]
passed = failed = 0


def judge(run):
    global passed, failed
    problems = []
    for rule in RULES:
        bad, notes = rule(run)
        for note in notes:
            print(note)
        problems += [f"{rule.__name__}: {b}" for b in bad]
    if problems:
        failed += 1
        for p in problems:
            print(f"Fail: d750 {run.name}: {p}")
    else:
        passed += 1
        print(f"Pass: d750 {run.name}")


def check(args, want_rc=(0,), keep=()):
    """Run one verb and judge it. keep: reads whose answers must be the same afterwards."""
    before = {r: ask(r) for r in keep}
    run = d750(args, want_rc)
    for r in keep:
        now = ask(r)
        if now != before[r]:
            run.changed.append(f"{r}: {before[r]} to {now}")
    judge(run)
    return run


def save(reads):
    return [(r, ask(r)) for r in reads]


def restore(saved):
    """Put values back with the radio's own answers, which are also its set commands: FQ 0,0147040000."""
    global failed
    for r, answer in saved:
        if answer.split(" ", 1)[0].upper() in UNSAFE or answer in ("", "N", "?") or answer.startswith("ERR"):
            continue
        ask(answer)
        now = ask(r)
        if now != answer:
            failed += 1
            print(f"Fail: could not put back {r}: {answer}, it is {now}")


def changer(reads, dry, real):
    """A verb that changes the radio: its dry runs, which must change nothing, then its real runs,
    then everything it read put back as it was."""
    saved = save(reads)
    try:
        for args in dry:
            check(args + ["-n"], keep=reads)
        for args in real:
            check(args)
    finally:
        restore(saved)


def main():
    if not bed_running():
        print("The test bed is not running on ports 4542 and 4543; start tests/test-env.sh first.")
        return 2
    tmp = tempfile.mkdtemp(prefix="d750-output-rules.")
    locked = False
    try:
        # The same surroundings as tests.sh: the test ports and log, a settings folder of our own.
        conf = os.path.join(tmp, "conf")
        os.makedirs(conf)
        with open(os.path.join(conf, "fixup.conf"), "w", encoding="ascii") as f:
            f.write("TNC=2,1\nSQUELCH_B=3\nGPS_OUTPUT=0\n")
        table = os.path.expanduser("~/.config/d750ctrl/commands.txt")
        if os.path.isfile(table):
            shutil.copy(table, conf)
        with open(os.path.join(conf, "d750ctrl.conf"), "w", encoding="ascii") as f:
            f.write("mycall = N0CALL-7\n")      # for the VarAC dry runs, as tests.sh does
        os.environ.update(D750_CMD_PORT=str(CMD_PORT), D750_PTT_PORT=str(PTT_PORT), D750_CONF_DIR=conf,
                          D750_LOG_DIR=os.path.expanduser("~/.local/share/d750ctrl/log/test"))

        for rule in RULES:
            print(f"Rule {rule.__name__}: {rule.__doc__}")

        # Reads.
        for args in (["help"], ["status"], ["state"], ["raw", "ID"], ["busy", "B"], ["watch", "B", "3"],
                     ["mem", "list", "0", "5"], ["mem", "show", "0"], ["gps"], ["vox"], ["clock"]):
            check(args)
        # Verbs that change the radio: dry runs first, then for real, then put back.
        changer(["FQ 0"], [["freq", "A", "146.555"]], [["freq", "A", "146.520"]])
        changer(["BC"], [["band", "A"]], [["band", "A"], ["band", "B"]])
        changer(["MD 0"], [["mode", "A", "am"]], [["mode", "A", "nfm"], ["mode", "A", "fm"]])
        changer(["SQ 1"], [["squelch", "B", "7"]], [["squelch", "B", "4"]])
        changer(["PC 0"], [["power", "A", "el"]], [["power", "A", "low"]])
        changer(["TN"], [["tnc", "aprs", "B"]], [["tnc", "off"], ["tnc", "kiss", "B"]])
        changer(["VM 0", "FQ 0"], [["mem", "goto", "A", "1"]], [["mem", "goto", "A", "1"]])
        changer(["GP"], [["gps", "output", "on"]], [["gps", "output", "off"]])
        changer(["VX"], [["vox", "on"]], [["vox", "on"], ["vox", "off"]])
        changer(["TN", "SQ 1", "GP"], [], [["fixup"]])
        # Dry runs only: the clock moves on its own, and a VarAC frame for real would transmit.
        check(["clock", "set", "-n"])
        check(["-n", "vara", "cq"], keep=["BC"])
        check(["-n", "vara", "beacon"], keep=["BC"])
        # Refusals and usage errors, which must change nothing either.
        check(["freq", "A", "27.000"], want_rc=(1,), keep=["FQ 0"])
        check(["squelch", "B", "12"], want_rc=(2,), keep=["SQ 1"])
        check(["nonsense"], want_rc=(2,))
        # The daemon's own words, and unkeying: their dry runs first, which send nothing.
        for args in (["-n", "lock"], ["-n", "unlock"], ["-n", "ptt", "off"], ["-n", "raw", "ID"]):
            check(args, keep=["BC"])
        locked = True
        check(["lock"])
        check(["unlock"])
        locked = False
        check(["ptt", "off"])
        check(["log", "12"])
        # doctor's exit follows the machine it runs on: 0 when every check passes, 1 when one fails.
        check(["doctor"], want_rc=(0, 1))
    finally:
        if locked:
            ask("unlock")
        if os.path.basename(tmp).startswith("d750-output-rules."):
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"{passed} passed, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
