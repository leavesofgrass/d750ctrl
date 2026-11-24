# d750ctrl: the rig screen, in three views

## What it is for

`d750ctrl` is a full-screen rig control for the TM-D750 that runs in a terminal. It shows both
bands, and you tune, set squelch, power and mode, browse memories and open the other tools without
leaving the keyboard. The mouse is not used.

The screen comes in three views. One is built to be read line by line, by speech or on a Braille
display. One is a small pane. One shows both bands at a glance. See [Choosing a
view](choosing-a-view.md). For a screen reader or a Braille display, the [d750 verbs](d750.md)
print one short line per fact and are still the quickest way to ask one question. See [Screen
readers](screen-readers.md).

## Before you start

- [d750d](d750d.md) is running. If it is not, `d750ctrl` prints
  `Fail: d750d is not answering on 127.0.0.1:4533` and exits.
- tmux is optional. tmux is a terminal multiplexer: a program that gives one terminal several
  windows. With it installed, each tool you open from the screen gets a window of its own. Without
  it, or with `--no-tmux`, a tool takes over the terminal and hands it back when it ends.

## Try it

Start the screen:

```sh
d750ctrl
```

It opens in the face view, unless your settings say otherwise. Then try these keys:

- Press the Tab key to switch the active band.
- Press the Up arrow to tune one step up, and Down to tune one step down.
- Type `146.52` and press Enter to tune the active band to 146.520 MHz.
- Press the question mark to see the key list, and Escape to return.
- Press capital `V` to change the view.
- Press the letter `q` to quit. In the list view, quit is capital `Q`.

To start in the list view:

```sh
d750ctrl --view list
```

To see what is in force before you start, without a terminal or a daemon:

```sh
d750ctrl --check
```

No sample output is captured for the screen itself, which redraws in place. The samples on the view
pages are single frames. To run the screen against the simulator, see [Try it without a
radio](try-without-a-radio.md).

## What it can do

### The three views

- **List.** One control a row: the daemon, the PTT lock, the radio, both bands, the TNC, GPS, and
  the actions. You move down the rows and the message row says the row you are on. Small letters
  jump to a row, so they never change the radio. It needs 40 columns by 8 rows. See [The list
  view](list.md).
- **Face.** Both bands side by side. At 80 columns and 12 rows or more it is a wide face with a
  panel for each band, big digits when there is room, and a command log. Narrower, it stacks the
  two bands under each other. Letters act on the radio. See [The face view](face.md).
- **Compact.** Three rows of facts for a small pane: each band's frequency, mode, power and busy
  state, then the control band, the transmit band and the TNC. It needs 40 columns by 6 rows. Its
  keys are the face's keys. See [The compact view](compact.md).

In every view, row 0 says the state in words, the second row from the bottom is the message row,
and the bottom row is a hint, the line you are typing, or a question.

### Changing the view

There are three ways:

- The setting `view` in `d750ctrl.conf`: `face`, `list` or `compact`. Face is the default.
- The option `--view NAME`. It wins over the setting.
- Capital `V` on the screen. It goes from the face to compact, from compact to the list, and from
  the list to the face.

Leaving the list asks first, because the keys change meaning. In the list a small letter only
jumps. In the face and compact a small letter acts on the radio. The question is
`Face? Letters change the radio. y or n`. Only `y` goes. Any other key says
`Still the list. y goes to the face.`

Going from the face to compact, or from compact to the list, asks nothing. The message row says
`View: compact.` or `View: list.`

If your window is too small for the view you want, the screen shows what fits and says so. See
[Choosing a view](choosing-a-view.md). A smaller window never changes what a key means.

### Keys

The full list, view by view, is on the [keys page](keys.md). Here is the short form.

In the face and compact views:

- Tab: switch the active band.
- Up arrow and Down arrow: tune one step up or down.
- Page Up and Page Down: tune ten steps up or down.
- A digit or the period: start typing a frequency in MHz. Enter tunes. Escape cancels.
- The letter `s`: the next tuning step.
- Left square bracket and right square bracket: squelch down and up.
- The letters `p`, `m`, `b` and `v`: the next power, the next mode, control and transmit on this
  band, and VFO or memory.
