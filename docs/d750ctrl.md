# d750ctrl: the rig screen, with both bands and every dial on the keyboard

## What it is for

`d750ctrl` is a full-screen rig control for the TM-D750 that runs in a terminal. It shows both
bands, and you tune, set squelch, power and mode, browse memories and open the other tools without
leaving the keyboard. The mouse is not used. For a screen reader or a Braille display, the [d750
verbs](d750.md) print one short line per fact and are usually the better fit; the screen is for
operators who want the dials. See [Screen readers](screen-readers.md).

## Before you start

- [d750d](d750d.md) is running. If it is not, `d750ctrl` prints
  `Fail: d750d is not answering on 127.0.0.1:4533` and exits.
- tmux is optional. tmux is a terminal multiplexer: a program that gives one terminal several
  windows. With it installed, each tool you open from the screen gets a window of its own. Without
  it, or with `--plain`, a tool takes over the terminal and hands it back when it ends.

## Try it

Start the screen:

```sh
d750ctrl
```

Then try these keys:

- Press the Tab key to switch the active band.
- Press the Up arrow to tune one step up, and Down to tune one step down.
- Type `146.52` and press Enter to tune the active band to 146.520 MHz.
- Press the question mark to see the key list, and any key to return.
- Press the letter `q` to quit.

For a screen with plain characters in place of the block digits, and no colors:

```sh
d750ctrl --ascii --theme mono
```

No sample output is captured for the screen, which redraws itself in place. See [Try it without a
radio](try-without-a-radio.md) to run it against the simulator.

## What it can do

### What is on the screen

From the top to the bottom:

- The title bar: "d750ctrl", the radio's ID (it shows "radio?" until the radio answers), the tuning
  step, the TNC mode and band, whether GPS output to the PC is on or off, and whether VOX is on or
  off. At the right edge it says TRANSMIT while the radio is keyed, or PTT LOCKED while the daemon
  is locked.
- Two band panels, band A on the left and band B on the right. Each panel's heading says "BAND A" or
  "BAND B", then CTRL for the control band and "TX band" for the band that transmits. The active
  band, the one your keys act on, also carries the marker "<active>", and shows its frequency in big
  digits. The other band shows its frequency in plain text. Each panel then shows the mode, the
  power, and either VFO or the memory channel number, then the squelch level with a bar of nine
  marks (the number sign for each step up to the level, a period for the rest), and then the word
  BUSY or quiet, with a short history of the squelch (a vertical bar for busy, a period for quiet).
- A CAT log: the commands the screen sent and the answers, with times. Routine reads are left out.
- A key bar listing the keys, a message line with the result of the last action, and a typing line.

Colors never carry the meaning alone: BUSY, quiet, TRANSMIT and PTT LOCKED are words.

### Keys on the main screen

Tuning and bands:

- Tab: switch the active band.
- Up arrow and Down arrow: tune one step up or down.
- Page Up and Page Down: tune ten steps up or down.
- The letter `s`: cycle the step through 5, 6.25, 10, 12.5, 15, 20, 25, 50 and 100 kHz.
- A digit or the period: start typing a frequency in MHz. Enter tunes. Escape cancels. Backspace
  deletes.
- The letter `b`: make the active band the control band and the transmit band.

Settings on the active band:

- Left square bracket and right square bracket: squelch down and up, from 0 to 9.
- The letter `p`: cycle the power through high, mid, low and EL.
- The letter `m`: cycle the mode through FM, NFM, AM and DV.
- The letter `v`: switch the band between VFO and memory mode.

Memories, TNC and GPS:

- Capital `M`: open the memory browser (see below).
- The letter `t`: cycle the TNC through off, APRS and KISS on its current band. It asks first;
  answer with `y` or `n`.
- The letter `g`: switch the GPS output to the PC port on or off.

Keying and safety:

- The letter `u`: unkey now.
- Capital `L`: lock or unlock PTT in d750d. While locked, nothing can key the radio.

Other actions:

- The letter `c`: send one VarAC CQ or beacon frame through xara. **This transmits.** It asks first:
  `c` for a CQ, `b` for a beacon, `n` for nothing.
- The letter `k`: set the radio's clock from this computer. It asks first.
- The colon: type a raw CAT command, press Enter to send it. The command goes through the daemon's
  command port, which refuses commands that key or reset the radio.
- The question mark: help, a list of every key. Any key returns.
- The letter `q`: quit. If other windows are open (see "Jumping between modes"), it asks whether to
  close them too.

Other tools, each in its own window:

- The letter `x`: a chat window. This starts a program named `xarachat`.
- The letter `o`: a VarAC chat window. This is `xarachat` speaking VarAC's framing, or `openslot`
  when your settings say `varac = openslot`. See [VARA, xara and chat](vara-and-chat.md).
- The letter `r`: write a radiogram with `radiogram new`. See [radiogram](radiogram.md).
- Capital `S`: SSTV. Asks `r` to receive or `s` to send. See [SSTV and RTTY](sstv-and-rtty.md).
- Capital `R`: RTTY. Asks `r` to receive or `s` to send.

### Which keys can transmit

These can cause the radio to transmit:

- `c`, after you confirm. It hands one frame to xara, which keys the radio.
- `S` then `s`, after you give a file and a mode. It sends a picture.
- `R` then `s`, after you type the text. It sends that text.
- `x`, `o` and `r`. They only open programs. A chat program, once open, can transmit when you send
  something in it, and `radiogram new` can hand a message to one at its last question.

