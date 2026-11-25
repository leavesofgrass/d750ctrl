"""d750d-test: the daemon's rules for what a line may hold, through its own two ports, against the pretend radio.

The pretend radio (the Sim class of tests/d750-sim.py) runs in this process on a pseudo terminal, and
records every line it receives. d750d.py runs as a child with D750_PORT set to that pseudo terminal and
with two ports this test picked; both are asserted before it starts, so it never opens a real radio port
or a station port. Each refused line is checked to have reached the pretend radio not at all, locked and
unlocked; T keys only with 1 to 3, and only unlocked; lock and every unkey send RX and check the answer.
Then the other way: what the programs here send in ordinary use still passes. Last, the verbs' dry runs
send nothing. Nothing transmits: the radio is pretend.

Run: python3 -I tests/d750d-test.py   (-f stops at the first failure). Needs pyserial and bash.
GPL-2.0-or-later.
"""

import importlib.util
import os
import pty
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
TOP = os.path.dirname(HERE)
D750D = os.path.join(TOP, "d750d.py")
D750 = os.path.join(TOP, "d750")
# Never used by a daemon this test starts: the station's own ports and the test bed's.
STATION_PORTS = set(range(4532, 4544)) | {4552, 4553, 8001, 8300, 8301}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sim_mod = load("d750_sim", os.path.join(HERE, "d750-sim.py"))
fake = load("fakedaemon", os.path.join(HERE, "fakedaemon.py"))
probe = load("d750_probe", os.path.join(TOP, "probe.py"))

# Lines the command port refuses, whatever the lock. The fault probe's cases first.
LONG = b"FQ 0," + b"0" * 596  # 600 characters, each one allowed
CMD_REFUSED = [
    b"ID\rTX", b"ID;TX", b"TX0", b"TX1", b"TX,1", b"TX;", b"\x00TX", b"0M", LONG, b"UNLOCK", b"unlock now",
    b"TX", b"tx", b" Tx ", b"TX 1", b"\tTX", b"\x1cTX", b"\xe9TX", b"FQ 0\rTX", b"id\rtx", b"ID\rBE", b"ID \r TX",
    b"ID\r\rTX", b"BE", b"be", b"SR", b"RX", b"UP", b"DW", b"PS", b"0G", b" 0M", b"9", b"LOCK", b"Lock", b"lock please",
    b" lock", b"lock ", b"STATE", b"Quit", b"reconnect now", b"unlock;", b"FQ 0_", b"FQ 0\\", b"FQ\x7f0",
]
# Lines the command port refuses only while locked: they arm the radio to send by itself.
LOCKED_REFUSED = [b"VX 1", b"VX 2", b"VX 00", b"VX1", b"TN 1,1", b"TN 2,1", b"TN 2", b"TN 1,0", b"TN x", b"PT 1", b"PT 0"]
# Reads of the same commands, and TNC off: they pass while locked.
LOCKED_PASSED = [b"VX", b"VX 0", b"TN", b"TN 0,1", b"TN 0", b"PT"]
# Lines the rigctl port refuses, whatever the lock: the fault probe's cases first.
RIG_REFUSED = [
    b"T 00", b"T 0.0", b"T off", b"T -0", b"T 1 x", b"\\set_ptt 00", b"F inf", b"F nan", b"F -inf", b"F 1e999",
    b"L RFPOWER inf", b"L SQL nan", b"T 4", b"T", b"T +1", b"\\set_ptt", b"T 1\x00", b"T\t1", b"f\rT 1", b"T 1\r\r",
    b"t\x0bT 1", b"T 1\xe9", b"T " + b"1" * 600,
    b"L SQL 1e308", b"L SQL -1e308", b"F 1e308", b"F 1e10", b"F -1", b"+L SQL 1e308",
]
# What hamlib's NET rigctl client and the programs here send to the rigctl port.
RIG_PASSED = [
    b"\\chk_vfo", b"\\dump_state", b"\\get_powerstat", b"\\get_lock_mode", b"\\set_lock_mode 0", b"f", b"F 146520000",
    b"F 146520000.000000", b"m", b"M FMN 0", b"M FM 0", b"v", b"V VFOB", b"s", b"t", b"l RFPOWER", b"L RFPOWER 0.5",
    b"l SQL", b"L SQL 0.333333", b"l STRENGTH", b"l RAWSTR", b"\\get_vfo_info VFOB", b"+f", b"+\\get_freq", b";f",
    b"|f", b"\\get_info", b"T 0", b"\\set_ptt 0", b"F 144390000",
]
# What the screen sends when it sets a row, and the APRS daemon's TNC reset, in ordinary use.
SCREEN_SETS = [
    b"BC 1,1", b"BC 0,1", b"MD 0,1", b"MD 0,0", b"PC 0,2", b"PC 0,0", b"VM 0,0", b"GP 1,0", b"TN 2,1", b"TN 0,1",
    b"FQ 0,0146520000", b"FQ 0,0147040000", b"SQ 1,3", b"MR 0,001", b"VM 0,0", b"RT 261124120000", b"ME 000",
    b"ME 001", b"FO 0", b"VX 0",
]
APRS_LINES = [b"TN 0,1", b"TN 2,1"]
ME_LINES = [
    b"ME 000,0146520000,0000000000,2,2,0,0,0,0,0,0,0,0,0,0,08,08,000,0,CQCQCQ,0,00,0",
    b"ME 001,0144390000,0000000000,2,2,0,0,0,0,0,0,0,0,0,0,08,08,000,0,CQCQCQ,0,00,0",
]


