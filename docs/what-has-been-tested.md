# What has been tested, and what has not

This page says plainly how far each part of d750ctrl has been proven, so you know what to trust and
what to watch.

## With a real radio

The author runs these tools every day on one station: a Kenwood TM-D750 on a computer running
CachyOS, which is a relative of Arch Linux. Everything that was in the project before this version
has been used there, on the air:

- The daemon, d750d, and the programs that key and tune the radio through it.
- The verbs of `d750` and the rig screen, `d750ctrl`.
- `d750-aprs`: the beacon, the receive-only iGate, the fill-in digipeater and messages. It ran on
  the air for a full week before this version.
- `aprschat`.

To see what your own radio reports, run:

```sh
d750 doctor
d750 probe
```

`d750 doctor` prints the radio's firmware and type, or a note if the radio does not answer.
`d750 probe` asks the radio, read only, which
commands it answers.

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
- `station/install-station.sh`.
- The firmware line in `d750 doctor`.
- Keying for `d750-sstv tx` and `d750-rtty tx`. Before this version they keyed the radio and
  unkeyed it a few milliseconds later. The keyer now holds one connection to d750d for the whole
  transmission. It is proven against the pretend radio only, not yet on the air. See
  [SSTV and RTTY](sstv-and-rtty.md).
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

- **Other Linux distributions, with a real radio.** Package names, the udev rule and user services
  may need adjusting. [Installing](install.md) says what is likely to differ.
- **Other firmware versions.** The commands the tools rely on were learned from one radio.
- **Systems other than Linux.** The installer uses systemd user services and a udev rule. There is
  no macOS or Windows version.
- **Whether the radio is really transmitting after it restarts by itself.** `d750-aprs` cannot tell,
  and says only what it knows. [APRS](aprs.md) explains why.
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
