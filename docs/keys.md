# Keys: every key in every view

## What it is for

This page lists every key of the rig screen, grouped the way `d750ctrl --check` groups them, and
says how to change them. The keys here are the defaults.

The screen has two families of keys. The list view has its own family, since its letters jump to
rows. The face and compact views share the other family, since their letters act on the radio. A
few keys are the same in all three views.

Run `d750ctrl --check` to see the keys in force on your computer. See [Checking your
keys](#checking-your-keys).

## The fixed keys

These never change, and they mean the same in every view and every mode.

- Ctrl+C quits this screen.
- Ctrl+L draws the screen again.
- A digit or the period starts typing a frequency for the active band.
- While you type: Enter applies, Escape cancels, and Backspace deletes.
- The small letter `y` is the only yes. Any other key answers a question with no. No action may be
  given `y` or `n`, small or capital.
- In help: Up, Down, Page Up, Page Down, Home and End walk the rows. Escape or the help key goes
  back.
- In the memory browser: Enter recalls the channel, capital `R` reads the channels again, and
  Escape or the memory key goes back.

A paste that comes with the terminal's marks is not keys. In a typing line it is text, and
elsewhere it is dropped with `A paste was dropped.` Inside or right after a paste only an unkey key
unkeys and a lock key locks, and every other key is dropped for half a second ("A key after a paste
was dropped."). See [Pasting](d750ctrl.md#pasting).

The keys of `unkey` and `lock` are special, because they stop transmitting:

- They act in help, in the memory browser and at every question. At a question they also answer
  no, and the question ends.
- They do not act while you type a line. There they are just characters.
- They act when the window is too small to show a view, and `lock` there only locks.
- Keys typed ahead of a question, or right after Enter ends a typing line, are thrown away. The keys
  of `unkey` and `lock` are the exception: they still act.

## Keys in every view

These do the same thing in all three views. Two of them have other default keys in the list.

- `other-band`, Tab: the other band. In the list, Tab focuses the same control of the other
  band.
- `help`, the question mark: the list of keys in force. Escape or the question mark goes back.
- `raw`, the colon: type a raw command and press Enter to send it.
- `view-next`, capital `V`: the next view. From the list it asks first.
- `quit`: capital `Q` in the list. Capital `Q` and the small letter `q` in the face and compact.
- `unkey`: capital `U` in the list. Capital `U` and the small letter `u` in the face and compact.
  It sends the unkey line to the PTT port, so it never waits behind a read.
- `lock`, capital `L`: locks PTT at once, or asks to unlock it.
- `memory`, capital `C` and capital `M`: the memory browser.
- `sstv`, capital `S`: SSTV. Asks receive or send.
- `rtty`, capital `R`: RTTY. Asks receive or send.

## Keys in the list view

- `row-up`, Up and `row-down`, Down: one row.
- `page-up`, Page Up and `page-down`, Page Down: one screen.
- `first`, Home and `last`, End: the first row and the last.
- `step-down`, Left and minus: a number one step down, a choice the one before, a level one down, a
  toggle off.
- `step-up`, Right, plus and equals: the same, upward.
- `big-down`, left square bracket and `big-up`, right square bracket: the frequency ten steps. On
  any other row, what `step-down` and `step-up` do.
- `flip`, Space: flip a toggle, or go to the next choice, going round.
- `edit`, Enter: type a value for the row, or do the action.
- A small letter with no action: focus the next row whose name starts with it.

## Keys in the face and compact views

Every key acts on the active band.

- `tune-up`, Up and `tune-down`, Down: tune one step.
- `tune-up-big`, Page Up and `tune-down-big`, Page Down: tune ten steps.
- `next-step`, `s`: the next tuning step, going round.
- `squelch-down`, left square bracket and `squelch-up`, right square bracket: squelch.
- `act-mode`, `m`: the next mode. `act-power`, `p`: the next power. Both go round.
- `act-control`, `b`: the active band becomes the control band and the transmit band.
- `act-source`, `v`: VFO or memory.
- `act-tnc`, `t`: the next TNC mode on its band. Asks first.
- `act-gps`, `g`: GPS output on or off.
- `send-frame`, `c`: send a CQ or beacon frame. Asks in two steps, and only `y` sends.
- `set-clock`, `k`: set the radio clock from the computer. Asks first.
- `chat`, `x`: the chat window.
- `varac-chat`, `o`: the VarAC chat window.
- `radiogram`, `r`: a new radiogram.
- A small letter with no action says `Nothing on z. ? lists the keys.` A capital letter with no
  action says `Nothing on capital Z. Is Caps Lock on?`

## Changing keys

You can change any key above, except the fixed keys. Put the changes in a `[keys]` section at the
end of `~/.config/d750ctrl/d750ctrl.conf`. It is the same file as the settings. See the [settings
page](settings.md).

### The keys section

A line in `[keys]` names an action, an equals sign, and one to four keys, separated by commas:

```text
[keys]
step_up = =
act_mode = M, m
unkey = F5, U
```

- The section starts at a line `[keys]`, in any case. Any other line in square brackets ends it. The
  lines in the section are keys, not settings.
- A line that starts with `#` is a comment. Do not put a comment after a value.
- The action is a name from `--check`, such as `step-up` or `act-mode`. A hyphen and an underscore
  mean the same, and case does not matter.
- A key is one character or one of these names, in any case: `tab`, `space`, `enter`, `up`, `down`,
  `left`, `right`, `pgup`, `pgdn`, `home`, `end`, `backspace`, `comma`, and `f1` to `f12`. A
  single character is itself, and its case counts: `Q` and `q` are two keys.
- A line replaces the action's keys. It does so in every family that has the action, so a change to
  `quit` changes it in the list and in the face.
- A key you give to an action is taken from the action that held it. That action loses it, with no
  warning. If it had no other key, it has none. Check with `--check`.
- `none` takes every key from an action. It is refused for `unkey` and `lock`, which always keep a
  key in each family.
- A key cannot be given to two actions in one file. The second line is skipped.
- `quit = none` is allowed. Then only Ctrl+C quits the screen.

### What is skipped, and why

A line the screen cannot use is skipped, and the rest are used. The screen starts as usual, and the
first message says `Settings skipped. Try d750ctrl --check`.

Here is a settings file with bad lines. Line numbers count every line of the file, from 1.

```text
view = tiny
theme = red
digits =
live_meters = on
[keys]
quit
frobnicate = z
act_mode = banana
help = ctrl-x
act_power = 5
act_gps = a, b, c, d, e
act_tnc = a,,b
unkey = none
raw = y
send_frame = w
chat = w
act_source = n
sstv = comma
rtty = f5
memory = none
quit = escape
```

`D750_CONF_DIR=FOLDER d750ctrl --check` says this about it:

```text
Setting view skipped. tiny is not known.
Setting theme skipped. red is not known.
Setting digits skipped. Its value is empty.
Line 6 skipped: no equals sign.
Line 7 skipped: no such action, frobnicate.
Line 8 skipped: no such key, banana.
Line 9 skipped: that key cannot be changed, ctrl-x.
Line 10 skipped: that key cannot be changed, 5.
Line 11 skipped: more than 4 keys.
Line 12 skipped: a key name is missing.
Line 13 skipped: unkey must keep a key.
Line 14 skipped: y and n answer questions. Not for raw.
Line 16 skipped: w is already given to send-frame on line 15.
Line 17 skipped: y and n answer questions. Not for act-source.
Line 21 skipped: that key cannot be changed, escape.
```

What each means:

- `Setting view skipped. tiny is not known.` The setting has a value the screen does not know. The
  default is used. The same for `theme` and the others.
- `Setting digits skipped. Its value is empty.` The setting has no value.
- `Line 6 skipped: no equals sign.` A line in `[keys]` with no equals sign.
- `Line 7 skipped: no such action, frobnicate.` The name is not an action.
- `Line 8 skipped: no such key, banana.` The name is not a key name.
- `Line 9 skipped: that key cannot be changed, ctrl-x.` Escape, any Ctrl key, a digit and the
  period cannot be used. The message also fits a Ctrl key name the screen does not know.
- `Line 11 skipped: more than 4 keys.` At most four keys to an action.
- `Line 12 skipped: a key name is missing.` Two commas in a row, or one at the end.
- `Line 13 skipped: unkey must keep a key.` `none` for `unkey` or `lock`.
- `Line 14 skipped: y and n answer questions. Not for raw.` `y` and `n`, in either case, are
  refused for every action.
- `Line 16 skipped: w is already given to send-frame on line 15.` A key given twice in one file.
  The first line wins.

A line can also be refused because of what it would leave behind. Take `help = L` in a file, as line
3. Only `lock` held capital `L`, so:

```text
Line 3 skipped: it would leave lock with no key.
```

Lines that were used are not mentioned. After the bad file above, `memory = none`, `sstv = comma`
and `rtty = f5` took effect:

```text
Keys in every view:
other-band: Tab.
help: Question mark.
raw: Colon.
view-next: capital V.
quit in the list: capital Q.
quit in the face: capital Q, q.
unkey in the list: capital U.
unkey in the face: capital U, u.
lock: capital L.
memory: no key.
sstv: Comma.
rtty: F5.
```

Notice `memory: no key.` An action other than `unkey` and `lock` can have no key. It then has no
way to run, except in the list, where its row has Enter.

### Checking your keys

`d750ctrl --check` prints the settings in force, then a line for each skipped setting or key line,
then every key. It needs no daemon and no terminal, and it exits 0. Point it at another folder to
try a file out:

```sh
D750_CONF_DIR=/tmp/mykeys d750ctrl --check
```

With the default keys it prints this. When something was skipped, the line
`No settings line was skipped.` is replaced by the lines that were.

```text
View face.
Theme dark.
Digits big.
Live meters auto.
Announce message.
No settings line was skipped.
Keys in every view:
other-band: Tab.
help: Question mark.
raw: Colon.
view-next: capital V.
quit in the list: capital Q.
quit in the face: capital Q, q.
unkey in the list: capital U.
unkey in the face: capital U, u.
lock: capital L.
memory: capital C, capital M.
sstv: capital S.
rtty: capital R.
Keys in the list view:
row-up: Up.
row-down: Down.
page-up: Page Up.
page-down: Page Down.
first: Home.
last: End.
step-down: Left, Minus.
step-up: Right, Plus, Equals.
big-down: Left bracket.
big-up: Right bracket.
flip: Space.
edit: Enter.
Keys in the face and compact views:
tune-up: Up.
tune-down: Down.
tune-up-big: Page Up.
tune-down-big: Page Down.
next-step: s.
squelch-down: Left bracket.
squelch-up: Right bracket.
act-mode: m.
act-power: p.
act-control: b.
act-source: v.
act-tnc: t.
act-gps: g.
send-frame: c.
set-clock: k.
chat: x.
varac-chat: o.
radiogram: r.
```

The lines read in three groups, as this page does: `Keys in every view:`, `Keys in the list view:`
and `Keys in the face and compact views:`. An action that has other keys in each family is given
twice, such as `quit in the list: capital Q.` and `quit in the face: capital Q, q.`

A capital letter is said with the word capital, as in `view-next: capital V.`, and a small letter is
said as itself, so `quit in the face: capital Q, q.` is two keys. A mark is said in words:
`Question mark`, `Colon`, `Left bracket`, `Minus`, `Equals`. Help rows say it the same way.

The help screen is built from the same keys. Press the question mark on the screen to see the keys
in force, one row for each action or pair. In the wide face, the key row above the message row lists
the same keys.

## See also

- [d750ctrl: the rig screen](d750ctrl.md)
- [Choosing a view](choosing-a-view.md)
- [The list view](list.md)
- [The face view](face.md)
- [The compact view](compact.md)
- [Settings reference](settings.md)
