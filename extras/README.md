# Extras: older pieces, kept for reference

Nothing in this folder is installed by `install.sh` or `station/install-station.sh`. Each piece
worked with the radio when it was written. Read its warning before you run it.

## d750-ptt.py: CAT keying for xara, and nothing else

This was the first keying program, written before d750d existed. It listens on 127.0.0.1 port 4532,
speaks the small part of the rigctld protocol that xara uses for keying, and keys the radio by
writing the radio's own TX and RX commands to `/dev/d750-cat`.

**Never run it beside d750d.** Both open the same serial port and both listen on port 4532. Two
programs on one serial port garble each other's commands, and one of them may unkey or fail to unkey
the radio. d750d does everything this program does, and much more. Use d750d unless you have a
reason not to.

It is kept for a station that wants keying for xara and nothing else.

What it does to stay safe, from its own code:

- It unkeys the radio when it starts.
- It unkeys when a client disconnects while keyed.
- It unkeys on any serial error.
- A watchdog unkeys after 30 seconds.

To try it, with d750d stopped:

```sh
systemctl --user stop d750d.service
python3 -I extras/d750-ptt.py
```

It needs the pyserial module and the `/dev/d750-cat` name that `install-udev.sh` sets up.
`D750_PORT` in the environment names another serial port. Stop it with Ctrl+C, then start d750d
again:

```sh
systemctl --user start d750d.service
```

## See also

- [d750d](../docs/d750d.md): the daemon that replaced this program.
- [VARA and chat](../docs/vara-and-chat.md): how xara keys the radio through d750d.
