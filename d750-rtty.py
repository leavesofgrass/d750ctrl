import os, sys, time, importlib.util
HERE = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("keyer", os.path.join(HERE, "d750-keyer.py")); keyer = importlib.util.module_from_spec(spec); spec.loader.exec_module(keyer)
spec2 = importlib.util.spec_from_file_location("rttymodem", os.path.join(HERE, "rttymodem.py")); rtty = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(rtty)

OUT = os.path.expanduser("~/.local/share/d750ctrl/rtty")


def opt(opts, name, default):
    return opts[opts.index(name) + 1] if name in opts else default


def main():
    opts = sys.argv[1:]
    args = [a for i, a in enumerate(opts) if not a.startswith("--") and (i == 0 or not opts[i - 1] in ("--sink", "--source", "--baud", "--shift"))]
    kw = dict(baud=float(opt(opts, "--baud", 45.45)), shift=float(opt(opts, "--shift", 170)), reverse="--reverse" in opts)
    no_key = "--no-key" in opts
    sink = opt(opts, "--sink", None) or keyer.radio_sink()
    source = opt(opts, "--source", None) or keyer.radio_source()
    cmd = args[0] if args else "help"
    if cmd == "rx":
        seconds = int(args[1]) if len(args) > 1 else 60
        if not source: print("Fail: the radio's sound card is not present"); return 1
        os.makedirs(OUT, exist_ok=True)
        wav = os.path.join(OUT, time.strftime("%Y%m%d-%H%M%S") + "-rx.wav")
        print(f"listening {seconds} s on {source} for RTTY at {kw['baud']:g} baud, {kw['shift']:g} Hz shift", flush=True)
        keyer.record(wav, source, seconds)
        samples, rate = rtty.read_wav(wav)
        text = rtty.decode(samples, rate=rate, **kw).strip()
        with open(os.path.join(OUT, "received.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M ") + text + "\n")
        print(text if text else "nothing decoded; the audio is kept at " + wav); return 0 if text else 1
    if cmd == "tx":
        if len(args) < 2: print('usage: d750-rtty tx "TEXT"'); return 2
        text = " ".join(args[1:])
        if not sink: print("Fail: the radio's sound card is not present"); return 1
        os.makedirs(OUT, exist_ok=True)
        wav = os.path.join(OUT, time.strftime("%Y%m%d-%H%M%S") + "-tx.wav")
        samples = rtty.encode(text, rate=48000, **kw); rtty.write_wav(wav, samples, 48000)
        print(f"sending {len(text)} characters, {len(samples)/48000:.0f} s, to {sink}", flush=True)
        with keyer.XaraPaused():
            with keyer.Keyed(enabled=not no_key):
                keyer.play(wav, sink)
        with open(os.path.join(OUT, "sent.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M ") + text + "\n")
        print("sent"); return 0
    print(open(os.path.join(HERE, "d750-rtty")).read().split("here=")[0]); return 2


if __name__ == "__main__":
    sys.exit(main())
