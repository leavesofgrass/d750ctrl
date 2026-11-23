# Settings: every settings file and environment variable

This page lists every setting the d750ctrl tools read. For each one it gives the name, what it does,
its default, and an example. Settings for the station tools (`station.conf` and `notify.conf`) are
on the [station tools page](station-tools.md).

## Where settings and data live

- `~/.config/d750ctrl/d750ctrl.conf`: the main settings. `install.sh` writes it from
  `config/d750ctrl.conf.example` the first time, with your call sign.
- `~/.config/d750ctrl/aprs.conf`: the settings for d750-aprs. `install.sh` writes it from
  `config/aprs.conf.example` if there is none.
- `~/.config/d750ctrl/fixup.conf`: what `d750 fixup` puts back. `d750 fixup` writes it the first
  time.
- `~/.config/d750ctrl/commands.txt`: the table `d750 probe` writes. It is not a setting.
- `~/.config/xara/xara.conf`: xara's own settings, which `d750 vara` reads and edits. See [VARA,
  xara and chat](vara-and-chat.md).
- `~/.config/kuma-push-url-aprs-tnc`, `-igate`, `-heard` and `-beacon`: optional, one Uptime Kuma
  push URL in each. See [d750-aprs](aprs.md).
- `~/.local/share/d750ctrl/log/`: d750d and d750-aprs logs, and the message history.
- `~/.local/share/d750ctrl/sstv/` and `~/.local/share/d750ctrl/rtty/`: pictures, recordings and
  text.
- `~/.local/state/d750ctrl/aprs.json` and `aprschat.json`: state that the tools keep for themselves.
- `~/.config/xarachat/radiogram.conf` and `addresses.txt`: what `radiogram` remembers. See
  [radiogram](radiogram.md).

## File format

Both main files are plain text, one `key = value` per line. Spaces around the equals sign do not
matter.

- `d750ctrl.conf`: a line that starts with `#` is a comment. A `#` later in a line is part of the
  value, so do not put a comment after a value. Names are not case sensitive.
- `aprs.conf`: a `#` starts a comment anywhere in a line, so a value cannot contain a `#`.
- `fixup.conf`: `KEY=VALUE` with no spaces around the equals sign, and comments after the value.

## d750ctrl.conf

Read by `d750`, by the [rig screen](d750ctrl.md), and by the tools that key the radio.

- `mycall`: your call sign, for the CQ and beacon frames (`d750 vara cq`, `d750 vara beacon`, and
  the `c` key on the rig screen). The SSID is dropped, and the beacon adds SSID 9. Default: none.
  The rig screen uses `N0CALL` when it is empty, and `d750 vara` stops. Example: `mycall = N0CALL`.
- `varac`: what the `o` key opens for VarAC chat. `xarachat` opens that program with VarAC's
  framing. `openslot` opens OpenSlot's terminal client. Any other value acts like `xarachat`.
  Default: `xarachat`. Example: `varac = openslot`.
- `bluetooth`: the radio's Bluetooth address, for the pairing checks in `d750 doctor` and
  `d750 fixup`. Leave it empty if the radio is not paired. Default: empty. Example:
  `bluetooth = AA:BB:CC:DD:EE:FF`.
- `ptt_port`: d750d's Hamlib port. Default: `4532`. Example: `ptt_port = 4532`.
- `cmd_port`: d750d's command port. Default: `4533`. Example: `cmd_port = 4533`.
- `status_seconds`: how often the rig screen reads everything, about 15 CAT commands. Not less than
  0.5. Default: `2`. Example: `status_seconds = 2`.
- `busy_seconds`: how often it reads only the busy flags of both bands, 2 commands. Not less than
  0.25. `0` reads them with the rest. Which views read them this often is up to `live_meters`
  below. Default: `1`. Example: `busy_seconds = 1`.
- `workspace`: `yes` runs the rig screen inside tmux with a window for each tool. `no`, `off`, `0`
  or `false` runs everything in one terminal, like `d750ctrl --no-tmux`. Default: `yes`.
- `rig_key`: the tmux key that returns to the rig screen. A tmux key name. Default: `F9`.
- `next_key`: the tmux key that steps to the next window. Default: `F12`.

### The rig screen's views and looks

These settings are for the [rig screen](d750ctrl.md). Each has an option of the same name, and the
option wins. A value the screen does not know is skipped and the default is used. When anything was
skipped, the first message on the screen says "Settings skipped. Try d750ctrl --check". Run
`d750ctrl --check` to see what is in force and what was skipped.

- `view`: which view the screen starts in. `face` shows both bands side by side. `list` shows one
  control a row, and is the view built for speech and Braille. `compact` shows three rows of facts.
  See [Choosing a view](choosing-a-view.md). Default: `face`. Option: `--view NAME`. Example:
  `view = list`.
- `theme`: the colors of the face. `dark`, `blue` or `mono`. `mono` has no color. A set `NO_COLOR`
  variable that is not empty also means `mono`, unless you give `--theme`. No theme uses red or
  green, and color never carries a meaning alone. Default: `dark`. Option: `--theme NAME`.
