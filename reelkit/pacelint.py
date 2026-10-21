"""pacelint.py — Q23: the explanation must MOVE like the winners (docs/DECODE_2026-10-18.md: ~27 visual events / 10 s, no dead air).

  python3 reelkit/pacelint.py <episode_dir>      # exit 1 on FAIL · needs timeline.json (reelkit/plan.py) + visuals.json

Scope (owner 2026-10-21): the quiz part (question · options · timer · reveal) is fixed; this gate looks only at the explanation
window — from the first story scene (s05) to the start of the CTA scene. It measures the RESOLVED timeline, not the author's intent:
  FAIL  motion density < 15 events / 10 s in the explanation
  FAIL  a static span > 2.5 s (no event starts and no camera / chart / photo tween is in flight)
  FAIL  no real visual beyond the map + cards + stickers (needs ≥ 1 of photo · chart · compare · split · erase · route · rise · travel)
  FAIL  a story scene with fewer than 2 visual events (the cut did not follow the sentence)
  WARN  density < 20 (good, not great)
It prints the static spans with timestamps so the editor fixes THAT moment instead of adding filler everywhere.
"""
import json, re, sys
from pathlib import Path
EVENT = {"fact_in", "fact_out", "sticker_in", "sticker_out", "character_in", "character_out", "photo_in", "photo_out", "hide", "reveal",
         "geo.cam_to", "geo.pin_in", "geo.pin_out", "geo.label_in", "geo.label_out", "geo.highlight_in", "geo.highlight_out", "geo.highlight_pulse",
         "geo.route_draw", "geo.disputed_in", "geo.disputed_out", "geo.spin", "geo.rise", "geo.travel", "geo.fade", "fx.flash", "fx.pop"}
SPAN = {"geo.cam_to", "geo.spin", "geo.route_draw", "geo.travel", "geo.fade", "chart.counter_run", "chart.erase_run", "chart.bars_in", "chart.compare_in"}
REAL = {"photo_in", "geo.rise", "geo.travel", "geo.route_draw", "chart.counter_run", "chart.bars_in", "chart.compare_in", "chart.split_in", "chart.erase_run", "chart.callouts_in", "chart.strip_in"}
DEFAULT_DUR = {"geo.cam_to": 1.2, "geo.spin": 1.2, "geo.route_draw": 1.2, "geo.travel": 1.2, "geo.fade": 1.2, "chart.counter_run": 1.5, "chart.erase_run": 1.5, "chart.bars_in": 1.2, "chart.compare_in": 1.4}

def resolver(TL):
    SC = {s["id"]: s for s in TL["scenes"]}; total = float(TL["total"])
    def T(expr):
        if isinstance(expr, (int, float)): return float(expr)
        m = re.fullmatch(r"(end|s\w+?)(?:\.(end))?(?:@([\w-]+))?(?:([+-])([\d.]+))?", str(expr).strip())
        if not m: return None
        base, end, cue, sign, off = m.groups()
        if base == "end": t = total
        else:
            s = SC.get(base)
            if not s: return None
            if cue: t = TL["cues"].get(f"{base}@{cue}", s["start"])
            elif end or sign == "-": t = s["end"]
            else: t = s["start"]
        if sign and off: t += float(off) * (1 if sign == "+" else -1)
        return round(t, 3)
    return T, SC, total

def run(ep):
    ep = Path(ep); F, W = [], []
    if not (ep / "timeline.json").exists(): return [], ["Q23: no timeline.json — pace not checked (run reelkit/plan.py)"]
    TL = json.loads((ep / "timeline.json").read_text()); X = json.loads((ep / "visuals.json").read_text())
    T, SC, total = resolver(TL)
    story = [s for s in TL["scenes"] if s.get("role") == "story"]; cta = [s for s in TL["scenes"] if s.get("role") == "cta"]
    if not story: return F, ["Q23: no story scenes"]
    w0, w1 = story[0]["start"], (cta[0]["start"] if cta else story[-1]["end"]); win = w1 - w0
    starts, spans, kinds = [], [], set()
    for b in X.get("beats", []):
        do = str(b.get("do", "")); t = T(b.get("at", 0))
        if t is None or not (w0 - 0.01 <= t <= w1): continue
        if do in EVENT or do.startswith("chart."): starts.append(t); kinds.add(do)
        if do in SPAN or do.startswith("chart."):
            t1 = T(b["until"]) if "until" in b else t + float(b.get("dur", (b.get("args") or {}).get("dur", DEFAULT_DUR.get(do, 1.0))))
            if t1 and t1 > t: spans.append((t, min(t1, w1)))
    dens = len(starts) / win * 10 if win else 0
    if dens < 15: F.append(f"Q23: explanation has {len(starts)} visual events in {win:.1f} s = {dens:.1f}/10 s — needs ≥ 15 (winners ≈ 27). Add moves where the sentence changes idea, not filler")
    elif dens < 20: W.append(f"Q23: pace {dens:.1f}/10 s — fine, winners run ≈ 27")
    # static spans: walk the window; covered = an event starts or a tween is in flight
    marks = sorted(set([w0] + starts + [w1])); static = []
    def covered(a, b): return any(s <= a and e >= b for s, e in spans)
    for a, b in zip(marks, marks[1:]):
        if b - a > 2.5 and not covered(a, b):
            # allow partial coverage: subtract in-flight tween time
            gap = b - a - sum(max(0, min(e, b) - max(s, a)) for s, e in spans)
            if gap > 2.5: static.append((a, b))
    for a, b in static: F.append(f"Q23: nothing moves {a:.1f}–{b:.1f} s ({b - a:.1f} s) — the viewer swipes here; give this sentence its own visual")
    if not (kinds & REAL): F.append("Q23: the explanation is only map + cards + stickers — show the real thing (photo / chart / route / rise / split)")
    for s in story:
        n = sum(1 for t in starts if s["start"] - 0.01 <= t < s["end"])
        if n < 2: F.append(f"Q23: scene {s['id']} ({s['start']:.1f}–{s['end']:.1f} s) has {n} visual event(s) — every sentence gets at least two moves")
    return F, W

if __name__ == "__main__":
    F, W = run(sys.argv[1])
    for x in F: print("  FAIL ", x)
    for x in W: print("  WARN ", x)
    print(f"pacelint: {Path(sys.argv[1]).name} → FAIL {len(F)} WARN {len(W)}"); sys.exit(1 if F else 0)