def wait_until(check, limit=5.0, step=0.02):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(step)
    return bool(check())


def pick_port():
    """A free port the system gives, never a station port."""
    while True:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        if port not in STATION_PORTS:
            return port


class Client:
    """One connection to a port of the test daemon; one line out, one answer line back."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.file = self.sock.makefile("rb")

    def ask(self, data):
        self.sock.sendall(data + b"\n")
        return self.file.readline().decode(errors="replace").strip()

    def ask_all(self, data, quiet=0.3):
        """Every line of an answer of many lines: read until the daemon has said nothing for quiet seconds."""
        self.sock.sendall(data + b"\n")
        self.sock.settimeout(quiet)
        got = b""
        try:
            while True:
                piece = self.sock.recv(4096)
                if not piece:
                    break
                got += piece
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(5)
        return got.decode(errors="replace")

    def close(self):
        self.file.close()
        self.sock.close()


class Bed:
    """The pretend radio in this process, and d750d against it on two ports this test picked. prepare, when
    given, is done to the pretend radio before the daemon starts; script is the daemon to run, d750d.py or a
    copy of it with a window widened."""

    def __init__(self, prepare=None, script=D750D):
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)
        self.sim = sim_mod.Sim()
        self.sim.flicker = False
        if prepare is not None:
            prepare(self.sim)
        self.stop = threading.Event()
        threading.Thread(target=sim_mod.serve, args=(self.master, self.sim), kwargs={"stop": self.stop},
                         daemon=True).start()
        self.tmp = tempfile.mkdtemp(prefix="d750d-test.")
        self.log_dir = os.path.join(self.tmp, "log")
        self.cmd_port = pick_port()
        self.ptt_port = pick_port()
        while self.ptt_port == self.cmd_port:
            self.ptt_port = pick_port()
        env = dict(os.environ, D750_PORT=self.path, D750_CMD_PORT=str(self.cmd_port),
                   D750_PTT_PORT=str(self.ptt_port), D750_LOG_DIR=self.log_dir, HOME=self.tmp)
        env.pop("D750_LOG_ALL", None)
        # Before the daemon starts: the radio is the pretend one, and the ports are the ones picked here.
        assert self.path.startswith("/dev/pts/") and env["D750_PORT"] == self.path, env["D750_PORT"]
        for port in (env["D750_CMD_PORT"], env["D750_PTT_PORT"]):
            assert int(port) not in STATION_PORTS and int(port) > 0, port
        self.out = open(os.path.join(self.tmp, "d750d.out"), "w", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "-I", script], env=env, stdout=self.out,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        ok = wait_until(lambda: self._listening(self.cmd_port) and self._listening(self.ptt_port), 15, 0.1)
        assert ok, "the test daemon did not start listening"
        assert wait_until(lambda: b"RX" in self.sim.received, 5), "the test daemon did not unkey at start"

    @staticmethod
    def _listening(port):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            return False

    def end(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(10)
        self.out.close()
        self.stop.set()

    def mark(self):
        return len(self.sim.received)

    def since(self, mark, settle=0.25):
        time.sleep(settle)
        return list(self.sim.received[mark:])

    def cmd(self, data):
        c = Client(self.cmd_port)
        try:
            return c.ask(data)
        finally:
            c.close()

    def state(self):
        return self.cmd(b"state")

    def set_locked(self, locked):
        answer = self.cmd(b"lock" if locked else b"unlock")
        assert answer.startswith("OK"), answer
        assert ("; locked;" if locked else "; unlocked;") in self.state()

    def log(self):
        path = os.path.join(self.log_dir, time.strftime("d750d-%Y-%m-%d.txt"))
        with open(path, encoding="utf-8") as f:
            return f.read()


bed = None


def setUpModule():
    global bed
    bed = Bed()


def tearDownModule():
    if bed is not None:
        bed.end()


class Refused(unittest.TestCase):
    """Refused lines reach the pretend radio not at all, locked and unlocked, and change nothing."""

    def tearDown(self):
        bed.sim.answer_n.clear()
        bed.set_locked(False)

    def check_nothing_reached(self, line, locked, mark, answer):
        state = bed.state()
        self.assertEqual(bed.since(mark), [], f"{line!r}, locked {locked}: the radio was sent something")
        self.assertFalse(bed.sim.keyed, f"{line!r}, locked {locked}: the pretend radio is keyed")
        self.assertIn("; not keyed;", state, f"{line!r}, locked {locked}")
        self.assertIn("; locked;" if locked else "; unlocked;", state, f"{line!r} changed the lock")

    def test_command_port(self):
        for locked in (True, False):
            bed.set_locked(locked)
            for line in CMD_REFUSED:
                mark = bed.mark()
                answer = bed.cmd(line)
                self.assertTrue(answer.startswith("ERR "), f"{line!r}, locked {locked}: answer {answer!r}")
                self.check_nothing_reached(line, locked, mark, answer)

    def test_command_port_words(self):
        self.assertEqual(bed.cmd(b"ID\rTX"), "ERR only plain letters, digits, spaces and , . - / + are allowed")
        self.assertEqual(bed.cmd(b"0M"), "ERR a line may not start with a digit")
        self.assertEqual(bed.cmd(LONG), "ERR the line is longer than 512 characters")
        self.assertEqual(bed.cmd(b"UNLOCK"), "ERR say the word alone, in small letters")
        self.assertEqual(bed.cmd(b"TX,1"), "ERR TX is not allowed on this port")
        self.assertEqual(bed.cmd(b" Tx "), "ERR TX is not allowed on this port")

    def test_line_limit(self):
        """512 characters pass; 513 are refused, and the rest of a long line is dropped, not read as lines."""
        c = Client(bed.cmd_port)
        try:
            mark = bed.mark()
            ok = b"FQ 0," + b"0" * 507
            self.assertEqual(len(ok), 512)
            self.assertNotEqual(c.ask(ok), "ERR the line is longer than 512 characters")
            self.assertEqual(bed.since(mark), [ok])
            mark = bed.mark()
            self.assertEqual(c.ask(ok + b"0"), "ERR the line is longer than 512 characters")
            self.assertEqual(c.ask(b"ID\r" + b"TX " * 3000), "ERR the line is longer than 512 characters")
            self.assertEqual(c.ask(b"ID"), "ID TM-D750", "the client was not kept after a long line")
            self.assertEqual(bed.since(mark), [b"ID"])
        finally:
            c.close()

    def test_client_kept(self):
        c = Client(bed.cmd_port)
        try:
            self.assertTrue(c.ask(b"ID\rTX").startswith("ERR"))
            self.assertEqual(c.ask(b"ID"), "ID TM-D750")
        finally:
            c.close()

    def test_locked_only(self):
        bed.set_locked(True)
        for line in LOCKED_REFUSED:
            mark = bed.mark()
            answer = bed.cmd(line)
            self.assertEqual(answer, f"ERR {line[:2].decode()} is refused while PTT is locked", line)
            self.check_nothing_reached(line, True, mark, answer)
        for line in LOCKED_PASSED:
            mark = bed.mark()
            answer = bed.cmd(line)
            self.assertFalse(answer.startswith("ERR"), f"{line!r}: {answer!r}")
            self.assertEqual(bed.since(mark), [line])
        bed.set_locked(False)
        for line in LOCKED_REFUSED:
            mark = bed.mark()
            answer = bed.cmd(line)
            self.assertFalse(answer.startswith("ERR"), f"{line!r} unlocked: {answer!r}")
            self.assertEqual(bed.since(mark), [line])
        for line in (b"VX 0", b"TN 2,1"):
            bed.cmd(line)

    def test_rigctl_port(self):
        for locked in (True, False):
            bed.set_locked(locked)
            c = Client(bed.ptt_port)
            try:
                for line in RIG_REFUSED:
                    mark = bed.mark()
                    answer = c.ask(line)
                    if line.startswith(b"+"):  # the extended answer: the command's name, then the error
                        self.assertEqual(c.file.readline().decode().strip(), "RPRT -1", f"{line!r} after {answer!r}")
                    else:
                        self.assertEqual(answer, "RPRT -1", f"{line!r}, locked {locked}")
                    self.check_nothing_reached(line, locked, mark, answer)
                self.assertEqual(c.ask(b"t"), "0", "the rigctl client was not kept")
            finally:
                c.close()

    def test_fake_daemon_follows(self):
        """tests/fakedaemon.py answers every refused line as d750d does."""
        for locked in (True, False):
            bed.set_locked(locked)
            for line in CMD_REFUSED + (LOCKED_REFUSED if locked else []):
                f = fake.FakeDaemon()
                f.locked = locked
                self.assertEqual(f.command(line.decode("latin-1")), bed.cmd(line), f"{line!r}, locked {locked}")
                self.assertEqual(f.locked, locked)


class Keying(unittest.TestCase):
    """T keys only with 1 to 3 and only unlocked; lock and every unkey send RX and check the answer."""

    def tearDown(self):
        bed.sim.answer_n.clear()
        bed.set_locked(True)  # RX, checked
        bed.set_locked(False)

    def test_t_values(self):
        bed.set_locked(False)
        c = Client(bed.ptt_port)
        try:
            for v in (b"1", b"2", b"3"):
                mark = bed.mark()
                self.assertEqual(c.ask(b"T " + v), "RPRT 0")
                self.assertEqual(bed.since(mark), [b"TX"], v)
                self.assertTrue(bed.sim.keyed, v)
                self.assertIn("; keyed;", bed.state())
                mark = bed.mark()
                self.assertEqual(c.ask(b"T 0"), "RPRT 0")
                self.assertEqual(bed.since(mark), [b"RX"], v)
                self.assertFalse(bed.sim.keyed, v)
            bed.set_locked(True)
            for v in (b"1", b"2", b"3"):
                mark = bed.mark()
                self.assertEqual(c.ask(b"T " + v), "RPRT -1")
                self.assertEqual(bed.since(mark), [], v)
                self.assertFalse(bed.sim.keyed, v)
        finally:
            c.close()

    def test_t0_not_confirmed_stays_keyed(self):
        bed.set_locked(False)
        c = Client(bed.ptt_port)
        try:
            self.assertEqual(c.ask(b"T 1"), "RPRT 0")
            bed.sim.answer_n.add("RX")
            mark = bed.mark()
            self.assertEqual(c.ask(b"T 0"), "RPRT 0")
            self.assertEqual(bed.since(mark), [b"RX"])
            self.assertTrue(bed.sim.keyed)
            self.assertIn("; keyed;", bed.state(), "a T 0 the radio did not confirm was believed")
            self.assertEqual(c.ask(b"t"), "1")
            bed.sim.answer_n.clear()
            self.assertEqual(c.ask(b"T 0"), "RPRT 0")
            self.assertIn("; not keyed;", bed.state())
            self.assertFalse(bed.sim.keyed)
        finally:
            c.close()

    def test_lock_unkeys(self):
        bed.set_locked(False)
        c = Client(bed.ptt_port)
        try:
            self.assertEqual(c.ask(b"T 1"), "RPRT 0")
            self.assertTrue(bed.sim.keyed)
            mark = bed.mark()
            self.assertEqual(bed.cmd(b"lock"), "OK locked, PTT refused until unlock")
            self.assertEqual(bed.since(mark), [b"RX"])
            self.assertFalse(bed.sim.keyed)
            state = bed.state()
            self.assertIn("; not keyed;", state)
            self.assertIn("; locked;", state)
        finally:
            c.close()

    def test_lock_sends_rx_when_not_keyed(self):
        bed.set_locked(False)
        mark = bed.mark()
        self.assertEqual(bed.cmd(b"lock"), "OK locked, PTT refused until unlock")
        self.assertEqual(bed.since(mark), [b"RX"])

    def test_lock_not_confirmed(self):
        bed.set_locked(False)
        bed.sim.answer_n.add("RX")
        mark = bed.mark()
        self.assertEqual(bed.cmd(b"lock"), "OK locked; the radio did not say it is receiving")
        self.assertEqual(bed.since(mark), [b"RX"])
        self.assertIn("; locked;", bed.state())
        self.assertIn("lock: locked, but the radio did not say it is receiving", bed.log())

    def test_unkey_not_confirmed_stays_keyed(self):
        bed.set_locked(False)
        before = bed.log().count("unkey: ptt client disconnected")
        c = Client(bed.ptt_port)
        self.assertEqual(c.ask(b"T 1"), "RPRT 0")
        bed.sim.answer_n.add("RX")
        mark = bed.mark()
        c.close()
        self.assertTrue(wait_until(lambda: b"RX" in bed.sim.received[mark:], 5), "no RX when the client dropped")
        time.sleep(0.2)
        self.assertIn("; keyed;", bed.state(), "an unkey the radio did not confirm was believed")
        log = bed.log()
        self.assertEqual(log.count("unkey: ptt client disconnected"), before + 1)
        self.assertIn("unkey not confirmed (ptt client disconnected): the radio did not say it is receiving", log)
        bed.sim.answer_n.clear()
        self.assertEqual(bed.cmd(b"lock"), "OK locked, PTT refused until unlock")
        self.assertIn("; not keyed;", bed.state())
        self.assertFalse(bed.sim.keyed)

    def test_unkey_on_drop_when_not_keyed(self):
        bed.set_locked(False)
        before = bed.log().count("unkey:")
        c = Client(bed.ptt_port)
        self.assertEqual(c.ask(b"t"), "0")
        mark = bed.mark()
        c.close()
        self.assertTrue(wait_until(lambda: b"RX" in bed.sim.received[mark:], 5), "no RX when the client dropped")
        time.sleep(0.2)
        self.assertEqual(bed.log().count("unkey:"), before, "unkey logged when the radio was not keyed")


def widened_copy():
    """A copy of d750d.py with 0.3 s added between each lock check and its command, as the safety review did:
    in ptt() right after the check that refuses PTT while locked, at that check's own level; on the command port
    right before a line goes to the radio. Held under the serial lock, as it must be, the window cannot be raced;
    a check outside it loses the race."""
    with open(D750D, encoding="utf-8") as f:
        lines = f.read().split("\n")

    def indent(line):
        return line[: len(line) - len(line.lstrip(" "))]

    def where(text):
        found = [i for i, line in enumerate(lines) if text in line]
        assert len(found) == 1, f"the place to widen the window, {text!r}, is in d750d.py {len(found)} times"
        return found[0]

    i = where('raise OSError("locked: PTT refused")')
    lines.insert(i + 1, indent(lines[i - 1]) + "if on: time.sleep(0.3)  # the test widens the window")
    i = where("reply = radio.command(line)")
    lines.insert(i, indent(lines[i]) + 'if line == "VX 1": time.sleep(0.3)  # the test widens the window')
    path = os.path.join(tempfile.mkdtemp(prefix="d750d-widened."), "d750d.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


class Race(unittest.TestCase):
    """A lock and a keying command cannot race, with the window widened: nothing keys or arms the radio after
    the lock's RX, and the state never reads keyed and locked together."""

    @classmethod
    def setUpClass(cls):
        cls.bed = Bed(script=widened_copy())

    @classmethod
    def tearDownClass(cls):
        cls.bed.end()

    def race(self, send, after):
        b = self.bed
        states, done = [], threading.Event()

        def poll():
            while not done.is_set():
                states.append(b.state())
                time.sleep(0.02)

        b.set_locked(False)
        mark = b.mark()
        res = {}
        poller = threading.Thread(target=poll)
        poller.start()
        sender = threading.Thread(target=lambda: res.setdefault("sent", send()))
        sender.start()
        time.sleep(0.1)
        res["lock"] = b.cmd(b"lock")
        sender.join(5)
        time.sleep(0.2)
        done.set()
        poller.join(5)
        got = b.since(mark)
        self.assertTrue(res["lock"].startswith("OK locked"), res)
        self.assertIn(b"RX", got, got)
        rx = got.index(b"RX")
        self.assertNotIn(after, got[rx:], f"{after!r} reached the radio after the lock's RX: {got}; {res}")
        both = [s for s in states if "; keyed;" in s and "; locked;" in s]
        self.assertEqual(both, [], "the state read keyed and locked together")
        return res

    def test_lock_against_t1(self):
        c = Client(self.bed.ptt_port)
        try:
            self.race(lambda: c.ask(b"T 1"), b"TX")
            self.assertFalse(self.bed.sim.keyed, "the radio is keyed after lock")
            self.assertIn("; not keyed;", self.bed.state())
        finally:
            c.close()

    def test_lock_against_vx(self):
        try:
            self.race(lambda: self.bed.cmd(b"VX 1"), b"VX 1")
        finally:
            self.bed.set_locked(False)
            self.bed.cmd(b"VX 0")


