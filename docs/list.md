# The list view: one control a row

## What it is for

The list shows every control the screen can read or set, one short line each, in a fixed order.
It is the view for reading by speech or on a Braille display. You move down the rows, and the
message row says the row you are on. Small letters jump to a row, so they never change the radio.

It needs a window of 40 columns by 8 rows or more. It never falls back to another view. See
[Choosing a view](choosing-a-view.md).

Start it with `d750ctrl --view list`, or set `view = list` in the settings.

## A sample screen

A window of 40 by 12, as the program draws it at the start. Row 0 is the status row. The focus is
on the first row, and the cursor sits at the start of that row.

```text
d750ctrl. Receiving. Unlocked.
Daemon port open
PTT unlocked
Radio TM-D750
Firmware 1.03
Control band B
Transmit band B
Step 10 kHz
A frequency 147.040 MHz
A mode FM

Letters jump. Arrows change. ? help
Cursor: row 1, column 0.
```

After the End key, the last rows show:

```text
d750ctrl. Receiving. Unlocked.
Set the radio clock
Unkey now
Raw command
Send a CQ or beacon frame
Chat window
VarAC chat window
Radiogram
SSTV
RTTY
RTTY
Letters jump. Arrows change. ? help
Cursor: row 9, column 0.
```

The row you are on shows twice: once in its place, and once in the message row. That is how the
screen says where you are. With the setting `announce = cursor` the message row stays empty for a
move, and says only refusals, errors and events.

## What is on it, row by row

Row 0 is always the status row. It says `d750ctrl. Receiving. Unlocked.`, or `PTT locked.` in place
of Unlocked. Other states are `TRANSMITTING.`, `No radio.` and `No daemon.`

Then these rows, top to bottom. The words change with the radio's state. The values here are sample
values.

Read only:

- `Daemon port open`. Also `Daemon port closed` or `Daemon not answering`.
- `Radio TM-D750`, or `Radio not read`. From the radio's ID.
- `Firmware 1.03`, or `Firmware not read`.
- `VOX off` or `VOX on`. Read only here. Set it with `d750 vox`.
- For each band, the last row: `A quiet` or `A BUSY`.

The PTT row:

- `PTT unlocked` or `PTT locked`. Any key that changes a row does what the lock key does here: it
  locks at once, or asks to unlock. So Enter, Space, Left or Right on this row all lock or ask.

Controls:

- `Control band B` and `Transmit band B`. A choice, A or B. Space moves to the other band.
- `Step 10 kHz`. A choice among the tuning steps. The screen's own; nothing is sent.
- For band A, then band B, each row starting with the band's letter:
  - `A frequency 147.040 MHz`. A number. Left and Right move one step. Enter types a frequency.
  - `A mode FM`. A choice: FM, NFM, AM or DV.
  - `A squelch 6`. A level from 0 to 9.
  - `A power high`. A choice: high, mid, low or EL.
  - `A source VFO` or `A source memory`.
  - `A channel 012` or `A channel none`. Enter types a channel number, 000 to 199, and recalls it.
  - `A quiet` or `A BUSY`. Read only.
- `TNC mode KISS`. A choice: off, APRS or KISS. A change asks first.
- `TNC band B`. A choice. A change asks first.
- `GPS output off`. A toggle. It says `GPS output not read` when the radio has not answered.

Actions, each done with Enter:

- `Memory channels`: the memory browser.
- `Set the radio clock`: asks first.
- `Unkey now`.
- `Raw command`: asks for a line to send.
- `Send a CQ or beacon frame`: asks first, in two steps.
- `Chat window`, `VarAC chat window` and `Radiogram`: open a tool.
- `SSTV` and `RTTY`: ask receive or send.

## Keys

The keys here are the defaults. You can change them. See [Keys](keys.md).

Moving:

- Up and Down: one row. Page Up and Page Down: one screen. Home and End: the first row and the
  last.
- A small letter with no other job: focus the next row whose name starts with it, in either case,
  going round. `a` goes to `A frequency`. `m` goes to `Memory channels`. A letter no row starts
  with says `No control starts with x.`
- Tab: on a band's row, focus the same control of the other band. Elsewhere it says
  `Tab works on a band's row.` Focusing a band's row makes that band the active band.

Changing:

- Left and minus: a number one step down, a choice the one before, a level one down, a toggle off.
- Right, plus and equals: the same, upward. A choice stops at its ends.
- Left square bracket and right square bracket: the frequency ten steps. On any other row they do
  what Left and Right do.
- Space: a toggle flips, and a choice goes to the next one, going round. On an action or a
  read-only row it says what Enter does, or that the row cannot be set.
- Enter: type a value for the row, or do the action. On a choice row it first says the choices,
  such as `Choices: high, mid, low, EL`, and the bottom row asks for one. On a read-only row it
  says, for example, `Daemon cannot be set here.`

Everywhere:

- A digit or the period starts typing a frequency for the active band. Enter applies. Escape
  cancels.
- Capital `V`: the next view. From the list it asks first.
- Question mark: help. Colon: a raw command.
- Capital `Q`: quit. Capital `U`: unkey. Capital `L`: lock, or ask to unlock.
- Capital `M` or capital `C`: the memory browser. Capital `S` and capital `R`: SSTV and RTTY.

The list has no lowercase `q` or `u`: a small letter there jumps. See [Keys](keys.md) for the full
list.

## Where the cursor sits

The cursor is always shown. In the list it sits at column 0 of the row in focus. While you type or
answer a question, it moves to the end of the bottom row. In help and in the memory browser it sits
at column 0 of the row in focus. The cursor moves only when the focus moves.

## What the message row says

With the default `announce = message`, every key that moves the focus or changes a value puts the
row's line in the message row. Examples from runs:

- `A frequency 147.050 MHz`, after Right on the frequency row.
- `A power mid`, after Right on the power row.
- `Control band A`, after Space on the control row.
- `Step 12.5 kHz`, after Right on the step row.

It also says refusals and results:

- `PTT locked.`, after the lock key or Enter on the PTT row.
- `Locked. The radio did not confirm RX.`, when the lock holds but the radio did not say it is
  receiving.
- `PTT is no longer locked.`, once, when the lock went away without this screen's unlock: another
  program unlocked, or d750d started again.
- `VOX is read only here. Try: d750 vox`
- `Enter does what this row says.`, after Space on an action row.
- `Still the list. y goes to the face.`, when you answer the view question with anything but `y`.

No message starts with the time.

## Questions the list asks

Each question sits on the bottom row. Only `y` says yes.

- `Face? Letters change the radio. y or n`, from capital `V`. After `y` the message row says
  `View: face. Letters change the radio.`
- `Unlock PTT? y or n`, when you try to change the PTT row while it is locked, or press capital
  `L`.
- `TNC to KISS on band A? y or n`, after a change to the TNC rows. The words name the new mode and
  band.
- The clock, the frame, SSTV and RTTY, as on [d750ctrl](d750ctrl.md#the-questions-that-ask-before-a-change).

## See also

- [d750ctrl: the rig screen](d750ctrl.md)
- [Choosing a view](choosing-a-view.md)
- [The face view](face.md)
- [The compact view](compact.md)
- [Keys](keys.md)
- [Screen readers](screen-readers.md)
