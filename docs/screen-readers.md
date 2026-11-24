# Screen readers and Braille

This page says how the project is built for a screen reader and a Braille display, and what has and
has not been tested. The owner uses these tools daily with a screen reader and a Braille display.
The tools were built for that first. Every fact below comes from what the code does.

## The short version

- The `d750` command prints one short line per fact, with the answer first.
- Pass, Fail and the other results are words, never colors or symbols.
- Exit code 0 is Pass, 1 is Fail, 2 is a usage mistake.
- `-n` anywhere on a command is a dry run: it shows what would be sent and changes nothing.
- `aprschat --line` prints one event per line and never redraws the screen.
- The rig screen has a list view, built for reading by speech and Braille, and `--check`, which
  prints its settings and keys as plain lines. No view has been tried with speech or Braille yet.
- The d750 verbs are the better fit for reading line by line. The rig screen is for operators who
  want the dials.

## The d750 command

- Each line starts with the fact. A band line starts with the band: "band A: 147.040 MHz, FM,
  squelch 6, busy, power high". A change prints "before:" and then "after:".
- Results are words at the start of the line: Pass, Fail, Warn, Fixed and note. `d750 doctor` and
  `d750 fixup` use them, one check per line, so you can listen for the first word.
- A verb that stops with a failure prints a line that starts with "Fail:" to the standard error
  stream, and the exit code is 1. `d750 doctor` prints its Fail lines in its normal output. A usage
  mistake prints a line that starts with "usage:" and the exit code is 2. Check the exit code in a
  script instead of reading the text.
- The line "would send:" in a dry run goes to the standard error stream too.
- `d750 watch A 30` prints a line only when the busy state changes, with the time, and a count at
  the end. It does not repeat a state that has not changed.
- `d750 help` prints the verbs as plain text. An unknown verb prints the same text and exits with 2.
- d750 output has no box drawing, no color codes, no spinners and no progress bars.

## aprschat: line mode

- `aprschat --line CALL` prints one event per line and never redraws. Event lines start with the
  time. Use it with a screen reader or a Braille display.
- Line mode is also chosen on its own when the output is not a terminal.
- You type a line and press Enter to send it to the station you chose. Commands are `/to CALL`,
  `/list`, `/status` and `/quit`.
- The result of each of your messages is said in words: waiting, sent with the try number out of 5,
  acknowledged, refused, or did not acknowledge after 5 tries.
- A new message from another station arrives as a line that starts with the time and the words "New
  from" and the call sign.
- The screen mode keeps the cursor on the typing line, and on the chosen line in a list, so a screen
  reader that follows the cursor follows the conversation. `aprschat --help` lists its keys.
- `d750-aprs listen` follows every packet as a plain line. The call sign comes first, then the
  distance and direction, the status or comment, and whether it was heard direct or through a
  digipeater.

## The rig screen: d750ctrl

The rig screen is a full-screen program with three views. See [Choosing a view](choosing-a-view.md)
for how to pick one and [d750ctrl](d750ctrl.md) for the rest.

- **The list view is the one built for reading by speech and Braille.** Each row is one control and
  starts with its name: "A frequency 147.040 MHz", "A squelch 6", "PTT unlocked". Words come first,
  and rows are 40 cells or fewer. Start it with `d750ctrl --view list`, or set `view = list`.
- **The cursor** is always shown, and it moves only when the focus moves. In the list it sits at the
  start of the row in focus. In the compact view and the stacked face it sits at the start of the
  active band's first row. In the wide face it sits on the active band's frequency. While you type or
  answer a question it sits after the last character of the bottom row. In help and the memory list
  it sits at the start of the row in focus.
- **The message row** is the second row from the bottom. It is empty until something happens. It
  holds the answer to what you did, and it never starts with the time. With `announce = message`, the
  default, moving or changing a value in the list puts the focused row's line there. With
  `announce = cursor` it holds only refusals, errors and events, for a screen reader that already
  follows the cursor. In the face and compact views tuning follows `announce`, and every other change
  is said in both modes, because its row is not at the cursor.
- **The active band** is named in the text: the stacked face and the compact view say "Active." at
  the end of its row, and the wide face says "Band A. Active."
