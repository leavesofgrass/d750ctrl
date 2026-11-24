# d750-sstv and d750-rtty: pictures and teletype through the radio's sound card

## What it is for

`d750-sstv` sends and receives SSTV, slow-scan television, which is a way to send a still picture as
sound. `d750-rtty` sends and receives RTTY, radioteletype, which is a way to send text as Baudot
(five-bit teletype) tones. Both use the sound card in the radio's control head, and both key the
radio through [d750d](d750d.md), so the radio is unkeyed again when they finish.

## Before you start

- **Transmitting with these two tools was fixed in this version and has not been confirmed on the
  air yet.** Before, they keyed the radio and unkeyed it a few milliseconds later. The fix is proven
  against the pretend radio, and both modes were sent and decoded in a closed loop through a virtual
  sound device; see [What has been tested](what-has-been-tested.md). Listen to your own first
  transmissions, and keep `d750 ptt off` ready.
- **Both send commands transmit.** `d750-sstv tx` and `d750-rtty tx` key the radio and put audio on
  the air for as long as the picture or text takes. Check the frequency, mode and power, and that
  the channel is clear, before you run them.
- The Python environment that `install.sh` makes. It creates `.venv` in the project folder and
  installs `sstv`, `pillow` and `numpy` into it. The two commands run with that environment's
  Python. If `install.sh` could not make it, nothing here runs.
- The sound card. The control head's USB socket carries it, and it is also a charger, so put a
  data-only adapter or a powered hub between that socket and the computer. The tools find the card
  by looking for "TM-D750" in the names that `pactl` lists, so you need the PulseAudio or PipeWire
  command line tools: `pactl`, `parecord` and `paplay`. Check with `d750 level`. It prints a level,
  or says the sound card is not present.
- The radio's audio level. `d750 level` listens for a few seconds and says whether the level is
  silence, quiet, good, hot or clipping. If it says hot, lower menu 913. If it says quiet, menu 913
  could go up.
- d750d is running, and the daemon is not locked. A locked daemon refuses to key, and the tool stops
  with "could not key the radio".
- xara, the VARA-compatible modem, is paused automatically while these tools run, and started again
  afterwards if it was running. Nothing else should use the radio's sound card at the same time.

## Try it

You can try the whole chain without a radio, with no keying, using a virtual sound device. The
`tests/modes-test.sh` script in the project does exactly that. See [Testing](testing.md).

On a real radio, listen for a picture, for the default 150 seconds:

```sh
d750-sstv rx
```

The tool prints that it is recording, and when the time is up it saves what it found and prints one
line per picture: its path, its size, its mode, and "complete" or "cut short". If nothing was found
it says "no SSTV picture found in the recording; the audio is kept at" and the path, and exits with
code 1.

List the picture modes the tool knows:

```sh
d750-sstv modes
```

It prints the mode names on one line.

Listen for RTTY for 60 seconds:

```sh
d750-rtty rx 60
```

It prints the decoded text, or says "nothing decoded".

The two commands that transmit, with made-up arguments:

```sh
d750-sstv tx ~/Pictures/crow.png ROBOT_36
d750-rtty tx "CQ CQ DE N0CALL RAIN ON THE BRIDGE 73"
```

## What it can do

### d750-sstv

From `d750-sstv --help` (the first line of the real output, a shell header, is trimmed):

```text
# d750-sstv: send and receive SSTV through the TM-D750's sound card, keyed through d750d.
#   d750-sstv rx [SECONDS]              record the radio for SECONDS (default 150), decode every image found,
#                                       save them under ~/.local/share/d750ctrl/sstv/, print their paths and modes
#   d750-sstv tx IMAGE [MODE]           pause xara, key the radio, send the image, unkey, resume xara
#                                       MODE: ROBOT_36 (default, 37 s), MARTIN_1, SCOTTIE_1, PD_120, ...; d750-sstv modes lists them
#   d750-sstv modes
# Options anywhere: --no-key (no PTT, for tests), --sink NAME, --source NAME (other audio devices).
```

- `d750-sstv rx [SECONDS]`: records the radio's sound card for SECONDS (default 150), decodes every
  picture in the recording, and saves each as a PNG next to the recording under
  `~/.local/share/d750ctrl/sstv/`. A picture takes 37 seconds in Robot 36 and up to about 2 minutes
  in Martin or PD modes, so listen for at least that long.
- `d750-sstv tx IMAGE [MODE]`: resizes your picture to the mode's size, makes the audio, pauses
  xara, keys the radio, plays the audio, unkeys, and starts xara again. The default mode is
  ROBOT_36. The picture is resized to 320 by 256 for the Martin and Scottie modes, 640 by 496 for
  the PD modes, and 320 by 240 otherwise. It prints how long the audio is. The audio file is kept
  next to the pictures. An unknown mode name stops with "unknown mode" and exit code 2.
- `d750-sstv modes`: the mode names the SSTV package offers.
- `--no-key`: never key the radio. The audio still plays to the sound device, so use it with
  `--sink` pointing at a virtual device, as the tests do.
- `--sink NAME` and `--source NAME`: use another audio output or input instead of the radio's.

### d750-rtty

From `d750-rtty --help` (the shell header line is trimmed):

```text
# d750-rtty: send and receive Baudot RTTY (45.45 baud, 170 Hz shift) through the TM-D750, keyed through d750d.
#   d750-rtty rx [SECONDS]        listen for SECONDS (default 60), print the decoded text, keep it in ~/.local/share/d750ctrl/rtty/
#   d750-rtty tx "TEXT"           pause xara, key the radio, send the text, unkey, resume xara
# Options anywhere: --no-key, --sink NAME, --source NAME, --baud 50, --shift 450, --reverse.
```

