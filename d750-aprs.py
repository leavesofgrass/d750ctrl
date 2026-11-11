"""d750-aprs: APRS through the TM-D750's own TNC in KISS mode.

The daemon reads KISS frames from the radio's TNC port, says each packet as
one plain line, beacons the home station on a timer, sends and acknowledges
APRS messages, and shares the TNC with other programs on KISS TCP.

Nothing transmits until transmitting is switched on. With it off, beacons,
acknowledgements, messages and frames from KISS clients are all held back.

As a receive-only iGate (igate = rx) it also passes what the radio hears to
APRS-IS, by the usual rules, and never transmits anything from the internet.
"""

import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

CONF = os.path.expanduser("~/.config/d750ctrl/aprs.conf")
STATE = os.path.expanduser("~/.local/state/d750ctrl/aprs.json")
LOGDIR = os.path.expanduser("~/.local/share/d750ctrl/log")
MESSAGES = os.path.join(LOGDIR, "messages.jsonl")   # every APRS message to or from us, one JSON event a line
SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache"), "d750-aprs.sock")
VERSION = "0.2.0"
BEACON_WAIT = 60          # seconds to watch APRS-IS for our beacon after it goes out on the air
DIGI_PER_MINUTE = 20      # the digipeater repeats at most this many packets a minute
DIGI_WORDS = {"off": "Digipeater off", "fillin": "Fill-in digipeater", "wide": "Wide digipeater"}
# Uptime Kuma push URLs, written by ~/lab/kuma/setup-kuma.py. Each push is skipped while its file is missing.
PUSH_FILES = {w: f"~/.config/kuma-push-url-aprs-{w}" for w in ("tnc", "igate", "heard", "beacon")}
HEARTBEAT = 300           # seconds between pushes that say the TNC and the iGate link are up


def _quietly(*cmd_or_url):
    """Run a command or fetch a URL in the background; errors are dropped, nothing waits on it."""
    def work():
        try:
            if cmd_or_url[0].startswith("http"):
                urllib.request.urlopen(cmd_or_url[0], timeout=10).read()
            else:
                subprocess.run(cmd_or_url, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


def push_url(base, msg, up=True):
    """A Kuma push URL from the one in the file, with this status and message."""
    return base.split("?", 1)[0] + "?" + urllib.parse.urlencode({"status": "up" if up else "down", "msg": msg, "ping": ""})

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
    "tnc_lines": "raised",
    "igate": "off",
    "aprsis_server": "noam.aprs2.net:14580",
    "aprsis_pass": "",
    "aprsis_beacon": "fallback",
    "digi": "off",
    "digi_aliases": "",
    "digi_max_hops": "2",
    "digi_viscous": "0",
    "digi_dupe": "30",
    "notify": "on",
    "notify_topic": "aprs",
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
    # The settings hold the exact home position: owner only, whatever the umask.
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path + ".tmp", 0o600)
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


# ---------------------------------------------------------------- digipeater

MAX_DIGIS = 8   # AX.25 allows eight digipeater addresses