- **The bottom row** is the hint, what you are typing, or a question. Only the small letter y says
  yes to a question. Any other key says no, and the message row says what stayed.
- **The top row** is the status in words: "d750ctrl. Receiving. Unlocked.", PTT locked,
  TRANSMITTING, "No radio." or "No daemon."
- **`live_meters`** sets how often the busy lamps are read. The default, `auto`, reads them often only
  in the wide face. In the list, the stacked face and compact they are read with each full read, so a
  row away from the cursor does not flicker under a screen reader. See [Settings](settings.md).
- **`d750ctrl --check`** prints the settings in force, the lines it skipped and every key, one
  fact a line, and exits. It needs no daemon and no terminal. Use it to read the keys without
  opening the screen. It says "capital Q" and "capital V", so that Q and q do not sound alike.
- **A question waits half a second.** A key that comes too soon is dropped, the question stays, and
  the message row says "Too fast. Answer again." A stream of keys, such as a paste, never answers a
  question. The screen also asks the terminal to mark pastes, on when it starts and off on every way
  out and while a tool has the terminal. A marked paste is never keys: in a typing line it is text
  ("Pasted 14 characters. Enter applies."), and anywhere else it is dropped ("A paste was dropped.").
  It never answers a question, never presses Enter and never changes the radio. Pasting a line of
  text into "Text to send:" is the supported way. A key that comes inside or right after a paste can
  only unkey, or lock when PTT is not locked. Every other key is dropped for half a second (two
  seconds after an Escape), and the message row says "A key after a paste was dropped." What is left:
  a marked paste can only add text to a typing line, unkey, or lock. Beyond that it takes a link that
  stalls inside a paste for more than a second or two, which makes the rest of the paste keys. A
  terminal that sends no marks pastes as keys, and there a paste that pauses for half a second or
  more and then has a small y could still answer a send question.
- **The keys of unkey and lock** act in help, in the memory list and at every question, and in a
  window too small to show anything. A frame or a send is refused while PTT is locked or its state is
  not known.
- **The lock is told in words.** "Locked. The radio did not confirm RX." when the lock holds but the
  radio did not say it is receiving. "PTT is no longer locked." once, when the lock went away without
  this screen's unlock. Both are said in both announce modes.
- **Ctrl+C and Ctrl+backslash** quit and put the terminal back. An unkey or lock key typed just
  ahead of them still acts.
- **A window that is too small** shows one row that says so. The list needs 40 by 8, the compact view
  40 by 6, and the face 40 by 10 stacked or 80 by 12 wide.
- **`--ascii` now means `--digits plain`**: no large digits.
  Block characters in the digits often come out as noise on a Braille display, and the
  list and compact views have none. Large digits show only in a window 17 rows tall or more.
- **`--theme mono`** turns color off. `NO_COLOR` does the same. In the mono theme the alarm and the
  lit cells use reverse video. The themes do not use red or green, and the list and compact views have
  no color at all.
- **`--no-tmux`** keeps the screen in this one terminal. Its old name, `--plain`, still works. It
  does not change how the screen is drawn. Without it, and with tmux installed, the screen opens its
  own tmux session and each tool gets a window. With `--no-tmux`, or with `workspace = no`, a tool
  takes over the terminal and hands it back when it ends.
- Color never carries meaning alone. A busy band says BUSY and a quiet one says quiet. A keyed radio
  says TRANSMITTING, and a locked one says PTT locked. Squelch is a number.
- Keys are named in words, and the question mark shows them all. The mouse is not used.
- The keys can be changed in a `[keys]` section of the settings. See [Settings](settings.md).

## Tested and not tested

- The owner uses a screen reader and a Braille display every day, and tested the first version of the
  rig screen that way.
- **No view of the new rig screen has been tried with speech or Braille yet.** The list, the face and
  the compact view were checked only by the automated tests, which read the text on a pseudo
  terminal and check each row against a 40-cell line rule. They do not run a screen reader.
- Whether the cursor's place reads well, and whether `announce` should be `message` or `cursor` for
  you, is not known yet. Please report what reads badly.
- Other screen readers, other terminals and other Braille displays have not been tested.

## See also

- [d750](d750.md)
- [d750ctrl](d750ctrl.md)
- [aprschat](aprschat.md)
- [Recipes](recipes.md)
