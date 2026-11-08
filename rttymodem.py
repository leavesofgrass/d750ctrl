#!/usr/bin/env python3
"""rttymodem: Baudot RTTY, 45.45 baud, 170 Hz shift, mark 2125 Hz and space 2295 Hz, in plain Python with numpy.

  rttymodem.py tx "TEXT" OUT.wav       encode text to a wav file, 48 kHz mono
  rttymodem.py rx IN.wav               decode a wav file and print the text
  rttymodem.py selftest                encode, add noise, decode, compare

Options: --baud 45.45|50|75, --shift 170|450|850, --mark 2125, --reverse (swap mark and space), --rate 48000.
The decoder measures the energy at the mark and space tones over each bit time and reads the Baudot frame
like a UART: one start bit, five data bits, one and a half stop bits. No external code. MIT, 2026."""
import argparse
import math
import sys
import wave

import numpy as np

LTRS = {"A": 0x03, "B": 0x19, "C": 0x0E, "D": 0x09, "E": 0x01, "F": 0x0D, "G": 0x1A, "H": 0x14, "I": 0x06, "J": 0x0B,
        "K": 0x0F, "L": 0x12, "M": 0x1C, "N": 0x0C, "O": 0x18, "P": 0x16, "Q": 0x17, "R": 0x0A, "S": 0x05, "T": 0x10,
        "U": 0x07, "V": 0x1E, "W": 0x13, "X": 0x1D, "Y": 0x15, "Z": 0x11, "\r": 0x08, "\n": 0x02, " ": 0x04}
FIGS = {"-": 0x03, "?": 0x19, ":": 0x0E, "$": 0x09, "3": 0x01, "!": 0x0D, "&": 0x1A, "#": 0x14, "8": 0x06, "'": 0x0B,
        "(": 0x0F, ")": 0x12, ".": 0x1C, ",": 0x0C, "9": 0x18, "0": 0x16, "1": 0x17, "4": 0x0A, "\x07": 0x05, "5": 0x10,
        "7": 0x07, ";": 0x1E, "2": 0x13, "/": 0x1D, "6": 0x15, '"': 0x11, "\r": 0x08, "\n": 0x02, " ": 0x04}
SHIFT_LTRS, SHIFT_FIGS = 0x1F, 0x1B
R_LTRS = {v: k for k, v in LTRS.items()}
R_FIGS = {v: k for k, v in FIGS.items()}


def text_to_codes(text):
    """Baudot codes with shift characters where needed. Unknown characters become spaces."""
    codes = [SHIFT_LTRS, SHIFT_LTRS]
    figs = False
    for ch in text.upper().replace("\n", "\r\n"):
        if ch in LTRS and not (figs and ch in FIGS and ch not in " \r\n"):
            if figs and ch not in " \r\n":
                codes.append(SHIFT_LTRS); figs = False
            codes.append(LTRS[ch])
        elif ch in FIGS:
            if not figs:
                codes.append(SHIFT_FIGS); figs = True
            codes.append(FIGS[ch])
        else:
            codes.append(LTRS[" "])
    codes += [LTRS["\r"], LTRS["\n"], SHIFT_LTRS]
    return codes


def encode(text, rate=48000, baud=45.45, mark=2125.0, shift=170.0, reverse=False, lead=0.5, tail=0.3):
    """Samples of the transmission as float32 in -1..1: idle mark, then each character as 1 start, 5 data, 1.5 stop."""
    space = mark + shift
    if reverse:
        mark, space = space, mark
    bit = rate / baud
    bits = [1.0] * int(lead * baud)               # idle on mark
    for code in text_to_codes(text):
        bits.append(0.0)                           # start bit: space
        for i in range(5):
            bits.append(1.0 if (code >> i) & 1 else 0.0)   # least significant bit first
        bits.append(1.0); bits.append(0.5)         # one and a half stop bits on mark
    bits += [1.0] * int(tail * baud)
    # expand bits to samples with continuous phase
    total = 0.0
    samples = []
    phase = 0.0
    for b in bits:
        n = bit if b != 0.5 else bit / 2
        level = 1.0 if b != 0.0 else 0.0
        total += n
        count = int(round(total)) - len(samples)
        f = mark if level else space
        t = np.arange(count) / rate
        samples.extend(np.sin(phase + 2 * math.pi * f * t))
        phase = (phase + 2 * math.pi * f * count / rate) % (2 * math.pi)
    return (np.array(samples, dtype=np.float32) * 0.6)