- The letters `t` and `g`: the TNC and GPS output.
- The letters `c` and `k`: a CQ or beacon frame, and the radio clock. Both ask first.
- The letters `x`, `o` and `r`: the tools.
- The letter `u`: unkey now. Capital `L`: lock PTT, or ask to unlock it.
- Capital `M` or capital `C`: the memory browser.
- Capital `S` and capital `R`: SSTV and RTTY.
- The colon: a raw command. The question mark: help. The letter `q`: quit.

In the list view, Up and Down move between rows, Left and Right change the value, Space flips or
steps to the next choice, and Enter types a value or does an action. Quit and unkey are capital
`Q` and capital `U`.

You can change most keys. See [The keys page](keys.md#changing-keys).

### Which keys can transmit

These can cause the radio to transmit:

- The frame: `c`, then `c` or `b`, then `y`. It hands one frame to xara, which keys the radio.
- SSTV: `S`, then `s`, then a picture and a mode, then `y`. It sends the picture.
- RTTY: `R`, then `s`, then the text, then `y`. It sends that text.
- `x`, `o` and `r`. They only open programs. A chat program, once open, can transmit when you send
  something in it, and `radiogram new` can hand a message to one at its last question.

In the list view the same things are rows you press Enter on. The questions are the same.

These never transmit: tuning, squelch, power, mode, `b`, `v`, `t`, `g`, `k`, the memory browser, and
the raw command (the screen refuses the keying words). `u` and `L` stop transmitting.

Only the small letter `y` says yes to a question. A send question is the last step, so `y` is the
only key that can send. Sends are refused while PTT is locked, and while the lock state has not
been read.

### Pasting

While the screen is up it asks the terminal to mark pastes. A paste that comes with its marks is
never taken as keys:

- In a typing line it is text. Line ends become spaces. Enter still applies it, and the paste never
  presses Enter itself. The message row says how much came in, such as
  `Pasted 14 characters. Enter applies.` When something was left out it says
  `Pasted 14 characters, some left out.` An empty paste says `Nothing in the paste.`
- Everywhere else it is dropped, and the message row says `A paste was dropped.` It never answers a
  question and never changes the radio.
- A key that comes inside or right after a paste can do only two things: a key of unkey unkeys, and a
  key of lock locks when PTT is not locked. Escape ends a paste that hangs. While a paste is open and
  unfinished, the message row says `A paste is open. Escape ends it.` at the first key.
- After a paste, no key acts for half a second, or two seconds when an Escape ended the paste. A key
  in that time is dropped and starts the wait again, and the message row says `A key after a paste
  was dropped.` The wait never lasts more than five seconds. So text that follows a paste's end, even
  inside the same paste, is never keys. If Enter right after a paste did nothing, wait half a second
  and press it again.

Pasting into a typing line is the supported way to enter long text, such as a line of RTTY text or a
picture path.

A terminal that sends no marks pastes as keys, as before. Then the half second below and the
dropping of keys typed ahead still stand. The same is true when the link cuts a mark from its text
by more than a second.

What is left: a marked paste can only add text to a typing line, unkey, or lock. Beyond that it takes
a link that stalls inside a paste for more than a second or two, which makes the rest of the paste
keys.

### The questions that ask before a change

Each question sits on the bottom row. Only `y` says yes. Any other key says no, and the message row
says what stayed.

A question takes no answer in its first half second. A key that comes sooner is dropped, the
question stays, and the message row says `Too fast. Answer again.` A stream of keys keeps starting
the half second again, so it never answers a question. With a terminal that marks pastes, a paste
cannot answer at all. What is left is a terminal that sends no marks, where a paste that pauses for
half a second or more and holds a small `y` could still answer, or a link that stalls inside a paste
for more than a second or two, which makes the rest of the paste keys.

Keys typed ahead of a question, or right after Enter ends a typing line, are thrown away. The keys
of unkey and lock are the exception, and still act. They also act in help, in the memory browser and
at every question, where they answer no as well. They do not act while you type a line.

- Leaving the list: `Face? Letters change the radio. y or n`. No says
  `Still the list. y goes to the face.`
- Unlocking PTT: `Unlock PTT? y or n`. No says `Still locked.`
- The TNC: it names the new mode and the band, as `TNC to off on band B? y or n`. No says
  `TNC unchanged.`
- The radio clock: `Set the radio clock from here? y or n`. No says `Clock unchanged.`
- The CQ or beacon frame, in two steps: `Frame: c CQ, b beacon, n no`, then, naming the transmit
  band, `Send one CQ frame on band B? y or n`. For a beacon it says `Send one beacon on band B? y or
  n`. Anything but `y` says `Nothing sent.`
- SSTV and RTTY: `SSTV: r receive, s send`. Anything else says `SSTV: nothing done.` After the last
  typing line a send asks `Send the picture on band B? y or n`, or `Send this text on band B? y or
  n`. The message row first says what would go, such as `Picture pic.png, mode ROBOT 36.`
- Quit, when tool windows are open in the tmux workspace: `Close the tool windows too? y or n`. The
  message row names the open windows. `y` quits and closes them. The small letter `n` quits this
  screen only. Any other key says `Still here.`

The frame is also refused before it asks:

- `PTT is locked. Nothing sent.` while PTT is locked. SSTV and RTTY say the same.
- `PTT state not read. Nothing sent.` while the daemon has not told the screen whether PTT is
  locked, for example when it does not answer. SSTV and RTTY say the same.
- `Set mycall in the settings first.` when `mycall` is empty or `N0CALL`.
- `The frame's port is not a number.` when `D750_XARA_PORT` is set to something that is not a port
  number. The frame is not sent.

After you answer `y` to the frame, the message row says `CQ frame handed to xara.` or `Beacon
handed to xara.` If xara does not answer it says `Xara does not answer on port 8300.`

### What changed from the earlier version

- The CQ or beacon frame now takes `c`, then `c` or `b`, then `y`. Before, pressing `c` twice sent
  it.
- SSTV and RTTY sends ask `y or n` last. Before, the last Enter sent.
- Capital `L` asks before it unlocks. It still locks at once.
- Sends are refused while PTT is locked or its state is not known. The frame is also refused while
  `mycall` is not set.
- A raw command may no longer lock, unlock or send the daemon's own words. The screen also refuses
  a raw line that starts with `TX`, `RX`, `UP`, `DW`, `SR`, `PS`, `0M`, `0G` or `BE`, in any case.
  It also refuses a raw line that turns VOX on or changes the TNC. Examples from runs:
  `Refused: TX can key or move the radio.`, `Refused: VOX lets the radio key itself.`,
  `Refused. The t key changes the TNC.`, `Refused. Capital L locks and unlocks.` and
  `Refused: quit is the daemon's own word.` A raw `VX 0`, which turns VOX off, is sent.
- Pastes are marked by the terminal and never taken as keys. See [Pasting](#pasting).
- A question takes no answer in its first half second, and keys typed ahead are thrown away. The
  keys of unkey and lock still act, in help, in the memory browser and at questions.
- Messages no longer start with the time. The command log keeps the times.
- The daemon's state line no longer shows in the message row. Row 0 says the state in words.
- The cursor is shown. It sits where the focus is, so a screen reader or a Braille display can
  follow it.
- The memory browser goes back on Escape or the memory key. The letter `q` no longer does.
- There are three views, key remapping, three themes and `--check`.
- The program's code now lives in a folder, `d750ui`, and `d750ctrl` starts it.

### The memory browser

Press capital `M` or capital `C`, or press Enter on the row "Memory channels" in the list. The first
time, the screen reads memory channels 000 to 199 from the radio, ten at a time, so keys stay
responsive. The message row counts the channels found, such as `2 memory channels in 000 to 199.`
Then:

- Up arrow and Down arrow move one channel. Page Up and Page Down move a screen.
- Each row reads like `000 146.520 MHz FM, offset 0.000 MHz`.
- Enter recalls the highlighted channel on the active band and returns to the main screen.
- Capital `R` reads the channels again.
- Escape or the memory key goes back without changing anything.

The bottom row says `Enter recalls. R rereads. Esc back`. The cursor sits at column 0 of the row in
focus.

### Jumping between modes

When tmux is installed, d750ctrl starts itself inside tmux, on a tmux server of its own, so your
other tmux sessions are untouched. The rig screen is window 0, named `rig`.

- `x` opens the chat program in a window named `chat`.
- `o` opens VarAC chat in a window named `varac`. That is `xarachat` with VarAC's framing on
  (`xarachat --tui --varac yes`), or openslot's terminal client when the settings say
  `varac = openslot`. See [VARA, xara and chat](vara-and-chat.md).
- xara takes one client, so `x` and `o` share one `xarachat`. The other letter jumps to the window
  that is open and names the `/varac on` or `/varac off` command that switches it.
- `r` opens a radiogram. Capital `S` and capital `R` open the SSTV and RTTY tools.
- In the list view the same tools are rows: "Chat window", "VarAC chat window", "Radiogram", "SSTV"
  and "RTTY". Press Enter on one.
- Each tool keeps running while you tune, so a chat link stays up.
- F9 brings the rig screen back from anywhere. F12 steps through the open windows. The same key
  jumps to a window that is already open instead of starting a second copy. These two are tmux keys
  that d750ctrl sets for its own tmux server.
- The rig screen's message row and the bottom tmux line list the open windows.
- A tool's own quit key closes its window: F10 in xarachat, Ctrl+Q in openslot. A tool that was
  started from `r`, `S` or `R` waits at the end with a line saying that Enter closes the window.
- Quit on the rig screen asks whether to close the other windows too.
- Change the two tmux keys with `rig_key` and `next_key` in the settings file.
- `d750ctrl --no-tmux`, or `workspace = no`, gives the old way: a tool takes over the terminal and
  hands it back when it ends. The tmux prefix, Ctrl+B, works as usual.

### Options

From `d750ctrl --help`:

```text
d750ctrl: the TM-D750 on one screen.
Usage: d750ctrl, options if wanted.
--view NAME: list, face or compact.
--theme NAME: mono, dark or blue.
--digits NAME: big or plain.
--ascii: the same as --digits plain.
--step KHZ: the tuning step in kHz.
Steps: 5, 6.25, 10, 12.5, 15 or 20.
Or 25, 50 or 100. 10 by default.
--no-tmux: no tool windows. One terminal.
--plain: the same as --no-tmux.
--check: say the settings and the keys.
--help: say this.
The settings file is d750ctrl.conf.
Its folder is .config/d750ctrl at home.
Keys: press ? on the screen.
GPL-2.0-or-later.
```

What each one does:

- `--view NAME`: the view to start in. It wins over the `view` setting. Also written
  `--view=NAME`.
- `--theme NAME`: the colors of the face view. `dark` is the default. `mono` uses no color.
  `blue` uses blue and yellow. No theme uses red or green. Color never carries meaning alone.
  Setting the `NO_COLOR` environment variable to anything, with no `--theme`, gives `mono`, and so
  does a terminal with no colors. The list and compact views use no color.
- `--digits NAME`: `big` shows the frequency in big digits on the wide face when there are 17 rows
  or more. `plain` never does.
- `--ascii`: the old name for plain digits. It now means `--digits plain`. It still works.
- `--step KHZ`: the starting tuning step in kHz: 5, 6.25, 10, 12.5, 15, 20, 25, 50 or 100. A number
  that is not in the list is ignored and 10 is used. Something that is not a number stops the
  program with `Fail: no such step. Try: d750ctrl --help`.
- `--no-tmux`: this terminal only, no tool windows. A tool takes the terminal over and hands it
  back.
- `--plain`: the old name for `--no-tmux`. It still works and means the same.
- `--check`: say the settings in force, what was skipped, and the keys in force, then exit. It needs
  no daemon and no terminal. See [the keys page](keys.md#checking-your-keys).
- `--help`: say the list above.

A name the program does not know stops it, with `Fail: no such view. Try: d750ctrl --help` (or
`theme` or `digits`) and exit code 2. An option it does not know says
`Fail: unknown option. Try: d750ctrl --help`.

The default step is 10 kHz.

## Settings

The screen reads `~/.config/d750ctrl/d750ctrl.conf`. The settings it reads:

- `mycall`, `varac`, `ptt_port`, `cmd_port`, `status_seconds`, `busy_seconds`, `workspace`,
  `rig_key` and `next_key`, as before.
- `view`: `face`, `list` or `compact`. Default `face`.
- `theme`: `dark`, `mono` or `blue`. Default `dark`.
- `digits`: `big` or `plain`. Default `big`.
- `live_meters`: how often the busy lamps are read. `auto` is the default: only the wide face reads
  busy every `busy_seconds`, so a row away from your cursor does not change under you. `yes` reads
  busy that often in every view. `no` reads busy only with the full read. The older words `on`,
  `true` and `1` mean `yes`, and `off`, `false` and `0` mean `no`.
- `announce`: `message` is the default. In the list, a key that moves or changes puts the row's
  line in the message row. `cursor` leaves the message row for refusals, errors and events, since
  the cursor already sits on the row. In the face and compact, `cursor` stops tuning from being
  announced; every other change is still told.
- A `[keys]` section, to change keys. See [the keys page](keys.md#the-keys-section).

An option wins over its setting. A value the program does not know is skipped and the default is
used. When anything was skipped, the first message is `Settings skipped. Try d750ctrl --check`.

`D750_CMD_PORT`, `D750_PTT_PORT` and `D750_CONF_DIR` override the defaults. The screen reads the
radio every `status_seconds` (default 2) for everything and every `busy_seconds` (default 1) for
the busy flags only. A change you make from the screen is read back at once. Details are on the
[settings page](settings.md).

## When something goes wrong

- **You see:** `Fail: d750d is not answering on 127.0.0.1:4533 (systemctl --user status d750d)`.
  - **Why:** the daemon is not running, or the ports in your settings are not the daemon's.
  - **What to do:** see [d750d](d750d.md).

- **You see:** row 0 says `d750ctrl. No radio.`, or the frequencies are not read.
  - **Why:** the daemon is up but the radio is not answering.
  - **What to do:** check the cable and that the radio is on. Run `d750 doctor`.

- **You see:** the message `Window too small. Need 40 by 8.` or `Window too small. Need 40 by 6.`
  - **Why:** the window is smaller than the smallest view you asked for.
  - **What to do:** make the window larger. Ctrl+C, quit, unkey and Ctrl+L still work meanwhile.
    See [Choosing a view](choosing-a-view.md).

- **You see:** `Settings skipped. Try d750ctrl --check`.
  - **Why:** a setting or a key line has a value the screen does not know.
  - **What to do:** run `d750ctrl --check`. It names each skipped line.

- **You see:** a message such as `No answer: A squelch.`
  - **Why:** the radio did not answer the change. When the radio answers with a refusal, the
    message says `Radio refused` and names the change instead.
  - **What to do:** check the cable and that the radio is on, or try a value the radio takes.

- **You see:** `Xara does not answer on port 8300.`
  - **Why:** the frame goes to xara's command port, and xara is not running.
  - **What to do:** start xara. See [VARA, xara and chat](vara-and-chat.md).

- **You see:** a message saying there is no window for the tool, after pressing `x`, `o`, `r`, `S`
  or `R`.
  - **Why:** tmux could not create the window.
  - **What to do:** run `d750ctrl --no-tmux`, or check that tmux works.

- **You see:** a message such as `Chat is not installed.`
  - **Why:** the program is not installed or not on your PATH. The keys only start programs by name.
  - **What to do:** install it, or do not use that key.

- **You see:** F9 or F12 does nothing.
  - **Why:** they are tmux keys, so they work only inside the d750ctrl tmux session.
  - **What to do:** start `d750ctrl` without `--no-tmux`, with tmux installed.

- **You see:** `Nothing on z. ? lists the keys.` or `Nothing on capital Z. Is Caps Lock on?`
  - **Why:** that key has no action in the face or compact view.
  - **What to do:** press the question mark for the keys. Check Caps Lock.

## See also

- [Choosing a view](choosing-a-view.md)
- [The list view](list.md)
- [The face view](face.md)
- [The compact view](compact.md)
- [Keys](keys.md)
- [d750: the verbs](d750.md)
- [d750d: the daemon](d750d.md)
- [VARA, xara and chat](vara-and-chat.md)
- [SSTV and RTTY](sstv-and-rtty.md)
- [radiogram](radiogram.md)
- [Settings reference](settings.md)
- [Screen readers](screen-readers.md)
- [Glossary](glossary.md)
