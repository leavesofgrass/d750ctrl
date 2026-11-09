#!/bin/bash
# tests.sh: run every d750 verb against the simulator (ports 4542 and 4543) and check the answers.
# Start the test bed first: ./test-env.sh. Written Saturday, November 7, 2026.
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
check "state" "port open" d750 state
check "status bands" "band B: 144.390 MHz, FM, squelch 3" d750 status
check "status tnc" "tnc: KISS on band B" d750 status
check "raw ID" "ID TM-D750" d750 raw ID
check "raw refuses TX" "not allowed" d750 raw TX
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
check "gps output on" "GPS PC output: on" d750 gps output on
sleep 2.5
check "state sees the stream" "unsolicited bytes seen" d750 state
check "fixup turns it off" "Fixed: GPS PC output now 0" d750 fixup
d750 squelch B 5 >/dev/null
check "fixup squelch" "Fixed: band B squelch 3" d750 fixup
check "fixup clean" "Pass: band B squelch 3" d750 fixup
check "vox read" "VOX off" d750 vox
check "vox on" "VOX: 1" d750 vox on
check "vox off" "VOX: 0" d750 vox off
check "clock" "radio clock: 20" d750 clock
check "clock set dry" "would send: RT" d750 clock set -n
check "ptt off" "unkey: RPRT 0" d750 ptt off
check "lock" "locked" d750 lock
check "ptt refused while locked" "RPRT -1" bash -c 'printf "T 1\n" | nc -w 2 127.0.0.1 4542'
check "unlock" "unlocked" d750 unlock
check "ptt key and unkey" "RPRT 0" bash -c 'printf "T 1\nT 0\n" | nc -w 2 127.0.0.1 4542 | tail -1'
check "log" "key in" d750 log 40
check "vara status" "xara:" d750 vara status
printf 'mycall = KD7SWH-7\n' > "$D750_CONF_DIR/d750ctrl.conf"
check "vara cq dry run, VarAC CQ frame" "would send one VarAC cq frame through xara: CQFRAME KD7SWH" d750 -n vara cq
check "vara beacon dry run, VarAC beacon frame" "CQFRAME KD7SWH-9" d750 -n vara beacon
check "doctor runs" "pass," d750 doctor
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
check "help" "Verbs:" d750 help
check "usage code" "unknown verb" d750 nonsense
printf '%s pass, %s fail\n' "$pass" "$fail"; [ "$fail" = 0 ]
