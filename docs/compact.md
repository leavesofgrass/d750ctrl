# The compact view: three rows of facts

## What it is for

The compact view is for a small pane, such as a tmux pane beside an editor. Three rows hold the
facts of both bands. It needs a window of 40 columns by 6 rows or more. Its keys are the face's
keys, so small letters act on the radio.

Start it with `d750ctrl --view compact`, or set `view = compact` in the settings. The face also
falls back to compact when the window is too small for it. See [Choosing a
view](choosing-a-view.md).

## A sample screen

A window of 40 by 6, the smallest the compact view shows, as the program draws it at the start:

```text
d750ctrl. Receiving. Unlocked.
A 147.040 MHz FM, high, quiet. Active.
B 144.390 MHz FM, mid, quiet
Control B. Transmit B. TNC KISS on B.

Tab band. Up, Down tune. V view. ? help
Cursor: row 1, column 0.
```

In a taller window the extra rows are empty, and the message row and the bottom row stay at the
bottom:

```text
d750ctrl. Receiving. Unlocked.
A 147.040 MHz FM, high, quiet. Active.
B 144.390 MHz FM, mid, quiet
Control B. Transmit B. TNC KISS on B.







Tab band. Up, Down tune. V view. ? help
Cursor: row 1, column 0.
```

## What is on it, row by row

- Row 0: the status row, such as `d750ctrl. Receiving. Unlocked.` The other states are `PTT
  locked.`, `TRANSMITTING.`, `No radio.` and `No daemon.`
- Row 1: band A: `A 147.040 MHz FM, high, quiet`, then `. Active.` on the active band. The state is `quiet` or `BUSY`. A band
  that is not read says `A not read`.
- Row 2: band B, the same way.
- Row 3: `Control B. Transmit B. TNC KISS on B.`
- Empty rows.
- The message row, second from the bottom.
- The bottom row: the hint, the line you are typing, or a question. The hint is `Tab band. Up, Down
  tune. V view. ? help`.

The active band's row ends with `Active.` The cursor sits on that row, and
pressing Tab says the new band in the message row, such as `Band B. 144.390 MHz FM, power mid.`

## Keys

The keys are the face's keys, and every key acts on the active band. The full list is on [the face
page](face.md#keys). In short:

- Tab: the other band. Up and Down: tune one step. Page Up and Page Down: ten steps.
- A digit or the period: type a frequency.
- `s`, `m`, `p`, `b`, `v`, `t`, `g`, `k`, `c`: step, mode, power, control, source, TNC, GPS, clock,
  frame. Square brackets: squelch.
- `x`, `o`, `r`: chat, VarAC chat, radiogram. Capital `S` and `R`: SSTV and RTTY.
- Capital `M` or `C`: memory channels. `u`: unkey. Capital `L`: lock. `q`: quit.
- Capital `V`: the next view. From compact it goes to the list, with no question.
- The question mark: help. The colon: a raw command.

With the compact view there is no key row, so press the question mark to see the keys in force.
Help and the memory browser draw between the status row and the message row, as in every view.

## Where the cursor sits

The cursor is always shown. It sits at column 0 of the active band's row: row 1 for band A, and
row 2 for band B. While you type or answer a question it moves to the end of the bottom row. In
help and the memory browser it sits at column 0 of the row in focus.

## What the message row says

The message row works as it does in the face. Tuning follows the `announce` setting, and every other
change is told in both modes. For example, after `Tab` it says
`Band B. 144.390 MHz FM, power mid.`

When the window is under 40 by 6, the view is replaced by one row, `Window too small. Need 40 by
6.`, and the cursor goes to row 0, column 0.

## See also

- [d750ctrl: the rig screen](d750ctrl.md)
- [Choosing a view](choosing-a-view.md)
- [The face view](face.md)
- [The list view](list.md)
- [Keys](keys.md)
