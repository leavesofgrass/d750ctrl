"""Offline tests for d750-aprs: KISS, AX.25, APRS parsing and the plain lines.

Run: python3 -I d750-aprs-test.py. Nothing here opens a port or transmits.
"""

import importlib.util
import os
import sys

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

print(f"{passed} passed, {failed} failed.")
sys.exit(1 if failed else 0)
