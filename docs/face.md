# The face view: both bands at a glance

## What it is for

The face shows both bands on one screen. In a window of 80 columns or more it puts a panel for each
band side by side, with the active band's frequency in big digits, a squelch bar, a short busy
history and a log of the commands sent. In a narrower window it stacks the two bands, a few short
lines each. Small letters act on the radio: `p` changes the power, `m` the mode, and so on.

The face is the default view. Start it with `d750ctrl`, or `d750ctrl --view face`.

It needs 80 columns by 12 rows for the wide face, and 40 by 10 for the stacked face. In a smaller
window it falls back to compact. See [Choosing a view](choosing-a-view.md).

## The stacked face

This is the face at 40 columns and 10 rows or more. It is also what you get under 80 columns, or at
10 or 11 rows of any width. A window of 40 by 12, as the program draws it at the start:

```text
d750ctrl. Receiving. Unlocked.
A 147.040 MHz
A FM, power high, VFO. Active.
A squelch 6, quiet
B 144.390 MHz. Control. Transmit.
B FM, power mid, VFO
B squelch 3, quiet
TNC KISS on B. GPS out off. VOX off.



Tab band. Up, Down tune. V view. ? help
Cursor: row 1, column 0.
```

Row by row:

- Row 0: the status row, such as `d750ctrl. Receiving. Unlocked.` The other states are `PTT
  locked.`, `TRANSMITTING.`, `No radio.` and `No daemon.`
- Row 1: band A's frequency, then the tags it has: `A 147.040 MHz`, or `B 144.390 MHz. Control.
  Transmit.` A band that is not read says `A not read`.
- Row 2: `A FM, power high, VFO`, with `. Active.` added on the active band. In memory mode it says `memory 012` in place of `VFO`.
- Row 3: `A squelch 6, quiet`, or `A squelch 6, BUSY`.
- Rows 4 to 6: the same three rows for band B.
- Row 7: `TNC KISS on B. GPS out off. VOX off.` A part that is not read is left out.
- Then empty rows, the message row, and the bottom row.

The active band says `Active.` at the end of its mode row. The cursor sits at column 0 of the
active band's first row, and pressing Tab says the new band in the message row, such as
`Band B. 144.390 MHz FM, power mid.`

## The wide face

This is the face at 80 columns and 12 rows or more. A window of 80 by 24, as the program draws it
at the start:

```text
d750ctrl. Receiving. Unlocked.           Step 10 kHz. TNC KISS on B.
Band A. Active.                          Band B. Control. Transmit.
147.040 MHz                              144.390 MHz
 #  # # ###     ### # # ###
##  # #   #     # # # # # #
 #  ###   #     # # ### # #
 #    #   #     # #   # # #
###   #   #  #  ###   # ###
FM, power high, VFO                      FM, power mid, VFO
Squelch 6   ######                       Squelch 3   ###
quiet   .                                quiet   .
TM-D750. GPS out off. VOX off.

Command log







Tab band. Up, Down tune. ? help. u unkey. L lock. V view. q quit. s step.

Tab band. Up, Down tune. V view. ? help
Cursor: row 2, column 0.
```

Row by row, with the left panel for band A and the right panel for band B. Each panel is 39 cells
wide or less.

- Row 0: on the left, the status row. On the right, the step and the TNC: `Step 10 kHz. TNC KISS on
  B.`
- Row 1: the band's name and its tags: `Band A. Active.`, `Band B. Control. Transmit.` Only the tags
  the band has show.
- Row 2: the frequency in text, such as `147.040 MHz`, or `Not read`.
- The next five rows: the active band's frequency in big digits, in its own panel. The other panel
  is empty there. They show only when `digits` is `big`, the window is 17 rows or more, and the
  frequency is read. Otherwise these rows are left out. Big digits are drawn as blocks in reverse
  video. In the sample above a `#` stands for a lit block.
- The mode row: `FM, power high, VFO`, or `memory 012`.
- The squelch row: `Squelch 6`, then a bar of up to nine cells with one lit cell for each squelch
  step. In the sample the lit cells are `#`.
- The busy row: `quiet` or `BUSY`, then the busy history, newest at the right, up to 30 cells. A
  period is a quiet read. A lit block, a `#` in the sample, is a busy read.
