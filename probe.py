#!/usr/bin/env python3
"""probe: ask the TM-D750, read only, which Kenwood PC commands it answers, through d750d on port 4533.

Writes ~/.config/d750ctrl/commands.txt: one line per command tried, with the answer, the meaning the
community list gives for the TH-D74, and the date. Commands that act (TX, RX, UP, DW, SR,
PS, 0M, 0G) are listed but never sent; the daemon refuses them too.
Usage: probe.py            run and write the table
       probe.py --show     print the last table
Written Saturday, November 7, 2026."""
import os
import socket
import sys
import time

TABLE = os.path.expanduser("~/.config/d750ctrl/commands.txt")
# command: (meaning from the LA3QMA TH-D74 list, arguments to try after the bare form)
MEANINGS = {
    "ID": ("radio model", []), "FV": ("firmware version", []), "TY": ("radio type", []),
    "AE": ("serial number and model", []), "AI": ("auto information on changes", []),
    "AS": ("TNC baud rate", ["0", "1"]), "BC": ("control band and transmit band", []),
    "BE": ("APRS beacon", []), "BL": ("battery level", []), "BS": ("bar antenna", []),
    "BT": ("Bluetooth", []), "BY": ("squelch open or closed, per band", ["0", "1"]),
    "CS": ("callsign", []), "DC": ("D-STAR slot, callsign, message", ["0", "1"]),
    "DL": ("dual or single band", []), "DS": ("D-STAR callsign slot", []),
    "FO": ("VFO channel contents", ["0", "1"]), "FQ": ("frequency, per band", ["0", "1"]),
    "FR": ("FM broadcast radio", []), "FS": ("fine step", []), "FT": ("fine tuning", []),
    "GM": ("radio or GPS", []), "GP": ("internal GPS position", []), "GS": ("GPS sentence", []),
    "IO": ("IF output mode", []), "LC": ("display light", []), "MD": ("mode, per band", ["0", "1"]),
    "ME": ("memory channel contents", ["000", "001"]), "MR": ("memory channel, per band", ["0", "1"]),
    "MS": ("my position", []), "PC": ("output power, per band", ["0", "1"]), "PT": ("beacon control", []),
    "RA": ("attenuator", ["0", "1"]), "RT": ("time", []), "SF": ("receive step size", ["0", "1"]),
    "SH": ("filter cutoff", ["0", "1"]), "SM": ("S meter, per band", ["0", "1"]),
    "SQ": ("squelch level, per band", ["0", "1"]), "TN": ("TNC mode and band", []),
    "VD": ("VOX delay", []), "VG": ("VOX gain", []), "VM": ("memory or VFO, per band", ["0", "1"]),
    "VX": ("VOX on or off", []),
}
NEVER = {"TX": "key the transmitter", "RX": "unkey", "UP": "microphone up key", "DW": "microphone down key",
         "SR": "reset the radio", "PS": "power off", "0M": "programming mode", "0G": "service mode"}


def ask(sock_file, line):
    sock_file.write((line + "\n").encode())
    return sock_file.readline().decode(errors="replace").strip()


def main():
    if "--show" in sys.argv:
        print(open(TABLE, encoding="utf-8").read() if os.path.exists(TABLE) else "no table yet")
        return
    s = socket.create_connection(("127.0.0.1", 4533), timeout=5)
    f = s.makefile("rwb", buffering=0)
    state = ask(f, "state")
    print("daemon:", state)
    if "port closed" in state:
        ident = ask(f, "ID")
        if ident.startswith("ERR"):
            print("Fail: the radio's port is not available:", ident)
            sys.exit(1)
    rows, answered, unknown = [], 0, 0
    for cmd, (meaning, args) in MEANINGS.items():
        for arg in [""] + args:
            line = f"{cmd} {arg}".strip()
            reply = ask(f, line)
            if reply.startswith("ERR"):
                print("Fail:", reply); sys.exit(1)
            verdict = "unknown to the radio" if reply == "?" else ("no answer" if not reply else "answers")
            if reply == "?": unknown += 1
            elif reply: answered += 1
            rows.append((line, reply, verdict, meaning))
            print(f"{line:8} -> {reply!r:40} {verdict}")
            time.sleep(0.05)
    s.close()
    with open(TABLE, "w", encoding="utf-8") as t:
        t.write(f"# TM-D750 PC commands as answered on {time.strftime('%A, %B %-d, %Y, %H:%M')}. Read only probe through d750d.\n")
        t.write("# Meanings are the community's for the TH-D74 and are a guide, not a promise. Columns: command, answer, verdict, meaning\n")
        for line, reply, verdict, meaning in rows:
            t.write(f"{line}\t{reply}\t{verdict}\t{meaning}\n")
        t.write("# Never sent by the probe or allowed on port 4533:\n")
        for cmd, meaning in NEVER.items():
            t.write(f"{cmd}\t-\tnever sent\t{meaning}\n")
    print(f"Pass: {answered} commands answer, {unknown} unknown to this radio; table in {TABLE}")


if __name__ == "__main__":
    main()
