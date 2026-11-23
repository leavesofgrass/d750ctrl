# Testing: for people who change the code

## What it is for

The project's tests prove the tools work without a radio. They run against a simulator, a pretend
TM-D750 that answers Kenwood commands on a pseudo terminal, so nothing here needs your radio, and
**no test ever keys a radio**. This page is for people who change the code. If you only want to try
the tools without a radio, see [Try it without a radio](try-without-a-radio.md).

## Before you start

- A Linux computer with `python3`, `bash`, and the project cloned.
- `pyserial` for Python (the test daemon uses it), `nc` (netcat), and Hamlib's `rigctl`. On Debian
  or Ubuntu the packages are `python3-serial`, `netcat-openbsd` and `libhamlib-utils`. The packages
  for Fedora and Arch are listed in [Install](install.md), under "Other distributions".
- The `d750` command on your PATH for `tests/tests.sh`. The GitHub workflow does this by adding the
  project folder to PATH.
- For the two sound tests only: a PulseAudio or PipeWire sound server with `pactl`, and the `.venv`
  that `install.sh` makes.

## Try it

Start the test bed in one terminal. It runs the simulator and a second d750d on ports 4542 (Hamlib)
and 4543 (commands), and writes its logs under `~/.local/share/d750ctrl/log/test`:

```sh
tests/test-env.sh
```

It prints the simulator's device path and the daemon's process number, and keeps running until you
stop it. In another terminal, run the verbs' test:

```sh
tests/tests.sh
```

Each check prints "Pass:" or "Fail:" and the last line is the total. Each test prints its own
count. To stop the test bed, end the
two processes whose numbers are in `~/.local/share/d750ctrl/log/test/pids`.

You can also use the test bed by hand, for example:

```sh
D750_CMD_PORT=4543 D750_PTT_PORT=4542 d750 status
```

## What it can do

### The tests

- `tests/tests.sh`: the `d750` verbs and d750d, against the test bed. It runs every verb and
  checks the answers, the dry runs, the refusals, the lock and keying through the Hamlib port, the
  rigctl commands (a handshake, frequency, mode, VFO, levels and an extended reply), what d750d logs
  and what it leaves out, the firmware line of `d750 doctor`, the keying that `d750-sstv tx` and
  `d750-rtty tx` use (the radio stays keyed for the whole block and is unkeyed after it), and a
  daemon started with no radio. It needs the test bed running, `d750`
  on the PATH, `nc` and `rigctl`. It uses a settings folder of its own, so your `fixup.conf` and
  your call sign stay out of it.
- `python3 tests/d750ctrl-test.py`: the rig screen, under a pseudo terminal. It presses the
  keys, and checks what the simulated radio ended up with and what the screen showed: each view at
  two window sizes, the cursor, the questions, `--check`, a `[keys]` section, a window that is too
  small, and every way out. It also counts how often the screen reads the radio. It starts its own
  test bed, so stop the one you started for `tests/tests.sh` first, as the GitHub workflow does. It
  sets `D750_XARA_PORT` to a port of its own and puts stubs for the chat, SSTV and RTTY programs first
  on the path. It never answers a send question with `y`.
- `python3 tests/d750ctrl-tmux-test.py`: the rig screen's tmux workspace, in a real tmux. It starts
  the screen without `--no-tmux` and checks the session and its `rig` window, a tool window with and
  without a pause, going back to a window that is open, the keys from `rig_key` and `next_key`, the
  list of open windows, both answers to the question when you quit with windows open, and that typed
  text reaches a tool whole and is never read by a shell. It uses only the tmux socket named `d750`,
  with the same stubs and the same test bed. When tmux is not installed it prints a note and passes.
- `python3 -I tests/keymap-test.py`: which action each key means, in both families of keys, the
  `[keys]` rules and what is skipped. It needs no terminal, no daemon and no test bed.
- `python3 -I tests/screen-model-test.py`: the rig screen's decisions, with no terminal: the frames
  of each view at many window sizes, the 40-cell line rule, the reading rates, every question, and the
  safety rules, with a walk of random keys. It needs no terminal, no daemon and no test bed.
- `python3 -I tests/showframe.py VIEW WIDTHxHEIGHT [KEY ...]`: not a test. It prints one frame of a
  view as plain lines, from the pretend daemon in `tests/fakedaemon.py`, for the docs and for a look
  with no terminal.
- `tests/modes-test.sh`: RTTY and SSTV round trips over a virtual sound device. It makes a throwaway
  test picture, loads a null sound sink with `pactl`, sends RTTY text and an SSTV picture into it
  with `--no-key`, receives them back, and checks the text and the picture's mode. It takes more
  than a minute, because it listens in real time. It needs the sound server and the `.venv`.
