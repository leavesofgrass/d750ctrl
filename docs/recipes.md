# Recipes: short how-tos for common tasks

Each recipe is a few lines. A recipe that transmits says so in its first line. Add `-n` anywhere on
a `d750` command to see what would be sent without changing the radio. The memory channels shown in
the examples are the pretend radio's; see [Try it without a radio](try-without-a-radio.md).

## Tune to a frequency

This does not transmit. Band A and band B are named by letter.

```sh
d750 freq A 146.520 -n
d750 freq A 146.520
d750 mode A fm
```

The first line is the dry run. The second sets the frequency and prints before and after. The third
sets the mode: fm, nfm, am or dv. If the radio refuses a frequency, you see a line that starts with
Fail and the exit code is 1. `d750 band A` makes band A the control and transmit band.

## Change power

This does not transmit, but it sets how strong later transmissions will be.

```sh
d750 power A low
```

The levels are high, mid, low and el. The verb may print a note that the command is not yet verified
on this radio; run `d750 probe` once to check which commands your radio answers.

## Watch a channel for activity

This does not transmit. It reads the squelch of one band.

```sh
d750 busy B
d750 watch B 60
```

The first line says busy or quiet now. The second watches for 60 seconds, once a second, and prints
a line only when the state changes, then how many times the squelch opened. Without the number of
seconds, it watches for 30.

## Recall a memory

This does not transmit. It tunes a band to a stored channel.

```sh
d750 mem list 0 5
d750 mem show 0
d750 mem goto A 1
```

The first line lists the channels in that range that hold something. The second shows one channel,
field by field. The third recalls channel 1 on band A. `d750 mem export FILE` and
`d750 mem import FILE` save and restore channels; try the import with `-n` first.

## Lock the transmitter and unkey

This does not transmit; it stops transmitting. The lock is held by d750d.

```sh
d750 lock
d750 ptt off
d750 unlock
```

`d750 lock` unkeys the radio and makes d750d refuse every key request until you unlock. It also
refuses turning VOX on and putting the TNC into APRS or KISS mode, but it does not stop KISS frames
through a TNC already in KISS mode; `d750-aprs transmit off` does that. See [what lock
covers](d750d.md#what-lock-covers-and-what-it-does-not).
`d750 ptt off` unkeys the radio now. In the rig screen capital L locks at once, and asks "Unlock PTT? y or n"
before it unlocks. The letter u unkeys in the face and compact views, and capital U in every view.
The screen's raw command line (the colon) refuses `lock` and `unlock`.

## Set the radio's clock

This does not transmit.

```sh
d750 clock
d750 clock set -n
d750 clock set
```

The first line shows the radio's clock beside your computer's. The second shows what would be sent.
The third sets the radio's clock from your computer.

## Send an APRS message

This transmits on the air. Nothing transmits until you turn it on, and d750-aprs must be running.

```sh
d750-aprs transmit on
d750-aprs send N0CALL-7 "Crows on the wire again"
d750-aprs last 20
d750-aprs transmit off
```

The message is retried until the other station acknowledges it. The last command stops every
transmission again. For a conversation, use `aprschat --line N0CALL-7`. Details are on the
[aprschat](aprschat.md) and [d750-aprs](aprs.md) pages.

## Become a receive-only iGate

This does not transmit what it gates. It passes packets the radio hears to the APRS-IS network, and
never sends anything from the internet out on the air.

```sh
d750-aprs igate on
d750-aprs status
d750-aprs igate off
```

It needs the APRS-IS passcode for your call in the `aprsis_pass` setting of
`~/.config/d750ctrl/aprs.conf`. See the [d750-aprs](aprs.md) page for the rest.

## Send one RTTY line and one SSTV picture

This transmits on the air. Both tools pause xara, key the radio through d750d, send, unkey and start
xara again.

```sh
d750-rtty tx "CQ CQ DE N0CALL"
d750-sstv tx picture.png
```

The SSTV mode is ROBOT_36 unless you name another after the file name; `d750-sstv modes` lists them.
Both tools need the Python environment that `install.sh` makes and the radio's sound card. See
[d750-sstv and d750-rtty](sstv-and-rtty.md), which also covers receiving.

## See also

- [d750](d750.md): every verb.
- [d750-aprs](aprs.md)
- [aprschat](aprschat.md)
- [d750-sstv and d750-rtty](sstv-and-rtty.md)
- [Troubleshooting](troubleshooting.md)
