# Glossary

These are the words the project uses, in alphabetical order, with what each means here. They are
not encyclopedia entries.

## A

- APRS: Automatic Packet Reporting System. Short packets that carry positions, messages and status.
  d750-aprs reads and sends them through the radio's own TNC.
- APRS-IS: The internet network that APRS packets are passed into. An iGate sends what the radio
  hears to it.
- AX.25: The packet format APRS uses on the air. d750-aprs decodes it from the frames the TNC hands
  over.

## B

- Band A and band B: The radio's two sides, each with its own frequency, mode, squelch and power.
  One of them is the transmit band, and one is the control band, which the front panel acts on. In
  d750 they are the letters A and B. Band B is the data band by default, the one the TNC uses.
- Beacon: A packet your station sends on a timer to say where it is. A VarAC beacon frame is a
  different thing: one frame sent through xara, in the form `CQFRAME` and your call with the suffix
  -9.

## C

- CAT: Computer Aided Transceiver: the radio's command port. The computer reads and sets the radio
  over a serial line. On the TM-D750 it is the control head's USB socket, named `/dev/d750-cat`.

## D

- D-STAR: A digital voice mode. The radio's mode DV is D-STAR, and `d750 mode A dv` selects it.
- d750d: The daemon. It is the only program that opens the radio's serial port. Everything else,
  including the `d750` command, asks it.
- Digipeater: A station that repeats other stations' packets. `d750-aprs digi fillin` repeats
  packets whose next hop is WIDE1-1 or your call. `digi wide` repeats WIDEn-N packets too.
- Dry run: A command that shows what it would do and changes nothing. Add `-n` to a `d750` command
  that changes the radio. The line "would send:" shows the command.

## H

- Hamlib: A common library and protocol for controlling radios. d750d speaks Hamlib's NET rigctl
  protocol on port 4532, so programs that know Hamlib can tune and key the radio through it.

## I

- iGate: An Internet gateway. It passes packets the radio hears to APRS-IS. `d750-aprs igate on`
  makes a receive-only iGate, which never sends anything from the internet out on the air.

## K

- KISS: A simple framing protocol that a TNC uses to hand packets to a computer. With the TNC in
  KISS mode, d750-aprs reads KISS frames from the base unit's port, and shares them with other
  programs on TCP port 8001.

## M

- Memory channel: A stored frequency and settings in the radio. `d750 mem` lists, shows, recalls,
  exports and imports them.

## N

- NTS radiogram: A message in the ARRL National Traffic System format, with a preamble, address,
  text and signature. The `radiogram` tool writes, checks and logs them as plain text.
- ntfy: A service that sends notifications to your phone or computer. d750-aprs posts through a
  command named notify, when it is present and the setting notify is on.

## P

- PTT: Push to talk: the key line that makes the radio transmit. d750d owns it, takes it on port
  4532, and unkeys after 30 seconds, on a lost client, and on serial errors.

## R

- rigctl: Hamlib's command line client for a radio. The tests use it to check d750d's Hamlib port.
- RTTY: Radio teletype. `d750-rtty` sends and receives Baudot RTTY at 45.45 baud with 170 Hz shift
  through the radio's sound card.

## S

- Squelch: The level below which the radio keeps its receiver quiet. In d750 it is 0 to 9, and 0 is
  wide open. The busy flag says whether the squelch is open now.
- SSTV: Slow-scan television: sending a still picture as sound. `d750-sstv` sends and receives
  pictures through the radio's sound card.
- Systemd user service: A program that systemd starts for your own user, without root, usually at
  login. d750d runs as one, named d750d.service. You control it with `systemctl --user`.

## T

- TNC: Terminal node controller: a packet modem. The TM-D750 has one built in. d750-aprs uses it to
  hear and send packets.
- tmux: A terminal multiplexer: several windows in one terminal. The rig screen runs inside its own
  tmux session, so each tool gets a window and keeps running while you tune.

## U

- udev: The part of Linux that creates device names when hardware is plugged in. The project's udev
  rule names the radio's two USB serial ports `/dev/d750-cat` and `/dev/d750-tnc`.
- Uptime Kuma: A self-hosted monitoring service. d750-aprs can send it a heartbeat through push URLs
  kept in files in `~/.config`, so you can see that the TNC and the iGate are alive.

## V

- VARA: A family of modems for amateur data links on HF and FM. In this project the `d750 vara`
  verbs work through xara, and the rig screen can open a chat window for it.
- VarAC: A chat program for VARA. Its CQ and beacon frames have a particular format. `d750 vara cq`
  and `d750 vara beacon` send one in that form through xara, with your call from the settings.

## X

- xara: The modem program that the VARA tools talk to. It runs as a user service, takes commands on
  TCP port 8300 and keys the radio through d750d. It is a separate program that is not part of this
  repository.

## See also
- [Documentation index](README.md)
- [d750d](d750d.md)
- [Troubleshooting](troubleshooting.md)
