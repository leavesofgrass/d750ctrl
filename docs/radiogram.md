# radiogram: write, check, read and log NTS radiograms as plain text

## What it is for

The ARRL National Traffic System (NTS) carries written messages between amateurs, and a message in
its standard form is called a radiogram. A radiogram has a numbered preamble, an address, a text
counted in groups (roughly, words), and a signature, and it travels by voice, digital chat or
e-mail.

`radiogram` asks you the questions one at a time, builds the radiogram in that form as plain text,
counts the groups for the check, saves it, and logs it. It can also read a radiogram you received
and show it as a delivery form. It runs in the terminal, and it is also what the letter `r` starts
on the [rig screen](d750ctrl.md).

The tool is in `station/radiogram` in the repository, and after `station/install-station.sh` it is
on your PATH as `radiogram`. See [Station tools](station-tools.md).

## Before you start

- `python3`. The tool has no other requirements. The Tab key completes from what the tool remembers
  when your Python has the `readline` module.
- Nothing here transmits. The tool only writes and reads text files. The one place it can lead to a
  transmission is its last question, which can hand the saved text to a chat program (see
  "Sending").

## Try it

Count the groups in a text, the way the check in the preamble counts them:

```sh
radiogram check "Rain on the bridge. Coffee is on."
```

It prints the count, then a colon, then the groups as they would be sent. Periods become the letter
X and question marks become QUERY, so a sentence's end is counted as a group.

List the ARL numbered texts, then show one:

```sh
radiogram arl
radiogram arl 46
```

Set up your defaults once, then write a radiogram:

```sh
radiogram setup
radiogram new
```

`new` asks the questions in the order set out under "What it can do". Press Enter to keep the answer
in brackets.

Read the help:

```sh
radiogram help
```

```text
radiogram: write, check, read and log ARRL NTS radiograms as plain text, ready for a VARA chat, a Winlink
message, or voice.

  radiogram new                 questions one at a time, most answered by Enter from what it remembers
  radiogram new --send CALL     the same, then handed to xarachat to send to CALL
  radiogram setup               your station, place, signature, usual precedence and the station you send traffic to
  radiogram address [list|show NAME|add NAME|remove NAME]   the address book of saved addressees
  radiogram check TEXT          the group count for a text, the way the check in the preamble counts it
  radiogram parse FILE          read a received radiogram, show it as a delivery form, log it as received
  radiogram arl [NUMBER]        the ARL numbered texts, or one of them
  radiogram log                 the traffic log
  radiogram list                radiograms kept on this machine

It remembers: every addressee, place, station, signature and destination you use is offered next time,
and Tab completes from them. Files: ~/.local/share/xarachat/radiograms/ (one file per message, traffic-log.txt),
~/.config/xarachat/radiogram.conf (your defaults and what it has learned), addresses.txt beside it. GPL-2.0-or-later, 2026.
```

## What it can do

### radiogram new

It asks, in this order. Enter keeps the answer in brackets. Tab completes from what it remembers.

1. Message number. It starts at 1 and goes up by one each time.
2. Precedence: R routine, W welfare, P priority, or EMERGENCY.
3. Handling instructions: HXA to HXG, or none. It prints what the one you chose means.
4. Station of origin, which is your call.
5. Place of origin, city and state.
6. Time filed: four digits of UTC, `now`, or `none`.
7. Date, month and day.
8. The addressee. A saved short name fills every line of the address. Otherwise you type the lines,
   one at a time, and an empty line ends the address. It then offers to save the addressee under a
   short name.
9. The text, one line at a time, ending with an empty line. The tool turns it into groups: upper
   case, periods become X, question marks become QUERY, other punctuation is dropped. Write `ARL 46`
   for a numbered text (see below). It prints the check, and warns when there are more than 25
   groups and it may be worth splitting the message.
10. Signature.
11. An op note, or none.
12. Whether to send it now with a chat program (see "Sending"). Answer `none` to only save it.

It then prints the radiogram as it is sent, one line at a time:

- the preamble line: `NR`, the number, the precedence, the handling instruction if any, the station,
  the check, the place, the time filed if any, and the date;
- the address lines;
- `BT`, which separates the address from the text;
- the text, in lines of five groups;
- `BT` again;
- the signature, then an `OP NOTE` line if you gave one;
- `AR`, which ends the message.