def next_hop(digis, mycall, mode, aliases=(), max_hops=2):
    """The path after this station repeats a packet, as ([(call, used)], kind), or (None, None) to stay quiet.

    The first unused hop decides:
    - our call, or an alias: it is marked used, an alias replaced by our call. Kind "call".
    - WIDE1-1 (fill-in and wide): replaced by our call, used. Kind "fillin".
    - WIDEn-N, n from 2 up to max_hops (wide only): our call goes in front, used, and N drops by one; at 0
      the WIDEn is used up. With eight hops already, only N drops. Kind "wide".
    Never: a packet we have repeated already, WIDEn-N asking more than max_hops, or N above n.
    """
    me = mycall.upper()
    if mode not in ("fillin", "wide") or any(d.upper() == me and used for d, used in digis):
        return None, None
    i = next((n for n, (_, used) in enumerate(digis) if not used), None)
    if i is None:
        return None, None
    hop = digis[i][0].upper()
    names = {me} | {a.upper() for a in aliases if a}
    if hop in names:
        return digis[:i] + [(mycall, True)] + digis[i + 1:], "call"
    m = re.fullmatch(r"WIDE([1-7])-([1-7])", hop)
    if not m:
        return None, None
    n, left = int(m.group(1)), int(m.group(2))
    if left > n or n > max_hops:
        return None, None
    if n == 1:
        return digis[:i] + [(mycall, True)] + digis[i + 1:], "fillin"
    if mode != "wide":
        return None, None
    left -= 1
    wide = (f"WIDE{n}-{left}" if left else f"WIDE{n}", left == 0)
    new = digis[:i] + [(mycall, True), wide] + digis[i + 1:]
    if len(new) > MAX_DIGIS:
        new = digis[:i] + [wide] + digis[i + 1:]
    return new, "wide"


def frame_key(frame):
    """The same packet by any path: (source, destination, everything after the addresses), or None."""
    i = 0
    while i + 7 <= len(frame):
        last = frame[i + 6] & 0x01
        i += 7
        if last:
            break
    else:
        return None
    if i < 14:
        return None
    return _addr_decode(frame[7:14])[0].upper(), _addr_decode(frame[0:7])[0].upper(), frame[i:]


def digi_frame(frame, mycall, mode, aliases=(), max_hops=2):
    """The whole frame to send when repeating an APRS packet heard, as (frame, kind), or None.

    APRS only: a UI frame with PID F0. Only the digipeater addresses change; the destination, the source
    and everything after the addresses go out byte for byte as heard.
    """
    addrs, i = [], 0
    while i + 7 <= len(frame):
        call, hbit, last = _addr_decode(frame[i:i + 7])
        addrs.append((call, hbit))
        i += 7
        if last:
            break
    else:
        return None
    if len(addrs) < 3 or i + 2 > len(frame) or frame[i] & 0xEF != 0x03 or frame[i + 1] != 0xF0:
        return None
    rest = frame[i:]
    new, kind = next_hop(addrs[2:], mycall, mode, aliases, max_hops)
    if new is None:
        return None
    out = bytearray(frame[:14])
    for n, (d, used) in enumerate(new):
        out += _addr_encode(d, last=n == len(new) - 1, repeated=used)
    return bytes(out) + rest, kind


# ---------------------------------------------------------------- APRS-IS

NOGATE = {"TCPIP", "TCPXX", "NOGATE", "RFONLY"}


def aprsis_passcode(call):
    """The APRS-IS passcode for a call sign: the usual hash of the call without its SSID."""
    c = call.split("-")[0].upper()
    h = 0x73E2
    for i in range(0, len(c), 2):
        h ^= ord(c[i]) << 8
        if i + 1 < len(c):
            h ^= ord(c[i + 1])
    return h & 0x7FFF


def igate_line(source, dest, digis, info, igate_call):
    """The APRS-IS line for a packet heard on the air, or None when the iGate rules say not to gate it.

    Not gated: an empty packet, a query (?), a third-party packet (}), a packet with NUL in it, and one
    whose path names TCPIP, TCPXX, NOGATE or RFONLY. The information field ends at the first line break.
    """
    info = re.split(r"[\r\n]", info, maxsplit=1)[0]
    if not info or info[0] in "?}" or "\x00" in info:
        return None
    if any(d.split("-")[0].upper() in NOGATE for d, _ in digis):
        return None
    last_rep = max((n for n, (_, rep) in enumerate(digis) if rep), default=-1)
    path = [d + ("*" if n == last_rep else "") for n, (d, _) in enumerate(digis)]
    return f"{source}>{','.join([dest] + path + ['qAR', igate_call])}:{info}"


