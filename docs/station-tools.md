# Station tools: the small programs that run the station computer

These tools live in the `station/` folder. They are not needed to control the radio. They help you
run a computer that keeps a station up: starting and stopping the services, sending notices to your
phone, watching the radio's health, and a few helpers for sound and Bluetooth.

They came from the author's own station, where they were written for one computer. Here they are
general: nothing in them names a person or a machine, and each reads its settings from a file. See
[What has been tested](what-has-been-tested.md) for how far that packaging has been proven.

## What is in the folder

- `station`: raise and lower the station's services by short names, with a question before anything
  that can transmit.
- `notify`: send one notice to an ntfy server. ntfy is a small program that pushes messages to a
  phone.
- `radiogram`: write, check and log NTS radiograms. It has its own page: [radiogram](radiogram.md).
- `d750d-kuma`: tell Uptime Kuma, a monitoring program, whether the daemon, the radio and xara are
  well.
- `xara-wait-audio`: wait for the radio's sound card before xara starts.
- `xara-radio-pair`: pair the computer with a radio over Bluetooth and list the sound names xara can
  use.
- `mode-listen`: step through the radio's mode codes on a weather broadcast so you can hear each
  one.

## Install them

They are installed separately from the core tools, so nothing here changes unless you ask.

```sh
cd ~/d750ctrl
station/install-station.sh
```

It needs no root and is safe to run twice. It prints numbered lines:

- It links the tools into `~/.local/bin`. It never replaces a file of your own: a name there that is
  not already a link into this folder is left alone, and it says so.
- It writes `station.conf` and `notify.conf` in `~/.config/d750ctrl` only when they are missing. The
  notify file is readable by you only.
- The Uptime Kuma timer is installed only when you ask for it:

```sh
station/install-station.sh --kuma
```

## station

### What it is for

One short command to see, start and stop the station's services, without remembering unit names. It
asks before a start that can transmit, and the answer No is the default. It unkeys the radio before
it stops the radio service.

It uses only `systemctl --user`, `docker` when you list a container, and `d750 ptt off`. It never
uses root and never uses the internet.

### Try it

```sh
station help
station status
station --dry-run stop xara
```

With no settings file, `station help` prints:

```text
station: raise and lower services.
Words:
status [NAME]: show
start NAME: raise
stop NAME: lower until a reboot
restart NAME: stop, then start
on NAME: start, and on at boot
off NAME: lower, and off at boot
help: this text
Station names:
radio: Radio service
xara: xara
aprs: APRS
all: the three above
all: start, stop, status only.
Options:
--dry-run: show commands, run none
--yes: skip the questions
Questions: start APRS.
No internet needed.
Examples:
station status
station stop xara
```

`--dry-run` shows the commands it would run and runs none. Use it first.

### What it can do

- `status`, for everything or for one name.
- `start`, `stop` and `restart`. Services start in the order of the settings file and stop in
  reverse.
- `on` and `off`: the same, and also on or off at boot.
- `all` as a name, for the whole station group. It accepts start, stop and status only.
- A question before any start or stop that you marked as needing one. `--yes` skips the questions.
- Before the radio service stops, it runs `d750 ptt off`, because stopping the service alone does
  not unkey the radio.
- After a stop, it tells you what else stopped working, when you listed dependents.

### Settings

The file is `~/.config/d750ctrl/station.conf`. With no file, station knows three services: the radio
service (d750d), xara and APRS. A file replaces that list completely. A mistake in the file is
refused with one line that names the file and the reason, and nothing runs.

The format is sections with `key = value` lines. Lines starting with `#` are comments. This is the
default list, as the example file writes it:

```text
[service radio]
unit = d750d.service
label = Radio service
unkey = yes
dependents = xara.service: xara cannot key until it is back.

[service xara]
unit = xara.service
no_block = yes
waiting = Waiting for the radio's sound card.

[service aprs]
unit = d750-aprs.service
label = APRS
warn = Starting APRS can transmit.
ask = Start APRS? No is the default
```

Each `[service NAME]` section is one service. NAME is the word you type. The order of the sections
is the start order.

The fields of a service:

- `unit`: the systemd user unit, when `kind` is `unit`. That is the default kind.
- `kind`: `unit` or `container`. A container also needs `container`, its name, and `compose`, the
  path to its compose file.
- `group`: `station`, the default, or `network`. The word `network` then works as a name for that
  group.
- `label`: the words printed first on every line about it. The default is NAME.
- `warn` and `ask`: said and asked before a start. Give both or neither.
- `stop_warn` and `stop_ask`: the same, before a stop.
- `stop_note`: said after a stop.
- `no_block`: `yes` means do not wait for it to finish starting. `waiting` is said while it starts.
- `unkey`: `yes` means run `d750 ptt off` before stopping it. Units only.
- `dependents`: one `UNIT: note` per line. The note is said when that unit is running and this one
  stops.
