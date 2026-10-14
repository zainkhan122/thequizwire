#!/usr/bin/env python3
"""Voice performance plan + take gate.  The plan (<ep>/voice.json) is the single source of truth for
narration text, tone, energy, pauses and the end hold; plan.py reads its pauses, and every take is
MEASURED against it.

  python3 reelkit/voice.py check  <ep> [--plan-only] [--report out/voice.json]   # gate (episode.sh stage 'voice')
  python3 reelkit/voice.py sample <ep> [--take a.mp3 b.mp3 …] [--kokoro] [--line v10]
        Sample-first gate: synthesise/judge the MOST EMOTIONAL line before producing the rest.
        --take   judge takes you generated (e.g. Arena generate_speech); ranks them, best first
        --kokoro synthesise 3 speed variants locally with the Kokoro fallback voice and judge them
  python3 reelkit/voice.py lines  <ep>              # TTS-ready lines + direction (for generate_speech)
  python3 reelkit/voice.py kokoro <ep> [--only v01,v02] [--out DIR]   # synthesise with per-tone speed
  python3 reelkit/voice.py words  <ep> [--only v08,v09]
        Word timings: trims each vo/ take exactly like trim_vo.py and transcribes it with word timestamps
        -> <ep>/words.json {id: {dur, words: [{w, s, e}]}} (merged with --only). Run after every new take.
  python3 reelkit/voice.py shape  <ep> [--only v10] [--dry-run]
        Lengthen marked pauses that fall short of the plan by extending the take's own silence (never
        touches speech). Original take is kept at vo/orig/<id>.<ext>; shaped take = vo/<id>.wav (lossless);
        words.json is shifted; the edit is recorded in voice.json ("shaped"). Then: plan → score → build, media push.

Measured per take (waveform first; whisper only locates words):
  fidelity  words actually spoken vs plan text (numbers compared as values)   FAIL > 8 % WER or a wrong number
            (base.en first; any error is re-checked with small.en — VOICE_ASR2, 'off' to disable — and the better reading kept)
  pace      syllables per second of phonation, banded per tone                FAIL outside band ±15 %, WARN outside band
  pauses    every marked pause (… : —, plus explicit "pauses") must exist as a real silence
                                                                              FAIL if dropped (< 0.12 s), WARN if < 80 % of target
  pitch     p10–p90 pitch range in semitones                                  WARN < 4 st (monotone)
  peak      sample peak                                                       FAIL ≥ −0.1 dBFS (clipped), WARN > −1 dBFS
Plan checks: tones known, energies 1–5, pause_after inside the tone's range, one climax, a sample line,
an arc (≥ 3 tones, energy span ≥ 3), the plan text matches the VO the episode actually uses.
"""
import argparse, difflib, json, os, re, subprocess, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
SR = 16000

# pace = syllables per second of phonation (silences ≥ 150 ms removed). Bands calibrated on the approved
# ep01 narration and documentary norms (~150 wpm ≈ 4.5–5 syl/s articulation). after = pause after the line (s).
TONES = {
    "urgent":     {"pace": (5.0, 7.4), "after": (0.25, 0.70), "speed": 1.10},
    "tense":      {"pace": (4.4, 6.8), "after": (0.30, 0.80), "speed": 1.03},
    "neutral":    {"pace": (4.2, 6.6), "after": (0.30, 0.80), "speed": 1.00},
    "resolute":   {"pace": (4.0, 6.4), "after": (0.35, 0.90), "speed": 1.00},
    "revelatory": {"pace": (3.8, 6.2), "after": (0.45, 1.20), "speed": 0.97},
    "suspense":   {"pace": (3.2, 5.6), "after": (0.60, 1.40), "speed": 0.90},
    "somber":     {"pace": (3.6, 6.2), "after": (0.60, 1.40), "speed": 0.93},
    "tender":     {"pace": (3.4, 6.0), "after": (0.70, 1.60), "speed": 0.90},
    "reverent":   {"pace": (3.2, 5.6), "after": (0.80, 2.00), "speed": 0.88},
}
END_HOLD = (2.0, 5.0)
MARK_DEFAULT = 0.30           # default target for a marked pause (… : —)
MARK_DROPPED = 0.12           # below this the TTS ignored the mark
SIL_MIN = 0.15                # silence ≥ 150 ms counts as a pause
WER_FAIL, WER_WARN = 0.08, 0.03