def igate_of(line):
    """Who passed a packet to APRS-IS, from the q construct in its path: (q code, call), or None."""
    header = line.split(":", 1)[0]
    m = re.search(r",(qA[A-Za-z]),([^,]+)", header)
    return (m.group(1), m.group(2)) if m else None


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
    comment = _mice_type_code(info[9:])
    m = re.search(r"(.{3})\}", comment)
    if m:
        try:
            out["alt_m"] = b91(m.group(1)) - 10000
        except ValueError:
            pass
        comment = comment[:m.start()] + " " + comment[m.end():]
    out["comment"] = " ".join(comment.split())
    return out


def _mice_type_code(c):
    """Drop the radio's type code from a Mic-E comment: > and ] for Kenwood, with = ^ or & after
    (TH-D72, TH-D74, TH-D75, TM-D710); ` and ' with two characters after (Yaesu _x, Byonics |3)."""
    if c[:1] in (">", "]"):
        c = c[1:]
        if c[-1:] in ("=", "^", "&"):
            c = c[:-1]
    elif c[:1] in ("`", "'"):
        c = c[1:]
        if len(c) >= 2 and c[-2] in "_|":
            c = c[:-2]
    return c


def _weather(text):
    w = {}
    for key, name in (("c", "dir"), ("s", "wind"), ("g", "gust"), ("t", "temp"), ("h", "humidity")):
        m = re.search(rf"{key}(-?\d{{2,3}})", text)
        if m:
            w[name] = int(m.group(1))
    return w


def parse(source, dest, info):
    """What one APRS packet says, as a dict with a "type"."""
    info = info.rstrip("\r\n")
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
    line = _describe(p, digis, home, units, mycall)
    return " ".join("".join(ch if ch.isprintable() else " " for ch in line).split()) if line else line


def _comment(c):
    """A comment as words: the APRS frequency field (146.520MHz T100 +060) runs straight into the text after it."""
    return re.sub(r"^(\d{3}\.\d{2,3}MHz(?: [A-Za-z]\w{3})?(?: [+-]\d{3})?)(?=\S)", r"\1 ", c)


def _describe(p, digis, home, units, mycall):
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
            parts.append(_comment(p["comment"])[:60])
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
            bits.append(_comment(p["comment"])[:60])
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


def message_parts(text, limit=67):
    """A message as parts of at most limit characters, split between words, without the characters APRS
    keeps for itself (| ~ {) or control characters."""
    text = "".join(ch for ch in text if ch.isprintable()).translate(str.maketrans("|~{", "/-(")).strip()
    parts = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit + 1)
        cut = cut if cut > limit // 2 else limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts + ([text] if text else [])