- `digits`: `big` draws the active band's frequency in large digits when the window is 17 rows or
  more, and the band is read. `plain` never does. Default: `big`. Option: `--digits NAME`. The
  older `--ascii` means `--digits plain`.
- `live_meters`: how often the busy lamps are read. `auto` reads them every `busy_seconds` in the
  wide face only, and with each full read in the list, the stacked face and compact. `yes` reads
  them every `busy_seconds` in every view. `no` reads them with each full read in every view. The
  older words `on`, `true` and `1` mean `yes`, and `off`, `false` and `0` mean `no`. Default: `auto`.
- `announce`: where a change is told. `message` puts the focused row's line in the message row when
  you move or change a value in the list, and the new frequency when you tune in the face and
  compact. `cursor` leaves the message row for refusals, errors and events, so a screen reader that
  follows the cursor is not told twice. Default: `message`.

### The [keys] section

A line `[keys]` in `d750ctrl.conf` starts a section. Every line after it is a key change, until
another line in square brackets. Put the section last. A line in it is not a setting.

- A line is `action = key, key`. It gives the action those keys, and takes them from any other
  action. Up to 4 keys. `none` takes every key away, except from `unkey` and `lock`, which always
  keep one.
- Action names are the ones `d750ctrl --check` prints, such as `quit`, `unkey`, `lock`, `memory` and
  `act-power`. Hyphens or underscores. The list view and the face have some different ones.
- A key is a single printable character, or `tab`, `space`, `enter`, `up`, `down`, `left`, `right`,
  `pgup`, `pgdn`, `home`, `end`, `backspace`, `comma` or `f1` to `f12`.
- Never changed: Ctrl+C, Ctrl+L, Escape, the digits and the period. Never given to an action: `y`
  and `n`, which only answer questions.
- A line that cannot be used is skipped, and `d750ctrl --check` says which line and why.

Examples. Every line is a comment in the example file.

```text
[keys]
quit = Q
unkey = F5
act-power = P
```

Keys in a view are described on the [keys page](keys.md).

## aprs.conf

Read by [d750-aprs](aprs.md), and `call` is also read by [aprschat](aprschat.md). The daemon reads
the file when it starts. After an edit, restart it with `systemctl --user restart d750-aprs`. The
subcommands `transmit`, `digi` and `igate` change their own lines for you.

### Your station

- `call`: your call sign with the SSID this station beacons as. Default: `N0CALL`. Example:
  `call = N0CALL-2`.
- `tnc`: the TNC's serial port. Default: `/dev/d750-tnc`. Example: `tnc = /dev/d750-tnc`.
- `tnc_lines`: the port's DTR and RTS lines, `raised` or `low`. Default: `raised`.
- `lat` and `lon`: the beacon's position in decimal degrees, north and east positive. Default:
  empty, which means no beacon. Example: `lat = 45.5189` and `lon = -122.6793`, an example position.
- `symbol`: the APRS symbol, table character then code. `/-` is a house. Default: `/-`.
- `comment`: text added to the beacon. The whole beacon is cut at 80 characters. Default: empty. The
  example file says `home station`.
- `path`: the digipeater path the station uses. Default: `WIDE1-1,WIDE2-1`.
- `interval`: minutes between beacons. Not less than 10. Default: `30`.
- `tocall`: the destination name in every packet the station sends. It is not in the example file.
  Default: `APZ750`.
- `units`: `mi` or `km`, for distances and speeds in the plain lines. Default: `mi`.

### Transmitting

- `transmit`: `on` (also `yes` or `true`) allows beacons, messages, acknowledgements, the digipeater
  and KISS programs to transmit. Anything else is off. Default: `off`. Change it with
  `d750-aprs transmit on`.

### KISS programs and the TNC

- `kiss_listen`: where KISS programs can connect, space separated `host:port`. Default:
  `127.0.0.1:8001`.
- `kiss_txdelay`: the TNC's TX delay, in 10 ms units. Default: `30`.
- `kiss_persist`: persistence, 0 to 255. Default: `255`.
- `kiss_slottime`: slot time, in 10 ms units. Default: `10`.

These three are sent to the TNC every time d750-aprs connects to it.

### The iGate

- `igate`: `rx`, `on` or `yes` passes what the radio hears to APRS-IS. Anything else is off.
  Default: `off`. Change it with `d750-aprs igate on`, which writes `rx`.
- `aprsis_server`: the APRS-IS server, `host:port`. Default: `noam.aprs2.net:14580`.
- `aprsis_pass`: your APRS-IS passcode. Default: empty, and then nothing is gated. Keep the file
  readable by you only.
- `aprsis_beacon`: what happens after each beacon on the air. `watch` looks on APRS-IS for 60
  seconds and says which iGate carried it. `fallback` does that and sends the beacon to APRS-IS
  directly if none did. `on` always sends it directly. `off` does neither. Default: `fallback`.