The handling instructions are:

- HXA: collect landline delivery authorized by the addressee within the given miles.
- HXB: cancel if not delivered within the given hours of filing time; service the originating
  station.
- HXC: report the date and time of delivery to the originating station.
- HXD: report to the originating station who it was received from, with the date and time, and the
  station it was relayed to.
- HXE: the delivering station gets a reply from the addressee and originates a message back.
- HXF: hold delivery until the given date.
- HXG: delivery by mail or toll call is not required; if it costs money, cancel and service the
  originating station.

The precedences are Routine, Welfare, Priority and Emergency.

### ARL numbered texts

ARL texts are standard messages with a number, from the ARRL's list. `radiogram arl` lists them with
their numbers and spelled-out numbers (for example 46 is FORTY SIX), and `radiogram arl 46` shows
one, with blanks shown as three underscores. In a text, write `ARL 46`, and the tool spells the
number and makes the check read `ARL` and the group count. When a received radiogram uses an ARL
text, the delivery form says what it means.

### Sending

`radiogram new` saves the message as a text file under `~/.local/share/xarachat/radiograms/`, one
file per message, named with the date, `sent`, the number and your call. It also adds a line to
`traffic-log.txt` in that folder, with the UTC time.

The saved file is plain text. You can send it by voice, in a Winlink message, or in a VARA chat.

The last question, "Send it now with xarachat to station, or none", hands the file to a chat program
named `xarachat`, which connects, sends the lines and stays in the chat. `radiogram new --send CALL`
answers that question for you. A chat program is optional, and this project does not include one. If
you answer `none`, the tool prints the command for sending the saved file later. See [VARA, xara and
chat](vara-and-chat.md).

### Other subcommands

- `radiogram setup`: asks for your call, place, usual signature, usual precedence, usual handling
  instructions, and the station you normally send traffic to. You can run it again at any time.
- `radiogram address [list|show NAME|add NAME|remove NAME]`: the address book. `add` asks for the
  address lines. The book is a plain file with one block per addressee.
- `radiogram check TEXT`: the group count, with the groups. With no text it reads the text from
  standard input.
- `radiogram parse FILE`: reads a received radiogram in the form above (use `-` to read standard
  input), prints it as a delivery form with labels, and tells you if the check in the preamble does
  not match the count, so you can service the originating station. It asks who you received it from,
  saves a copy, and logs it as received.
- `radiogram log`: prints the traffic log, or "no traffic yet".
- `radiogram list`: the radiogram files kept on this machine.

## Settings

Your answers are remembered in `~/.config/xarachat/radiogram.conf`. It is a plain text file you may
edit: `station`, `place`, `signature`, `precedence`, `hx`, `send_to` (the station traffic normally
goes to), `next` (the next message number), and the lists `places`, `stations` and `signatures`,
whose items are separated by a vertical bar with spaces around it. The address book is
`addresses.txt` in the same folder. If you have not set `station`, the tool offers the `mycall` from
`~/.config/xarachat/xarachat.conf` when that file exists. There is nothing for this tool in
`d750ctrl.conf`. See the [settings page](settings.md).

## When something goes wrong

- **You see:** an error that the first line should start with NR, or that the text should sit
  between two BT lines.
  - **Why:** `radiogram parse` was given text that is not in the radiogram form shown above.
  - **What to do:** check the file. The first line is the preamble and starts with `NR`, and the
    text sits between two lines that say `BT`.

- **You see:** "check mismatch: the preamble says X, the text counts Y".
  - **Why:** the check in the received preamble does not match the number of groups in the text.
  - **What to do:** service the originating station, as the message says.

- **You see:** "Fail: --send needs a call sign".
  - **Why:** `--send` was the last word on the line.
  - **What to do:** add the call sign after it.

- **You see:** the program fails when it hands the file to a chat program.
  - **Why:** that program is not installed.
  - **What to do:** answer `none` at the last question and send the saved file another way.

## See also

- [Station tools](station-tools.md)
- [d750ctrl: the rig screen](d750ctrl.md)
- [VARA, xara and chat](vara-and-chat.md)
- [Settings reference](settings.md)
- [Glossary](glossary.md)
