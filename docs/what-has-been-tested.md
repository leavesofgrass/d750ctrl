# What has been tested, and what has not

This page says plainly how far each part of d750ctrl has been proven, so you know what to trust and
what to watch.

## With a real radio

The author runs these tools every day on one station: a Kenwood TM-D750 on a computer running
CachyOS, which is a relative of Arch Linux. These have been used there, on the air:

- The daemon, d750d, and the programs that key and tune the radio through it.
- The verbs of `d750` and the rig screen, `d750ctrl`.
- `d750-aprs`: the beacon, the receive-only iGate, the fill-in digipeater and messages. It ran on
  the air for a full week before this version.
- `aprschat`.
- Sending with `d750-sstv` and `d750-rtty`. Their keying was fixed in this version, and the author's
  transmit tests of both on the air then succeeded.
- The radio after it restarts by itself. An earlier restart once left it receiving but not
  transmitting. After thorough testing, the author has seen it transmit again after restarting by
  itself.

To see what your own radio reports, run:

```sh
d750 doctor
d750 probe
```

`d750 doctor` prints the radio's firmware and type, or a note if the radio does not answer.
`d750 probe` asks the radio, read only, which commands it answers.

## The installers, by hand

The author has run `install.sh` and `station/install-station.sh` by hand on an Arch Linux relative
and on Debian. That testing covered some of what the installers do, not every path through them.
Fedora has been tried only by the automated tests.

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
- The firmware line in `d750 doctor`.
- The corrected exit codes of `d750`: 0 for Pass, 1 for Fail and 2 for usage, for every verb.
- The APRS service step of `install.sh`, which writes the `d750-aprs` service and the APRS settings
  file and never starts the service.
- The layout of `d750 help`, and the words `on` and `off` in the answer of `d750 vox on` and
  `d750 vox off`.

## Not run automatically

- `modes-test.sh`, the SSTV and RTTY round trip. It needs a sound server, so it runs only on a
  computer with one.
- The RTTY modem selftest. It needs the Python environment that `install.sh` makes.

## Not established

Nobody has shown these to work, or they are known not to be knowable from the computer:

- **Other Linux distributions, with a real radio.** Only an Arch Linux relative has had the radio on
  it day to day. Package names, the udev rule and user services may need adjusting elsewhere.
  [Installing](install.md) says what is likely to differ.
- **Other firmware versions.** The commands the tools rely on were learned from one radio.
- **Systems other than Linux.** The installer uses systemd user services and a udev rule. There is
  no macOS or Windows version.
- **Knowing from the computer whether the radio transmits after it restarts by itself.** The author
  has seen it transmit after such restarts, but `d750-aprs` still cannot check that and says only
  what it knows. [APRS](aprs.md) explains why.
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