class StartUp(unittest.TestCase):
    """The radio keyed before the daemon starts, and its first RX answered N: the daemon believes it keyed
    and tries again until the radio says RX."""

    def test_startup_unkey_retried(self):
        def keyed_and_deaf(sim):
            sim.keyed = True
            sim.answer_n.add("RX")
        b = Bed(prepare=keyed_and_deaf)
        try:
            mark = b.mark()  # after the start-up RX; nothing connects to the rigctl port from here, so no drop sends RX
            time.sleep(2.5)
            tries = [g for g in b.sim.received[mark:] if g == b"RX"]
            self.assertGreaterEqual(len(tries), 2, "the start-up unkey was not tried again")
            self.assertIn("; keyed;", b.state(), "an unkey the radio did not confirm was believed at start")
            self.assertTrue(b.sim.keyed)
            b.sim.answer_n.clear()
            self.assertTrue(wait_until(lambda: not b.sim.keyed, 5), "the watchdog did not unkey the radio")
            self.assertTrue(wait_until(lambda: "; not keyed;" in b.state(), 3))
        finally:
            b.end()


class Ordinary(unittest.TestCase):
    """What the programs here send in ordinary use still passes, and reaches the radio as it was sent."""

    def tearDown(self):
        bed.set_locked(False)

    def passes(self, line, locked=False):
        mark = bed.mark()
        answer = bed.cmd(line)
        self.assertFalse(answer.startswith("ERR"), f"{line!r}, locked {locked}: {answer!r}")
        self.assertEqual(bed.since(mark, 0.1), [line.strip(b" ")], f"{line!r}, locked {locked}")
        return answer

    def test_daemon_words(self):
        for word in (b"state", b"lock", b"state", b"unlock", b"reconnect", b"state"):
            answer = bed.cmd(word)
            self.assertFalse(answer.startswith("ERR"), f"{word!r}: {answer!r}")
        c = Client(bed.cmd_port)
        try:
            c.sock.sendall(b"quit\n")
            self.assertEqual(c.file.readline(), b"", "quit did not close the connection")
        finally:
            c.close()

    def screen_lines(self):
        """Every line the screen's model sends to the command port while it starts, sweeps, locks and unlocks."""
        r = fake.Runner()
        r.model.size(80, 24)
        r.tick(3.0)
        r.press("L")
        r.tick(2.0)
        r.press("L")
        r.press("y")
        r.tick(2.0)
        lines = []
        for line in r.daemon.lines:
            if line not in lines:
                lines.append(line)
        return lines

    def test_screen(self):
        lines = self.screen_lines()
        self.assertIn("state", lines)
        self.assertIn("lock", lines)
        for line in lines:
            data = line.encode("ascii")
            if line in fake.DAEMON_WORDS:
                self.assertFalse(bed.cmd(data).startswith("ERR"), line)
            else:
                self.passes(data)
        bed.set_locked(True)
        for line in fake.Runner(start=False).model._sweep_lines():  # the sweep goes on while locked
            if line not in fake.DAEMON_WORDS:
                self.passes(line.encode("ascii"), True)
        bed.set_locked(False)
        for line in SCREEN_SETS:
            self.passes(line)

    def test_aprs_daemon_and_station(self):
        for line in APRS_LINES + [b"ID"]:
            self.passes(line)
        self.assertFalse(bed.cmd(b"state").startswith("ERR"))

    def test_probe(self):
        for cmd, (_meaning, args) in probe.MEANINGS.items():
            for arg in [""] + args:
                self.passes(f"{cmd} {arg}".strip().encode("ascii"))

    def test_rigctl(self):
        c = Client(bed.ptt_port)
        try:
            for line in RIG_PASSED:
                answer = c.ask_all(line)
                self.assertTrue(answer, f"{line!r}: no answer")
                self.assertNotIn("RPRT -", answer, f"{line!r}: {answer!r}")
                if line == b"\\dump_state":
                    self.assertTrue(answer.endswith("done\n"), answer[-40:])
        finally:
            c.close()

    def verb(self, *args, conf=None):
        conf = conf or os.path.join(bed.tmp, "conf")
        os.makedirs(conf, exist_ok=True)
        env = dict(os.environ, HOME=bed.tmp, D750_CONF_DIR=conf, D750_CMD_PORT=str(bed.cmd_port),
                   D750_PTT_PORT=str(bed.ptt_port), D750_LOG_DIR=bed.log_dir)
        return subprocess.run(["bash", D750, *args], env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)

    def test_memory_import_with_crlf(self):
        path = os.path.join(bed.tmp, "mem-crlf.txt")
        with open(path, "wb") as f:
            f.write(b"# TM-D750 memory channels, written with CRLF line ends\r\n" + b"".join(m + b"\r\n" for m in ME_LINES))
        mark = bed.mark()
        done = self.verb("mem", "import", path)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("2 channels written, 0 refused", done.stdout)
        self.assertEqual(bed.since(mark), ME_LINES)

    def test_verbs(self):
        for args in (["state"], ["status"], ["raw", "ID"], ["freq", "A", "146.520"], ["band", "A"], ["band", "B"],
                     ["mode", "A", "nfm"], ["mode", "A", "fm"], ["squelch", "B", "4"], ["squelch", "B", "3"],
                     ["power", "A", "low"], ["busy", "B"], ["tnc", "off"], ["tnc", "kiss", "B"], ["mem", "list", "0", "3"],
                     ["mem", "show", "0"], ["mem", "goto", "A", "1"], ["gps"], ["vox"], ["vox", "on"], ["vox", "off"],
                     ["clock"], ["clock", "set"], ["lock"], ["unlock"], ["ptt", "off"]):
            done = self.verb(*args)
            self.assertEqual(done.returncode, 0, f"d750 {' '.join(args)}: {done.stdout}{done.stderr}")
            self.assertNotIn("ERR", done.stdout + done.stderr, f"d750 {' '.join(args)}")


