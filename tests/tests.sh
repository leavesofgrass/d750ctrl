#!/bin/bash
# tests.sh: run every d750 verb against the simulator (ports 4542 and 4543) and check the answers.
# Start the test bed first: tests/test-env.sh. Written Saturday, November 7, 2026.
export D750_CMD_PORT=4543 D750_PTT_PORT=4542 D750_LOG_DIR="$HOME/.local/share/d750ctrl/log/test"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/d750ctrl-tests.XXXXXX"); trap 'rm -rf "$TMP"' EXIT
# the tests get a settings folder of their own, so the operator's fixup.conf and call sign stay out of them
export D750_CONF_DIR="$TMP/conf"; mkdir -p "$D750_CONF_DIR"
printf 'TNC=2,1\nSQUELCH_B=3\nGPS_OUTPUT=0\n' > "$D750_CONF_DIR/fixup.conf"
[ -f "$HOME/.config/d750ctrl/commands.txt" ] && cp "$HOME/.config/d750ctrl/commands.txt" "$D750_CONF_DIR/"
pass=0; fail=0
check() {  # check "name" "expected substring" command...
  local name=$1 want=$2; shift 2; local out
  out=$("$@" 2>&1); rc=$?
  if [[ $out == *"$want"* ]]; then pass=$((pass + 1)); printf 'Pass: %s\n' "$name"; else fail=$((fail + 1)); printf 'Fail: %s\n  wanted: %s\n  got (rc %s): %s\n' "$name" "$want" "$rc" "$(printf '%s' "$out" | head -4 | tr '\n' '|')"; fi
}
HERE=$(dirname "$(readlink -f "$0")")
TOP=$(dirname "$HERE")
LOG="$D750_LOG_DIR/d750d-$(date +%F).txt"
lines() { wc -l < "$LOG" 2>/dev/null || echo 0; }
logged() {  # logged TEXT FROM : is TEXT in the test daemon's log after line FROM?
  if tail -n +"$(( $2 + 1 ))" "$LOG" | grep -qF -- "$1"; then echo "logged: $1"; else echo "not logged: $1"; fi
}
check "state" "port open" d750 state
check "status bands" "band B: 144.390 MHz, FM, squelch 3" d750 status
check "status tnc" "tnc: KISS on band B" d750 status
check "raw ID" "ID TM-D750" d750 raw ID
check "raw refuses TX" "not allowed" d750 raw TX
check "raw refuses BE, which can send a beacon" "not allowed" d750 raw BE
check "freq dry run" "would send: FQ 0,0146520000" d750 freq A 146.520 -n
check "freq set" "after: band A 146.520 MHz" d750 freq A 146.520
check "freq refused out of band" "refused" d750 freq A 27.000
check "band" "control and transmit band: A" d750 band A
check "band back" "control and transmit band: B" d750 band B
check "mode" "band A mode: NFM" d750 mode A nfm
check "mode back" "band A mode: FM" d750 mode A fm
check "squelch" "band B squelch: 4" d750 squelch B 4
check "squelch usage" "usage" d750 squelch B 12
check "power" "band A power: low" d750 power A low
check "busy" "band B:" d750 busy B
check "watch" "squelch opened" d750 watch B 3
check "tnc off" "after: off on band B" d750 tnc off
check "tnc kiss" "after: KISS on band B" d750 tnc kiss B
check "mem list" "001: 144.390 MHz, FM" d750 mem list 0 5
check "mem show" "frequency: 146.520 MHz" d750 mem show 0
check "mem goto" "band A on channel 001, now 144.390 MHz" d750 mem goto A 1
check "mem export" "exported 2 channels" d750 mem export $TMP/mem-test.txt 0 9
check "mem import dry" "would send: ME 000" d750 mem import $TMP/mem-test.txt -n
check "mem import" "2 channels written, 0 refused" d750 mem import $TMP/mem-test.txt
check "gps read" "GPS on; PC output off" d750 gps
gps_from=$(lines)
check "gps output on" "GPS PC output: on" d750 gps output on
sleep 2.5
check "state sees the stream" "unsolicited bytes seen" d750 state
check "fixup turns it off" "Fixed: GPS PC output now 0" d750 fixup
d750 squelch B 5 >/dev/null
check "fixup squelch" "Fixed: band B squelch 3" d750 fixup
check "fixup clean" "Pass: band B squelch 3" d750 fixup
check "vox read" "VOX off" d750 vox
check "vox on" "VOX: on" d750 vox on
check "vox off" "VOX: off" d750 vox off
check "clock" "radio clock: 20" d750 clock
check "clock set dry" "would send: RT" d750 clock set -n
check "ptt off" "unkey: RPRT 0" d750 ptt off
check "lock" "locked" d750 lock
check "ptt refused while locked" "RPRT -1" bash -c 'printf "T 1\n" | nc -w 2 127.0.0.1 4542'
check "unlock" "unlocked" d750 unlock
check "ptt key and unkey" "RPRT 0" bash -c 'printf "T 1\nT 0\n" | nc -w 2 127.0.0.1 4542 | tail -1'
# d750-keyer's Keyed, as d750-sstv and d750-rtty use it: keyed half a second into the block, unkeyed after it
keyed=$(python3 -I -B - "$TOP/d750-keyer.py" 2>&1 <<'PY'
import importlib.util, socket, sys, time
spec = importlib.util.spec_from_file_location("keyer", sys.argv[1]); k = importlib.util.module_from_spec(spec); spec.loader.exec_module(k)
if k.PTT_PORT != 4542: print(f"not the test port: {k.PTT_PORT}"); sys.exit(1)    # never key anything but the simulator
def keyed():
    s = socket.create_connection(("127.0.0.1", 4543), timeout=5); s.sendall(b"state\n")
    r = s.makefile("rb").readline().decode().strip(); s.close()
    return "not keyed" if "not keyed" in r else "keyed" if "; keyed;" in r else r
with k.Keyed():
    time.sleep(0.5); inside = keyed()
time.sleep(0.3)
print(f"inside: {inside}"); print(f"after: {keyed()}")
PY
)
check "Keyed holds the radio keyed for the whole block" "inside: keyed" printf '%s\n' "$keyed"
check "Keyed unkeys at the end of the block" "after: not keyed" printf '%s\n' "$keyed"
check "log" "key in" d750 log 40
# d750d's log since November 11: reads the radio answers stay out; sets, refusals, refused keying and bytes sent unasked stay in
from=$(lines)
for c in TY FV 'FQ 0' 'BY 1' VX 'SQ 1,5' 'SQ 1,12' TX 'SQ 1,3'; do d750 raw "$c" >/dev/null 2>&1; done
check "log leaves out a read the radio answered" "not logged: cmd 'TY'" logged "cmd 'TY'" "$from"
check "log leaves out the firmware read" "not logged: cmd 'FV'" logged "cmd 'FV'" "$from"
check "log leaves out band reads" "not logged: cmd 'FQ 0'" logged "cmd 'FQ 0'" "$from"
check "log leaves out busy reads" "not logged: cmd 'BY 1'" logged "cmd 'BY 1'" "$from"
check "log keeps a set" "logged: cmd 'SQ 1,5' -> 'SQ 1,5'" logged "cmd 'SQ 1,5' -> 'SQ 1,5'" "$from"
check "log keeps a refusal" "logged: cmd 'SQ 1,12' -> 'N'" logged "cmd 'SQ 1,12' -> 'N'" "$from"
check "log keeps a refused TX" "logged: refused 'TX'" logged "refused 'TX'" "$from"
check "log keeps the GPS bytes sent unasked" "logged: unsolicited" logged "unsolicited" "$gps_from"
check "vara status" "xara:" d750 vara status
printf 'mycall = N0CALL-7\n' > "$D750_CONF_DIR/d750ctrl.conf"
check "vara cq dry run, VarAC CQ frame" "would send one VarAC cq frame through xara: CQFRAME N0CALL" d750 -n vara cq
check "vara beacon dry run, VarAC beacon frame" "CQFRAME N0CALL-9" d750 -n vara beacon
check "doctor runs" "pass," d750 doctor
check "doctor shows the firmware" "Pass: radio firmware 1.03, type K,2,1" d750 doctor
# hamlib's NET rigctl client against the daemon: the open handshake, then reads and writes on the transmit band (B on the simulator)
R="rigctl -m 2 -r 127.0.0.1:4542"
check "rigctl handshake" "done" bash -c 'printf "\\chk_vfo\n\\dump_state\n" | nc -w 2 127.0.0.1 4542'
check "rigctl frequency" "144390000" $R f
check "rigctl mode" "FM" $R m
check "rigctl vfo is the transmit band" "VFOB" $R v
check "rigctl ptt reads" "0" $R t
check "rigctl set frequency" "FQ 1,0146520000" bash -c "$R F 146520000 && d750 raw 'FQ 1'"
check "rigctl set mode narrow" "MD 1,1" bash -c "$R M FMN 0 && d750 raw 'MD 1'"
check "rigctl set mode back" "MD 1,0" bash -c "$R M FM 0 && d750 raw 'MD 1'"
check "rigctl power level" "0.5" $R l RFPOWER
check "rigctl set power" "PC 1,2" bash -c "$R L RFPOWER 0.2 && d750 raw 'PC 1'"
check "rigctl power back" "PC 1,1" bash -c "$R L RFPOWER 0.5 && d750 raw 'PC 1'"
check "rigctl strength" "-54" $R l STRENGTH
check "rigctl vfo info" "146520000" bash -c 'printf "\\\\get_vfo_info VFOB\\n" | nc -w 2 127.0.0.1 4542'
check "rigctl extended reply" "Frequency: 146520000" bash -c 'printf "+f\n" | nc -w 2 127.0.0.1 4542'
check "rigctl frequency back" "FQ 1,0144390000" bash -c "$R F 144390000 && d750 raw 'FQ 1'"
# d750d's logging rules on their own: which reads stay out, APRS packet lines, the count of a repeated error
unit=$(D750_LOG_DIR="$TMP/unit" python3 -I -B - "$TOP/d750d.py" 2>&1 <<'PY'
import importlib.util, os, sys, time
spec = importlib.util.spec_from_file_location("d750d", sys.argv[1]); d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
LOG = os.path.join(d.LOG_DIR, time.strftime("d750d-%Y-%m-%d.txt"))
at = 0
def new_lines():
    global at
    text = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
    out, at = text[at:], len(text); return out
def say(name, good, detail=""): print(f"{'ok' if good else 'bad'} {name}" + ("" if good else f": {detail}"))
quiet = [("FQ 0", "FQ 0,0144390000"), ("BY 1", "BY 1,0"), ("VX", "VX 0"), ("ME 005", "ME 005,0146520000,0"), ("TN", "TN 2,1")]
loud = [("FQ 0,0146520000", "FQ 0,0146520000"), ("VX 1", "VX 1"), ("RT 261111120000", "RT 261111120000"), ("BE", "BE"),
        ("FQ 0", "N"), ("FQ 0", "?"), ("FQ 0", ""), ("DL 1", "DL 1"), ("FQ 0", "BY 0,1")]
bad = [p for p in quiet if not d.routine(*p)] + [p for p in loud if d.routine(*p)]
say("routine", not bad, f"wrong for {bad}")
class Fake:
    """A serial port: bytes waiting now, bytes that arrive while d750d waits, and the radio's answer to a write."""
    def __init__(self, waiting=b"", later=b"", answer=b""): self.buf, self.later, self.answer = waiting, later, answer
    @property
    def in_waiting(self): return len(self.buf)
    def read(self, n): out, self.buf = self.buf[:n], self.buf[n:]; return out
    def write(self, data): self.buf += self.answer
    def flush(self): pass
    def read_until(self, end, size):
        self.buf += self.later; self.later = b""
        i = self.buf.find(end); i = len(self.buf) if i < 0 else i + 1
        out, self.buf = self.buf[:i], self.buf[i:]; return out
    def close(self): pass
r = d.Radio()
r.ser = Fake(waiting=b"N0CALL-7>T5RYYP,WIDE1-1,WIDE2-1:`2EAl \x1c)\r$GPGGA,000000.000,,,,,0,0,,,M,,M,,*43\r\n", answer=b"BC 0,0\r")
got = r.command("BC"); out = new_lines()
say("aprs", got == "BC 0,0" and "APRS packet on the CAT port: N0CALL-7>T5RYYP,WIDE1-1,WIDE2-1:`2EAl \\x1c)\n" in out
    and "discarded: b'$GPGGA" in out and out.count("\n") == 2, f"answer {got!r}, log {out!r}")
r.ser = Fake(waiting=b"N0CALL-9>APDR16,WIDE2-1:=45", later=b"00.00N/12300.00W-hello\r", answer=b"FQ 0,0144390000\r")
got = r.command("FQ 0"); out = new_lines()
say("aprs-late", got == "FQ 0,0144390000" and out.count("\n") == 1 and "N0CALL-9>APDR16,WIDE2-1:=4500.00N/12300.00W-hello" in out,
    f"answer {got!r}, log {out!r}")
r.ser = Fake(answer=b"N0CALL-9>APDR16,WIDE2-1:>status text\rFQ 1,0144390000\r")
got = r.command("FQ 1"); out = new_lines()
say("aprs-ahead", got == "FQ 1,0144390000" and "APRS packet on the CAT port: N0CALL-9>APDR16,WIDE2-1:>status text" in out,
    f"answer {got!r}, log {out!r}")
rp = d.Repeats()
for _ in range(5): rp.note("radio port not available", "cmd 'FQ 0' failed: radio port not available")
rp.tick(now=True); out = new_lines()
say("repeats", out.count("failed: radio port not available") == 1 and "repeated 4 more times since " in out, repr(out))
d.REPEAT_SECONDS = 0; rp.tick(); rp.note("radio port not available", "cmd 'BC' failed: radio port not available"); out = new_lines()
say("repeats-reset", "cmd 'BC' failed" in out, repr(out))
PY
)
check "d750d: reads the radio answered stay out of the log, sets and refusals stay in" "ok routine" printf '%s\n' "$unit"
check "d750d: an APRS packet line on the CAT port is logged as one line" "ok aprs" printf '%s\n' "$unit"
check "d750d: a packet line still arriving is read to its end first" "ok aprs-late" printf '%s\n' "$unit"
check "d750d: a packet line ahead of the answer is logged, the answer still returned" "ok aprs-ahead" printf '%s\n' "$unit"
check "d750d: the same error again is counted, not logged" "ok repeats" printf '%s\n' "$unit"
check "d750d: after a quiet minute an error is logged in full again" "ok repeats-reset" printf '%s\n' "$unit"
# a daemon with no radio at all, on ports 4552 and 4553: 20 reads, how many failure lines in its log
noradio() {  # noradio [VAR=VALUE]
  local dir="$TMP/noradio$#" pid; mkdir -p "$dir"
  env "$@" D750_PORT="$TMP/no-radio" D750_PTT_PORT=4552 D750_CMD_PORT=4553 D750_LOG_DIR="$dir" python3 -I "$TOP/d750d.py" >/dev/null 2>&1 &
  pid=$!
  for _ in $(seq 1 50); do nc -z 127.0.0.1 4553 2>/dev/null && break; sleep 0.1; done
  { printf 'FQ 0\nBC\n%.0s' $(seq 1 10); printf 'quit\n'; } | nc -w 2 127.0.0.1 4553 >/dev/null
  kill "$pid"; wait "$pid" 2>/dev/null
  echo "$(cat "$dir"/d750d-*.txt | grep -c 'failed: radio port not available') failure lines for 20 reads"
}
check "d750d: a missing radio port is logged once, not on every read" "1 failure lines for 20 reads" noradio
check "d750d: D750_LOG_ALL=1 logs every read" "20 failure lines for 20 reads" noradio D750_LOG_ALL=1
check "help" "Verbs:" d750 help
check "usage code" "unknown verb" d750 nonsense
printf '%s pass, %s fail\n' "$pass" "$fail"; [ "$fail" = 0 ]
