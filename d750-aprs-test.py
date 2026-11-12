"""Offline tests for d750-aprs: KISS, AX.25, APRS parsing and the plain lines.

Run: python3 -I d750-aprs-test.py. Nothing here opens a port or transmits.
"""

import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("aprs", os.path.join(HERE, "d750-aprs.py"))
aprs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aprs)

passed = failed = 0


def check(name, got, want):
    global passed, failed
    if got == want:
        passed += 1
    else:
        failed += 1
        print(f"Fail: {name}\n  got:  {got!r}\n  want: {want!r}")


def near(a, b, tol=1e-4):
    return abs(a - b) < tol


# KISS: escaping both special bytes, and a frame split across reads.
data = bytes([0x01, 0xC0, 0x02, 0xDB, 0x03])
enc = aprs.kiss_encode(data)
check("kiss escapes", enc, bytes([0xC0, 0x00, 0x01, 0xDB, 0xDC, 0x02, 0xDB, 0xDD, 0x03, 0xC0]))
r = aprs.KissReader()
check("kiss split read, first half", r.feed(enc[:4]), [])
check("kiss split read, second half", r.feed(enc[4:]), [data])
check("kiss skips non-data frames", aprs.KissReader().feed(bytes([0xC0, 0x06, 0x01, 0xC0])), [])

# AX.25: a round trip with a path, and the repeated flag shown as *.
frame = aprs.ax25_encode("N0CALL-2", "APZ750", ["WIDE1-1", "WIDE2-1"], "=test")
src, dst, digis, info = aprs.ax25_decode(frame)
check("ax25 source", src, "N0CALL-2")
check("ax25 dest", dst, "APZ750")
check("ax25 path", [d for d, _ in digis], ["WIDE1-1", "WIDE2-1"])
check("ax25 info", info, "=test")
check("tnc2 text", aprs.tnc2(src, dst, [("W7DEN-3", True), ("WIDE2-1", False)], info), "N0CALL-2>APZ750,W7DEN-3*,WIDE2-1:=test")
check("ax25 rejects junk", aprs.ax25_decode(b"\x01\x02"), None)

# Uncompressed position, the APRS spec's own example.
p = aprs.parse("N0CALL", "APRS", "!4903.50N/07201.75W-Test 001234")
check("position type", p["type"], "position")
check("position lat", near(p["lat"], 49 + 3.50 / 60), True)
check("position lon", near(p["lon"], -(72 + 1.75 / 60)), True)
check("position symbol", p["symbol"], "/-")
check("position comment", p["comment"], "Test 001234")

# With a timestamp, course and speed, and altitude.
p = aprs.parse("N0CALL", "APRS", "@092345z4903.50N/07201.75W>088/036/A=001234 moving")
check("timestamped course", p["course"], 88)
check("timestamped speed", p["speed_kn"], 36)
check("altitude", p["alt_ft"], 1234)
check("altitude removed from comment", p["comment"], "moving")

# Compressed position, worked from the spec: 49.5 N, 72.75 W.
p = aprs.parse("N0CALL", "APRS", "=/5L!!<*e7> sT")
check("compressed lat", near(p["lat"], 49.5), True)
check("compressed lon", near(p["lon"], -72.75), True)
check("compressed symbol", p["symbol"], "/>")

# Mic-E: 41 43.25 N, 72 43.50 W, 20 knots, course 90, In Service.
p = aprs.parse("N0CALL-9", "T1TS2U", "`dGNn v>/hello")
check("mic-e type", p["type"], "position")
check("mic-e lat", near(p["lat"], 41 + 43.25 / 60), True)
check("mic-e lon", near(p["lon"], -(72 + 43.50 / 60)), True)
check("mic-e speed", p["speed_kn"], 20)
check("mic-e course", p["course"], 90)
check("mic-e symbol", p["symbol"], "/>")
check("mic-e status", p["status"], "In Service")
check("mic-e comment", p["comment"], "hello")

