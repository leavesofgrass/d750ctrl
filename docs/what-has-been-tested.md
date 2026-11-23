# What has been tested, and what has not

This page says plainly how far each part of d750ctrl has been proven, so you know what to trust and
what to watch.

## With a real radio

The author runs these tools every day on one station: a Kenwood TM-D750 reporting firmware 1.03,
connected by USB to a computer running CachyOS, which is a relative of Arch Linux. Screen readers
and Braille displays were used in the testing. These have been used there, on the air:

- The daemon, d750d, and the programs that key and tune the radio through it.
- The verbs of `d750` and the rig screen, `d750ctrl`, as it was before the three views. The new screen
  has not been run against the radio; see below.
- `d750-aprs`: the beacon, the receive-only iGate, the fill-in digipeater and messages. It was
  tested extensively on the air for a full week before this version. Now and then something needed a
  hand, and every part works as expected.
- `aprschat`.
- The radio after it restarts by itself. This radio restarts about every 3 hours and 4 minutes. The
  cause is not known, and it does not follow a drop in supply voltage. It transmits normally after
  each restart: `d750-aprs`, which is already running, picks the radio up again and goes on
  regulating its transmissions.

To see what your own radio reports, run:

```sh
d750 doctor
d750 probe
```

`d750 doctor` prints the radio's firmware and type, or a note if the radio does not answer.
`d750 probe` asks the radio, read only, which commands it answers.

## In a closed loop, without the air

SSTV and RTTY were sent and received in a closed loop through a virtual sound device: what
`d750-sstv` and `d750-rtty` send was fed straight back and decoded. That proves the modems and the
sound path in software. It does not key a radio, and neither mode has been confirmed on the air yet.

## The installers, by hand

The first testing of the software was on Debian 13, over USB. The author has run `install.sh` and
`station/install-station.sh` by hand on an Arch Linux relative and on Debian. That testing covered
some of what the installers do, not every path through them. Fedora has been tried only by the
automated tests.

## By the automated tests

The tests run against a pretend radio, never a real one. They run on every push, on four
distributions on GitHub: Ubuntu, Debian, Fedora and Arch. [Testing](testing.md) lists each test and
how to run it yourself.

They prove that the programs behave as written. They do not prove that a radio behaves the way the
pretend radio does.

## New in this version, proven by the automated tests only

These parts are new or changed, and have not yet had time on the air:

- The station tools under `station/`, as they are packaged here. They came from the author's
  station, where they were written for one computer. Here `station` reads its list of services from
  a settings file, and `notify` reads its server and token from a settings file.
- Keying for `d750-sstv tx` and `d750-rtty tx`. Before this version they keyed the radio and unkeyed
  it a few milliseconds later. The keyer now holds one connection to d750d for the whole
  transmission. That is proven against the pretend radio only. See
  [SSTV and RTTY](sstv-and-rtty.md).
- The corrected exit codes of `d750`: 0 for Pass, 1 for Fail and 2 for usage, for every verb.
- The APRS service step of `install.sh`, which writes the `d750-aprs` service and the APRS settings
  file and never starts the service.
- The layout of `d750 help`, and the words `on` and `off` in the answer of `d750 vox on` and
  `d750 vox off`.

The firmware line in `d750 doctor` is new too. It has been run once on the author's radio, where it
printed firmware 1.03.

## The rig screen's three views: not tried by a person yet

The rig screen was rebuilt with three views (list, face and compact), remappable keys, themes and
`--check`. Its code moved into `d750ui/`. The automated tests cover it, and nothing else does yet:

- The decisions of every view, at many window sizes, with no terminal: `tests/screen-model-test.py` and
  `tests/keymap-test.py`. The screen itself, in a pseudo terminal against the pretend radio:
  `tests/d750ctrl-test.py`. The tmux workspace, in a real tmux with stand-in tools:
  `tests/d750ctrl-tmux-test.py`. See [Testing](testing.md).
- These checks do not send anything. No test answers a send question with `y`.

Not tested:

- **Any view with speech or Braille.** Nobody has used the list, the face or the compact view with a
  screen reader or a Braille display yet. Where the cursor sits, and what the message row says, are
  decided from the written rules and checked only as text.
- **The tmux workspace on a real station.** `tests/d750ctrl-tmux-test.py` runs the workspace in a real
  tmux with stand-in tools: the tool windows, the keys from `rig_key` and `next_key`, and the question
  when you quit with windows open. It has not been run with the real chat, SSTV and RTTY programs, or
  beside an operator's own tmux sessions on a station.
- **Colors on a real terminal.** The tests read the text on a pseudo terminal and the marks the model
  gives. They do not look at what a real terminal draws in `dark` or `blue`.
- **The real radio.** The new screen has not been run against the TM-D750.
- **A send, a CQ frame or a beacon from the new screen.** The questions are tested. The frame to xara
  goes to a port the test picked, and no send was finished.

## Not run automatically

- `tests/modes-test.sh`, the SSTV and RTTY round trip. It needs a sound server, so it runs only on a
  computer with one.
- The RTTY modem selftest. It needs the Python environment that `install.sh` makes.

## Not established

Nobody has shown these to work, or they are known not to be knowable from the computer:

- **SSTV and RTTY on the air.** See the closed loop above.
- **Bluetooth.** All testing was over USB. Nothing here has been used with the radio over Bluetooth.
- **Other Linux distributions, with a real radio day to day.** Only an Arch Linux relative has had
  the radio on it every day. Package names, the udev rule and user services may need adjusting
  elsewhere. [Installing](install.md) says what is likely to differ.
- **Other firmware versions.** The commands the tools rely on were learned from one radio, which
  reports firmware 1.03.
- **Systems other than Linux.** The installer uses systemd user services and a udev rule. There is
  no macOS or Windows version.
- **Knowing from the computer whether the radio transmits after it restarts by itself.** The author
  has seen it transmit after such restarts, but `d750-aprs` still cannot check that and says only
  what it knows. [APRS](aprs.md) explains why.
- **Why the radio restarts by itself.** The cause has not been found.
- **Power cycling the radio automatically.** `d750-power` and the relay work by hand. Nothing runs
  them for you yet.

## If you find something

A report of what worked or failed on your distribution, your firmware or your cabling is worth a
great deal to the next reader. Before you share a log, read it first: logs can hold call signs,
positions and the text of messages.

## See also

- [Testing](testing.md): each test, what it needs, and how to run it.
- [Installing](install.md): requirements, and what may differ on other distributions.
- [What the radio taught us](radio-notes.md): hard-won facts about the radio itself.
- [Troubleshooting](troubleshooting.md): what to do when something does not work.