def parse_tnc2(line):
    """An APRS-IS line, SOURCE>DEST,PATH:info, as (source, dest, [(digi, used)], info), or None."""
    head, sep, info = line.partition(":")
    if not sep or ">" not in head:
        return None
    source, _, rest = head.partition(">")
    dest, *path = rest.split(",")
    return source, dest, [(d.rstrip("*"), d.endswith("*")) for d in path], info


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
        self.last_beacon = float(self.state.get("last_beacon", 0.0))   # kept, so a restart keeps the schedule
        self.started = time.time()
        self.heard = 0
        self.bytes_in = 0
        self.igate = conf["igate"].lower() in ("rx", "on", "yes")
        self.is_writer = None          # the APRS-IS connection, when logged in and verified
        self.is_server = ""
        self.is_task = None
        self.is_problem = None
        self.gated = 0
        self.gate_seen = {}
        self.beacon_watch = None
        self.beacon_misses = 0
        self.watch_up = False
        self.digi = conf["digi"].lower() if conf["digi"].lower() in DIGI_WORDS else "off"
        self.digi_aliases = [a.strip() for a in conf["digi_aliases"].replace(",", " ").split() if a.strip()]
        self.repeated = 0
        self.heard_keys = {}           # packet key -> when first heard, for the duplicate check
        self.digi_pending = {}         # packet key -> timer, while a fill-in repeat waits (viscous delay)
        self.digi_times = []
        self.digi_limit_said = False

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

    def push(self, what, msg, up=True):
        try:
            base = open(os.path.expanduser(PUSH_FILES[what]), encoding="utf-8").read().strip()
        except OSError:
            return
        _quietly(push_url(base, msg, up))

    def notify(self, topic, title, message, priority=3):
        """One ntfy message through the notify command, when notify = on and the command is there."""
        exe = shutil.which("notify") or os.path.expanduser("~/.local/bin/notify")
        if self.conf["notify"].lower() in ("on", "yes") and os.path.exists(exe):
            _quietly(exe, topic, title, message, str(priority))

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
            self.state["last_beacon"] = self.last_beacon
            self._save_state()
            self.say(f"Beacon sent: {self.call} at home, path {','.join(self.path)}")
            mode = self.conf["aprsis_beacon"].lower()
            if self.is_writer and mode in ("on", "yes"):
                self._is_send(self._direct_beacon())
            elif self.watch_up and mode in ("watch", "fallback"):
                # Watch APRS-IS for the beacon gated from the air; the radio never hears its own.
                token = self.beacon_watch = time.time()
                asyncio.get_running_loop().call_later(BEACON_WAIT, self._beacon_check, token)

    def msg_event(self, **event):
        """One line in the message history that aprschat reads: time, direction, call, and what happened."""
        event = {"t": round(time.time(), 1), **event}
        os.makedirs(LOGDIR, exist_ok=True)
        with open(MESSAGES, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def send_message(self, to, text):
        """Queue a message, in parts when it is long; the message numbers, one per part."""
        ids = []
        for part in message_parts(text):
            self.state["msgno"] = self.state.get("msgno", 0) % 999 + 1
            msgid = str(self.state["msgno"])
            self.outbox[msgid] = {"to": to.upper(), "text": part, "tries": 0, "next": time.time()}
            self.msg_event(dir="out", call=to.upper(), id=msgid, text=part, state="queued")
            wait = "" if self.transmit else " It waits until transmitting is on."
            self.say(f"Message to {to.upper()} queued: {part}.{wait}")
            ids.append(msgid)
        self._save_state()
        return ids

    def _ack(self, to, msgid, via="rf"):
        """Acknowledge the way the message came: on the air, or through APRS-IS."""
        info = f":{to.upper():<9}:ack{msgid}"
        if via == "is" and self.is_writer:
            self._is_send(f"{self.call}>{self.conf['tocall']},TCPIP*:{info}")
        else:
            self.send_frame(info, why=f"the acknowledgement to {to}")

    # -- receiving
    def on_frame(self, frame, from_client=None):
        note = self._digi_consider(frame)
        d = ax25_decode(frame)
        if not d:
            return
        source, dest, digis, info = d
        self.raw("RX " + tnc2(source, dest, digis, info))
        self.heard += 1
        if time.time() - getattr(self, "_heard_pushed", 0) > 60:
            self._heard_pushed = time.time()
            self.push("heard", f"heard {source}")
        if self.is_writer:
            self._gate(source, dest, digis, info)
        p = parse(source, dest, info)
        if p["type"] in ("message", "ack", "rej") and p.get("to", "").upper() in (self.call, self.call.split("-")[0]):
            self._for_us(p)
            return
        line = describe(p, digis, self.home, self.units, self.call)
        if line:
            self.say(line + (f", {note}" if note else ""))

    def _for_us(self, p, via="rf"):
        src = p["source"].upper()
        if p["type"] == "message":
            key = (src, p.get("id"), p["text"])
            fresh = key not in self.seen_msgs or time.time() - self.seen_msgs[key] > 1800
            self.seen_msgs[key] = time.time()
            if fresh:
                self.say(f"Message from {src}{' through the internet' if via == 'is' else ''}: {p['text']}")
                self.msg_event(dir="in", call=src, id=p.get("id"), text=p["text"], via=via)
                self.notify(self.conf["notify_topic"], f"APRS from {src}", p["text"], 4)
            if p.get("id"):
                self._ack(src, p["id"], via)
        elif p["type"] == "ack":
            m = self.outbox.pop(p["id"], None)
            if m:
                self.say(f"Message to {m['to']} acknowledged")
                self.msg_event(dir="out", call=m["to"], id=p["id"], state="acked")
        elif p["type"] == "rej":
            m = self.outbox.pop(p["id"], None)
            if m:
                self.say(f"Message to {m['to']} was refused")
                self.msg_event(dir="out", call=m["to"], id=p["id"], state="rejected")

    def _from_is(self, line):
        """A line from APRS-IS: a message, acknowledgement or refusal for us, sent through the internet."""
        d = parse_tnc2(line)
        if not d:
            return
        p = parse(d[0], d[1], d[3])
        if p["type"] in ("message", "ack", "rej") and p.get("to", "").upper() in (self.call, self.call.split("-")[0]):
            self.raw("IS in " + line)
            self._for_us(p, via="is")

    # -- the digipeater
    def _digi_consider(self, frame):
        """Decide on repeating a frame just heard; a few words for its line when it is repeated."""
        key = frame_key(frame)
        if not key:
            return None
        now = time.time()
        keep = max(5, int(self.conf["digi_dupe"]))
        self.heard_keys = {k: t for k, t in self.heard_keys.items() if now - t < keep}
        waiting = self.digi_pending.pop(key, None)
        if waiting:
            waiting.cancel()
            self.raw(f"DIGI skipped {key[0]}: another station repeated it first")
        seen = key in self.heard_keys
        self.heard_keys.setdefault(key, now)
        if self.digi == "off" or seen or key[0] == self.call.upper() or not (self.transmit and self.serial):
            return None
        out = digi_frame(frame, self.call, self.digi, self.digi_aliases, int(self.conf["digi_max_hops"]))
        if not out:
            return None
        new, kind = out
        wait = int(self.conf["digi_viscous"])
        if kind == "fillin" and wait > 0:
            self.digi_pending[key] = asyncio.get_running_loop().call_later(wait, self._digi_send, key, new)
            return f"repeating in {wait} seconds unless another digipeater does"
        return "repeated" if self._digi_send(None, new) else None

    def _digi_send(self, key, frame):
        if key is not None:
            self.digi_pending.pop(key, None)
        now = time.time()
        self.digi_times = [t for t in self.digi_times if now - t < 60]
        if len(self.digi_times) >= DIGI_PER_MINUTE:
            if not self.digi_limit_said:
                self.say(f"The digipeater repeated {DIGI_PER_MINUTE} packets in the last minute, its limit. "
                         "It skips packets until the minute is over.")
                self.digi_limit_said = True
            return False
        self.digi_limit_said = False
        if not (self.transmit and self.serial):
            return False
        self.serial.write(kiss_encode(frame))
        self.digi_times.append(now)
        self.repeated += 1
        d = ax25_decode(frame)
        self.raw("DIGI " + (tnc2(*d) if d else frame.hex()))
        for w in list(self.clients):
            self._client_write(w, kiss_encode(frame))
        return True

    def _digi_state(self):
        if self.digi == "off":
            return "Digipeater off."
        tail = "" if self.transmit else ", but transmitting is off, so it repeats nothing"
        return f"{DIGI_WORDS[self.digi]} on{tail}. {self.repeated} repeated."

    # -- the iGate
    def _direct_beacon(self):
        return f"{self.call}>{self.conf['tocall']},TCPIP*:{beacon_info(self.conf)}"

    def _own_seen(self, line):
        """Our own call came back from APRS-IS: an iGate passed the beacon on."""
        if not self.beacon_watch:
            return
        self.beacon_watch = None
        self.beacon_misses = 0
        who = igate_of(line)
        self.say(f"Our beacon reached APRS-IS through {who[1]}." if who else "Our beacon reached APRS-IS.")
        self.push("beacon", f"beacon carried by {who[1]}" if who else "beacon on APRS-IS")

    def _beacon_check(self, token):
        if self.beacon_watch != token:
            return
        self.beacon_watch = None
        self.beacon_misses += 1
        if self.conf["aprsis_beacon"].lower() == "fallback" and self.is_writer and self._is_send(self._direct_beacon()):
            self.say(f"No iGate passed our beacon to APRS-IS in {BEACON_WAIT} seconds. Sent it there directly.")
        else:
            self.say(f"No iGate passed our beacon to APRS-IS in {BEACON_WAIT} seconds.")
        if self.beacon_misses == 2:
            self.say("Two beacons in a row reached no iGate. The radio may not be transmitting; "
                     "if it restarted by itself, power cycle it.")

    def _gate(self, source, dest, digis, info):
        line = igate_line(source, dest, digis, info, self.call)
        if not line:
            return
        now = time.time()
        self.gate_seen = {k: t for k, t in self.gate_seen.items() if now - t < 30}
        key = (source.upper(), line.split(":", 1)[1])
        if key in self.gate_seen:
            return
        self.gate_seen[key] = now
        if self._is_send(line):
            self.gated += 1

    def _is_send(self, line):
        try:
            self.is_writer.write(line.encode("latin-1", "replace") + b"\r\n")
        except Exception:
            return False
        self.raw("IS " + line)
        return True

    def _is_say(self, problem):
        """Say an APRS-IS problem once, not on every retry."""
        if problem != self.is_problem:
            self.say(problem)
            self.is_problem = problem

    async def _beacon_watcher(self):
        """Read-only APRS-IS link that sees our own packets: APRS-IS never sends a client the packets from
        its own login call, so this logs in as N0CALL, read only, with a filter for our call."""
        host, _, port = self.conf["aprsis_server"].rpartition(":")
        wait = 10
        while True:
            writer = None
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), 30)
                writer.write(f"user N0CALL pass -1 vers d750-aprs {VERSION} filter b/{self.call}\r\n".encode())
                await writer.drain()
                self.watch_up = True
                wait = 10
                while True:
                    raw = await asyncio.wait_for(reader.readline(), 120)
                    if not raw:
                        raise ConnectionError("the server closed the connection")
                    text = raw.decode("latin-1").strip()
                    if text.upper().startswith(self.call + ">"):
                        self.raw("IS heard " + text)
                        self._own_seen(text)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            self.watch_up = False
            if writer:
                try:
                    writer.close()
                except Exception:
                    pass
            await asyncio.sleep(wait)
            wait = min(wait * 2, 600)

    def igate_start(self):
        if self.is_task is None or self.is_task.done():
            self.is_task = asyncio.get_running_loop().create_task(self._aprsis())

    def igate_stop(self):
        if self.is_task:
            self.is_task.cancel()
            self.is_task = None
        if self.is_writer:
            try:
                self.is_writer.close()
            except Exception:
                pass
        self.is_writer = None
        self.is_problem = None

    async def _aprsis(self):
        host, _, port = self.conf["aprsis_server"].rpartition(":")
        passcode = self.conf["aprsis_pass"].strip()
        if not passcode:
            self.say("The iGate is on, but aprsis_pass is not set in aprs.conf, so nothing is gated.")
            return
        wait = 10
        while True:
            writer = None
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), 30)
                await asyncio.wait_for(reader.readline(), 30)
                base = self.call.split("-")[0]
                # g/ brings messages addressed to us that were sent through the internet, aprs.fi for one.
                writer.write(f"user {self.call} pass {passcode} vers d750-aprs {VERSION} filter g/{self.call}/{base}\r\n".encode())
                await writer.drain()
                while True:
                    # Servers send a keepalive line every 20 seconds; two minutes of silence is a dead link.
                    raw = await asyncio.wait_for(reader.readline(), 120)
                    if not raw:
                        raise ConnectionError("the server closed the connection")
                    text = raw.decode("latin-1").strip()
                    if text and not text.startswith("#"):
                        self._from_is(text)
                        continue
                    if not text.startswith("# logresp"):
                        continue
                    if " verified" not in text:
                        self._is_say("APRS-IS did not verify the passcode, so nothing is gated. Check aprsis_pass.")
                        writer.close()
                        await asyncio.sleep(1800)
                        break
                    self.is_server = text.rsplit("server", 1)[-1].strip() if "server" in text else host
                    self.is_writer = writer
                    self.is_problem = None
                    wait = 10
                    self.say(f"iGate on: passing what the radio hears to APRS-IS, server {self.is_server}.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                why = str(e) or type(e).__name__
                self._is_say(f"Lost APRS-IS ({why}). Trying again, every few minutes at most.")
            self.is_writer = None
            if writer:
                try:
                    writer.close()
                except Exception:
                    pass
            await asyncio.sleep(wait)
            wait = min(wait * 2, 600)

    # -- the loops
    async def run(self):
        import serial
        self.say(f"d750-aprs for {self.call} starting. Transmitting is {'on' if self.transmit else 'off'}.")
        await self._start_servers()
        asyncio.get_running_loop().create_task(self._timers())
        if self.igate:
            self.igate_start()
        if self.conf["aprsis_beacon"].lower() in ("watch", "fallback"):
            asyncio.get_running_loop().create_task(self._beacon_watcher())
        if self.digi != "off":
            self.say(self._digi_state())
        while True:
            try:
                s = serial.Serial()
                s.port, s.baudrate, s.timeout = self.conf["tnc"], 9600, 0
                # DTR and RTS as most serial programs set them. d750d has opened this radio's ports with
                # both raised for days without keying it; "low" holds them down instead.
                up = self.conf.get("tnc_lines", "raised") != "low"
                s.dtr, s.rts = up, up
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
            if getattr(self, "_port_lost", False):
                self.say(f"Listening on {self.conf['tnc']} again. If the radio restarted by itself, power cycle it: "
                         "after one such restart it received but did not transmit until it was switched off and on.")
                self._port_lost = False
            else:
                self.say(f"Listening on {self.conf['tnc']}.")
            lost = asyncio.get_running_loop().create_future()
            loop = asyncio.get_running_loop()

            def readable():
                try:
                    data = s.read(4096)
                except Exception:
                    data = None
                if data:
                    self.bytes_in += len(data)
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
            self._port_lost = True
            self.say("Lost the TNC port; the radio may have restarted or been unplugged. Trying again in 10 seconds.")
            if time.time() - getattr(self, "_lost_told", 0) > 600:
                self._lost_told = time.time()
                self.notify("alerts", "TM-D750 dropped off USB",
                            f"d750-aprs lost the TNC port at {datetime.now():%H:%M}. If the radio restarted by itself, "
                            "power cycle it: after one such restart it received but did not transmit.", 4)
            await asyncio.sleep(10)

    async def _timers(self):
        interval = max(10, int(self.conf["interval"])) * 60
        beat = 0.0
        while True:
            now = time.time()
            if now - beat >= HEARTBEAT:
                beat = now
                if self.serial:
                    self.push("tnc", f"TNC connected, {self.heard} heard")
                if self.is_writer:
                    self.push("igate", f"server {self.is_server}, {self.gated} gated")
            if self.transmit and self.home and self.serial:
                # Due by the kept time of the last beacon; 20 seconds after a start to let the TNC settle.
                if now - self.last_beacon >= interval and now - self.started > 20:
                    self.beacon()
            for msgid, m in list(self.outbox.items()):
                if self.transmit and now >= m["next"]:
                    if m["tries"] >= 5:
                        self.outbox.pop(msgid)
                        self.say(f"Message to {m['to']} was not acknowledged after 5 tries")
                        self.msg_event(dir="out", call=m["to"], id=msgid, state="failed")
                        self.notify(self.conf["notify_topic"], f"APRS message to {m['to']} not acknowledged",
                                    f"After 5 tries: {m['text']}", 3)
                        continue
                    if self.send_frame(message_info(m["to"], m["text"], msgid), why=f"the message to {m['to']}"):
                        m["tries"] += 1
                        m["next"] = now + 30 * (2 ** (m["tries"] - 1))
                        self.say(f"Message to {m['to']} sent, try {m['tries']}")
                        self.msg_event(dir="out", call=m["to"], id=msgid, state="sent", tries=m["tries"])
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
        told = False
        k = KissReader()
        try:
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(4096), 3 if not told else None)
                except asyncio.TimeoutError:
                    data = None
                if not told and (data or data is None):
                    # A port check (Uptime Kuma) connects and leaves at once; only a program that stays or sends is said.
                    self.say(f"KISS program connected from {who}.")
                    told = True
                if data is None:
                    continue
                if not data:
                    break
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
            if told:
                self.say(f"KISS program from {who} disconnected.")

    async def _control(self, reader, writer):
        line = (await reader.readline()).decode("utf-8", "replace").strip()
        cmd, _, rest = line.partition(" ")
        reply = "Unknown command."
        if cmd == "status":
            up = int((time.time() - self.started) / 60)
            reply = (f"{self.call}: TNC {'connected' if self.serial else 'not connected'}, transmitting "
                     f"{'on' if self.transmit else 'off'}, {self.heard} packet{'' if self.heard == 1 else 's'} heard in {up} minute{'' if up == 1 else 's'} from {self.bytes_in} bytes, "
                     f"{len(self.clients)} KISS programs, {len(self.outbox)} messages waiting. "
                     + (f"iGate on, server {self.is_server}, {self.gated} gated." if self.is_writer else
                        "iGate on, not connected to APRS-IS." if self.igate else "iGate off.")
                     + " " + self._digi_state())
        elif cmd == "beacon":
            self.beacon("by hand")
            reply = "Done."
        elif cmd == "digi":
            if rest in DIGI_WORDS:
                self.digi = rest
                for h in self.digi_pending.values():
                    h.cancel()
                self.digi_pending = {}
                self.say(self._digi_state())
            reply = self._digi_state()
        elif cmd == "igate":
            self.igate = rest == "on"
            if self.igate:
                self.igate_start()
            else:
                self.igate_stop()
                self.say("iGate off.")
            reply = f"iGate {'on' if self.igate else 'off'}."
        elif cmd == "transmit":
            self.transmit = rest == "on"
            self.say(f"Transmitting is now {'on' if self.transmit else 'off'}.")
            reply = f"Transmitting is {'on' if self.transmit else 'off'}."
        elif cmd == "send":
            to, _, text = rest.partition(" ")
            if to and text:
                ids = self.send_message(to, text)
                reply = (f"Queued as {ids[0]}." if len(ids) == 1 else
                         f"Queued in {len(ids)} parts, as {', '.join(ids)}.") if ids else "Nothing to send."
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
  d750-aprs igate on|off       pass what the radio hears to APRS-IS (receive-only; needs aprsis_pass)
  d750-aprs digi off|fillin|wide   repeat APRS packets: fillin for WIDE1-1 and our call, wide also WIDEn-N
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
    elif cmd == "digi" and len(argv) == 2 and argv[1] in DIGI_WORDS:
        set_conf("digi", argv[1])
        return control(f"digi {argv[1]}")
    elif cmd == "igate" and len(argv) == 2 and argv[1] in ("on", "off"):
        set_conf("igate", "rx" if argv[1] == "on" else "off")
        return control(f"igate {argv[1]}")
    elif cmd in ("status", "beacon"):
        return control(cmd)
    elif cmd == "send" and len(argv) >= 3:
        return control("send " + argv[1] + " " + " ".join(argv[2:]))
    else:
        print(USAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
