# Choosing a view: which screen suits you

## What it is for

`d750ctrl` has three views of the same radio. They show the same facts and send the same commands.
They differ in how the facts are laid out, how big a window they need, and what the letter keys do.
This page helps you pick one.

## The three views side by side

- **The list.** One control a row. Each row is a short line of words, such as `A mode FM`. You move
  between rows with the arrow keys, and the message row says the row you are on. Small letters
  jump to a row by its first letter, so a stray key never changes the radio. It shows everything
  the screen can read or set, including the firmware, the PTT lock and the actions. See [The list
  view](list.md).
- **The face.** Both bands at once. At 80 columns and 12 rows or more, a panel for each band side by
  side, with big digits for the active band, a squelch bar, a short busy history and a log of the
  commands sent. Under 80 columns it stacks the two bands, a few short lines each. Small letters
  act on the radio. See [The face view](face.md).
- **Compact.** Three rows of facts: band A, band B, then the control band, the transmit band and
  the TNC. Small letters act on the radio, the same as in the face. See [The compact
  view](compact.md).

## Who each view is for

- **Reading by speech or on a Braille display: the list.** Every row is one fact in plain words, in
  a fixed order. The cursor sits at the start of the row in focus, so a screen reader or a Braille
  display follows you down the list. Busy states are read only with the full read, not on a faster
  timer, so a row away from your cursor does not flicker under you (the `live_meters` setting
  changes this). Letters jump, so you can
  reach a row without knowing a key for it.
- **A small pane: compact.** It needs 40 columns by 6 rows, so it fits beside an editor or in a
  tmux pane. Everything it shows is on three short lines.
- **Seeing both bands at a glance: the face.** The wide face shows both frequencies, squelch and
  busy history side by side. The active band's frequency is in big digits when the window is 17
  rows or more. It is the view with the most on screen and the one that reads best by eye.

The face is the default. Change the default with the `view` setting, and change it for one run with
`--view`. See [d750ctrl: the rig screen](d750ctrl.md#changing-the-view).

## What each needs in window size

All sizes are columns by rows.

- **List:** 40 by 8 or more.
- **Face, wide:** 80 by 12 or more.
- **Face, stacked:** 40 by 10 or more, when the wide face does not fit. That is a window under 80
  columns, or one that is 10 or 11 rows high.
- **Compact:** 40 by 6 or more.

In the wide face:

- Big digits need 17 rows or more. With `--digits plain` they never show.
- The command log needs 13 rows, or 18 rows when big digits show.
- The key row, above the message row, is as wide as the window. A wider window lists more keys.

## When the window is too small

What happens depends on the view you asked for. A smaller window never changes what a key means:
the keys follow the view you asked for.

- **You asked for the list.** The list never falls back. Under 40 by 8 you get one row:
  `Window too small. Need 40 by 8.`
- **You asked for the face.** The screen shows the best view that fits. Under 80 by 12 it stacks.
  Under 40 by 10 it falls back to compact, and the message row says `Too small for the face.
  Compact.` When the window grows again the message row says `The face again.` Each is said once,
  when the change happens. Going from wide to stacked says nothing. Under 40 by 6 you get one row:
  `Window too small. Need 40 by 6.`
- **You asked for compact.** Under 40 by 6 you get one row: `Window too small. Need 40 by 6.`

In the one-row case the cursor sits at row 0, column 0. A question that was open when the window
shrank is cancelled and says its "no" words.

While the window is too small to show anything, only these keys act:

- Ctrl+C and Ctrl+backslash quit, and Ctrl+L draws again.
- Unkey and lock, with the keys in force, in help, in the memory list and at a question as well as
  in the main screen. They act as in a window big enough, except that lock while PTT is locked
  never asks to unlock here: in the main screen it says `Still locked.` They do not act while you
  type a line.
- Quit, with the keys in force, in the main screen only.

Every other key is ignored until the window is large enough. Nothing is lost: make the window
larger and the screen is back as it was.

## See also

- [d750ctrl: the rig screen](d750ctrl.md)
- [The list view](list.md)
- [The face view](face.md)
- [The compact view](compact.md)
- [Keys](keys.md)
- [Screen readers](screen-readers.md)
