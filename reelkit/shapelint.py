#!/usr/bin/env python3
"""shapelint.py — the anti-template gates (owner 2026-10-19: "each short's explanation must be thought out like a human would").

  python3 reelkit/shapelint.py <episode_dir>        # exit 1 on FAIL

Q19 brief      <ep>/brief.md exists and every section is actually written (not the placeholder), incl. the swipe test at
               three timestamps and the "how this differs from the last ones" line. The brief is the author's thinking,
               committed next to the episode so the owner can read WHY this short looks the way it does.
Q20 shape      the explanation's structural fingerprint — number of story scenes and the device set used in each
               (fact card · sticker · counter · bars · compare · pin · label · route · highlight-out · spin · flash · cam) —
               must differ from every other episode in the same series, and the scenes inside one episode must not all share
               the same device set (the "three identical cards" smell). Devices named in the brief must be present.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ["Hook fact", "Show it", "Beat order", "Different from", "Swipe test", "Devices"]
PLACEHOLDER = re.compile(r"(?i)\b(todo|tbd|lorem|fill me|xxx)\b")
DEVICE_OF = {"fact_in": "card", "sticker_in": "sticker", "chart.counter_run": "counter", "chart.bars_in": "bars", "chart.compare_in": "compare",
             "geo.pin_in": "pin", "geo.label_in": "label", "geo.route_draw": "route", "geo.highlight_out": "erase", "geo.spin": "spin",
             "fx.flash": "flash", "geo.cam_to": "cam", "character_in": "character", "geo.disputed_in": "disputed", "geo.highlight_in": "highlight"}
DEVICE_WORDS = {"card": r"\bcard", "sticker": r"\bsticker", "counter": r"\bcounter", "bars": r"\bbar( |s\b|chart)", "compare": r"\bcompar", "pin": r"\bpin",
                "label": r"\blabel", "route": r"\broute|\btrace", "erase": r"\berase|\bfall away|\bhighlight.out", "spin": r"\bspin|\bglobe",
                "flash": r"\bflash", "character": r"\bmascot|\bcharacter|\bflag.?ball"}


def brief_check(ep):
    F = []
    p = Path(ep) / "brief.md"
    if not p.exists(): return [f"Q19: {p.name} missing — write the creative brief before authoring (docs/BRIEF.md)"], {}
    txt = p.read_text()
    secs = {}
    for i, name in enumerate(SECTIONS):
        m = re.search(rf"^##\s*{re.escape(name)}.*?$([\s\S]*?)(?=^##\s|\Z)", txt, re.M)
        body = (m.group(1) if m else "").strip()
        secs[name] = body
        if not m: F.append(f"Q19: brief section '## {name}' missing")
        elif len(re.sub(r"\s+", " ", body)) < 40: F.append(f"Q19: brief section '{name}' is not written ({len(body)} chars)")
        elif PLACEHOLDER.search(body): F.append(f"Q19: brief section '{name}' still has a placeholder")
    sw = secs.get("Swipe test", "")
    stamps = re.findall(r"(\d{1,2})\s*s\b", sw)
    if len(set(stamps)) < 3: F.append("Q19: swipe test needs three timestamps (e.g. 8 s / 15 s / 22 s) each with what moves and why someone stays")
    return F, secs


def fingerprint(ep):
    V = json.loads((Path(ep) / "visuals.json").read_text())
    scenes = {}
    for b in V.get("beats", []):
        at = str(b.get("at", "")); m = re.match(r"s(\d\d)", at)
        if not m: continue
        n = int(m.group(1))
        if n < 5: continue                                   # s01–s04 are the quiz; the explanation starts at s05
        d = DEVICE_OF.get(b.get("do"))
        if d and d != "cam": scenes.setdefault(n, set()).add(d)
        elif d == "cam": scenes.setdefault(n, set())
    ids = sorted(scenes)
    if ids: ids = ids[:-1]                                   # the last scene is the CTA
    return [tuple(sorted(scenes[i])) for i in ids]


def shape_check(ep, secs):
    F, W = [], []
    E = json.loads((Path(ep) / "episode.json").read_text())
    fp = fingerprint(ep)
    if not fp: return ["Q20: no story scenes found in visuals.json"], []
    if len(fp) < 2: F.append("Q20: fewer than 2 story beats")
    if len(fp) >= 3 and len(set(fp)) == 1: F.append(f"Q20: every story scene uses the same device set {fp[0]} — that is a template, not a story")
    if all(set(x) <= {"card", "sticker", "pin", "label"} for x in fp): F.append("Q20: explanation is only cards + stickers + pins (the old recipe) — SHOW the hook fact (counter, comparison, route, erase, spin, flash …)")
    if sum(1 for x in fp if "card" in x and "sticker" in x) == len(fp) and len(fp) >= 3: F.append("Q20: every beat is card + sticker — vary the beats")
    mine = (len(fp), tuple(fp))
    for other in sorted((ROOT / "series").glob("*/ep*/visuals.json")):
        if other.parent.resolve() == Path(ep).resolve() or "_template" in str(other): continue
        try:
            OE = json.loads((other.parent / "episode.json").read_text())
            if OE.get("series") != E.get("series") or OE.get("status") not in ("ready", "sent", "scheduled", "published"): continue
            ofp = fingerprint(other.parent)
        except Exception: continue
        if ofp and (len(ofp), tuple(ofp)) == mine: F.append(f"Q20: same explanation shape as {other.parent.name} {fp} — give this one its own structure")
    devs = secs.get("Devices", "").lower() if secs else ""
    used = set().union(*[set(x) for x in fp]) if fp else set()
    for d, rx in DEVICE_WORDS.items():
        if re.search(rx, devs) and d not in used and d != "character": W.append(f"Q20: brief promises '{d}' but the timeline never uses it")
    return F, W


def run(ep):
    F1, secs = brief_check(ep)
    F2, W = shape_check(ep, secs) if (Path(ep) / "visuals.json").exists() else ([], [])
    return F1 + F2, W


if __name__ == "__main__":
    F, W = run(sys.argv[1])
    for w in W: print(f"  WARN  {w}")
    for f in F: print(f"  FAIL  {f}")
    print(f"shapelint: {Path(sys.argv[1]).name} · shape {fingerprint(sys.argv[1])} → FAIL {len(F)} WARN {len(W)}")
    sys.exit(1 if F else 0)
