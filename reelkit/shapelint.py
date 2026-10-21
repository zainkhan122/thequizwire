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
             "fx.flash": "flash", "geo.cam_to": "cam", "geo.travel": "travel", "photo_in": "photo", "geo.rise": "rise", "chart.split_in": "split", "chart.erase_run": "erase", "character_in": "character", "geo.disputed_in": "disputed", "geo.highlight_in": "highlight"}
DEVICE_WORDS = {"card": r"\bcard", "sticker": r"\bsticker", "counter": r"\bcounter", "bars": r"\bbar( |s\b|chart)", "compare": r"\bcompar", "pin": r"\bpin",
                "label": r"\blabel", "route": r"\broute|\btrace", "erase": r"\berase|\bfall away|\bhighlight.out", "spin": r"\bspin|\bglobe", "photo": r"\bphoto|\bpicture|\bfootage|\bstill\b", "rise": r"\brises?\b|\bpops? (up )?out of", "travel": r"\btravel|\brides?\b|\bruns along|\bmoves along", "split": r"\bsplit|then.vs.now|then-and-now",
                "flash": r"\bflash", "character": r"\bmascot|\bcharacter|\bflag.?ball"}


def brief_check(ep):
    F, W = [], []
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
    # P2 (2026-10-21): real media is part of the thinking. "## Media" names the asset(s) (Commons file + why it is the right image) or
    # says in a sentence why this Short is better without one. Episodes authored before P2 (no section) get a WARN until re-authored.
    m = re.search(r"^##\s*Media.*?$([\s\S]*?)(?=^##\s|\Z)", txt, re.M); media = (m.group(1) if m else "").strip()
    V = json.loads((Path(ep) / "visuals.json").read_text()) if (Path(ep) / "visuals.json").exists() else {}
    has_photo = any(e.get("type") == "photo" for e in V.get("elements", []))
    lp = Path(ep).resolve().parents[2] / "dispatch/ledger.json"
    live = lp.exists() and any(x.get("episode") == Path(ep).name and x.get("state") in ("scheduled", "sent") for x in json.loads(lp.read_text()).get("posts", []))
    sink = W if live else F                                           # already-shipped episodes are not re-gated on a rule written after them
    if not m: sink.append("Q19: brief section '## Media' missing — name the real photo/footage (File:… on Commons) or say why none")
    elif len(media) < 40: sink.append("Q19: brief 'Media' is not written")
    elif has_photo and "file:" not in media.lower(): F.append("Q19: the episode uses a photo but the brief's Media section does not name the Commons file")
    sw = secs.get("Swipe test", "")
    stamps = re.findall(r"(\d{1,2})\s*s\b", sw)
    if len(set(stamps)) < 3: F.append("Q19: swipe test needs three timestamps (e.g. 8 s / 15 s / 22 s) each with what moves and why someone stays")
    secs["_warn"] = W
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


def truth_check(ep):
    """Q21: the declared opener / reveal (episode.json variety) must be visible on the timeline — a label is not a look."""
    ep = Path(ep); F = []
    try:
        E = json.loads((ep / "episode.json").read_text()); V = json.loads((ep / "visuals.json").read_text()); G = json.loads((ep / "geo.json").read_text())
    except Exception: return F
    var = E.get("variety") or {}; B = V.get("beats", [])
    cams = [(str(b.get("at")), b.get("args") or {}) for b in B if b.get("do") in ("geo.cam_to", "geo.cam_set")]
    pre = [(at, a) for at, a in cams if not at.startswith(("s04", "s05", "s06", "s07", "s08", "s09", "end"))]
    scene = next(iter((G.get("scenes") or {}).values()), {})
    hl = [L for L in scene.get("layers", []) if L.get("kind") == "highlight"]
    op = var.get("opener"); rv = var.get("reveal")
    if op == "split-candidates" and sum(1 for at, _ in pre if at.startswith("s02@")) < 3: F.append("Q21: opener 'split-candidates' declared but the camera never visits the candidates during s02")
    if op == "mystery-zoom-out":
        ks = [float(a.get("k", 0)) for _, a in pre if a.get("k")]
        if len(ks) < 2 or ks[0] <= ks[-1] + 0.05: F.append("Q21: opener 'mystery-zoom-out' declared but the pre-reveal camera does not pull out")
    if op == "night-lights" and (scene.get("basemap") or {}).get("layer") != "night": F.append("Q21: opener 'night-lights' declared but the basemap is not the night layer")
    if rv == "flag-lift" and not any(L.get("lift") == "flag" for L in hl): F.append("Q21: reveal 'flag-lift' declared but the highlight layer has no flag lift")
    if rv == "colour-lift" and not any(L.get("lift") == "color" for L in hl): F.append("Q21: reveal 'colour-lift' declared but the highlight layer has no colour lift")
    if rv == "fill-pulse" and not any(b.get("do") == "geo.highlight_pulse" and str(b.get("at", "")).startswith("s04") for b in B): F.append("Q21: reveal 'fill-pulse' declared but there is no highlight pulse at s04")
    if rv == "flash-cut" and not any(b.get("do") == "fx.flash" and str(b.get("at", "")).startswith("s04") for b in B): F.append("Q21: reveal 'flash-cut' declared but there is no flash at s04")
    if rv == "feature-fill" and not any(L.get("kind") == "area" for L in scene.get("layers", [])): F.append("Q21: reveal 'feature-fill' declared but the scene has no area layer")
    if rv == "route-draw" and not any(b.get("do") == "geo.route_draw" and str(b.get("at", "")).startswith("s04") for b in B): F.append("Q21: reveal 'route-draw' declared but nothing draws at s04")
    return F


def run(ep):
    F1, secs = brief_check(ep)
    F2, W = shape_check(ep, secs) if (Path(ep) / "visuals.json").exists() else ([], [])
    return F1 + F2 + truth_check(ep), W + secs.get("_warn", [])


if __name__ == "__main__":
    F, W = run(sys.argv[1])
    for w in W: print(f"  WARN  {w}")
    for f in F: print(f"  FAIL  {f}")
    print(f"shapelint: {Path(sys.argv[1]).name} · shape {fingerprint(sys.argv[1])} → FAIL {len(F)} WARN {len(W)}")
    sys.exit(1 if F else 0)
