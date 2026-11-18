# aprschat: APRS messages from the terminal

## What it is for

`aprschat` lets you send and read APRS messages in a terminal, over SSH or at the console. It looks
and works like a chat program: you pick a station, type, and press Enter. It also has a line mode
for screen readers and Braille displays that prints one event per line and never redraws the screen.

aprschat does not touch the radio. It hands messages to [d750-aprs](aprs.md), which does the radio
side: it sends with retries until the other station acknowledges, acknowledges what comes in, and
writes every message event to a history file that aprschat reads.

## Before you start

- [d750-aprs](aprs.md) is running, with your `call` set in `aprs.conf`. aprschat takes your call
  from that file.
- **Messages go out only while transmit is on** in d750-aprs. With it off, a message you type is
  queued, waits, and is sent when you run `d750-aprs transmit on`. The top line shows "Transmit on"
  or "Transmit off, messages wait", so you can see which it is.
- aprschat is plain Python with nothing else to install.

## Try it

Open the screen, talking with a station:

```sh
aprschat W7XYZ
```

Open line mode instead, for a screen reader:

```sh
aprschat --line W7XYZ
```

Both start by showing the last lines of the conversation, if there is one. In line mode the first
line says "aprschat for", your call, "line mode", and whether transmit is on. Type `/help` to see
the commands.

Type a line and press Enter to send it. A line you send is shown with what became of it, such as
"Waiting to go out." or "Sent, try 1 of 5, waiting for the acknowledgement." and then
"Acknowledged."

Quit the screen with F10. Quit line mode with `/quit`.

Show the program's help:

```sh
aprschat --help
```

```text
aprschat: APRS messages from the terminal, through d750-aprs.

Over SSH or at the console. The screen works like xarachat's: the top line says who you are talking with,
the middle is the conversation, the bottom line is where you type, and the cursor rests there. Enter sends.
Line mode (--line) prints one event per line and never redraws, for a screen reader or a Braille display.

d750-aprs does the radio side: it sends with retries until acknowledged, acknowledges what comes in, and
writes every message event to its history file, which this program reads. Nothing here opens the radio.
Written Wednesday, November 11, 2026.

Usage: aprschat [CALL]          the screen; aprschat --line [CALL]   one event per line
```

## What it can do

### The screen

- The top line says who you are (your call), who you are talking with, how many unread messages wait
  from other stations, and whether transmit is on. It ends with "F1 help, F10 quits."
- The middle is the conversation, oldest at the top. Each line has the time, who said it and what.
  Messages that came through the internet say so at the end.
- The bottom line is where you type. The cursor stays there. It begins "To" and the other station's
  call.

If you give no call, aprschat opens the last conversation, or asks you to choose one.

### Keys on the screen

- Enter: send what you typed to the station named on the top line.
- F2: talk to another station. Type its call sign and press Enter. Enter alone takes the previous
  one. Escape cancels.
- F3: list the conversations, newest first, with the number unread. Up and Down choose, Enter opens,
  Escape goes back.
- F4: go to the next conversation with unread messages.
- Page Up and Page Down: scroll the conversation.
- Up and Down: bring back lines you typed earlier. Down past the last one clears the line.
- Backspace: delete a character. Ctrl+U: clear the typing line.
- F1: show the help. F10: quit.

When a message arrives from a station you are not talking with, a line says so, and F4 goes there.

### Commands inside the chat

Type these at the typing line, in the screen or in line mode:

- `/to CALL`: talk to that station. It needs a call sign, such as `/to N0CALL-7`. A call sign has 3
  to 6 letters and digits, at least one digit, and an optional SSID from 0 to 15.
- `/list`: list the conversations. In line mode it prints their calls on one line.
- `/status`: show d750-aprs's own status line.
- `/quit`: quit. `/q` and `/exit` also work.
- `/help`: show the commands. On the screen it shows the key help.
- Screen only: `/next` goes to the next unread conversation.

Anything else you type, on a line that does not start with a slash, is sent as a message to the
current station. If no station is chosen yet, aprschat says so.

### Line mode

`aprschat --line [CALL]` prints one event per line and never redraws. It is also used on its own
whenever its output is not a terminal. Use it with a screen reader or a Braille display. It prints:

- the time (HH:MM, or the month, day and time for an older message), then who and what;
- "New from CALL" for a message from a station you are not talking with;
- what became of each of your messages: "Sent to CALL, try 2 of 5", "CALL acknowledged", "CALL
  refused", or "CALL did not acknowledge after 5 tries".

Line mode reads what you type one line at a time, so a screen reader can follow it as it would any
line-based program.

### What each message state means

The state of each message you sent is shown as a sentence:

- Waiting to go out: queued in d750-aprs, not sent yet. This is also what you see while transmit is
  off.
- Sent, try N of 5, waiting for the acknowledgement: it went out on the air, and the other station
  has not answered yet. d750-aprs sends it again, up to 5 tries in all, waiting longer between
  tries.
- Acknowledged: the other station said it received it.
- Refused: the other station sent a refusal.
- Not acknowledged after 5 tries: nobody answered. d750-aprs gave up.

### Long messages

An APRS message holds at most 67 characters. A longer message is split into parts, between words,
and each part is sent as its own message with its own number and its own state. So a long message
appears as several lines, each with its own "Acknowledged".

### Where the history is kept

- `~/.local/share/d750ctrl/log/messages.jsonl`: every message event, written by d750-aprs. One line
  is one event in JSON form. aprschat reads it and keeps reading as it grows.
- `~/.local/state/d750ctrl/aprschat.json`: which conversation you were in, and what you have read.

## Settings

aprschat has no settings file of its own. It takes your call from `call` in `aprs.conf`. The
environment variables `APRSCHAT_MESSAGES`, `APRSCHAT_SOCK` and `APRSCHAT_STATE` point it at other
files; the tests use them. See the [settings page](settings.md).

## When something goes wrong

- **You see:** "Not sent: d750-aprs is not running. Start it with: systemctl --user start
  d750-aprs".
  - **Why:** the daemon is not running, so there is nothing to hand the message to.
  - **What to do:** start it. See [d750-aprs](aprs.md).

- **You see:** a message stays at "Waiting to go out".
  - **Why:** transmit is off in d750-aprs, or the TNC is not connected.
  - **What to do:** check the top line. Run `d750-aprs transmit on` if you mean to send, and
    `d750-aprs status` to see whether the TNC is connected.

- **You see:** "Not a call sign: ..." and the program exits with code 2.
  - **Why:** the call sign on the command line is not valid.
  - **What to do:** give a call such as `N0CALL-7`.

- **You see:** "Give a call sign: /to N0CALL-7".
  - **Why:** the call after `/to` is not valid.
  - **What to do:** type a valid call.

- **You see:** a message to a station ends "Not acknowledged after 5 tries".
  - **Why:** the other station is not on the air, not in range, or does not acknowledge messages.
  - **What to do:** try later, or send again.

## See also

- [d750-aprs](aprs.md)
- [Settings reference](settings.md)
- [Screen readers](screen-readers.md)
- [Troubleshooting](troubleshooting.md)
- [Glossary](glossary.md)