# Mic-E from a TH-D75: type code > and &, altitude after it, a carriage return at the end.
p = aprs.parse("N0CALL-7", "T1TS2U", "`dGNn v>/>\"3r}146.520MHz T100 +060 hello&\r")
check("mic-e kenwood comment", p["comment"], "146.520MHz T100 +060 hello")
check("mic-e kenwood altitude", p.get("alt_m"), 0)
line = aprs.describe(p, [], None, "mi", "N0CALL-2")
check("mic-e kenwood line", line, "N0CALL-7 car: 23 mph east, In Service, 146.520MHz T100 +060 hello, direct")
p = aprs.parse("N0CALL-7", "T1TS2U", "`dGNn v>/>440.475MHz T123 +500n0call@example.org&\r")
check("frequency field gets a space after it", aprs.describe(p, [], None, "mi", "X"),
      "N0CALL-7 car: 23 mph east, In Service, 440.475MHz T123 +500 n0call@example.org, direct")
p = aprs.parse("N0CALL-9", "T1TS2U", "`dGNn v>/`hi there_%")
check("mic-e yaesu comment", p["comment"], "hi there")
check("one line, whatever the comment", aprs.describe(aprs.parse("N0CALL", "APRS", ">two\rlines\n"), [], None, "mi", "X"),
      "N0CALL status: two lines, direct")

# Status, messages, acknowledgements, third party, objects, weather.
check("status", aprs.parse("N0CALL", "APRS", ">Net tonight 1900")["text"], "Net tonight 1900")
m = aprs.parse("W7XYZ", "APRS", ":N0CALL-2 :Hello there{12")
check("message", (m["type"], m["to"], m["text"], m["id"]), ("message", "N0CALL-2", "Hello there", "12"))
m = aprs.parse("W7XYZ", "APRS", ":N0CALL-2 :Reply ack style{AB}CD")
check("message with reply-ack id", (m["text"], m["id"]), ("Reply ack style", "AB"))
a = aprs.parse("W7XYZ", "APRS", ":N0CALL-2 :ack12")
check("ack", (a["type"], a["id"]), ("ack", "12"))
t = aprs.parse("N0IGATE", "APRS", "}W7XYZ>APRS,TCPIP,N0IGATE*:>via the internet")
check("third party", (t["type"], t["source"], t.get("third_party")), ("status", "W7XYZ", True))
o = aprs.parse("W7XYZ", "APRS", ";CERT-HQ  *111111z4903.50N/07201.75W-shelter open")
check("object", (o["type"], o["name"], o["alive"], o["comment"]), ("object", "CERT-HQ", True, "shelter open"))
w = aprs.parse("W7WX", "APRS", "!4903.50N/07201.75W_220/004g005t077r000p000h50b09900")
check("weather in a position", (w["weather"]["dir"], w["weather"]["wind"], w["weather"]["temp"]), (220, 4, 77))

# The beacon, and coordinate text.
check("lat text", aprs.lat_text(41.7147), "4142.88N")
check("lon text", aprs.lon_text(-72.7272), "07243.63W")
check("lon text, three digits", aprs.lon_text(-122.5), "12230.00W")
check("lat text rounds up a minute", aprs.lat_text(45.99999), "4600.00N")
conf = dict(aprs.DEFAULTS, lat="41.7147", lon="-72.7272", symbol="/-", comment="home")
check("beacon info", aprs.beacon_info(conf), "=4142.88N/07243.63W-home")
check("message info", aprs.message_info("w7xyz", "hi", "7"), ":W7XYZ    :hi{7")
p = aprs.parse("N0CALL-2", "APZ750", aprs.beacon_info(conf))
check("our beacon parses back", (near(p["lat"], 41.7147, 1e-3), near(p["lon"], -72.7272, 1e-3)), (True, True))