### The digipeater

- `digi`: `off`, `fillin` or `wide`. It needs `transmit = on`. Default: `off`. Change it with
  `d750-aprs digi fillin`.
- `digi_aliases`: other names this station answers to as a digipeater, separated by spaces or
  commas. Default: empty.
- `digi_max_hops`: the most hops a WIDEn-N may ask for. Default: `2`.
- `digi_viscous`: seconds a fill-in repeat waits, dropped if another digipeater repeats it first.
  `0` repeats at once. Default: `0`.
- `digi_dupe`: seconds within which a packet heard again counts as a duplicate and is not repeated.
  Not less than 5. Default: `30`.

### Notices and restarts

- `notify`: `on` or `yes` sends ntfy notices through the `notify` command. Default: `on`.
- `notify_topic`: the topic for APRS messages for this station and for failed messages. Default:
  `aprs`. The restart notices go to the topic `alerts`.
- `restart_check`: `on` or `yes` sends one check beacon after the TNC reset that follows a return of
  the radio. Default: `on`.
- `deaf_minutes`: minutes after a restart with nothing heard before one notice. `0` sends none.
  Default: `90`.
- `power_cycle_cmd`: a command for a power cycle after a real transmit check. Nothing runs it now.
  Default: empty. Example: `power_cycle_cmd = d750-power cycle 10`. The example file also shows a
  `curl` command that posts to a Home Assistant webhook, with placeholders for its address and ID.

### Status message

- `status`: the station's status message, up to 62 characters. Empty sends none. Default: empty.
  Example: `status = Fill-in digipeater and RX iGate`.
- `status_interval`: minutes between status messages. Not less than 30. Default: `360`.

## fixup.conf

Read by `d750 fixup`. It is written the first time with these defaults.

- `TNC`: the TNC mode and band, as two digits. Mode 0 is off, 1 is APRS, 2 is KISS. Band 0 is A and
  1 is B. Default: `TNC=2,1`, KISS on band B.
- `SQUELCH_B`: the data band's squelch, 0 to 9. Never 0 while menu 508 is on Busy, or the TNC will
  not transmit. `d750 fixup` checks band B. Default: `SQUELCH_B=3`.
- `GPS_OUTPUT`: GPS sentences to the PC port, `0` off or `1` on. Menu 403 Off also turns it off.
  Default: `GPS_OUTPUT=0`.

## Environment variables

For d750d (see [d750d](d750d.md)):

- `D750_PORT`: the radio's serial device. Default: `/dev/d750-cat`.
- `D750_PTT_PORT`: the Hamlib port. Default: `4532`. Also overrides `ptt_port` for `d750`, the rig
  screen and the SSTV and RTTY tools.
- `D750_CMD_PORT`: the command port. Default: `4533`. Also overrides `cmd_port` for `d750` and the
  rig screen.
- `D750_LOG_DIR`: the log folder. Default: `~/.local/share/d750ctrl/log`. `d750 log` reads it too.
- `D750_BAUD`: the serial speed. Default: `9600`.
- `D750_LOG_ALL`: any value except empty, `0`, `no`, `off` or `false` logs every exchange. Default:
  off.

For the tools:

- `D750_CONF_DIR`: the settings folder for `d750` and the rig screen. Default: `~/.config/d750ctrl`.
  The tests use a folder of their own. Example: `D750_CONF_DIR=/tmp/mytest d750 status`.
- `D750_XARA_PORT`: the port the rig screen sends the CQ and beacon frame to. Default: `8300`. It
  has no setting in the file. The tests point it at a port of their own.
- `NO_COLOR`: when set and not empty, the rig screen uses the `mono` theme unless you give
  `--theme`.
- `D750_RELAY_PORT`: the relay's serial port for `d750-power`. See [d750-power and the
  relay](power-relay.md).
- `APRSCHAT_MESSAGES`, `APRSCHAT_SOCK` and `APRSCHAT_STATE`: where aprschat reads the message
  history, talks to d750-aprs, and keeps its state. They exist for the tests.
- `XDG_RUNTIME_DIR`: where d750-aprs puts its control socket, `d750-aprs.sock`. If it is not set,
  `~/.cache` is used.
- `ESCDELAY`: how long curses waits after the Escape key. The rig screen sets it to 100 and aprschat
  to 50 unless you set it.
- `TMPDIR`: where `d750 level` and the tests make temporary files. Default: `/tmp`.

Some paths are fixed: d750-aprs always uses `~/.config/d750ctrl/aprs.conf` and
`~/.local/share/d750ctrl/log`, and the SSTV and RTTY tools read `ptt_port` from the standard
settings folder.

## See also

- [d750d: the daemon](d750d.md)
- [d750: the verbs](d750.md)
- [d750ctrl: the rig screen](d750ctrl.md)
- [Choosing a view](choosing-a-view.md) and [the keys](keys.md)
- [d750-aprs](aprs.md)
- [Station tools](station-tools.md)
- [Testing](testing.md)