- `.venv/bin/python rttymodem.py selftest`: the RTTY modem encodes some text, adds noise, decodes it
  and compares. It needs the `.venv` (it uses numpy).
- `python3 -I tests/d750-aprs-test.py`: KISS framing, AX.25, APRS positions, Mic-E, messages, the
  plain lines and the restart notices. It opens no port and transmits nothing.
- `python3 -I tests/aprschat-test.py`: the chat, in line mode and on its screen. A stand-in for
  d750-aprs answers on a throwaway socket, and one check drives the screen in a pseudo terminal.
- `python3 -I tests/output-rules-test.py`: every line the `d750` verbs print, checked against the
  project's written output rules. It runs a fixed list of verbs, with the test bed from
  `tests/test-env.sh` running first, and uses the `d750` in the project's top folder, never the one
  on your PATH. It checks that each line is plain printable ASCII with no trailing spaces, that no
  line is longer than 80 characters (a short list of known long lines is reported as notes), that
  the exit code is 0, 1 or 2 as it should be, that a failure says why, that a working verb prints
  its answer first, that VOX and GPS states are said as on or off, and that a dry run says "would
  send" and changes nothing. It puts back every value it changes on the pretend radio, and it never
  keys: the only PTT word it sends is `ptt off`, and VarAC frames only as dry runs. It prints a Pass
  or Fail line for each verb run, then its own count.
- `python3 -I station/station-test.py` and `python3 -I station/notify-test.py` are the tests for the
  station tools: `station`, with fake services, and `notify`, with a fake `curl`. See
  [Station tools](station-tools.md).

### The simulator

`tests/d750-sim.py` is a pretend TM-D750 on a pseudo terminal. It prints the device path to use as
`D750_PORT`, and answers the Kenwood commands the way the real radio did when its answers were
captured, and the way the community's TH-D74 command list says for the rest. Commands it does not
know get `?`. It starts with band A on 147.040 MHz, band B on 144.390 MHz, KISS on band B, and two
memory channels. The option `--busy-flicker` makes the busy flags change now and then. The `d750`
verbs, the rig screen and the Hamlib port work against it, which is also how the sample output in
these docs was captured. See [Try it without a radio](try-without-a-radio.md).

### What runs on GitHub, and what stays local

The workflow `.github/workflows/tests.yml` runs on every push and every pull request, on four
distributions: Ubuntu, Debian, Fedora and Arch. Each job installs that distribution's packages for
pyserial, netcat, Hamlib and procps (listed in [Install](install.md)) and tmux, starts the test bed, and
runs:

- `tests/tests.sh`, then it stops the test bed;
- `tests/output-rules-test.py`, on a fresh test bed that it also stops afterwards;
- `tests/keymap-test.py` and `tests/screen-model-test.py`;
- `tests/d750ctrl-test.py`;
- `tests/d750ctrl-tmux-test.py`, with tmux installed for it;
- `tests/d750-aprs-test.py`;
- `tests/aprschat-test.py`;
- `station/station-test.py`;
- `station/notify-test.py`.

These need no radio and no sound device, so they run there against the simulator only.

`tests/modes-test.sh` and the `rttymodem.py` self test stay local, because they need a sound server
and the `.venv`.

### Tests never key a radio

- The tests use the simulator, never your radio's port.
- The SSTV and RTTY tests use `--no-key` and a virtual sound device.
- The APRS tests open no port and transmit nothing.
- The test daemon listens on ports 4542 and 4543, so it does not touch a real d750d on 4532 and
  4533.

## Settings

The tests use these environment variables, and you can use them too: `D750_PORT`, `D750_PTT_PORT`,
`D750_CMD_PORT`, `D750_XARA_PORT`, `D750_LOG_DIR`, `D750_CONF_DIR`, `APRSCHAT_MESSAGES`, `APRSCHAT_SOCK` and
`APRSCHAT_STATE`. They are described on the [settings page](settings.md).

## When something goes wrong

- **You see:** many checks in `tests/tests.sh` fail, with "ERR d750d is not answering" in the
  output.
  - **Why:** the test bed is not running.
  - **What to do:** start `tests/test-env.sh` first. `tests/tests.sh` sets the test ports itself.

- **You see:** "simulator gave no device path" from `tests/test-env.sh`.
  - **Why:** the simulator did not start in about ten seconds.
  - **What to do:** run `python3 -I tests/d750-sim.py` by hand to see its error.

- **You see:** checks fail with `rigctl` or `nc` not found.
  - **Why:** those programs are not installed.
  - **What to do:** install them (see "Before you start").

## See also

- [Try it without a radio](try-without-a-radio.md)
- [Station tools](station-tools.md)
- [Settings reference](settings.md)
- [d750d: the daemon](d750d.md)
- [Glossary](glossary.md)