# Plain lines: call first, distance and direction, how it was heard.
home = (41.7, -72.7)
p = aprs.parse("K7ABC-9", "APRS", "!4144.00N/07242.00W>090/020 Monitoring")
line = aprs.describe(p, [("W7DEN-3", True)], home, "mi", "N0CALL-2")
check("line starts with the call", line.startswith("K7ABC-9 car: "), True)
check("line has distance and direction", "mi north" in line or "mi northeast" in line, True)
check("line has speed", "23 mph east" in line, True)
check("line says how it was heard", line.endswith("via W7DEN-3"), True)
check("direct when not repeated", aprs.heard_via([("WIDE1-1", False)]), "direct")
own = aprs.parse("N0CALL-2", "APZ750", "=4142.88N/07243.63W-home")
check("our beacon repeated", aprs.describe(own, [("W7DEN-3", True)], home, "mi", "N0CALL-2"), "Our beacon, repeated via W7DEN-3")
check("our beacon heard direct says nothing", aprs.describe(own, [], home, "mi", "N0CALL-2"), None)
check("directions", [aprs.dir_word(d) for d in (0, 44, 46, 180, 315)], ["north", "northeast", "northeast", "south", "northwest"])
km, brg = aprs.distance_bearing(45.0, -122.0, 46.0, -122.0)
check("one degree of latitude", (round(km), round(brg)), (111, 0))

# iGate: the passcode hash, and which packets go to APRS-IS and how.
check("passcode of N0CALL", aprs.aprsis_passcode("N0CALL-2"), 13023)
heard = [("W7DEN-3", True), ("WIDE2-1", False)]
check("igate line", aprs.igate_line("N0CALL-9", "APRS", heard, "!4903.50N/07201.75W-Test\r", "N0CALL-2"),
      "N0CALL-9>APRS,W7DEN-3*,WIDE2-1,qAR,N0CALL-2:!4903.50N/07201.75W-Test")
check("igate line, direct", aprs.igate_line("N0CALL-9", "APRS", [], ">hi", "N0CALL-2"), "N0CALL-9>APRS,qAR,N0CALL-2:>hi")
check("igate stars only the last digi used", aprs.igate_line("N0CALL-9", "APRS", [("W7DEN-3", True), ("WIDE2", True)], ">hi", "X"),
      "N0CALL-9>APRS,W7DEN-3,WIDE2*,qAR,X:>hi")
for word in ("NOGATE", "RFONLY", "TCPIP", "TCPXX"):
    check(f"igate skips {word}", aprs.igate_line("N0CALL", "APRS", [(word, False)], ">hi", "X"), None)
check("igate skips third party", aprs.igate_line("N0CALL", "APRS", [], "}W7XYZ>APRS,TCPIP,N0CALL*:>hi", "X"), None)
check("igate skips queries", aprs.igate_line("N0CALL", "APRS", [], "?APRS?", "X"), None)
check("igate skips empty", aprs.igate_line("N0CALL", "APRS", [], "\r", "X"), None)
mice = "`dGNn\x1cv>/>\"3r}&\r"
line = aprs.igate_line("N0CALL-7", "T1TS2U", [], mice, "X")
check("igate keeps Mic-E bytes as heard", line.encode("latin-1"), b"N0CALL-7>T1TS2U,qAR,X:`dGNn\x1cv>/>\"3r}&")

check("which igate, from the q construct", aprs.igate_of("N0CALL-2>APZ750,WIDE1-1,qAR,W7ABC-10:=hello"), ("qAR", "W7ABC-10"))
check("which igate, after a digi", aprs.igate_of("N0CALL-2>APZ750,W7DEN-3*,WIDE2-1,qAO,K7XYZ:=a:b"), ("qAO", "K7XYZ"))
check("no q construct", aprs.igate_of("N0CALL-2>APZ750,TCPIP*:=hello"), None)

# Digipeater: which packets to repeat, and the path they go out with. APRS only.
me = "N0CALL-2"
check("fill-in repeats WIDE1-1", aprs.next_hop([("WIDE1-1", False), ("WIDE2-1", False)], me, "fillin"),
      ([(me, True), ("WIDE2-1", False)], "fillin"))
check("fill-in leaves WIDE2-1 alone", aprs.next_hop([("W7DEN-3", True), ("WIDE2-1", False)], me, "fillin"), (None, None))
check("wide repeats WIDE2-1 and uses it up", aprs.next_hop([("W7DEN-3", True), ("WIDE2-1", False)], me, "wide"),
      ([("W7DEN-3", True), (me, True), ("WIDE2", True)], "wide"))
