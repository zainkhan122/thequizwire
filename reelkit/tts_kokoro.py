#!/usr/bin/env python3
"""
reelkit/tts_kokoro.py — free, offline, unlimited voice-over with Kokoro-82M (Apache-2.0, CPU).

Replaces the generate_speech step for English (and es/fr/hi/it/ja/pt/zh) reels:
reads each beat's Hypit-markup `script`, speaks the *spoken* form, writes beat["vo"].

  python3 tts_kokoro.py reel.json                       # voice from spec.voice.kokoro_voice
  python3 tts_kokoro.py reel.json --voice am_michael --speed 1.08 --force
  python3 tts_kokoro.py reel.json --voice "af_heart:60,am_adam:40"   # blend voices
  python3 tts_kokoro.py --list                          # all voice ids
  python3 tts_kokoro.py --say "Hello there" --voice bf_emma -o ~/.cache/tmp/t.wav

LIMIT: Kokoro has NO Urdu / Arabic-script voice. Urdu reels -> use generate_speech (add_voice
language "ur"). Hindi voices (hf_alpha, hm_omega …) read Devanagari, not Urdu script.
Voice prefixes: a=US English, b=UK English, e=es, f=fr, h=hi, i=it, j=ja, p=pt-br, z=zh;
second letter f/m = feminine/masculine.  Good narrators: am_michael, am_adam, af_heart,
af_bella, bf_emma, bm_george, bm_fable.
"""
import argparse, json, os, re, sys, time
os.environ["PATH"] = os.path.expanduser("~/.cache/bin") + os.pathsep + os.environ.get("PATH", "")  # setup.sh tools
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script as SC

K = os.path.expanduser("~/.cache/kokoro")
MODEL, VOICES = f"{K}/kokoro-v1.0.int8.onnx", f"{K}/voices-v1.0.bin"
LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it",
        "j": "ja", "p": "pt-br", "z": "cmn"}

def load():
    if not os.path.exists(MODEL):
        sys.exit("Kokoro model missing — run:  source ~/reelkit/setup.sh")
    from kokoro_onnx import Kokoro
    return Kokoro(MODEL, VOICES)

def voice_vec(k, spec):
    """'am_adam' or blend 'af_heart:60,am_adam:40' -> (style, lang)"""
    parts = [p.split(":") for p in spec.split(",")]
    if len(parts) == 1: return parts[0][0], LANG.get(parts[0][0][0], "en-us")
    tot = sum(float(w) for _, w in parts)
    vec = sum(k.get_voice_style(v) * (float(w) / tot) for v, w in parts)
    return vec.astype(np.float32), LANG.get(parts[0][0][0], "en-us")

def speak(k, text, voice, speed, out):
    if re.search(r"[\u0600-\u06ff]", text):
        raise SystemExit("Kokoro can't speak Urdu/Arabic script — use generate_speech for this reel.")
    style, lang = voice_vec(k, voice)
    pcm, sr = k.create(text, voice=style, speed=speed, lang=lang)
    pcm = np.concatenate([np.zeros(int(sr * .08), np.float32), pcm, np.zeros(int(sr * .15), np.float32)])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sf.write(out, pcm, sr, subtype="PCM_16")
    return len(pcm) / sr

def selftest(voice="am_michael"):
    """CI smoke: model loads, the channel voice speaks, whisper hears it (same whisper the voice gate uses)."""
    out = os.path.expanduser("~/.cache/tmp/kokoro_selftest.wav"); text = "Which is the largest peninsula in the world? The answer is Arabia."
    k = load(); d = speak(k, text, voice, 1.0, out)
    assert 2.0 < d < 8.0, f"take length {d:.2f}s out of range"
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel("base.en", device="cpu", compute_type="int8").transcribe(out, beam_size=1)
    heard = " ".join(s.text for s in segs).lower()
    for w in ("largest", "peninsula", "arabia"):
        assert w in heard, f"whisper did not hear {w!r} in {heard!r}"
    print(f"kokoro selftest OK  voice={voice}  {d:.2f}s  heard: {heard.strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reel", nargs="?"); ap.add_argument("--voice"); ap.add_argument("--speed", type=float)
    ap.add_argument("--force", action="store_true"); ap.add_argument("--list", action="store_true")
    ap.add_argument("--say"); ap.add_argument("-o", "--out", default="say.wav")
    ap.add_argument("--selftest", action="store_true", help="speak one line with am_michael, transcribe it with whisper, assert the words came back")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.voice or "am_michael")
    k = load()
    if a.list:
        print(" ".join(sorted(k.get_voices()))); return
    if a.say:
        d = speak(k, a.say, a.voice or "am_michael", a.speed or 1.0, a.out); print(f"{a.out}  {d:.2f}s"); return
    spec = json.load(open(a.reel)); root = os.path.dirname(os.path.abspath(a.reel))
    v = spec.get("voice", {})
    voice = a.voice or v.get("kokoro_voice") or "am_michael"
    if " " in voice or voice.startswith("not"):
        sys.exit(f"spec says kokoro_voice = '{voice}' — this reel needs generate_speech.")
    speed = a.speed or v.get("kokoro_speed", 1.05)
    t0 = time.time(); tot = 0
    for b in spec["beats"]:
        out = os.path.join(root, b["vo"])
        if os.path.exists(out) and not a.force:
            print(f"skip {b['vo']} (exists; --force to redo)"); continue
        text = SC.tts_text(b["script"]) if "script" in b else b["text"]
        d = speak(k, text, voice, speed, out); tot += d
        print(f"{b['vo']:<10} {d:5.2f}s  {text[:70]}")
    print(f"done: {tot:.1f}s of VO in {time.time() - t0:.1f}s  (voice={voice}, speed={speed})")

if __name__ == "__main__":
    main()
