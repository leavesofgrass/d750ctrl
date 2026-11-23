"""showframe: print one frame of d750ctrl's screen as plain lines, from the pretend daemon.

For the docs and for a look at a view with no terminal. Nothing here touches a radio, a
daemon or a terminal: the model runs against tests/fakedaemon.py in this process, as the
model's tests do.

  python3 -I tests/showframe.py VIEW WIDTHxHEIGHT [KEY ...]

VIEW is list, face or compact. Each KEY is a key's name as the model takes it (down,
tab, V, m, enter, esc, space ...), or `tick` for one second passing, or `type:TEXT` to
press each character of TEXT, or `paste:TEXT` for a paste of TEXT with its marks. Options before VIEW: --digits plain, --live yes,
--announce cursor. The rows are printed as they are, an empty row as an empty line,
then one line saying where the cursor is.

GPL-2.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from fakedaemon import Runner  # noqa: E402

USAGE = "Usage: showframe.py VIEW WIDTHxHEIGHT, then keys if wanted."


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    settings = {"digits": "big", "live_meters": "auto", "announce": "message"}
    names = {"--digits": "digits", "--live": "live_meters", "--announce": "announce"}
    while len(args) >= 2 and args[0] in names:
        settings[names[args[0]]] = args[1]
        args = args[2:]
    if len(args) < 2 or args[0] not in ("list", "face", "compact") or "x" not in args[1]:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        width, height = (int(part) for part in args[1].split("x", 1))
    except ValueError:
        print(USAGE, file=sys.stderr)
        return 2
    radio = Runner(view=args[0], **settings)
    radio.model.size(width, height)
    radio.tick(0.1)
    for key in args[2:]:
        if key == "tick":
            radio.tick(1.0)
        elif key.startswith("type:"):
            for ch in key[5:]:
                radio.run(radio.model.key("space" if ch == " " else ch))
        else:
            radio.press(key)
        radio.model.size(width, height)
    frame = radio.model.frame(width, height)
    for row in frame.rows:
        print(row.rstrip())
    print(f"Cursor: row {frame.cursor[0]}, column {frame.cursor[1]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