def write_wav(path, samples, rate=48000):
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def read_wav(path):
    with wave.open(path) as w:
        rate = w.getframerate(); n = w.getnframes(); ch = w.getnchannels(); width = w.getsampwidth()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError("16 bit wav expected")
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, rate


def tone_levels(samples, rate, freq, window):
    """Goertzel energy of one tone over consecutive windows of `window` samples."""
    n = len(samples) // window
    seg = samples[:n * window].reshape(n, window)
    t = np.arange(window) / rate
    ref = np.exp(-2j * math.pi * freq * t)
    return np.abs(seg @ ref)


def decode(samples, rate=48000, baud=45.45, mark=2125.0, shift=170.0, reverse=False):
    """Text from samples. Works on clean and moderately noisy audio of a steady signal."""
    space = mark + shift
    if reverse:
        mark, space = space, mark
    sub = 8                                        # eight decisions per bit
    window = max(8, int(round(rate / baud / sub)))
    m = tone_levels(samples, rate, mark, window)
    s = tone_levels(samples, rate, space, window)
    level = (m - s) / (m + s + 1e-9)               # +1 mark, -1 space
    out = []
    figs = False
    i = 0
    n = len(level)
    while i + 7 * sub < n:
        if level[i] < 0 and (i == 0 or level[i - 1] >= 0):   # a falling edge: start bit begins
            # confirm the start bit at its middle
            if level[i + sub // 2] >= 0:
                i += 1; continue
            code = 0
            for b in range(5):
                centre = i + sub // 2 + (b + 1) * sub
                if level[centre] >= 0:
                    code |= 1 << b
            stop_centre = i + sub // 2 + 6 * sub
            if level[min(stop_centre, n - 1)] < 0:          # no stop bit: not a frame
                i += 1; continue
            if code == SHIFT_LTRS: figs = False
            elif code == SHIFT_FIGS: figs = True
            else:
                table = R_FIGS if figs else R_LTRS
                out.append(table.get(code, ""))
            i += int(7.5 * sub) - 1
        else:
            i += 1
    return "".join(out).replace("\r", "")


def main():
    ap = argparse.ArgumentParser(description="Baudot RTTY encoder and decoder")
    ap.add_argument("cmd", choices=["tx", "rx", "selftest"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--baud", type=float, default=45.45)
    ap.add_argument("--shift", type=float, default=170.0)
    ap.add_argument("--mark", type=float, default=2125.0)
    ap.add_argument("--reverse", action="store_true")
    ap.add_argument("--rate", type=int, default=48000)
    a = ap.parse_args()
    kw = dict(rate=a.rate, baud=a.baud, mark=a.mark, shift=a.shift, reverse=a.reverse)
    if a.cmd == "tx":
        if len(a.args) != 2: print("usage: rttymodem.py tx TEXT OUT.wav"); return 2
        write_wav(a.args[1], encode(a.args[0], **kw), a.rate); print(f"wrote {a.args[1]}"); return 0
    if a.cmd == "rx":
        if len(a.args) != 1: print("usage: rttymodem.py rx IN.wav"); return 2
        samples, rate = read_wav(a.args[0]); kw["rate"] = rate
        print(decode(samples, **kw)); return 0
    text = "CQ CQ DE KD7SWH KD7SWH K 73 TEST 12345 (NTS) ?"
    clean = encode(text, **kw)
    rng = np.random.default_rng(1)
    noisy = clean + rng.normal(0, 0.25, len(clean)).astype(np.float32)
    got_clean = decode(clean, **kw).strip(); got_noisy = decode(noisy, **kw).strip()
    print("sent:  ", text); print("clean: ", got_clean); print("noisy: ", got_noisy)
    ok = got_clean == text and got_noisy == text
    print("Pass: rtty modem round trip" if ok else "Fail: rtty modem round trip"); return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
