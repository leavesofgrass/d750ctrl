#!/bin/sh
# modes-test.sh: RTTY and SSTV round trips over a virtual sink, no radio, no keying.
set -u
here=$(dirname "$(readlink -f "$0")")
T=$(mktemp -d "${TMPDIR:-/tmp}/d750ctrl-modes.XXXXXX")
"$here/.venv/bin/python" - "$T" <<'PYX'
import sys
from PIL import Image, ImageDraw
img = Image.new("RGB", (320, 240), (20, 60, 120)); d = ImageDraw.Draw(img)
d.rectangle((20, 20, 300, 220), outline=(255, 255, 0), width=6); d.text((40, 110), "SSTV TEST", fill=(255, 255, 255))
img.save(sys.argv[1] + "/test.png")
PYX
m=$(pactl load-module module-null-sink sink_name=xl_modes rate=48000 channels=1 sink_properties="device.description=xl_modes priority.session=10")
trap 'pactl unload-module '"$m"' 2>/dev/null; rm -rf "$T"' EXIT
pass=0; fail=0
echo "--- rtty ---"
"$here/d750-rtty" rx 20 --source xl_modes.monitor --no-key > $T/rtty-rx.txt 2>&1 &
rxpid=$!; sleep 2
"$here/d750-rtty" tx "CQ CQ DE KD7SWH TESTING RTTY 73" --sink xl_modes --no-key | tail -1
wait $rxpid; rxout=$(cat $T/rtty-rx.txt)
if echo "$rxout" | grep -q 'CQ CQ DE KD7SWH TESTING RTTY 73'; then pass=$((pass+1)); echo "Pass: rtty text came through the virtual sink"; else fail=$((fail+1)); echo "Fail: rtty: $rxout"; fi
echo "--- sstv ---"
"$here/d750-sstv" rx 48 --source xl_modes.monitor --no-key > $T/sstv-rx.txt 2>&1 &
rxpid=$!; sleep 2
"$here/d750-sstv" tx $T/test.png ROBOT_36 --sink xl_modes --no-key | tail -1
wait $rxpid; rxout=$(cat $T/sstv-rx.txt)
if echo "$rxout" | grep -q 'mode ROBOT_36, complete'; then pass=$((pass+1)); echo "Pass: sstv picture came through: $(echo "$rxout" | grep picture | cut -c1-90)"; else fail=$((fail+1)); echo "Fail: sstv: $rxout"; fi
echo "$pass pass, $fail fail"; [ "$fail" = 0 ]
