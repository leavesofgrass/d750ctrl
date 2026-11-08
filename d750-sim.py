#!/usr/bin/env python3
"""d750-sim: a pretend TM-D750 on a pseudo terminal, for testing d750d and the d750 verbs with no radio.

Prints the device path to use as D750_PORT, then answers Kenwood commands the way the real radio
did on November 7 (ID, FV, TY, BC p1,p2, FQ, MD, SQ, BY, TN, TX, RX) and the way the TH-D74 list
says for the rest (PC, VM, MR, ME, FO, GP, DL, VX, VD, VG, RT, MS, CS, AS, SM, BL, AE).
Unknown commands get "?". GP x,1 starts a stream of GPS sentences, like menu 403 On does.
Options: --busy-flicker makes BY toggle now and then. Written Saturday, November 7, 2026."""
import os, pty, random, select, sys, time

class Sim:
    def __init__(self):
        self.freq = {0: 147040000, 1: 144390000}
        self.offset = {0: 600000, 1: 0}
        self.mode = {0: 0, 1: 0}
        self.sq = {0: 6, 1: 3}
        self.pc = {0: 0, 1: 1}
        self.vm = {0: 0, 1: 0}
        self.mr = {0: 0, 1: 0}
        self.ctrl, self.tx = 1, 1
        self.tn = [2, 1]
        self.keyed = False
        self.gp = [1, 0]
        self.vox = [0, 2, 4]
        self.dl, self.ms, self.cs, self.as_, self.sm = 0, 1, "N0CALL", 1, 0
        self.mem = {0: "0146520000,0000000000,2,2,0,0,0,0,0,0,0,0,0,0,08,08,000,0,CQCQCQ,0,00,0",
                    1: "0144390000,0000000000,2,2,0,0,0,0,0,0,0,0,0,0,08,08,000,0,CQCQCQ,0,00,0"}
        self.busy = {0: 0, 1: 0}
        self.flicker = "--busy-flicker" in sys.argv
        self.last_gps = 0.0

    def fo(self, b):
        return (f"FO {b},{self.freq[b]:010d},{self.offset[b]:010d},2,2,{self.mode[b]},0,0,0,0,0,0,0,0,08,08,000,0,CQCQCQ,0,00")

    def answer(self, line):
        parts = line.strip().split(" ", 1)
        cmd = parts[0].upper(); arg = parts[1] if len(parts) > 1 else ""
        a = arg.split(",") if arg else []
        def band():
            return int(a[0]) if a and a[0] in ("0", "1") else None
        try:
            if cmd == "ID": return "ID TM-D750"
            if cmd == "FV": return "FV 1.03"
            if cmd == "TY": return "TY K,2,1"
            if cmd == "AE": return "AE TM-D750,B5A000001"
            if cmd == "BC":
                if len(a) == 2: self.ctrl, self.tx = int(a[0]), int(a[1])
                elif len(a) == 1: self.ctrl = self.tx = int(a[0])
                return f"BC {self.ctrl},{self.tx}"
            if cmd in ("FQ", "MD", "SQ", "PC", "VM", "MR"):
                b = band()
                if b is None: return "?"
                table = {"FQ": self.freq, "MD": self.mode, "SQ": self.sq, "PC": self.pc, "VM": self.vm, "MR": self.mr}[cmd]
                if len(a) == 2:
                    v = int(a[1])
                    if cmd == "FQ" and not (118e6 <= v <= 524e6): return "N"
                    if cmd == "SQ" and not 0 <= v <= 9: return "N"
                    if cmd == "PC" and not 0 <= v <= 3: return "N"
                    if cmd == "MR":
                        if v not in self.mem: return "N"
                        self.vm[b] = 1; self.freq[b] = int(self.mem[v].split(",")[0])
                    table[b] = v
                if cmd == "FQ": return f"FQ {b},{self.freq[b]:010d}"
                if cmd == "MR": return f"MR {self.mr[b]:03d}" if self.vm[b] == 1 else "N"
                return f"{cmd} {b},{table[b]}"
            if cmd == "BY":
                b = band()
                if b is None: return "?"
                if self.flicker and random.random() < 0.15: self.busy[b] ^= 1
                return f"BY {b},{self.busy[b]}"
            if cmd == "FO":
                b = band()
                return self.fo(b) if b is not None else "?"
            if cmd == "ME":
                if not a: return "?"
                n = int(a[0])
                if len(a) >= 2:
                    if a[1] == "C": self.mem.pop(n, None); return f"ME {n:03d},C"
                    self.mem[n] = ",".join(a[1:]); return f"ME {n:03d}," + self.mem[n]
                return f"ME {n:03d}," + self.mem[n] if n in self.mem else "N"
            if cmd == "TN":
                if len(a) == 2: self.tn = [int(a[0]), int(a[1])]
                return f"TN {self.tn[0]},{self.tn[1]}"
            if cmd == "TX": self.keyed = True; return "TX 1"
            if cmd == "RX": self.keyed = False; return "RX"
            if cmd == "GP":
                if len(a) == 2: self.gp = [int(a[0]), int(a[1])]
                return f"GP {self.gp[0]},{self.gp[1]}"
            if cmd == "DL":
                if a: self.dl = int(a[0])
                return f"DL {self.dl}"
            if cmd == "VX":
                if a: self.vox[0] = int(a[0])
                return f"VX {self.vox[0]}"
            if cmd == "VD":
                if a: self.vox[1] = int(a[0])
                return f"VD {self.vox[1]}"
            if cmd == "VG":
                if a: self.vox[2] = int(a[0])
                return f"VG {self.vox[2]}"
            if cmd == "RT":
                return "RT " + time.strftime("%y%m%d%H%M%S")
            if cmd == "MS":
                if a: self.ms = int(a[0])
                return f"MS {self.ms}"
            if cmd == "CS":
                if a: self.cs = a[0]
                return f"CS {self.cs}"
            if cmd == "AS":
                if a: self.as_ = int(a[0])
                return f"AS {self.as_}"
            if cmd == "SM":
                b = band()
                if b is None: return "?"
                if len(a) == 2: self.sm = int(a[1])
                return f"SM {b},{self.sm}"
            if cmd == "BL": return "BL 3"
            if cmd == "DS": return "DS 1"
        except (ValueError, IndexError):
            return "N"
        return "?"

def main():
    master, slave = pty.openpty()
    path = os.ttyname(slave)
    print(path, flush=True)
    sim = Sim(); buf = b""
    while True:
        r, _, _ = select.select([master], [], [], 0.5)
        if r:
            try:
                data = os.read(master, 256)
            except OSError:
                break
            buf += data
            while b"\r" in buf or b"\n" in buf:
                cut = min(i for i in (buf.find(b"\r"), buf.find(b"\n")) if i >= 0)
                line, buf = buf[:cut].decode(errors="replace"), buf[cut + 1:]
                if line.strip():
                    time.sleep(0.02)
                    os.write(master, (sim.answer(line) + "\r").encode())
        if sim.gp[1] == 1 and time.time() - sim.last_gps > 1.0:
            sim.last_gps = time.time()
            os.write(master, b"$GPGGA,000000.000,,,,,0,0,,,M,,M,,*43\r\n")

if __name__ == "__main__":
    main()
