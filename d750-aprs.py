"""d750-aprs: APRS through the TM-D750's own TNC in KISS mode.

The daemon reads KISS frames from the radio's TNC port, says each packet as
one plain line, beacons the home station on a timer, sends and acknowledges
APRS messages, and shares the TNC with other programs on KISS TCP.

Nothing transmits until transmitting is switched on. With it off, beacons,
acknowledgements, messages and frames from KISS clients are all held back.
"""

import asyncio
import json
import math
import os
import re
import sys
import time
from datetime import datetime

CONF = os.path.expanduser("~/.config/d750ctrl/aprs.conf")
STATE = os.path.expanduser("~/.local/state/d750ctrl/aprs.json")
LOGDIR = os.path.expanduser("~/.local/share/d750ctrl/log")
SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache"), "d750-aprs.sock")

DEFAULTS = {
    "call": "N0CALL",
    "tnc": "/dev/d750-tnc",
    "lat": "",
    "lon": "",
    "symbol": "/-",
    "comment": "",
    "path": "WIDE1-1,WIDE2-1",
    "interval": "30",
    "transmit": "off",
    "kiss_listen": "127.0.0.1:8001",
    "units": "mi",
    "tocall": "APZ750",
}

# ---------------------------------------------------------------- settings


def load_conf(path=CONF):
    conf = dict(DEFAULTS)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip()
    return conf


