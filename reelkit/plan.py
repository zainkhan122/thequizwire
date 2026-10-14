#!/usr/bin/env python3
"""reelkit/plan.py — master timeline for a QuizWire episode (shared; episodes don't carry their own plan.py).

    python3 reelkit/plan.py <ep>                 words.json (whisper) + voice.json gaps -> timeline.json   (real timing)
    python3 reelkit/plan.py <ep> --estimate      no VO yet: estimate durations from the text (chars/s per tone) so the
                                                 composition can be built, linted and previewed in the sandbox before
                                                 the CI `tts` stage speaks it. timeline.json gets "estimated": true and
                                                 every release gate (planlint/qa) refuses an estimated timeline.

timeline.json = {total, estimated, scenes[{id, vo, start, vo_end, end, role}], words[{w, s, e, scene}], cues{name: t}}
Cues: voice.json lines may carry "cues": {"name": "word"} (nth match "word#2") -> absolute start time of that spoken
word in that line; the compose engine resolves beat times like "s03@answer" from them. Quiz pacing beats that have no
VO (countdown, reveal hold) are plain lines with "silence": seconds instead of text.
"""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice as VOICE  # noqa: E402

CPS = {"urgent": 17.5, "tense": 16.0, "neutral": 15.0, "resolute": 14.5, "revelatory": 14.0, "suspense": 12.5,
       "somber": 13.0, "tender": 12.5, "reverent": 12.0}     # chars/s of Kokoro am_michael at speed 1.0 (measured ~15 cps)


def estimate_words(text, tone, speed=1.0):
    """Even-spaced word timing from text length (good enough for layout; CI replaces it with whisper times)."""
    words = text.split()
    dur = max(0.6, len(text) / (CPS.get(tone, 15.0) * speed)) + 0.25 * text.count("…") + 0.15 * text.count(",")
    out, t = [], 0.0
    per = dur / max(1, sum(len(w) + 1 for w in words))
    for w in words:
        d = (len(w) + 1) * per
        out.append({"w": w, "s": round(t, 3), "e": round(t + d, 3)}); t += d
    return {"dur": round(dur, 3), "words": out}


def norm(w): return re.sub(r"[^a-z0-9]", "", w.lower())


def build(ep: Path, estimate=False):
    V = VOICE.load_plan(ep)
    kv = V.get("kokoro_fallback", {"voice": "am_michael", "speed": 1.0})
    W = {}
    wp = ep / "words.json"
    if wp.exists() and not estimate:
        W = json.loads(wp.read_text())
    order, end_hold = VOICE.gaps(ep)
    text = {l["id"]: l for l in V["lines"]}
    t = 0.0; scenes = []; words = []; est_used = False
    for sid, vo, gap in order:
        t += gap
        ln = text[vo]
        if ln.get("silence") is not None:                 # pacing beat without speech (countdown, reveal hold)
            d = float(ln["silence"]); ws = []
        elif vo in W:
            d = W[vo]["dur"]; ws = VOICE.script_words(ln["text"], W[vo]["words"])
        else:
            if not estimate:
                sys.exit(f"plan: no words.json entry for {vo} — run `voice.py words` (or use --estimate for a preview)")
            est = estimate_words(ln["text"], ln.get("tone", "neutral"), kv.get("speed", 1.0) * VOICE.TONES[ln.get("tone", "neutral")]["speed"])
            d, ws, est_used = est["dur"], est["words"], True
        scenes.append({"id": sid, "vo": vo, "start": round(t, 3), "vo_end": round(t + d, 3), "role": ln.get("role", "")})
        for w in ws:
            words.append({"w": w["w"], "s": round(t + w["s"], 3), "e": round(t + w["e"], 3), "scene": sid})
        t += d
    total = round(t + end_hold, 2)
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else total

    def find(word, scene):
        word, _, nth = word.partition("#"); nth = int(nth or 1); k = 0
        for w in words:
            if w["scene"] == scene and norm(w["w"]) == norm(word):
                k += 1
                if k == nth: return w["s"]
        raise KeyError(f"cue word '{word}' not found in {scene}")

    cues = {}
    for s in scenes:
        for name, word in text[s["vo"]].get("cues", {}).items():
            cues[f"{s['id']}@{name}"] = round(find(word, s["id"]), 3)
    return {"total": total, "estimated": est_used, "scenes": scenes, "words": words, "cues": cues}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("--estimate", action="store_true"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(); ep = Path(a.ep).resolve()
    tl = build(ep, a.estimate)
    (ep / "timeline.json").write_text(json.dumps(tl, indent=1) + "\n")
    if not a.quiet:
        print(f"timeline: total {tl['total']} s · {len(tl['scenes'])} scenes · {len(tl['words'])} words · {len(tl['cues'])} cues" + ("  (ESTIMATED — not for release)" if tl["estimated"] else ""))
        for s in tl["scenes"]: print(f"  {s['id']:5} {s['role']:10} {s['start']:6.2f} → {s['end']:6.2f}  ({s['vo']})")


if __name__ == "__main__":
    main()
