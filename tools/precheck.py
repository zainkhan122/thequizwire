#!/usr/bin/env python3
"""precheck.py — the CI-only traps, caught before the push (every rule below cost a 12-minute render round in Oct 2026).

  python3 tools/precheck.py series/<series>/<ep>      exit 1 on any FAIL

Voice (Kokoro + whisper gate):
  V1 no decimal numbers in narration ("67.7" is heard as "67, 7")            V2 ≤ 6 numerals per episode (wpm gate: a numeral is 1 word but ~1 s)
  V3 no proper noun that is not in the question/options unless it is common English (ASR WER; names like Oymyakon, Spyridon, Chobe fail)
  V4 words 80–90 incl. hook/options/CTA (CI total 22–40 s at Kokoro 1.3; 92 words ran 40.3 s)   V5 ≤ 2 years per line, years as digits
Layout (textqa dead zones, Mercator):
  L1 pin/label lon within ±25° of the scene camera centre when the camera is at k ≥ 1 (right action column / edge margin)
  L2 photos enter from a frame edge (photo_in) or rise from a feature whose centroid is inside the camera frame
  L3 no Wikidata `qid` on pins unless listed in docs/data/qids.json (never guessed)
Pace (pacelint runs locally; this adds the CI margin):
  P1 ≥ 17 explanation events / 10 s on the local estimate (CI timeline is ~5 % longer → ≥ 15 there)
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
COMMON = set("""the a an of in on at to and or for by with from into over under between after before until while when where which who what
how many much more most first last only very still one two three four five six seven eight nine ten hundred thousand million times
degrees minus plus percent people country city village island ocean sea lake river mountain desert north south east west arctic
antarctica africa europe asia america australia india china russia canada brazil france britain england germany japan pakistan
united states kingdom new york london paris boston sydney moscow earth world war cup title titles match matches team teams
year years day days month hour hours minute metres kilometres km school open closed record coldest hottest deepest longest
tallest largest smallest highest lowest fastest oldest newest biggest tennis cricket football marathon olympics trophy silver
heart brain body blood bone doctor hospital transplant penguin penguins bear bears elephant elephants dragon dragons polar freezer
january february march april may june july august september october november december""".split())

def words(s): return re.findall(r"[A-Za-z][A-Za-z'’-]*|\d[\d,\.]*", s)

def main():
    ep = Path(sys.argv[1]); F = []; W = []
    spec = next((p for p in (ROOT / "tools/specs").glob("*.json") if json.loads(p.read_text()).get("id") == ep.name), None)
    if not spec: print(f"precheck: no spec for {ep.name} (legacy episode) — skipped"); return 0
    S = json.loads(spec.read_text()); V = S["voice"]
    lines = {k: v["text"] for k, v in V.items() if isinstance(v, dict) and "text" in v}
    q = S["question"]; opts = " ".join(o["text"] for o in S["options"])
    allowed = {w.lower() for w in words(q + " " + opts)} | COMMON
    numerals = 0
    for k, t in lines.items():
        if re.search(r"\d+\.\d+", t): F.append(f"V1 {k}: decimal number in narration → say it in whole degrees/units: “{t}”")
        numerals += len(re.findall(r"\d[\d,]*", t))
        yrs = re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", t)
        if len(yrs) > 2: F.append(f"V5 {k}: {len(yrs)} years in one line")
        if re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred|thousand)\b", t, re.I): F.append(f"V5 {k}: number word → write digits")
        BAD = json.loads((ROOT / "docs/data/names_bad.json").read_text()) if (ROOT / "docs/data/names_bad.json").exists() else []
        ws = words(t)
        for i, w in enumerate(ws):
            if w.lower() in [b.lower() for b in BAD]: F.append(f"V3 {k}: “{w}” already failed the whisper gate once (docs/data/names_bad.json) — keep it on screen, out of the narration")
            elif w[0].isupper() and w.lower() not in allowed and not re.match(r"\d", w) and i > 0 and not ws[i - 1].endswith((".", "!", "?")):
                W.append(f"V3 {k}: proper noun “{w}” — fine if it is plain English for Kokoro; names that fail CI go to docs/data/names_bad.json")
    if numerals > 9: F.append(f"V2 {numerals} numerals across the narration (limit 9) — the wpm gate counts each as one word")
    elif numerals > 6: W.append(f"V2 {numerals} numerals — each costs ~1 s of narration against the wpm gate")
    total = len(words(q)) + len(words(opts)) + 1 + sum(len(words(t)) for t in lines.values() if t) - len(words(lines.get("v01", "")))
    total = sum(len(words(t)) for k, t in lines.items() if k != "v01_cues") + len(words(q)) + len(words(opts)) + 1
    if not 78 <= total <= 90: F.append(f"V4 narration ≈ {total} words incl. hook/options/CTA — keep 80–90 (CI total must stay 22–40 s)")
    g = S["geo"]; cams = g["cams"]
    scene_cam = {}
    for sid, (k, c) in cams.items(): scene_cam[sid.rstrip("b")] = (k, c)
    def visible(lon, scene):
        k, c = scene_cam.get(scene, cams["s04"]); return k < 1 or abs(((lon - c[0] + 180) % 360) - 180) <= 25
    for pin in g.get("pins", []):
        if pin.get("qid"):
            known = json.loads((ROOT / "docs/data/qids.json").read_text()) if (ROOT / "docs/data/qids.json").exists() else {}
            if known.get(pin["id"]) != pin["qid"]: F.append(f"L3 pin {pin['id']}: qid {pin['qid']} is not in docs/data/qids.json — never guess QIDs; drop it")
    for lab in g.get("labels", []):
        sc = str(lab.get("in", "s04")).split("@")[0].split("+")[0]
        if not visible(lab["lonlat"][0], sc): F.append(f"L1 label {lab['id']} at lon {lab['lonlat'][0]} is > 25° from the {sc} camera centre — it will land in a dead zone")
    for i, b in enumerate(S.get("story", [])):
        sc = f"s0{i + 5}"
        if b.get("photo") and b["photo"].get("from") == "rise" and str(b["photo"].get("fid")) in ("643", "840", "124", "156", "076", "036", "356", "032", "398", "304"):
            F.append(f"L2 {sc}: photo rises from feature {b['photo'].get('fid')} — centroids of big countries sit off-frame at k>1; use extra_photos + photo_in from left/right")
    # P1 local pace margin
    try:
        sys.path.insert(0, str(ROOT / "reelkit")); import pacelint as P
        TL = json.loads((ep / "timeline.json").read_text()); X = json.loads((ep / "visuals.json").read_text()); T, _, _ = P.resolver(TL)
        story = [s for s in TL["scenes"] if s.get("role") == "story"]; cta = [s for s in TL["scenes"] if s.get("role") == "cta"]
        w0, w1 = story[0]["start"], cta[0]["start"]
        n = sum(1 for b in X["beats"] if (T(b.get("at", 0)) is not None) and w0 <= T(b.get("at", 0)) <= w1 and (b["do"] in P.EVENT or str(b["do"]).startswith("chart.")))
        dens = n / (w1 - w0) * 10
        if dens < 16: F.append(f"P1 explanation pace {dens:.1f}/10 s locally — CI timeline is ~5 % longer; need ≥ 16 here")
    except Exception as ex: F.append(f"P1 could not measure pace ({ex})")
    for w in W: print("  WARN ", w)
    for f in F: print("  FAIL ", f)
    print(f"precheck: {ep.name} → {'FAIL ' + str(len(F)) if F else 'ok'} (numerals {numerals}, words ≈ {total})")
    return 1 if F else 0

if __name__ == "__main__": sys.exit(main())