def set_conf(key, value, path=CONF):
    """Change one key in the settings file, keeping its comments and order."""
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    done = False
    for i, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(key)}\s*=", line):
            lines[i] = f"{key} = {value}"
            done = True
    if not done:
        lines.append(f"{key} = {value}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(path + ".tmp", path)


# ---------------------------------------------------------------- KISS framing

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD


def kiss_encode(data, port=0):
    out = bytearray([FEND, (port << 4) & 0xF0])
    for b in data:
        if b == FEND:
            out += bytes([FESC, TFEND])
        elif b == FESC:
            out += bytes([FESC, TFESC])
        else:
            out.append(b)
    out.append(FEND)
    return bytes(out)


class KissReader:
    """Collects bytes and gives back whole data frames, without the command byte."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        frames = []
        for b in data:
            if b == FEND:
                if self.buf:
                    frame = self._unescape(self.buf)
                    if frame and frame[0] & 0x0F == 0:
                        frames.append(frame[1:])
                self.buf = bytearray()
            else:
                self.buf.append(b)
        return frames

    @staticmethod
    def _unescape(buf):
        out, esc = bytearray(), False
        for b in buf:
            if esc:
                out.append(FEND if b == TFEND else FESC if b == TFESC else b)
                esc = False
            elif b == FESC:
                esc = True
            else:
                out.append(b)
        return bytes(out)


# ---------------------------------------------------------------- AX.25 UI frames


def _addr_decode(b):
    call = "".join(chr(c >> 1) for c in b[:6]).strip()
    ssid = (b[6] >> 1) & 0x0F
    return (f"{call}-{ssid}" if ssid else call), bool(b[6] & 0x80), bool(b[6] & 0x01)


def _addr_encode(text, last=False, repeated=False):
    call, _, ssid = text.upper().partition("-")
    call = call[:6].ljust(6)
    b = bytearray((ord(c) << 1) for c in call)
    b.append(0x60 | ((int(ssid or 0) & 0x0F) << 1) | (0x80 if repeated else 0) | (0x01 if last else 0))
    return bytes(b)


def ax25_decode(frame):
    """An AX.25 UI frame as (source, dest, [(digi, repeated)], info), or None."""
    addrs, i = [], 0
    while i + 7 <= len(frame):
        call, hbit, last = _addr_decode(frame[i:i + 7])
        addrs.append((call, hbit))
        i += 7
        if last:
            break
    else:
        return None
    if len(addrs) < 2 or i + 2 > len(frame):
        return None
    control, pid = frame[i], frame[i + 1]
    if control & 0xEF != 0x03 or pid != 0xF0:
        return None
    dest, source = addrs[0][0], addrs[1][0]
    digis = addrs[2:]
    info = frame[i + 2:].decode("latin-1")
    return source, dest, digis, info


def ax25_encode(source, dest, path, info):
    digis = [p for p in path if p]
    out = bytearray(_addr_encode(dest))
    out += _addr_encode(source, last=not digis)
    for n, d in enumerate(digis):
        out += _addr_encode(d, last=n == len(digis) - 1)
    out += bytes([0x03, 0xF0]) + info.encode("latin-1", "replace")
    return bytes(out)


def tnc2(source, dest, digis, info):
    """The packet in the usual one-line text form: SOURCE>DEST,DIGI*:info."""
    last_rep = max((n for n, (_, rep) in enumerate(digis) if rep), default=-1)
    path = [d + ("*" if n == last_rep else "") for n, (d, _) in enumerate(digis)]
    return f"{source}>{','.join([dest] + path)}:{info}"


# ---------------------------------------------------------------- APRS parsing

MICE_MESSAGES = {
    "111": "Off Duty", "110": "En Route", "101": "In Service", "100": "Returning",
    "011": "Committed", "010": "Special", "001": "Priority", "000": "Emergency",
}

SYMBOLS = {
    "/-": "home", "/>": "car", "/k": "truck", "/u": "truck", "/v": "van", "/j": "jeep", "/b": "bicycle",
    "/[": "walker", "/<": "motorcycle", "/R": "RV", "/U": "bus", "/f": "fire truck", "/a": "ambulance",
    "/s": "boat", "/Y": "sailboat", "/^": "aircraft", "/'": "small aircraft", "/O": "balloon",
    "/#": "digipeater", "\\#": "digipeater", "/&": "gateway", "\\&": "gateway", "/r": "repeater",
    "/_": "weather station", "\\_": "weather station", "/y": "home with yagi", "/n": "node",
    "/!": "police", "/+": "Red Cross", "/o": "EOC", "/h": "hospital", "/W": "weather service",
}


def b91(s):
    n = 0
    for c in s:
        n = n * 91 + (ord(c) - 33)
    return n


def _uncompressed(s):
    """Lat and lon from DDMM.hhN/DDDMM.hhW (19 chars); spaces from ambiguity count as zero."""
    m = re.match(r"^(\d{2})([\d ]{2})\.([\d ]{2})([NS])(.)(\d{3})([\d ]{2})\.([\d ]{2})([EW])(.)", s)
    if not m:
        return None
    z = lambda t: t.replace(" ", "0")
    lat = int(m.group(1)) + float(z(m.group(2)) + "." + z(m.group(3))) / 60
    lon = int(m.group(6)) + float(z(m.group(7)) + "." + z(m.group(8))) / 60
    if m.group(4) == "S":
        lat = -lat
    if m.group(9) == "W":
        lon = -lon
    return lat, lon, m.group(5) + m.group(10), s[19:]


def _compressed(s):
    if len(s) < 13 or not re.match(r"^[/\\A-Za-j]", s):
        return None
    try:
        lat = 90 - b91(s[1:5]) / 380926
        lon = -180 + b91(s[5:9]) / 190463
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    out = {"lat": lat, "lon": lon, "symbol": s[0] + s[9]}
    c, sp = s[10], s[11]
    if c != " " and 0 <= ord(c) - 33 <= 89:
        out["course"] = (ord(c) - 33) * 4
        out["speed_kn"] = 1.08 ** (ord(sp) - 33) - 1
    return out, s[13:]


def _position(body):
    """Parse a position body, compressed or not, with course and speed when given."""
    p = _uncompressed(body)
    if p:
        lat, lon, sym, rest = p
        out = {"lat": lat, "lon": lon, "symbol": sym}
        m = re.match(r"^(\d{3})/(\d{3})", rest)
        if m and sym[1] != "_":
            out["course"], out["speed_kn"] = int(m.group(1)), int(m.group(2))
            rest = rest[7:]
        return out, rest
    c = _compressed(body)
    if c:
        return c
    return None, body


def _altitude(comment):
    m = re.search(r"/A=(-?\d{6})", comment)
    return (int(m.group(1)), comment[:m.start()] + comment[m.end():]) if m else (None, comment)


def _mice(dest, info):
    d = dest.split("-")[0]
    if len(d) != 6 or len(info) < 9:
        return None
    digits, bits = "", ""
    for ch in d:
        if ch.isdigit():
            digits += ch
            bits += "0"
        elif "A" <= ch <= "J":
            digits += str(ord(ch) - 65)
            bits += "1"
        elif "P" <= ch <= "Y":
            digits += str(ord(ch) - 80)
            bits += "1"
        elif ch in "KLZ":
            digits += "0"
            bits += "1" if ch != "L" else "0"
        else:
            return None
    lat = int(digits[:2]) + float(digits[2:4] + "." + digits[4:6]) / 60
    if not ("P" <= d[3] <= "Z"):
        lat = -lat
    lon_deg = ord(info[1]) - 28
    if "P" <= d[4] <= "Z":
        lon_deg += 100
    if 180 <= lon_deg <= 189:
        lon_deg -= 80
    elif 190 <= lon_deg <= 199:
        lon_deg -= 190
    lon_min = ord(info[2]) - 28
    if lon_min >= 60:
        lon_min -= 60
    lon = lon_deg + (lon_min + (ord(info[3]) - 28) / 100) / 60
    if "P" <= d[5] <= "Z":
        lon = -lon
    sp, dc, se = ord(info[4]) - 28, ord(info[5]) - 28, ord(info[6]) - 28
    speed = sp * 10 + dc // 10
    if speed >= 800:
        speed -= 800
    course = (dc % 10) * 100 + se
    if course >= 400:
        course -= 400
    out = {"lat": lat, "lon": lon, "symbol": info[8] + info[7], "speed_kn": speed, "course": course}
    std = any("P" <= ch <= "Z" for ch in d[:3])
    if std or bits[:3] == "000":
        out["status"] = MICE_MESSAGES.get(bits[:3], "")
    comment = info[9:]
    m = re.search(r"(.{3})\}", comment)
    if m:
        try:
            out["alt_m"] = b91(m.group(1)) - 10000
        except ValueError:
            pass
        comment = comment[:m.start()] + comment[m.end():]
    out["comment"] = comment.strip(" >]`'=^")
    return out


def _weather(text):
    w = {}
    for key, name in (("c", "dir"), ("s", "wind"), ("g", "gust"), ("t", "temp"), ("h", "humidity")):
        m = re.search(rf"{key}(-?\d{{2,3}})", text)
        if m:
            w[name] = int(m.group(1))
    return w


def parse(source, dest, info):
    """What one APRS packet says, as a dict with a "type"."""
    p = {"source": source, "dest": dest, "raw": info}
    if not info:
        p["type"] = "empty"
        return p
    t, body = info[0], info[1:]
    if t == "}":
        m = re.match(r"^([^>]+)>([^,:]+)[^:]*:(.*)$", body)
        if m:
            inner = parse(m.group(1), m.group(2), m.group(3))
            inner["third_party"] = True
            return inner
    if t in "`'\x1c\x1d":
        m = _mice(dest, info)
        if m:
            p.update(m, type="position")
            return p
    if t in "!=/@":
        if t in "/@":
            body = body[7:]
        pos, rest = _position(body)
        if pos:
            p.update(pos, type="position")
            alt, rest = _altitude(rest)
            if alt is not None:
                p["alt_ft"] = alt
            if p["symbol"][1] == "_":
                w = _weather(rest)
                m = re.match(r"^(\d{3})/(\d{3})", rest)
                if m:
                    w.setdefault("dir", int(m.group(1)))
                    w.setdefault("wind", int(m.group(2)))
                p["weather"] = w
            p["comment"] = rest.strip()
            return p
    if t == ">":
        p.update(type="status", text=body.strip())
        return p
    if t == ":" and len(body) >= 10 and body[9] == ":":
        to, text = body[:9].strip(), body[10:]
        m = re.match(r"^(ack|rej)([A-Za-z0-9}]{1,5})\s*$", text)
        if m:
            p.update(type=m.group(1), to=to, id=m.group(2).split("}")[0])
            return p
        msgid = None
        m = re.search(r"\{([A-Za-z0-9]{1,5})(\}.*)?$", text)
        if m:
            msgid, text = m.group(1), text[:m.start()]
        p.update(type="message", to=to, text=text.strip(), id=msgid)
        return p
    if t == ";" and len(body) >= 17:
        name, live, rest = body[:9].strip(), body[9], body[17:]
        pos, rest = _position(rest)
        p.update(pos or {}, type="object", name=name, alive=live == "*", comment=rest.strip())
        return p
    if t == ")":
        m = re.match(r"^([^!_]{3,9})([!_])(.*)$", body)
        if m:
            pos, rest = _position(m.group(3))
            p.update(pos or {}, type="object", name=m.group(1), alive=m.group(2) == "!", comment=rest.strip())
            return p
    if t == "_":
        p.update(type="weather", weather=_weather(body))
        return p
    if t == "T":
        p["type"] = "telemetry"
        return p
    p["type"] = "other"
    return p


# ---------------------------------------------------------------- distance and words

DIRS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]


def distance_bearing(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 2 * r * math.asin(math.sqrt(a))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return km, (math.degrees(math.atan2(y, x)) + 360) % 360


def dir_word(deg):
    return DIRS[int(((deg + 22.5) % 360) // 45)]


def dist_words(km, units):
    if units == "km":
        return f"{km:.1f} km" if km < 10 else f"{km:.0f} km"
    mi = km / 1.609344
    return f"{mi:.1f} mi" if mi < 10 else f"{mi:.0f} mi"


def speed_words(kn, units):
    return f"{kn * 1.852:.0f} km/h" if units == "km" else f"{kn * 1.150779:.0f} mph"


def heard_via(digis):
    reps = [d for d, rep in digis if rep]
    if not reps:
        return "direct"
    return "via " + reps[-1]


def describe(p, digis, home, units, mycall):
    """One plain line for a packet, after the time: the call first, then what it says."""
    src, kind = p["source"], p["type"]
    via = heard_via(digis) if not p.get("third_party") else "through the internet"
    sym = SYMBOLS.get(p.get("symbol", ""), "")
    where = ""
    if "lat" in p and home:
        km, brg = distance_bearing(home[0], home[1], p["lat"], p["lon"])
        where = f"{dist_words(km, units)} {dir_word(brg)}"
    if kind == "position":
        if src.upper() == mycall.upper():
            return f"Our beacon, repeated {via}" if via != "direct" else None
        parts = [where] if where else []
        if p.get("speed_kn"):
            parts.append(f"{speed_words(p['speed_kn'], units)} {dir_word(p.get('course', 0))}")
        if p.get("status"):
            parts.append(p["status"])
        if p.get("weather"):
            w = p["weather"]
            if "temp" in w:
                parts.append(f"{w['temp']} F")
            if "wind" in w:
                parts.append(f"wind {w['wind']} mph {dir_word(w.get('dir', 0))}")
        if p.get("comment"):
            parts.append(p["comment"][:60])
        head = f"{src}{' ' + sym if sym else ''}"
        return f"{head}: {', '.join(parts)}, {via}" if parts else f"{head}, {via}"
    if kind == "status":
        return f"{src} status: {p['text'][:80]}, {via}"
    if kind == "message":
        return f"{src} to {p['to']}: {p['text']}"
    if kind in ("ack", "rej"):
        return None
    if kind == "object":
        state = "" if p.get("alive", True) else " removed"
        bits = [where] if where else []
        if p.get("comment"):
            bits.append(p["comment"][:60])
        return f"Object {p['name']}{state} from {src}" + (f": {', '.join(bits)}" if bits else "")
    if kind == "weather":
        w = p.get("weather", {})
        bits = []
        if "temp" in w:
            bits.append(f"{w['temp']} F")
        if "wind" in w:
            bits.append(f"wind {w['wind']} mph {dir_word(w.get('dir', 0))}")
        return f"{src} weather: {', '.join(bits) or 'report'}, {via}"
    if kind == "telemetry":
        return f"{src} telemetry, {via}"
    return f"{src}: {p['raw'][:60]}, {via}"


# ---------------------------------------------------------------- the home beacon


def lat_text(lat):
    h = "N" if lat >= 0 else "S"
    lat = abs(lat)
    d = int(lat)
    m = round((lat - d) * 60, 2)
    if m >= 60:
        d, m = d + 1, 0.0
    return f"{d:02d}{m:05.2f}{h}"


def lon_text(lon):
    h = "E" if lon >= 0 else "W"
    lon = abs(lon)
    d = int(lon)
    m = round((lon - d) * 60, 2)
    if m >= 60:
        d, m = d + 1, 0.0
    return f"{d:03d}{m:05.2f}{h}"


def beacon_info(conf):
    lat, lon = float(conf["lat"]), float(conf["lon"])
    sym = conf["symbol"] if len(conf["symbol"]) == 2 else "/-"
    return f"={lat_text(lat)}{sym[0]}{lon_text(lon)}{sym[1]}{conf['comment']}"[:80]


def message_info(to, text, msgid):
    return f":{to.upper():<9}:{text[:67]}" + (f"{{{msgid}" if msgid else "")


# ---------------------------------------------------------------- the daemon


class Daemon:
    def __init__(self, conf):
        self.conf = conf
        self.call = conf["call"].upper()
        self.units = conf["units"]
        self.home = (float(conf["lat"]), float(conf["lon"])) if conf["lat"] and conf["lon"] else None
        self.path = [p.strip() for p in conf["path"].split(",") if p.strip()]
        self.transmit = conf["transmit"].lower() in ("on", "yes", "true")
        self.kiss = KissReader()
        self.clients = set()
        self.serial = None
        self.outbox = {}
        self.seen_msgs = {}
        self.state = self._load_state()
        self.last_beacon = 0.0
        self.started = time.time()
        self.heard = 0

    # -- state, logs
    def _load_state(self):
        try:
            return json.load(open(STATE))
        except (OSError, ValueError):
            return {"msgno": 0}

    def _save_state(self):
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(self.state, open(STATE + ".tmp", "w"))
        os.replace(STATE + ".tmp", STATE)

    def say(self, line):
        now = datetime.now()
        text = f"{now:%H:%M} {line}"
        print(text, flush=True)
        os.makedirs(LOGDIR, exist_ok=True)
        with open(os.path.join(LOGDIR, f"aprs-{now:%Y-%m-%d}.txt"), "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def raw(self, line):
        now = datetime.now()
        with open(os.path.join(LOGDIR, f"aprs-{now:%Y-%m-%d}.raw"), "a", encoding="utf-8") as f:
            f.write(f"{now:%H:%M:%S} {line}\n")

    # -- sending
    def send_frame(self, info, path=None, why=""):
        if not self.transmit:
            self.say(f"Held back, transmitting is off: {why or info[:40]}")
            return False
        if not self.serial:
            self.say(f"Not sent, the TNC is not connected: {why or info[:40]}")
            return False
        frame = ax25_encode(self.call, self.conf["tocall"], self.path if path is None else path, info)
        self.serial.write(kiss_encode(frame))
        self.raw("TX " + tnc2(self.call, self.conf["tocall"], [(p, False) for p in (self.path if path is None else path)], info))
        for w in list(self.clients):
            self._client_write(w, kiss_encode(frame))
        return True

    def beacon(self, why="timer"):
        if not self.home:
            self.say("No beacon: the home position is not set. Set lat and lon in aprs.conf.")
            return
        if self.send_frame(beacon_info(self.conf), why="the home beacon"):
            self.last_beacon = time.time()
            self.say(f"Beacon sent: {self.call} at home, path {','.join(self.path)}")

    def send_message(self, to, text):
        self.state["msgno"] = self.state.get("msgno", 0) % 999 + 1
        self._save_state()
        msgid = str(self.state["msgno"])
        self.outbox[msgid] = {"to": to.upper(), "text": text, "tries": 0, "next": time.time()}
        wait = "" if self.transmit else " It waits until transmitting is on."
        self.say(f"Message to {to.upper()} queued: {text}.{wait}")

    def _ack(self, to, msgid):
        self.send_frame(f":{to.upper():<9}:ack{msgid}", why=f"the acknowledgement to {to}")

    # -- receiving
    def on_frame(self, frame, from_client=None):
        d = ax25_decode(frame)
        if not d:
            return
        source, dest, digis, info = d
        self.raw("RX " + tnc2(source, dest, digis, info))
        self.heard += 1
        p = parse(source, dest, info)
        if p["type"] in ("message", "ack", "rej") and p.get("to", "").upper() in (self.call, self.call.split("-")[0]):
            self._for_us(p)
            return
        line = describe(p, digis, self.home, self.units, self.call)
        if line:
            self.say(line)

    def _for_us(self, p):
        src = p["source"].upper()
        if p["type"] == "message":
            key = (src, p.get("id"), p["text"])
            fresh = key not in self.seen_msgs or time.time() - self.seen_msgs[key] > 1800
            self.seen_msgs[key] = time.time()
            if fresh:
                self.say(f"Message from {src}: {p['text']}")
            if p.get("id"):
                self._ack(src, p["id"])
        elif p["type"] == "ack":
            m = self.outbox.pop(p["id"], None)
            if m:
                self.say(f"Message to {m['to']} acknowledged")
        elif p["type"] == "rej":
            m = self.outbox.pop(p["id"], None)
            if m:
                self.say(f"Message to {m['to']} was refused")

    # -- the loops
    async def run(self):
        import serial
        self.say(f"d750-aprs for {self.call} starting. Transmitting is {'on' if self.transmit else 'off'}.")
        await self._start_servers()
        asyncio.get_running_loop().create_task(self._timers())
        while True:
            try:
                s = serial.Serial()
                s.port, s.baudrate, s.timeout = self.conf["tnc"], 9600, 0
                s.dtr, s.rts = False, False  # held low, so opening the port never keys the radio
                s.open()
            except Exception as e:
                why = "is not there yet" if isinstance(e, FileNotFoundError) or "No such file" in str(e) else (
                    "is not yours to open; run ~/fixes/d750-tnc-udev-root.sh" if "denied" in str(e) else f"cannot be opened: {e}")
                if why != getattr(self, "_port_problem", None):
                    self.say(f"The TNC port {self.conf['tnc']} {why}. Waiting for it.")
                    self._port_problem = why
                await asyncio.sleep(30)
                continue
            self._port_problem = None
            self.serial = s
            self.say(f"Listening on {self.conf['tnc']}.")
            lost = asyncio.get_running_loop().create_future()
            loop = asyncio.get_running_loop()

            def readable():
                try:
                    data = s.read(4096)
                except Exception:
                    data = None
                if data is None:
                    loop.remove_reader(s.fileno())
                    if not lost.done():
                        lost.set_result(None)
                    return
                for frame in self.kiss.feed(data):
                    for w in list(self.clients):
                        self._client_write(w, kiss_encode(frame))
                    self.on_frame(frame)

            loop.add_reader(s.fileno(), readable)
            await lost
            self.serial = None
            try:
                s.close()
            except Exception:
                pass
            self.say("Lost the TNC port. Trying again in 10 seconds.")
            await asyncio.sleep(10)

    async def _timers(self):
        interval = max(10, int(self.conf["interval"])) * 60
        first = True
        while True:
            now = time.time()
            if self.transmit and self.home and self.serial:
                due = now - self.last_beacon >= interval
                if (first and now - self.started > 20) or due:
                    self.beacon()
                    first = False
            for msgid, m in list(self.outbox.items()):
                if self.transmit and now >= m["next"]:
                    if m["tries"] >= 5:
                        self.outbox.pop(msgid)
                        self.say(f"Message to {m['to']} was not acknowledged after 5 tries")
                        continue
                    if self.send_frame(message_info(m["to"], m["text"], msgid), why=f"the message to {m['to']}"):
                        m["tries"] += 1
                        m["next"] = now + 30 * (2 ** (m["tries"] - 1))
                        self.say(f"Message to {m['to']} sent, try {m['tries']}")
                    else:
                        m["next"] = now + 60
            await asyncio.sleep(5)

    async def _start_servers(self):
        for spec in self.conf["kiss_listen"].split():
            host, _, port = spec.rpartition(":")
            try:
                await asyncio.start_server(self._kiss_client, host, int(port))
                self.say(f"Sharing the TNC with KISS programs on {host} port {port}.")
            except OSError as e:
                self.say(f"Cannot share KISS on {spec}: {e.strerror}.")
        try:
            os.unlink(SOCK)
        except FileNotFoundError:
            pass
        await asyncio.start_unix_server(self._control, SOCK)
        os.chmod(SOCK, 0o600)

    def _client_write(self, w, data):
        try:
            w.write(data)
        except Exception:
            self.clients.discard(w)

    async def _kiss_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        who = f"{peer[0]}" if peer else "a client"
        self.clients.add(writer)
        self.say(f"KISS program connected from {who}.")
        k = KissReader()
        try:
            while data := await reader.read(4096):
                for frame in k.feed(data):
                    d = ax25_decode(frame)
                    if not self.transmit:
                        self.say(f"Held back a frame from {who}: transmitting is off.")
                        continue
                    if self.serial:
                        self.serial.write(kiss_encode(frame))
                        if d:
                            self.raw("TX from " + who + " " + tnc2(d[0], d[1], d[2], d[3]))
        finally:
            self.clients.discard(writer)
            self.say(f"KISS program from {who} disconnected.")

    async def _control(self, reader, writer):
        line = (await reader.readline()).decode("utf-8", "replace").strip()
        cmd, _, rest = line.partition(" ")
        reply = "Unknown command."
        if cmd == "status":
            up = int((time.time() - self.started) / 60)
            reply = (f"{self.call}: TNC {'connected' if self.serial else 'not connected'}, transmitting "
                     f"{'on' if self.transmit else 'off'}, {self.heard} packets heard in {up} minutes, "
                     f"{len(self.clients)} KISS programs, {len(self.outbox)} messages waiting.")
        elif cmd == "beacon":
            self.beacon("by hand")
            reply = "Done."
        elif cmd == "transmit":
            self.transmit = rest == "on"
            self.say(f"Transmitting is now {'on' if self.transmit else 'off'}.")
            reply = f"Transmitting is {'on' if self.transmit else 'off'}."
        elif cmd == "send":
            to, _, text = rest.partition(" ")
            if to and text:
                self.send_message(to, text)
                reply = "Queued."
            else:
                reply = "Usage: send CALL TEXT"
        writer.write((reply + "\n").encode())
        await writer.drain()
        writer.close()


# ---------------------------------------------------------------- the command line

USAGE = """d750-aprs: APRS through the TM-D750's TNC in KISS mode.
  d750-aprs daemon             run the daemon (the user service does this)
  d750-aprs listen             follow packets as plain lines; Ctrl+C stops
  d750-aprs last [N] [TEXT]    the last N lines of today's log (20), only those with TEXT
  d750-aprs status             the daemon's state
  d750-aprs beacon             send the home beacon now
  d750-aprs transmit on|off    allow or stop every transmission: beacons, messages, acks, KISS programs
  d750-aprs send CALL TEXT     send an APRS message, retried until acknowledged
Settings: ~/.config/d750ctrl/aprs.conf. Logs: ~/.local/share/d750ctrl/log/aprs-DATE.txt."""


def control(line):
    import socket
    s = socket.socket(socket.AF_UNIX)
    try:
        s.connect(SOCK)
    except OSError:
        print("The d750-aprs daemon is not running. Start it: systemctl --user start d750-aprs")
        return 1
    s.sendall((line + "\n").encode())
    print(s.makefile().readline().strip())
    return 0


def today_log():
    return os.path.join(LOGDIR, f"aprs-{datetime.now():%Y-%m-%d}.txt")


def main(argv):
    cmd = argv[0] if argv else "help"
    if cmd == "daemon":
        asyncio.run(Daemon(load_conf()).run())
    elif cmd == "listen":
        path = today_log()
        print(f"Following {path}. Ctrl+C stops.", flush=True)
        f = open(path, encoding="utf-8") if os.path.exists(path) else None
        if f:
            f.seek(0, 2)
        try:
            while True:
                if f is None and os.path.exists(path):
                    f = open(path, encoding="utf-8")
                line = f.readline() if f else ""
                if line:
                    print(line.rstrip("\n"), flush=True)
                else:
                    time.sleep(0.5)
                    if today_log() != path:
                        path, f = today_log(), None
        except KeyboardInterrupt:
            print("Stopped.")
    elif cmd == "last":
        n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 20
        text = " ".join(a for a in argv[1:] if not a.isdigit()).lower()
        path = today_log()
        lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
        if text:
            lines = [x for x in lines if text in x.lower()]
        print(f"{len(lines[-n:])} of {len(lines)} lines today{' with ' + repr(text) if text else ''}.")
        for x in lines[-n:]:
            print(x)
    elif cmd == "transmit" and len(argv) == 2 and argv[1] in ("on", "off"):
        set_conf("transmit", argv[1])
        return control(f"transmit {argv[1]}")
    elif cmd in ("status", "beacon"):
        return control(cmd)
    elif cmd == "send" and len(argv) >= 3:
        return control("send " + argv[1] + " " + " ".join(argv[2:]))
    else:
        print(USAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