class Listener:
    """Two ports this test picked, standing in for the daemon: counts connections, answers each line with answer."""

    def __init__(self, answer):
        self.answer = answer
        self.connections = 0
        self.lines = []
        self.socks = []
        self.ports = []
        for _ in range(2):
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            assert s.getsockname()[1] not in STATION_PORTS
            s.listen(4)
            self.socks.append(s)
            self.ports.append(s.getsockname()[1])
            threading.Thread(target=self._accept, args=(s,), daemon=True).start()

    def _accept(self, s):
        while True:
            try:
                c, _ = s.accept()
            except OSError:
                return
            self.connections += 1
            with c:
                line = c.makefile("rb").readline()
                self.lines.append(line)
                c.sendall(self.answer + b"\n")

    def close(self):
        for s in self.socks:
            s.close()


class Verbs(unittest.TestCase):
    """d750 -n lock, unlock, ptt off and raw send nothing; lock and unlock exit 1 on an ERR answer."""

    def run_verb(self, listener, *args):
        conf = os.path.join(bed.tmp, "conf-verbs")
        os.makedirs(conf, exist_ok=True)
        env = dict(os.environ, HOME=bed.tmp, D750_CONF_DIR=conf, D750_CMD_PORT=str(listener.ports[0]),
                   D750_PTT_PORT=str(listener.ports[1]), D750_LOG_DIR=bed.log_dir)
        return subprocess.run(["bash", D750, *args], env=env, capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)

    def test_dry_runs_send_nothing(self):
        listener = Listener(b"OK")
        try:
            for args, said in ((["-n", "lock"], "lock"), (["unlock", "-n"], "unlock"), (["-n", "ptt", "off"], "T 0"),
                               (["-n", "raw", "ID"], "ID"), (["-n", "raw", "FQ", "0"], "FQ 0")):
                done = self.run_verb(listener, *args)
                self.assertEqual(done.returncode, 0, f"{args}: {done.stdout}{done.stderr}")
                self.assertEqual(done.stderr, f"would send: {said}\n", args)
                self.assertEqual(done.stdout, "", args)
            time.sleep(0.3)
            self.assertEqual(listener.connections, 0, f"a dry run sent {listener.lines}")
        finally:
            listener.close()

    def test_lock_and_unlock_fail_on_err(self):
        listener = Listener(b"ERR a refusal from the test")
        try:
            for verb in ("lock", "unlock"):
                done = self.run_verb(listener, verb)
                self.assertEqual(done.returncode, 1, verb)
                self.assertEqual(done.stdout, "ERR a refusal from the test\n", verb)
        finally:
            listener.close()

    def test_lock_and_unlock_pass_on_ok(self):
        listener = Listener(b"OK locked; the radio did not say it is receiving")
        try:
            done = self.run_verb(listener, "lock")
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stdout, "OK locked; the radio did not say it is receiving\n")
            self.assertEqual(listener.lines, [b"lock\n"])
        finally:
            listener.close()


if __name__ == "__main__":
    unittest.main()