- The facts row: on the left, `TM-D750. GPS out off. VOX off.` On the right, `Windows open: chat,
  varac.` when tool windows are open.
- The command log, when the window is 13 rows or more, or 18 rows with big digits. The row `Command
  log` heads it. Under it are the newest exchanges, newest last, across the full width, such as
  `12:00:02 sent FQ 0,0147030000. Answer: FQ 0,0147030000`. A read is logged only when it fails.
  Memory reads are never logged.
- The key row, third from the bottom. It lists the keys in force, as many as fit the window. A
  wider window lists more. Unkey and lock always show.
- The message row, then the bottom row, as in every view.

A window of 80 by 12 shows the same rows, without the big digits and without the command log.

## Keys

The keys are the defaults. You can change them. See [Keys](keys.md). Every key acts on the active
band.

- Tab: the other band. The message row says `Band B. 144.390 MHz FM, power mid.`
- Up and Down: tune one step. Page Up and Page Down: tune ten steps.
- A digit or the period: type a frequency in MHz. Enter applies. Escape cancels.
- `s`: the next tuning step, as in `Step 12.5 kHz.`
- Left square bracket and right square bracket: squelch down and up.
- `m` and `p`: the next mode, the next power.
- `b`: make this band the control band and the transmit band.
- `v`: VFO or memory.
- `t`: the next TNC mode on its band. It asks first.
- `g`: GPS output on or off.
- `k`: set the radio clock from the computer. It asks first.
- `c`: send a CQ or beacon frame. It asks in two steps, and only `y` sends.
- `x`, `o` and `r`: the chat window, the VarAC chat window and a new radiogram.
- Capital `S` and capital `R`: SSTV and RTTY.
- Capital `M` or capital `C`: memory channels.
- `u`: unkey now. Capital `L`: lock PTT, or ask to unlock.
- Capital `V`: the next view. The colon: a raw command. The question mark: help.
- `q`: quit.

A small letter with no action says `Nothing on z. ? lists the keys.` A capital letter with no action
says `Nothing on capital Z. Is Caps Lock on?`

## Where the cursor sits

The cursor is always shown, and it moves only when the focus moves.

- Wide face: the first cell of the active band's frequency row, in its panel. For band A that is
  row 2, column 0. For band B it is row 2, column 41.
- Stacked face: column 0 of the active band's first row. For band A that is row 1. For band B it
  is row 4.
- While you type or answer a question: after the last character of the bottom row.
- In help and the memory browser: column 0 of the row in focus.

## What the message row says

Tuning follows the `announce` setting. With the default, `message`, the message row says the new
frequency, such as `Band A 147.030 MHz.` With `cursor` it says nothing, because the frequency is
where the cursor is.

Every other change is told in both modes, because its row is not at the cursor:

- `Band A squelch 7.`
- `Band A power mid.`
- `Step 12.5 kHz.`
- `PTT locked.`
- `Locked. The radio did not confirm RX.`, when the lock holds but the radio did not say it is
  receiving.
- `PTT is no longer locked.`, once, when the lock went away without this screen's unlock: another
  program unlocked, or d750d started again.
- `TNC off on band B.`
- `Radio clock set.`
- `Unkey sent.`

A refusal says so, such as `No answer: A squelch.` The answer to a raw command says
`Answer: ID TM-D750`. A raw line the screen will not send says
`Refused: TX can key or move the radio.`

Questions and their answers are on [d750ctrl](d750ctrl.md#the-questions-that-ask-before-a-change).

## Colors

Colors are for the face only, and never carry meaning alone. Every state is also a word: BUSY,
TRANSMITTING, PTT locked.

- `dark`, the default: band A cyan, band B magenta, TRANSMITTING and BUSY yellow, keys and bars
  cyan.
- `blue`: band A blue, band B yellow, TRANSMITTING and BUSY yellow in reverse video, keys and bars
  blue.
- `mono`: no color. TRANSMITTING and lit cells are in reverse video, and the band names are bold.

No theme uses red or green. Pick one with `--theme` or the `theme` setting. With the `NO_COLOR`
environment variable set and no `--theme`, the face is `mono`.

## See also

- [d750ctrl: the rig screen](d750ctrl.md)
- [Choosing a view](choosing-a-view.md)
- [The list view](list.md)
- [The compact view](compact.md)
- [Keys](keys.md)
