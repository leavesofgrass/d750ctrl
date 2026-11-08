import os, sys, time, importlib.util
HERE = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("keyer", os.path.join(HERE, "d750-keyer.py")); keyer = importlib.util.module_from_spec(spec); spec.loader.exec_module(keyer)
import sstv
from PIL import Image

OUT = os.path.expanduser("~/.local/share/d750ctrl/sstv")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]
    no_key = "--no-key" in opts
    sink = opts[opts.index("--sink") + 1] if "--sink" in opts else keyer.radio_sink()
    source = opts[opts.index("--source") + 1] if "--source" in opts else keyer.radio_source()
    cmd = args[0] if args else "help"
    if cmd == "modes":
        print(" ".join(m for m in dir(sstv.Mode) if m[0].isupper())); return 0
    if cmd == "rx":
        seconds = int(args[1]) if len(args) > 1 else 150
        if not source: print("Fail: the radio's sound card is not present"); return 1
        os.makedirs(OUT, exist_ok=True)
        wav = os.path.join(OUT, time.strftime("%Y%m%d-%H%M%S") + "-rx.wav")
        print(f"recording {seconds} s from {source}; an SSTV picture takes 37 s (Robot 36) to 2 minutes (Martin, PD)", flush=True)
        keyer.record(wav, source, seconds)
        images = list(sstv.decode_from_wav(wav))
        if not images:
            print("no SSTV picture found in the recording; the audio is kept at", wav); return 1
        for i, img in enumerate(images, 1):
            path = wav.replace("-rx.wav", f"-{i}.png"); img.save(path)
            print(f"picture {i}: {path}, {img.size[0]} by {img.size[1]}, mode {str(img.info.get('sstv_mode')).replace('Mode.', '')}, {'complete' if img.info.get('sstv_complete') else 'cut short'}")
        return 0
    if cmd == "tx":
        if len(args) < 2: print("usage: d750-sstv tx IMAGE [MODE]"); return 2
        mode_name = (args[2] if len(args) > 2 else "ROBOT_36").upper()
        mode = getattr(sstv.Mode, mode_name, None)
        if mode is None: print("unknown mode; d750-sstv modes lists them"); return 2
        if not sink: print("Fail: the radio's sound card is not present"); return 1
        img = Image.open(args[1]).convert("RGB")
        os.makedirs(OUT, exist_ok=True)
        wav = os.path.join(OUT, time.strftime("%Y%m%d-%H%M%S") + "-tx.wav")
        size = (320, 256) if "MARTIN" in mode_name or "SCOTTIE" in mode_name else (320, 240) if "ROBOT" in mode_name else (640, 496) if mode_name.startswith("PD") else (320, 240)
        sstv.encode_to_wav_file(img.resize(size), wav, mode)
        import wave
        with wave.open(wav) as w: secs = w.getnframes() / w.getframerate()
        print(f"sending {os.path.basename(args[1])} as {mode_name}, {secs:.0f} s of audio to {sink}", flush=True)
        with keyer.XaraPaused():
            with keyer.Keyed(enabled=not no_key):
                keyer.play(wav, sink)
        print("sent; audio kept at", wav); return 0
    print(open(os.path.join(HERE, "d750-sstv")).read().split("here=")[0]); return 2


if __name__ == "__main__":
    sys.exit(main())
