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
- The rig screen has `--ascii`, `--theme mono` and `--plain` for terminals that read better plain.
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

The rig screen is a full-screen program, and it has three options for terminals that read better
plain. See [d750ctrl](d750ctrl.md) for the keys.

- `--ascii` draws the big frequency digits with plain characters instead of block characters. Block
  characters often come out as noise on a Braille display. The band that is not active shows its
  frequency in plain digits, and after you tune, the message line says the new frequency in plain
  words.
- `--theme mono` turns color off. The default theme is `dark`. In the mono theme the title bar and
  the alarm lamps use reverse video instead of color.
- `--plain` keeps the screen in this one terminal. Without it, and with tmux installed, the screen
  opens its own tmux session and each tool gets a window. With `--plain`, or with `workspace = no`
  in the settings, a tool takes over the terminal and hands it back when it ends.
- Color never carries meaning alone. A busy band says BUSY and a quiet one says quiet. A keyed radio
  shows the word TRANSMIT, and a locked one PTT LOCKED. Squelch is a number and a bar of `#` and
  `.`.
- Every action prints a line of words in the message line, with the time. A refusal says so.
- Keys are named in words, and the question mark shows them all. The mouse is not used.

## Tested and not tested

- The owner tests with a screen reader and a Braille display every day. That is the real test.
- The automated tests drive the rig screen under a pseudo terminal and check the text on it. They do
  not run a screen reader.
- Other screen readers, other terminals and other Braille displays have not been tested. If
  something does not read well, please report it as a bug.

## See also

- [d750](d750.md)
- [d750ctrl](d750ctrl.md)
- [aprschat](aprschat.md)
- [Recipes](recipes.md)