check("wide takes one off WIDE2-2", aprs.next_hop([("WIDE2-2", False)], me, "wide"), ([(me, True), ("WIDE2-1", False)], "wide"))
check("our call in the path", aprs.next_hop([("W7DEN-3", True), (me, False), ("WIDE2-1", False)], me, "fillin"),
      ([("W7DEN-3", True), (me, True), ("WIDE2-1", False)], "call"))
check("an alias becomes our call", aprs.next_hop([("CLUB", False)], me, "fillin", aliases=["club"]), ([(me, True)], "call"))
check("never twice", aprs.next_hop([(me, True), ("WIDE2-1", False)], me, "wide"), (None, None))
check("too many hops asked", aprs.next_hop([("WIDE3-3", False)], me, "wide", max_hops=2), (None, None))
check("N above n", aprs.next_hop([("WIDE2-3", False)], me, "wide"), (None, None))
check("path used up", aprs.next_hop([("W7DEN-3", True)], me, "wide"), (None, None))
check("off repeats nothing", aprs.next_hop([("WIDE1-1", False)], me, "off"), (None, None))
full = [(f"DIGI{n}", True) for n in range(7)] + [("WIDE2-2", False)]
check("eight hops: only N drops", aprs.next_hop(full, me, "wide"), (full[:7] + [("WIDE2-1", False)], "wide"))

heard = aprs.ax25_encode("K7ABC-9", "APRS", ["WIDE1-1", "WIDE2-1"], "!4903.50N/07201.75W-Test")
out, kind = aprs.digi_frame(heard, me, "fillin")
src, dst, digis, info = aprs.ax25_decode(out)
check("repeated frame keeps source and destination", (src, dst, kind), ("K7ABC-9", "APRS", "fillin"))
check("repeated frame path", digis, [(me, True), ("WIDE2-1", False)])
check("repeated frame keeps the packet byte for byte", out[-len(info) - 2:], heard[-len(info) - 2:])
check("same packet, same key, by any path", aprs.frame_key(out), aprs.frame_key(heard))
i_frame = bytearray(heard); i_frame[28] = 0x00
check("not APRS: a connected-mode frame is left alone", aprs.digi_frame(bytes(i_frame), me, "wide"), None)
other_pid = bytearray(heard); other_pid[29] = 0xCF
check("not APRS: another protocol is left alone", aprs.digi_frame(bytes(other_pid), me, "wide"), None)

# The daemon's part: duplicates, our own packets, transmitting off, the limit. A stand-in serial port.
import tempfile
class FakeSerial:
    def __init__(self): self.sent = []
    def write(self, b): self.sent.append(b)
with tempfile.TemporaryDirectory() as tmp:
    aprs.STATE = os.path.join(tmp, "state.json")
    d = aprs.Daemon(dict(aprs.DEFAULTS, call=me, transmit="on", digi="fillin"))
    d.say = d.raw = lambda *a: None
    d.serial = FakeSerial()
    check("daemon repeats a WIDE1-1 packet", d._digi_consider(heard), "repeated")
    check("daemon skips the same packet again", d._digi_consider(heard), None)
    check("daemon skips a copy by another digi", d._digi_consider(out), None)
    ours = aprs.ax25_encode(me, "APZ750", ["WIDE1-1"], ">ours")
    check("daemon never repeats its own", d._digi_consider(ours), None)
    check("daemon sent exactly one", len(d.serial.sent), 1)
    d.transmit = False
    check("daemon repeats nothing with transmitting off", d._digi_consider(aprs.ax25_encode("K7ABC-9", "APRS", ["WIDE1-1"], ">x")), None)
    d.transmit = True
    for n in range(aprs.DIGI_PER_MINUTE + 3):
        d._digi_consider(aprs.ax25_encode("K7ABC-9", "APRS", ["WIDE1-1"], f">n{n}"))
    check("daemon stops at its limit a minute", len(d.serial.sent), aprs.DIGI_PER_MINUTE)
    check("status says the digipeater", d._digi_state(), f"Fill-in digipeater on. {aprs.DIGI_PER_MINUTE} repeated.")

