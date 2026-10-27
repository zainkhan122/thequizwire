#!/usr/bin/env python3
"""slots.py — per-channel posting times come from our own stats, not from habit (owner 2026-10-27).

Reads dispatch/stats_summary.json (tools/stats.py). For every channel that has learned `best_hours` (≥ 8 videos with
first-24 h data) the two slots in config/publishing.json → buffer.scheduling.times are replaced by the learned hours;
channels without data keep the researched defaults, and `times_source` records which is which so the reason is visible.
Learned hours are kept at least 3 h apart (one morning / one evening slot), like the defaults.

  python3 tools/slots.py apply     # rewrite config/publishing.json if anything changed; prints a one-line reason per channel
  python3 tools/slots.py show
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "config/publishing.json"; SUMMARY = ROOT / "dispatch/stats_summary.json"
DEFAULTS = {"youtube": ["12:00", "19:00"], "instagram": ["11:00", "19:00"], "facebook": ["13:00", "19:00"], "twitter": ["09:00", "17:00"], "threads": ["10:00", "19:00"]}

def spread(hours):
    """Two learned hours at least 3 h apart; if the top two are neighbours, keep the best and the default's other half."""
    hs = sorted(int(h[:2]) for h in hours)
    if len(hs) >= 2 and abs(hs[1] - hs[0]) >= 3: return [f"{h:02d}:00" for h in hs]
    return [f"{hs[0]:02d}:00", "19:00" if hs[0] < 15 else "12:00"]

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    pub = json.loads(PUB.read_text()); sch = pub.setdefault("buffer", {}).setdefault("scheduling", {})
    times = sch.setdefault("times", dict(DEFAULTS)); src = sch.setdefault("times_source", {})
    S = json.loads(SUMMARY.read_text()) if SUMMARY.exists() else {"channels": {}}
    changed = False
    for ch, default in DEFAULTS.items():
        learned = (S.get("channels", {}).get(ch) or {}).get("best_hours")
        want = spread(learned) if learned else default
        why = f"learned from {S['channels'][ch]['videos_with_first24']} videos' first-24 h views" if learned else "researched defaults (no per-channel counters yet)"
        if times.get(ch) != want or src.get(ch) != why: times[ch] = want; src[ch] = why; changed = True
        print(f"slots: {ch:9s} {want}  — {why}", file=sys.stderr)
    if cmd == "apply" and changed: PUB.write_text(json.dumps(pub, indent=1, ensure_ascii=False) + "\n"); print("slots: config/publishing.json updated", file=sys.stderr)

if __name__ == "__main__": main()