# ---------------------------------------------------------------- text
UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SCALES = {"hundred": 100, "thousand": 1000, "million": 10 ** 6}
ORD = {"first": "one", "third": "three", "fourth": "four", "fifth": "five", "sixth": "six", "seventh": "seven",
       "eighth": "eight", "ninth": "nine", "tenth": "ten", "twelfth": "twelve", "twentieth": "twenty"}


def _int_words(n: int) -> str:
    if n < 20:
        return list(UNITS)[n]
    if n < 100:
        t = [k for k, v in TENS.items() if v == n // 10 * 10][0]
        return t + ("" if n % 10 == 0 else " " + list(UNITS)[n % 10])
    if n < 1000:
        return list(UNITS)[n // 100] + " hundred" + ("" if n % 100 == 0 else " and " + _int_words(n % 100))
    if 1100 <= n <= 2099 and n % 100 and not (2000 <= n < 2010):      # years read as pairs: nineteen eighty-three
        return _int_words(n // 100) + " " + (("oh " + _int_words(n % 100)) if n % 100 < 10 else _int_words(n % 100))
    return _int_words(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + _int_words(n % 1000))


def spoken(text: str) -> str:
    """Text as it is spoken (digits → words) — used for syllable counts."""
    def rep(m):
        n, suf = int(m.group(1)), m.group(2) or ""
        w = _int_words(n)
        if suf:
            last = w.split()[-1]
            inv = {v: k for k, v in ORD.items()}
            w = w[: -len(last)] + (inv.get(last) or (last[:-1] + "ieth" if last.endswith("y") else last + "th"))
        return w
    return re.sub(r"\b(\d+)(st|nd|rd|th)?\b", rep, text)


def syllables(text: str) -> int:
    n = 0
    for w in re.findall(r"[a-z']+", spoken(text).lower()):
        w = w.replace("'", "")
        g = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and g > 1:
            g -= 1
        n += max(1, g)
    return n


def tokens(text: str):
    """Normalised comparison tokens; number-word runs collapse to digit strings. Returns [(token, raw_word_index)]."""
    raw = text.replace("—", " — ").split()
    out, run, run_idx = [], [], -1

    def flush():
        nonlocal run
        if not run:
            return
        vals = [v for v, _ in run]
        if len(vals) == 2 and 10 <= vals[0] < 100 and 10 <= vals[1] < 100 and "h" not in [k for _, k in run]:
            num = vals[0] * 100 + vals[1]                                # nineteen eighty(-three) as a year
        else:
            total, cur = 0, 0
            for v, k in run:
                if k == "h":
                    cur = max(cur, 1) * v
                    if v >= 1000:
                        total += cur; cur = 0
                else:
                    cur += v
            num = total + cur
        out.append((str(num), run_idx)); run = []

    for i, rw in enumerate(raw):
        t = re.fullmatch(r"(\d{1,2})?[:.](\d{2})\W*", rw)              # clock times: 11:18 / "11" ".18" -> 1118
        if t and t.group(1):
            flush(); out.append((t.group(1) + t.group(2), i)); continue
        if t and out and re.fullmatch(r"\d{1,2}", out[-1][0]) and not run:
            out[-1] = (out[-1][0] + t.group(2), i); continue           # raw indices stay aligned to ASR words
        for part in re.split(r"[-–]", rw):
            w = re.sub(r"[^\w']", "", part.lower())
            if not w:
                continue
            m = re.fullmatch(r"(\d+)(st|nd|rd|th)?", w)
            if m:
                flush(); out.append((m.group(1), i)); continue
            w2 = ORD.get(w, w) if run else w
            if w2 in UNITS or w2 in TENS:
                v = UNITS.get(w2, TENS.get(w2))
                if run and run[-1][1] == "u" and v < 10 and run[-1][0] % 10 == 0 and run[-1][0] >= 20:
                    run[-1] = (run[-1][0] + v, "u")                    # twenty + three
                else:
                    run.append((v, "u"))
                run_idx = i; continue
            if w in SCALES and run:
                run.append((SCALES[w], "h")); run_idx = i; continue
            if w == "and" and run and any(k == "h" for _, k in run):
                continue                                               # "two hundred AND sixty-nine"
            flush(); out.append((w, i))
    flush()
    return out


def marks(text: str, explicit: dict):
    """Pause targets: {raw_word_index: target_seconds} from … : — marks and explicit {"word": s}."""
    raw = text.replace("—", " — ").split()
    res = {}
    for i, rw in enumerate(raw):
        if rw.endswith(("…", "...", ":")) or (i + 1 < len(raw) and raw[i + 1] == "—"):
            res[i] = MARK_DEFAULT
    for key, tgt in (explicit or {}).items():           # "word" = first occurrence, "word#2" = second, …
        word, _, nth = key.partition("#")
        hits = [i for i, rw in enumerate(raw) if re.sub(r"[^\w']", "", rw.lower()) == word.lower()]
        n = int(nth or 1)
        if len(hits) < n:
            raise SystemExit(f"voice plan: pause word '{key}' not in line text")
        res[hits[n - 1]] = float(tgt)
    return res, raw


# ---------------------------------------------------------------- audio
def load(path):
    import librosa, numpy as np
    y, _ = librosa.load(str(path), sr=SR, mono=True)
    idx = np.flatnonzero(abs(y) > 0.01)                                # same trim as trim_vo.py
    if len(idx):
        y = y[max(0, idx[0] - int(0.04 * SR)): min(len(y), idx[-1] + int(0.12 * SR))]
    return y


def silences(y):
    import librosa, numpy as np
    hop = 160
    r = librosa.feature.rms(y=y, frame_length=640, hop_length=hop)[0]
    db = 20 * np.log10(r + 1e-9)
    ref = np.percentile(db[db > -60], 95) if (db > -60).any() else -20
    q = db < ref - 20
    out, s = [], None
    for i, v in enumerate(list(q) + [False]):
        if v and s is None:
            s = i
        elif not v and s is not None:
            a, b = s * hop / SR, i * hop / SR
            if b - a >= SIL_MIN and a > 0.05 and b < len(y) / SR - 0.05:   # inner silences only
                out.append((round(a, 3), round(b, 3)))
            s = None
    return out


def transcribe(y, model=None):
    from faster_whisper import WhisperModel
    m = WhisperModel(model or os.environ.get("VOICE_ASR", "base.en"), device="cpu", compute_type="int8")
    segs, _ = m.transcribe(y, language="en", word_timestamps=True, beam_size=5)
    return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in s.words]


def measure(line: dict, y, words: list):
    """Measure one take against its plan line. words = ASR words (times relative to the trimmed take)."""
    import librosa, numpy as np
    fails, warns, m = [], [], {}
    tone = TONES[line["tone"]]
    dur = len(y) / SR
    sil = silences(y)
    artic = dur - sum(b - a for a, b in sil) - 0.16                     # minus head/tail pads
    syl = syllables(line["text"])
    m["dur"], m["syllables"], m["pace"] = round(dur, 2), syl, round(syl / max(artic, 0.1), 2)
    lo, hi = tone["pace"]
    if not (lo * 0.85 <= m["pace"] <= hi * 1.15):
        fails.append(f"pace {m['pace']} syl/s far outside {line['tone']} band {lo}–{hi}")
    elif not (lo <= m["pace"] <= hi):
        warns.append(f"pace {m['pace']} syl/s outside {line['tone']} band {lo}–{hi}")

    # fidelity
    P = tokens(line["text"])

    def wer_of(ws):
        A = tokens(" ".join(w["w"] for w in ws))
        sm = difflib.SequenceMatcher(a=[t for t, _ in P], b=[t for t, _ in A], autojunk=False)
        return round(sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal") / max(1, len(P)), 3), A, sm
    m["wer"], A, sm = wer_of(words)                                   # A/sm (words.json timings) drive the pause mapping below
    heard, An = words, A                                               # fidelity reading (may come from the second opinion)
    # Second opinion: base.en mishears reduced function words ("as" -> "a"/"is"). When it reports errors, re-listen with a
    # larger model and keep the better reading for FIDELITY only (timings stay from words.json). Real skips fail both.
    asr2 = os.environ.get("VOICE_ASR2", "small.en")
    if m["wer"] > 0 and asr2 and asr2 != "off":
        w2 = transcribe(y, asr2); wer2, A2, _ = wer_of(w2)
        if wer2 < m["wer"]:
            m["wer_base"], m["wer"], heard, An = m["wer"], wer2, w2, A2
            m["asr"] = asr2
    pn = [t for t, _ in P if t.isdigit()]; an = [t for t, _ in An if t.isdigit()]
    if pn != an:
        fails.append(f"numbers spoken {an} ≠ script {pn}")
    if m["wer"] > WER_FAIL:
        fails.append(f"word error {m['wer']:.0%} (skipped/garbled words): heard “{' '.join(w['w'] for w in heard)}”")
    elif m["wer"] > WER_WARN:
        warns.append(f"word error {m['wer']:.0%}: heard “{' '.join(w['w'] for w in heard)}”")

    # marked pauses: map plan raw-word → ASR word via the token alignment, then find the real silence
    tgt, raw = marks(line["text"], line.get("pauses"))
    pi2ai = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                pi2ai[i1 + k] = j1 + k
    asr_tok_word = [ri for _, ri in A]                                  # ASR token index → ASR word index
    if len(" ".join(w["w"] for w in words).replace("—", " — ").split()) != len(words):
        warns.append("ASR word list has multi-part words; pause positions approximate")
    m["pauses"] = []
    for ri, target in sorted(tgt.items()):
        pidx = [k for k, (_, r) in enumerate(P) if r <= ri]
        if not pidx:
            continue
        pk = pidx[-1]
        ak = pi2ai.get(pk)
        if ak is None:
            warns.append(f"pause after “{raw[ri]}”: word not recognised, cannot verify"); continue
        w0 = words[asr_tok_word[ak]]
        nxt = words[asr_tok_word[ak] + 1] if asr_tok_word[ak] + 1 < len(words) else {"s": dur, "e": dur}
        lo_t, hi_t = w0["s"], max(nxt["e"], w0["e"] + 0.2)
        cand = [b - a for a, b in sil if a < hi_t and b > lo_t]
        got = round(max(cand), 2) if cand else 0.0
        m["pauses"].append({"after": raw[ri], "target": target, "measured": got})
        if got < MARK_DROPPED:
            fails.append(f"pause after “{raw[ri]}” dropped (measured {got}s, target {target}s)")
        elif got < 0.8 * target:
            warns.append(f"pause after “{raw[ri]}” short: {got}s vs target {target}s")

    # pitch + peak
    f0, _, _ = librosa.pyin(y, fmin=60, fmax=320, sr=SR, frame_length=1024)
    f = f0[~np.isnan(f0)]
    if len(f) > 20:
        m["pitch_med"] = round(float(np.median(f)), 1)
        m["pitch_range_st"] = round(float(12 * np.log2(np.percentile(f, 90) / np.percentile(f, 10))), 1)
        if m["pitch_range_st"] < 4:
            warns.append(f"monotone: pitch range {m['pitch_range_st']} st (< 4)")
    pk = float(np.abs(y).max()) if len(y) else 0
    m["peak_db"] = round(20 * np.log10(pk + 1e-9), 1)
    if m["peak_db"] >= -0.1:
        fails.append(f"clipped (peak {m['peak_db']} dBFS)")
    elif m["peak_db"] > -1:
        warns.append(f"hot peak {m['peak_db']} dBFS")
    return m, fails, warns


# ---------------------------------------------------------------- plan
def script_words(text: str, asr: list) -> list:
    """The script owns the WORDS, ASR owns the TIMING: align whisper words to the plan text and return
    [{w: script spelling + punctuation, s, e}]. 1:1 substitutions take the script word ("60" -> "sixty,", "is" -> "as");
    whisper splits ("11", ".18") or merges are re-timed across the span; unmatched ASR words keep their own text."""
    sw = [w for w in text.replace("—", " — ").replace("…", "… ").split() if re.sub(r"[^\w']", "", w)]
    key = lambda w: [t for t, _ in tokens(w)]
    a = [" ".join(key(w)) for w in sw]; b = [" ".join(key(w["w"])) for w in asr]
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            out += [{"w": sw[i1 + k], "s": asr[j1 + k]["s"], "e": asr[j1 + k]["e"]} for k in range(i2 - i1)]
        elif op == "replace" and j2 > j1:                              # n script words over m ASR words: spread the span
            s0, e0 = asr[j1]["s"], asr[j2 - 1]["e"]; n = i2 - i1; d = (e0 - s0) / n
            out += [{"w": sw[i1 + k], "s": round(s0 + k * d, 3), "e": round(s0 + (k + 1) * d, 3)} for k in range(n)]
        elif op == "insert":
            out += [dict(asr[j]) for j in range(j1, j2)]              # spoken but not scripted: keep (the voice gate flags it)
        # "delete" (scripted, not heard) -> nothing to time; the voice gate already FAILs real skips
    return out


def load_plan(ep: Path):
    p = ep / "voice.json"
    if not p.exists():
        sys.exit(f"voice: {p} missing — every episode needs a performance plan (see docs/OPENMONTAGE_LESSONS.md §D)")
    return json.loads(p.read_text())


def gaps(ep) -> tuple:
    """For plan.py: ([(scene, vo_id, gap_before)], end_hold) — pauses come from the performance plan."""
    V = load_plan(Path(ep))
    out, prev = [], V.get("start_hold", 0.35)
    for ln in V["lines"]:
        out.append((ln["scene"], ln["id"], prev)); prev = ln["pause_after"]
    return out, V["end_hold"]


def check_plan(V):
    F, W = [], []
    ids = [l["id"] for l in V["lines"]]
    if len(set(ids)) != len(ids):
        F.append("duplicate line ids")
    for i, l in enumerate(V["lines"]):
        if l.get("tone") not in TONES:
            F.append(f"{l['id']}: tone '{l.get('tone')}' not in {sorted(TONES)}"); continue
        if not 1 <= int(l.get("energy", 0)) <= 5:
            F.append(f"{l['id']}: energy must be 1–5")
        if not l.get("direction"):
            W.append(f"{l['id']}: no direction")
        last = i == len(V["lines"]) - 1
        if not last and l.get("silence") is None:        # silence lines (countdown/hold) are the pause; no band applies
            lo, hi = TONES[l["tone"]]["after"]
            if not lo <= l["pause_after"] <= hi:
                F.append(f"{l['id']}: pause_after {l['pause_after']}s outside {l['tone']} range {lo}–{hi}")
        try:
            marks(l["text"], l.get("pauses"))
        except SystemExit as e:
            F.append(f"{l['id']}: {e}")
    if not END_HOLD[0] <= V.get("end_hold", 0) <= END_HOLD[1]:
        F.append(f"end_hold {V.get('end_hold')}s outside {END_HOLD}")
    if sum(1 for l in V["lines"] if l.get("climax")) != 1:
        F.append("exactly one line must be marked climax")
    if V.get("sample_line") not in ids:
        F.append("sample_line must name a line (the most emotional one is judged first)")
    tones = [l.get("tone") for l in V["lines"]]
    en = [int(l.get("energy", 0)) for l in V["lines"]]
    if len(set(tones)) < 3 or max(en) - min(en) < 3:
        W.append(f"flat arc: {len(set(tones))} tones, energy span {max(en) - min(en)} (want ≥ 3 / ≥ 3)")
    run = 1
    for a, b in zip(tones, tones[1:]):
        run = run + 1 if a == b else 1
        if run > 3:
            W.append(f"tone '{b}' held for > 3 lines — vary the read"); break
    return F, W


def take_path(ep: Path, lid: str):
    for ext in ("mp3", "wav"):
        p = ep / "vo" / f"{lid}.{ext}"
        if p.exists():
            return p
    return None


def cmd_check(a):
    ep = Path(a.ep).resolve(); V = load_plan(ep)
    F, W = check_plan(V)
    rows = []
    T = json.loads((ep / "timeline.json").read_text()) if (ep / "timeline.json").exists() else None
    if T:                                          # timeline must use the plan's pauses (plan.py reads them)
        sc = {s["vo"]: s for s in T["scenes"]}
        g, eh = gaps(ep)
        t_prev_end = 0.0
        for sid, vid, gap in g:
            s = sc.get(vid)
            if not s:
                F.append(f"{vid}: not in timeline.json — rerun plan.py"); continue
            if abs((s["start"] - t_prev_end) - gap) > 0.011:
                F.append(f"{vid}: timeline gap {s['start'] - t_prev_end:.2f}s ≠ plan {gap}s — rerun plan.py")
            t_prev_end = s["vo_end"]
        if abs(T["total"] - (t_prev_end + eh)) > 0.011:
            F.append(f"timeline end hold {T['total'] - t_prev_end:.2f}s ≠ plan {eh}s — rerun plan.py")
    if not a.plan_only:
        Wj = json.loads((ep / "words.json").read_text())
        for l in V["lines"]:
            if l.get("silence") is not None:            # pacing beat (countdown / hold): no take by design
                continue
            p = take_path(ep, l["id"])
            if not p:
                F.append(f"{l['id']}: no take in vo/ (run the pull stage)"); continue
            m, f, w = measure(l, load(p), Wj[l["id"]]["words"])
            rows.append({"id": l["id"], "tone": l["tone"], **m, "fails": f, "warns": w})
            F += [f"{l['id']}: {x}" for x in f]; W += [f"{l['id']}: {x}" for x in w]
    report(a, V, rows, F, W)


def report(a, V, rows, F, W, extra=None):
    if rows:
        print(f"{'line':<6}{'tone':<11}{'pace':>6}{'band':>11}{'wer':>6}{'pitch':>7}  pauses")
        for r in rows:
            lo, hi = TONES[r["tone"]]["pace"]
            ps = " ".join(f"{p['after'].strip('…:,.')}:{p['measured']}/{p['target']}" for p in r.get("pauses", []))
            print(f"{r['id']:<6}{r['tone']:<11}{r['pace']:>6}{f'{lo}–{hi}':>11}{r['wer']:>6.2f}{r.get('pitch_range_st', 0):>6}st  {ps}")
    for x in F:
        print("  FAIL ", x)
    for x in W:
        print("  WARN ", x)
    print(f"voice: {len(V['lines'])} lines · FAIL {len(F)} · WARN {len(W)}")
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps({"fails": F, "warns": W, "lines": rows, **(extra or {})}, ensure_ascii=False, indent=1))
    sys.exit(1 if F else 0)


def pick_line(V, lid=None):
    lid = lid or V.get("sample_line") or next((l["id"] for l in V["lines"] if l.get("climax")), V["lines"][0]["id"])
    return next(l for l in V["lines"] if l["id"] == lid)


def kokoro_speak(text, voice, speed, out):
    sys.path.insert(0, str(HERE))
    import tts_kokoro as TK
    k = TK.load()
    return TK.speak(k, text.replace("…", "...").replace("—", ","), voice, speed, out)


def cmd_sample(a):
    ep = Path(a.ep).resolve(); V = load_plan(ep); line = pick_line(V, a.line)
    F, W = check_plan(V)
    if F:
        report(a, V, [], F, W)
    print(f"SAMPLE LINE {line['id']} ({line['tone']}, energy {line['energy']}{', CLIMAX' if line.get('climax') else ''})")
    print(f"  text: {line['text']}\n  direction: {line['direction']}")
    takes = [Path(t) for t in (a.take or [])]
    if a.kokoro:
        d = Path.home() / ".cache/build" / ep.name / "voice_sample"; d.mkdir(parents=True, exist_ok=True)
        kv = V.get("kokoro_fallback", {"voice": "am_michael", "speed": 1.0})
        for f in (0.94, 1.0, 1.06):
            sp = round(kv["speed"] * TONES[line["tone"]]["speed"] * f, 3)
            out = d / f"{line['id']}_kokoro_{sp}.wav"
            kokoro_speak(line["text"], kv["voice"], sp, str(out)); takes.append(out)
    if not takes:
        print("\nNo takes yet. Generate 2–3 takes of the line above (e.g. generate_speech with the episode voice),\n"
              f"then:  python3 reelkit/voice.py sample {a.ep} --take take1.mp3 take2.mp3")
        sys.exit(2)
    rows, best = [], None
    for t in takes:
        y = load(t)
        m, f, w = measure(line, y, transcribe(y))
        lo, hi = TONES[line["tone"]]["pace"]
        short = sum(max(0, p["target"] - p["measured"]) for p in m["pauses"])
        score = len(f) * 100 + len(w) * 10 + abs(m["pace"] - (lo + hi) / 2) / (hi - lo) * 10 + short * 20
        rows.append({"id": line["id"], "tone": line["tone"], "take": str(t), "score": round(score, 1), **m, "fails": f, "warns": w})
    rows.sort(key=lambda r: r["score"])
    print()
    for r in rows:
        verdict = "FAIL" if r["fails"] else ("WARN" if r["warns"] else "PASS")
        ps = " ".join(f"{p['after'].strip('…:,.')} {p['measured']}/{p['target']}s" for p in r["pauses"])
        print(f"  {verdict:<4} score {r['score']:>6}  pace {r['pace']}  wer {r['wer']:.2f}  pitch {r.get('pitch_range_st')}st  [{ps}]  {Path(r['take']).name}")
        for x in r["fails"] + r["warns"]:
            print(f"         - {x}")
    best = rows[0]
    print(f"\nBEST: {best['take']}" + ("" if not best["fails"] else "  — still FAILS: regenerate before producing the other lines"))
    if a.report:
        Path(a.report).write_text(json.dumps({"line": line["id"], "takes": rows}, ensure_ascii=False, indent=1))
    sys.exit(1 if best["fails"] else 0)


def cmd_lines(a):
    V = load_plan(Path(a.ep).resolve())
    print(f"# {V['episode']} — voice: {V['voice']}\n# intent: {V['intent']}\n# pacing: {V['pacing_profile']}\n")
    order = [pick_line(V)] + [l for l in V["lines"] if l["id"] != V.get("sample_line")]
    for i, l in enumerate(order):
        tag = "SAMPLE FIRST — gate with `voice.py sample` before the rest" if i == 0 else ""
        print(f"[{l['id']}] {l['tone']} · energy {l['energy']} · then {l['pause_after']}s  {tag}\n  SAY: {l['text']}\n  HOW: {l['direction']}\n")


def cmd_kokoro(a):
    ep = Path(a.ep).resolve(); V = load_plan(ep)
    kv = V.get("kokoro_fallback", {"voice": "am_michael", "speed": 1.0})
    out = Path(a.out or ep / "vo"); only = set((a.only or "").split(",")) - {""}
    for l in V["lines"]:
        if only and l["id"] not in only:
            continue
        sp = round(kv["speed"] * TONES[l["tone"]]["speed"], 3)
        d = kokoro_speak(l["text"], kv["voice"], sp, str(out / f"{l['id']}.wav"))
        print(f"{l['id']}  {d:5.2f}s  speed {sp}  {l['text'][:60]}")


def cmd_words(a):
    """words.json from the takes in vo/: dur = trim_vo.py's trimmed length (48 kHz), words from whisper."""
    import numpy as np
    ep = Path(a.ep); V = load_plan(ep)
    wp = ep / "words.json"
    Wj = json.loads(wp.read_text()) if wp.exists() else {}
    only = set(a.only.split(",")) if a.only else None
    missing = []
    for l in V["lines"]:
        if only and l["id"] not in only:
            continue
        p = take_path(ep, l["id"])
        if not p:
            missing.append(l["id"]); continue
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(pcm, np.float32); idx = np.flatnonzero(np.abs(x) > 0.01)
        n = (min(len(x), idx[-1] + int(0.12 * 48000)) - max(0, idx[0] - int(0.04 * 48000))) if len(idx) else len(x)
        words = transcribe(load(p))
        Wj[l["id"]] = {"dur": round(n / 48000, 3), "words": words}
        print(f"{l['id']}: {Wj[l['id']]['dur']:.3f}s  {' '.join(w['w'] for w in words)}")
    order = [l["id"] for l in V["lines"]]
    Wj = {k: Wj[k] for k in sorted(Wj, key=lambda k: order.index(k) if k in order else 99)}
    wp.write_text(json.dumps(Wj, indent=1) + "\n")
    print(f"words.json: {len(Wj)}/{len(order)} lines" + (f" · no take yet: {', '.join(missing)}" if missing else ""))


def cmd_shape(a):
    import numpy as np, soundfile as sf, shutil
    ep = Path(a.ep).resolve(); V = load_plan(ep); Wj = json.loads((ep / "words.json").read_text())
    only = set((a.only or "").split(",")) - {""}
    changed = False
    for l in V["lines"]:
        if only and l["id"] not in only:
            continue
        src = take_path(ep, l["id"])
        if not src:
            continue
        y16 = load(src)
        m, _, _ = measure(l, y16, Wj[l["id"]]["words"])
        todo = [p for p in m["pauses"] if MARK_DROPPED <= p["measured"] < 0.8 * p["target"]]
        if not todo:
            continue
        # full-rate decode exactly like trim_vo.py (48 kHz mono float, |x| > 0.01, pads 40/120 ms)
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(pcm, np.float32).copy()
        idx = np.flatnonzero(np.abs(x) > 0.01); t0 = max(0, idx[0] - int(0.04 * 48000))
        sil = silences(y16); words = Wj[l["id"]]["words"]
        inserts = []                                                    # (time in trimmed take, seconds to add)
        for p in todo:
            w = next(w for w in words if re.sub(r"[^\w']", "", w["w"].lower()) == re.sub(r"[^\w']", "", p["after"].lower()))
            nxt = words[words.index(w) + 1]
            a0, b0 = max(((a_, b_) for a_, b_ in sil if a_ < max(nxt["e"], w["e"] + .2) and b_ > w["s"]), key=lambda r: r[1] - r[0])
            add = round(p["target"] - p["measured"], 3)
            inserts.append(((a0 + b0) / 2, add, p, a0, b0))
        for mid, add, p, a0, b0 in sorted(inserts, reverse=True):      # back to front keeps earlier offsets valid
            i = t0 + int(mid * 48000)
            seg = x[i - int(0.05 * 48000): i + int(0.05 * 48000)]      # loop the take's own room tone (100 ms)
            fill = np.resize(seg, int(add * 48000))
            ramp = np.minimum(1, np.minimum(np.arange(len(fill)), np.arange(len(fill))[::-1]) / 240)
            x = np.concatenate([x[:i], fill * ramp, x[i:]])
            print(f"{l['id']}: pause after “{p['after']}” {p['measured']}s → {p['target']}s (+{add}s at {mid:.2f}s)")
        if a.dry_run:
            continue
        orig = ep / "vo" / "orig" / src.name
        orig.parent.mkdir(parents=True, exist_ok=True)
        if not orig.exists():
            shutil.move(str(src), orig)
        elif src.suffix == ".wav":
            src.unlink()
        sf.write(ep / "vo" / f"{l['id']}.wav", x, 48000, subtype="PCM_16")
        for mid, add, p, a0, b0 in sorted(inserts, reverse=True):
            key = re.sub(r"[^\w']", "", p["after"].lower())
            k = next(i for i, w in enumerate(words) if re.sub(r"[^\w']", "", w["w"].lower()) == key)
            for w in words[k + 1:]:
                w["s"] = round(w["s"] + add, 3); w["e"] = round(w["e"] + add, 3)
            # whisper stretches words over silences: snap the boundary words to the real (waveform) silence
            words[k]["e"] = round(min(words[k]["e"], a0), 3)
            nx = words[k + 1]
            nx["s"] = round(max(nx["s"], b0 + add), 3); nx["e"] = round(max(nx["e"], nx["s"] + 0.08), 3)
        idx = np.flatnonzero(np.abs(x) > 0.01)
        Wj[l["id"]]["dur"] = round((min(len(x), idx[-1] + int(0.12 * 48000)) - max(0, idx[0] - int(0.04 * 48000))) / 48000, 3)
        l.setdefault("shaped", {}).update({p["after"].strip("…:,."): {"from": p["measured"], "to": p["target"], "original": f"vo/orig/{src.name}"}
                                           for _, _, p, *_ in inserts})
        changed = True
    if changed:
        (ep / "words.json").write_text(json.dumps(Wj, indent=1) + "\n")
        (ep / "voice.json").write_text(json.dumps(V, ensure_ascii=False, indent=1) + "\n")
        print("shaped. next: python3 <ep>/plan.py → episode.sh <ep> trim score build … ; media.py push <ep>")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check"); c.add_argument("ep"); c.add_argument("--plan-only", action="store_true"); c.add_argument("--report")
    s = sp.add_parser("sample"); s.add_argument("ep"); s.add_argument("--take", nargs="*"); s.add_argument("--kokoro", action="store_true")
    s.add_argument("--line"); s.add_argument("--report")
    l = sp.add_parser("lines"); l.add_argument("ep")
    k = sp.add_parser("kokoro"); k.add_argument("ep"); k.add_argument("--only"); k.add_argument("--out")
    h = sp.add_parser("shape"); h.add_argument("ep"); h.add_argument("--only"); h.add_argument("--dry-run", action="store_true")
    w = sp.add_parser("words"); w.add_argument("ep"); w.add_argument("--only")
    a = ap.parse_args()
    {"check": cmd_check, "sample": cmd_sample, "lines": cmd_lines, "kokoro": cmd_kokoro, "shape": cmd_shape, "words": cmd_words}[a.cmd](a)


if __name__ == "__main__":
    main()