# Kuma pushes and ntfy notices: the URL each push makes, and notices only when asked for.
base = "http://127.0.0.1:3001/api/push/TOKEN?status=up&msg=OK&ping="
check("push URL, up", aprs.push_url(base, "heard K7ABC-9"), "http://127.0.0.1:3001/api/push/TOKEN?status=up&msg=heard+K7ABC-9&ping=")
check("push URL, down", aprs.push_url(base, "no TNC", up=False), "http://127.0.0.1:3001/api/push/TOKEN?status=down&msg=no+TNC&ping=")
calls = []
real, real_which = aprs._quietly, aprs.shutil.which
aprs._quietly = lambda *a: calls.append(a)
aprs.shutil.which = lambda name: sys.executable          # any program that exists stands in for notify
with tempfile.TemporaryDirectory() as tmp:
    aprs.STATE = os.path.join(tmp, "state.json")
    d = aprs.Daemon(dict(aprs.DEFAULTS, call=me, notify="off"))
    d.notify("aprs", "APRS from K7ABC", "hi", 4)
    check("no notice with notify off", calls, [])
    d.conf["notify"] = "on"
    d.notify("aprs", "APRS from K7ABC", "hi", 4)
    check("a notice with notify on", [c[1:] for c in calls], [("aprs", "APRS from K7ABC", "hi", "4")])
    aprs.PUSH_FILES = {"heard": os.path.join(tmp, "missing")}
    calls.clear()
    d.push("heard", "x")
    check("no push while the push file is missing", calls, [])
aprs._quietly, aprs.shutil.which = real, real_which

# Messages: long text in parts, APRS-IS lines, and the history aprschat reads.
check("short message, one part", aprs.message_parts("hello there"), ["hello there"])
long = "word " * 30
parts = aprs.message_parts(long)
check("long message in parts of at most 67", (len(parts), max(len(x) for x in parts)), (3, 64))
check("parts keep every word", " ".join(parts), long.strip())
check("APRS's own characters replaced", aprs.message_parts("a{b|c~d"), ["a(b/c-d"])
check("APRS-IS line", aprs.parse_tnc2("W7XYZ>APRS,TCPIP*,qAC,T2TEST::N0CALL-2 :hi{3"),
      ("W7XYZ", "APRS", [("TCPIP", True), ("qAC", False), ("T2TEST", False)], ":N0CALL-2 :hi{3"))
check("not an APRS-IS line", aprs.parse_tnc2("# aprsc 2.1"), None)
with tempfile.TemporaryDirectory() as tmp:
    aprs.STATE, aprs.MESSAGES = os.path.join(tmp, "state.json"), os.path.join(tmp, "messages.jsonl")
    d = aprs.Daemon(dict(aprs.DEFAULTS, call=me, transmit="on", notify="off"))
    d.say = d.raw = lambda *a: None
    sent = []
    d.send_frame = lambda info, path=None, why="": sent.append(info) or True
    ids = d.send_message("w7xyz", "hello")
    d._for_us(aprs.parse("W7XYZ", "APRS", f":{me:<9}:ack{ids[0]}"))
    d._for_us(aprs.parse("W7XYZ", "APRS", f":{me:<9}:how are you{{7"))
    class FakeWriter:
        def __init__(self): self.lines = []
        def write(self, b): self.lines.append(b.decode("latin-1").strip())
    d.is_writer = FakeWriter()
    d._from_is(f"K7ABC>APRS,TCPIP*,qAC,T2TEST::{me:<9}:from the web{{9")
    check("ack through APRS-IS for a message from the internet", d.is_writer.lines, [f"{me}>APZ750,TCPIP*::K7ABC    :ack9"])
    d.is_writer = None
    events = [json.loads(x) for x in open(aprs.MESSAGES)]
    check("history: queued, acked, two in", [(e["dir"], e.get("state") or e.get("via"), e["call"]) for e in events],
          [("out", "queued", "W7XYZ"), ("out", "acked", "W7XYZ"), ("in", "rf", "W7XYZ"), ("in", "is", "K7ABC")])
    check("ack on the air for a message heard on the air", sent, [f":W7XYZ    :ack7"])
    check("the outbox is empty after the ack", d.outbox, {})
    d._for_us(aprs.parse("W7XYZ", "APRS", f":{me:<9}:how are you{{7"))
    check("a repeat of the same message is not a new one", len([x for x in open(aprs.MESSAGES)]), 4)