These never transmit: tuning, squelch, power, mode, `b`, `v`, `t`, `g`, `k`, the memory browser, and
the colon (the daemon refuses the keying commands). `u` and `L` stop transmitting.

### The memory browser

Press capital `M`. The first time, the screen reads memory channels 000 to 199 from the radio one at
a time, so it takes a moment, and the message line counts the channels found. Then:

- Up arrow and Down arrow move one channel. Page Up and Page Down move ten.
- Enter recalls the highlighted channel on the active band and returns to the main screen.
- Capital `R` reads the channels again.
- Escape, the letter `q` or capital `M` goes back without changing anything.

### Jumping between modes

When tmux is installed, d750ctrl starts itself inside tmux, on a tmux server of its own, so your
other tmux sessions are untouched. The rig screen is window 0, named `rig`.

- `x` opens the chat program in a window named `chat`.
- `o` opens VarAC chat in a window named `varac`. That is `xarachat` with VarAC's framing on
  (`xarachat --tui --varac yes`), or openslot's terminal client when the settings say
  `varac = openslot`.
- xara takes one client, so `x` and `o` share one `xarachat`. The other letter jumps to the window
  that is open and names the `/varac on` or `/varac off` command that switches it.
- `r` opens a radiogram. `S` and `R` open the SSTV and RTTY tools.
- Each tool keeps running while you tune, so a chat link stays up.
- F9 brings the rig screen back from anywhere. F12 steps through the open windows. The same letter
  jumps to a window that is already open instead of starting a second copy. These two are tmux keys
  that d750ctrl sets for its own tmux server.
- The rig screen's message line and the bottom tmux line list the open windows.
- A tool's own quit key closes its window: F10 in xarachat, Ctrl+Q in openslot. A tool that was
  started from `r`, `S` or `R` waits at the end with a line saying that Enter closes the window.
- `q` on the rig screen asks whether to close the other windows too.
- Change the two tmux keys with `rig_key` and `next_key` in the settings file.
- `d750ctrl --plain`, or `workspace = no`, gives the old way: a tool takes over the terminal and
  hands it back when it ends. The tmux prefix, Ctrl+B, works as usual.

### Options

From `d750ctrl --help`:

```text
usage: d750ctrl [-h] [--ascii] [--theme {dark,mono}] [--step STEP] [--plain]

keyboard rig control for the Kenwood TM-D750 through d750d

options:
  -h, --help           show this help message and exit
  --ascii              plain characters instead of block digits
  --theme {dark,mono}
  --step STEP          tuning step in kHz: 5, 6.25, 10, 12.5, 15, 20, 25, 50,
                       100
  --plain              this terminal only, no tmux windows: a tool takes the
                       terminal over and hands it back
```

The default step is 10 kHz. A step that is not in the list is ignored and the default is used.

## Settings

The screen reads `~/.config/d750ctrl/d750ctrl.conf`: `mycall`, `varac`, `ptt_port`, `cmd_port`,
`status_seconds`, `busy_seconds`, `workspace`, `rig_key` and `next_key`. `D750_CMD_PORT`,
`D750_PTT_PORT` and `D750_CONF_DIR` override the defaults. The screen reads the radio every
`status_seconds` (default 2) for everything and every `busy_seconds` (default 1) for the busy flags
only. A change you make from the screen is read back at once. Details are on the [settings
page](settings.md).

## When something goes wrong

- **You see:** `Fail: d750d is not answering on 127.0.0.1:4533 (systemctl --user status d750d)`.
  - **Why:** the daemon is not running, or the ports in your settings are not the daemon's.
  - **What to do:** see [d750d](d750d.md).

- **You see:** the title bar says "radio?" and the frequencies show as dashes.
  - **Why:** the daemon is up but the radio is not answering.
  - **What to do:** check the cable and that the radio is on. Run `d750 doctor`.

- **You see:** a message such as `radio refused 27.000 MHz`.
  - **Why:** the radio did not accept that frequency.
  - **What to do:** type a frequency the radio covers.

- **You see:** the message `xara not reachable on 8300`.
  - **Why:** `c` hands its frame to xara's command port, and xara is not running.
  - **What to do:** start xara. See [VARA, xara and chat](vara-and-chat.md).

- **You see:** "could not open a window for ..." after pressing `x`, `o`, `r`, `S` or `R`.
  - **Why:** tmux could not create the window.
  - **What to do:** run `d750ctrl --plain`, or check that tmux works.

- **You see:** a program such as `xarachat`, `openslot` or `radiogram` fails to start.
  - **Why:** the program is not installed or not on your PATH. The keys only start programs by name.
  - **What to do:** install it, or do not use that key.

- **You see:** F9 or F12 does nothing.
  - **Why:** they are tmux keys, so they work only inside the d750ctrl tmux session.
  - **What to do:** start `d750ctrl` without `--plain`, with tmux installed.

## See also

- [d750: the verbs](d750.md)
- [d750d: the daemon](d750d.md)
- [VARA, xara and chat](vara-and-chat.md)
- [SSTV and RTTY](sstv-and-rtty.md)
- [radiogram](radiogram.md)
- [Settings reference](settings.md)
- [Screen readers](screen-readers.md)
- [Glossary](glossary.md)