- `marker`: for containers only. A stop writes an empty marker file, so that a watchdog of your own
  can tell "lowered on purpose" from "fell over". `off` writes one that survives a reboot.

Three more sections are optional:

- `[protect]`: names that station refuses to touch, each with the reason it says back, as
  `name = reason`. Use it for the services you reach the computer by.
- `[watch]`: a timer that station only reads, to tell you when your watchdog is stopped. Its keys
  are `unit`, `name`, `label` and `group`.
- `[help]`: `never_touched`, a comma list printed in the help, and `examples`, one per line.

`station/station.conf.example` shows every field, with a container and a network unit commented out
as patterns to copy.

### When something goes wrong

- **"Settings:" and a reason, then nothing happens.** The settings file has a mistake. Fix the line
  it names. It never falls back to the default list silently.
- **"Not a known name".** The word is not a section in your settings file. `station help` lists the
  names it knows.
- **A start asked a question and nothing started.** The default answer is No. Type yes, or use
  `--yes`.

## notify

### What it is for

`d750-aprs` sends notices: an APRS message arrived, the radio restarted, the radio hears again. It
sends them by running a program named `notify`. This is that program. It posts one message to an
ntfy server and never fails its caller: if the server is down, the message is lost and the exit code
is still 0.

### Try it

```sh
notify test "Hello" "Crows on the wire again"
```

The form is `notify TOPIC TITLE MESSAGE [PRIORITY] [TAGS]`. PRIORITY is 1 to 5, and 3 is the
default.

### Settings

The file is `~/.config/d750ctrl/notify.conf`. Keep it readable by you only.

```text
server = http://127.0.0.1:2586
token =
```

- `server`: where your ntfy server listens, with no slash at the end. The default above is a server
  on this computer, on the port the author uses. A stock ntfy server listens on another port unless
  you set it, so check yours.
- `token`: an ntfy access token, if your server asks for one. Leave it empty and no token is sent.

`NOTIFY_SERVER` and `NOTIFY_TOKEN` in the environment override the file. The token is never put on a
command line, so other users of the computer cannot see it in the list of running programs.

### When something goes wrong

- **Nothing arrives and nothing complains.** That is by design: notify never fails its caller. Check
  the server address, then send a test by hand as above and look at your ntfy server's own log.

## d750d-kuma

It runs once a minute from a timer and tells Uptime Kuma whether d750d, the radio and xara are well.
It asks the daemon for its state and the radio for its ID: one CAT command a minute. CAT is the
radio's control language over the serial port.

A radio that is switched off is a normal state. While it is off, the radio and xara report up, with
the words "radio off", so nothing alarms. With the radio on, a radio or xara that does not answer
reports down, with the reason.

Put each monitor's push address in its own file, one line each. Uptime Kuma shows that address when
you make a monitor of the Push kind:

- `~/.config/kuma-push-url-d750d`
- `~/.config/kuma-push-url-xara`

A push is skipped while its file is missing. Treat the addresses like passwords: anyone who has one
can report for your monitor.

## xara-wait-audio

xara is the modem program that digital modes use. It fails if the radio's sound card is not there
yet, and a service that fails too often is given up on. This helper waits until the sound card named
in xara's settings is present, then waits ten more seconds for it to settle, so xara starts cleanly
when the radio is switched on.

```sh
xara-wait-audio
```

It prints one line when it starts waiting and one when the card is there. Give it another settings
file as its one argument if yours is not `~/.config/xara/xara.conf`.

## xara-radio-pair

Pairs the computer with a radio over Bluetooth and lists the sound names that xara can use.

```sh
xara-radio-pair scan
xara-radio-pair wait
xara-radio-pair devices
```

- `scan` looks for radios for 20 seconds and lists what answered.
- `wait` lets the radio find the computer: it is discoverable and pairable for 3 minutes.
- Give it a Bluetooth address to pair, trust and connect that radio, then list the names.
- `devices` lists the sound names xara can use right now.

## mode-listen

A listening test for the radio's mode codes. It tunes band A to a weather broadcast, steps through
mode codes 0, 1, 2 and 3 for four seconds each, and puts band A back as it was.

```sh
mode-listen
mode-listen 162.400
```

With no argument it uses 162.550 MHz. Give it the weather channel you can hear. It receives only and
never transmits. This is how the mode codes in [What the radio taught us](radio-notes.md) were
found.

## See also

- [radiogram](radiogram.md): the radiogram tool in this folder.
- [APRS](aprs.md): the notices that `d750-aprs` sends through notify.
- [Settings](settings.md): the settings of the core tools.
- [What has been tested](what-has-been-tested.md): how far these tools have been proven.
- [Glossary](glossary.md): ntfy, Uptime Kuma, systemd user service and the rest.