# After a restart: power cycle once when the radio does not send, never twice in 30 minutes, never while
# keyed, and ask Jon when it cannot. A stand-in runs instead of the command; nothing is switched.
ran, told = [], []
real = aprs._quietly
aprs._quietly = lambda *a: ran.append(a)
with tempfile.TemporaryDirectory() as tmp:
    aprs.STATE, aprs.MESSAGES = os.path.join(tmp, "state.json"), os.path.join(tmp, "messages.jsonl")
    d = aprs.Daemon(dict(aprs.DEFAULTS, call=me, transmit="on"))
    d.say = d.raw = d.push = lambda *a, **k: None
    d.notify = lambda topic, title, msg, prio=3: told.append((topic, title, prio))
    d._keyed = lambda: False
    d._not_sending("a test")
    check("no command set: ask Jon, priority 5", (ran, told[-1]), ([], ("alerts", "TM-D750 is not transmitting", 5)))
    d.conf["power_cycle_cmd"] = "d750-power cycle 10"
    d._not_sending("a test")
    check("power cycled once", ran, [("d750-power", "cycle", "10")])
    check("and said so, priority 4", told[-1], ("alerts", "TM-D750 power cycled by the station computer", 4))
    check("the time is kept", json.load(open(aprs.STATE)).get("last_power_cycle", 0) > 0, True)
    d._not_sending("a test")
    check("not twice in 30 minutes: ask Jon", (len(ran), told[-1][2]), (1, 5))
    d.last_cycle = 0
    d._keyed = lambda: True
    d._not_sending("a test")
    check("never while xara is keyed", len(ran), 1)
    d._keyed = lambda: False
    d.last_cycle = time.time() - 60
    d.recovery = "the radio came back on USB"
    d.beacon_watch = time.time()                    # the check beacon is being watched
    d._own_seen(f"{me}>APZ750,WIDE1-1,qAR,K7BCX-10:=hello")
    check("sending again after the cycle, priority 3", (d.recovery, told[-1]), (None, ("alerts", "TM-D750 sending again", 3)))
aprs._quietly = real

# The status message: on the air and straight to APRS-IS, so aprs.fi shows it; nothing when none is set.
with tempfile.TemporaryDirectory() as tmp:
    aprs.STATE = os.path.join(tmp, "state.json")
    d = aprs.Daemon(dict(aprs.DEFAULTS, call=me, transmit="on", status="Fill-in digipeater and RX iGate"))
    d.say = d.raw = lambda *a: None
    air = []
    d.send_frame = lambda info, path=None, why="": air.append(info) or True
    class W:
        def __init__(self): self.lines = []
        def write(self, b): self.lines.append(b.decode().strip())
    d.is_writer = W()
    check("status goes out", d.announce(), True)
    check("status on the air", air, [">Fill-in digipeater and RX iGate"])
    check("status to APRS-IS", d.is_writer.lines, [f"{me}>APZ750,TCPIP*:>Fill-in digipeater and RX iGate"])
    check("status time kept", json.load(open(aprs.STATE)).get("last_status", 0) > 0, True)
    d.conf["status"] = ""
    check("no status set, nothing sent", d.announce(), False)

# The settings file holds the home position: set_conf keeps it owner only and keeps the other lines.
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "aprs.conf")
    open(path, "w").write("# note\ncall = N0CALL-2\ncomment = old\n")
    os.chmod(path, 0o644)
    aprs.set_conf("comment", "new text", path)
    check("set_conf keeps the file owner only", oct(os.stat(path).st_mode & 0o777), "0o600")
    check("set_conf changes one line", open(path).read(), "# note\ncall = N0CALL-2\ncomment = new text\n")

print(f"{passed} passed, {failed} failed.")
sys.exit(1 if failed else 0)