- `d750-rtty rx [SECONDS]`: listens for SECONDS (default 60), prints the decoded text, and appends
  it with the date and time to `~/.local/share/d750ctrl/rtty/received.txt`. The recording is kept.
  If nothing decodes, it says so and exits with code 1.
- `d750-rtty tx "TEXT"`: encodes the text, pauses xara, keys the radio, plays it, unkeys, and starts
  xara again. It prints how many characters it is sending and for how long. The text goes to upper
  case, and a character that Baudot has no code for becomes a space. It appends the text with the
  date and time to `sent.txt` in the same folder.
- The defaults are 45.45 baud and a shift of 170 Hz. `--baud` and `--shift` change them (for example
  `--baud 50 --shift 450`), and `--reverse` swaps mark and space. `--no-key`, `--sink` and
  `--source` work as for SSTV.

The modem is `rttymodem.py`, written for this project in plain Python with numpy. It can also run on
its own: `rttymodem.py tx "TEXT" OUT.wav` makes a WAV file, `rttymodem.py rx IN.wav` decodes one,
and `rttymodem.py selftest` encodes, adds noise, decodes and compares. It takes `--baud` (45.45, 50
or 75), `--shift` (170, 450 or 850), `--mark` (default 2125 Hz) and `--reverse`.

### What keys the radio

Only the two `tx` commands key it. Each opens one connection to d750d's Hamlib port, keys the
radio on it, and keeps that same connection open for the whole transmission. d750d unkeys the radio
whenever a client that keyed it disconnects, so the connection must stay up until the audio is
done. The tools hold PTT for the length of the audio, plus a short lead before it (0.3 seconds)
and a short tail after it (0.2 seconds). Because d750d also unkeys on its own after 30 seconds, the
tools send the key again every 15 seconds on the same connection. When the audio ends, they unkey on
that connection and close it, even if something goes wrong in the middle. If the unkey does not get
through, they unkey once more on a new connection. `d750 ptt off` unkeys by hand.

If the connection is lost in the middle, d750d has already unkeyed the radio. The tool prints one
line, `keying lost (` followed by the reason and `); d750d unkeyed the radio, the rest goes out
unkeyed`, and plays the rest of the audio without keying. Nothing more is transmitted. Run the
command again after you find the cause; `d750 log` shows what d750d saw.

On the [rig screen](d750ctrl.md), capital `S` and capital `R` ask whether to receive or send and
then run these tools in a window of their own. A send asks for its values first, then shows what
would go ("Picture pic.png, mode ROBOT 36." or the start of the text), and asks last: "Send the
picture on band B? y or n", or "Send this text on band B? y or n", naming the transmit band. Only
the small letter `y` sends. Any other key says "Nothing sent." A send is refused at its start, and
again at the `y`, while PTT is locked or its state is not known ("PTT state not read. Nothing sent.").
A question takes no answer in its first half second: a key that comes too soon is dropped, the
question stays, and the message row says "Too fast. Answer again." A stream of keys, such as a paste,
never answers a question, and keys typed ahead of a question are thrown away. The screen also asks
the terminal to mark pastes. A paste that comes with its marks is never keys, so it cannot answer a
question. In "Text to send:" it is text: pasting a line of RTTY text there is the supported way, and
the message row says "Pasted 14 characters. Enter applies." A key that comes inside or right after a
paste can only unkey, or lock when PTT is not locked; every other key is dropped for half a second.
What is left: a marked paste can only add text to a typing line, unkey, or lock. Beyond that it takes
a link that stalls inside a paste for more than a second or two, which makes the rest of the paste
keys. A terminal that sends no marks pastes as keys, and there a paste that pauses for half a second
or more and then has a small `y` could still answer a send question.

## Settings

Both tools find d750d's Hamlib port from `ptt_port` in `~/.config/d750ctrl/d750ctrl.conf`, or from
`D750_PTT_PORT`. They have no other settings. Where files go is fixed:
`~/.local/share/d750ctrl/sstv/` and `~/.local/share/d750ctrl/rtty/`. See the [settings
page](settings.md).

## When something goes wrong

- **You see:** "Fail: the radio's sound card is not present".
  - **Why:** the control head's USB socket is not connected, or the computer does not list a sound
    device with TM-D750 in its name.
  - **What to do:** connect it, and check with `pactl list short sinks`. Use `--sink` and `--source`
    for a different device.

- **You see:** "could not key the radio".
  - **Why:** d750d is not running, or it is locked.
  - **What to do:** check `d750 state`, and run `d750 unlock` if it is locked.

- **You see:** "no SSTV picture found in the recording".
  - **Why:** no picture was heard in that time, the audio level is wrong, or you stopped listening
    too early.
  - **What to do:** listen longer, and check the level with `d750 level`. The audio is kept so you
    can look at it.

- **You see:** "nothing decoded" from `d750-rtty rx`.
  - **Why:** no RTTY in that time, wrong speed or shift, or the tones are swapped.
  - **What to do:** try `--baud 50`, `--shift 450` or `--reverse`.

- **You see:** the tool does not start, or an error mentions `.venv`.
  - **Why:** the Python environment was not made.
  - **What to do:** run `./install.sh` again, which makes it if it is missing.

- **You see:** xara does not come back after the tool finishes.
  - **Why:** xara was not running to begin with, so the tool did not start it.
  - **What to do:** start it yourself. See [VARA, xara and chat](vara-and-chat.md).

## See also

- [d750d: the daemon](d750d.md)
- [d750: the verbs](d750.md)
- [d750ctrl: the rig screen](d750ctrl.md)
- [VARA, xara and chat](vara-and-chat.md)
- [Testing](testing.md)
- [Settings reference](settings.md)
- [Glossary](glossary.md)
