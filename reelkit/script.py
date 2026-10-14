#!/usr/bin/env python3
"""
reelkit/script.py — Hypit-style Script markup for reels.

  ||                    caption Cue handoff (Hypit)
  <1202|twelve-oh-two>  Dual Text: display side on screen, spoken side to TTS (Hypit)
  <|silent words>       spoken but not captioned
  *word* / *<a|b>*      emphasis (captions colour it after it is spoken)

Script owns the WORDS; ASR (words.json) owns the TIMING. Units are aligned to ASR with
difflib, unmatched spoken words are interpolated.

CLI:
  python3 script.py tts   <reel.json>   -> prints the TTS text for each beat (send to generate_speech)
  python3 script.py align <reel.json>   -> runs faster-whisper on every beat's VO, writes words.json
"""
import difflib, json, os, re, sys
os.environ["PATH"] = os.path.expanduser("~/.cache/bin") + os.pathsep + os.environ.get("PATH", "")  # setup.sh tools

TOK = re.compile(r"\|\||\*?<[^>]*>[^\s]*\*?|\S+")

def norm(w): return re.sub(r"[^a-z0-9\u0600-\u06ff]", "", w.lower())

def parse(script):
    units, brk = [], True
    for tk in TOK.findall(script):
        if tk == "||": brk = True; continue
        emph = tk.startswith("*") and tk.rstrip(".,!?:;…").endswith("*")
        core = tk.strip("*") if emph else tk
        m = re.match(r"^<([^|>]*)\|([^>]*)>(.*)$", core)
        if m:
            disp, spoken, tail = m.group(1), m.group(2), m.group(3)
            disp = (disp + tail) if disp else ""
            spoken = (spoken or m.group(1)) + tail
        else:
            disp = spoken = core.replace("*", "")
        disp = disp.replace("*", "")
        units.append(dict(display=disp, spoken=spoken.split(), emph=emph, brk=brk)); brk = False
    return units

def tts_text(script):
    return " ".join(w for u in parse(script) for w in u["spoken"])

def timed_units(script, asr):
    """attach start/end (relative to beat) to each unit using ASR words"""
    units = parse(script)
    sp = [(ui, w) for ui, u in enumerate(units) for w in u["spoken"]]
    a = [norm(w) for _, w in sp]; b = [norm(x["w"]) for x in asr]
    times = [None] * len(sp)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(i2 - i1): times[i1 + k] = (asr[j1 + k]["s"], asr[j1 + k]["e"])
        elif op == "replace":          # e.g. spoken 'twelve-oh-two' vs ASR '1202': share the ASR span
            s0, e0 = asr[j1]["s"], asr[j2 - 1]["e"]; n = i2 - i1
            for k in range(n): times[i1 + k] = (s0 + (e0 - s0) * k / n, s0 + (e0 - s0) * (k + 1) / n)
    # interpolate gaps
    known = [i for i, t in enumerate(times) if t]
    end = asr[-1]["e"] if asr else 1.0
    for i in range(len(times)):
        if times[i] is None:
            lo = max([k for k in known if k < i], default=None); hi = min([k for k in known if k > i], default=None)
            t0 = times[lo][1] if lo is not None else 0.0
            t1 = times[hi][0] if hi is not None else end
            n_lo = lo if lo is not None else -1; n_hi = hi if hi is not None else len(times)
            f = (i - n_lo) / (n_hi - n_lo)
            s = t0 + (t1 - t0) * f; times[i] = (s, s + .2)
    for ui, u in enumerate(units):
        ts = [times[k] for k, (uj, _) in enumerate(sp) if uj == ui]
        u["s"], u["e"] = ts[0][0], ts[-1][1]
    return units

def find(units, key):
    """anchor by word text: 'go' / '1202' / 'go#2' (2nd occurrence) / '@5' (unit index)"""
    if str(key).startswith("@"): return int(str(key)[1:])
    word, _, occ = str(key).partition("#"); occ = int(occ or 1); n = 0
    for i, u in enumerate(units):
        if norm(word) in (norm(u["display"]), norm(" ".join(u["spoken"]))) or norm(word) == norm(u["spoken"][0] if u["spoken"] else ""):
            n += 1
            if n == occ: return i
    raise KeyError(f"anchor word '{key}' not found")

if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    spec = json.load(open(path)); root = os.path.dirname(os.path.abspath(path))
    if cmd == "tts":
        for b in spec["beats"]:
            print(f"{b['id']}  ->  {b['vo']}\n    {tts_text(b['script'])}\n")
    elif cmd == "align":
        import subprocess, numpy as np
        from faster_whisper import WhisperModel
        lang = spec.get("asr_language", "en")
        m = WhisperModel(spec.get("asr_model", "base.en" if lang == "en" else "small"), device="cpu", compute_type="int8")
        out = {}
        for b in spec["beats"]:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(root, b["vo"]), "-f", "s16le",
                                  "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
            x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
            segs, _ = m.transcribe(x, word_timestamps=True, language=lang)
            out[b["vo"]] = dict(dur=len(x) / 16000, words=[dict(w=w.word.strip(), s=round(w.start, 3), e=round(w.end, 3))
                                                         for s in segs for w in s.words])
            print(b["id"], round(len(x) / 16000, 2), " ".join(w["w"] for w in out[b["vo"]]["words"]))
        json.dump(out, open(os.path.join(root, "words.json"), "w"), indent=1)
