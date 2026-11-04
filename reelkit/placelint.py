#!/usr/bin/env python3
"""placelint — the CI layout gates, approximated offline from the v4 spec (seconds, not a 6-minute cloud run).

  python3 reelkit/placelint.py tools/specs/<ep>.json            # FAIL list → exit 1
  python3 reelkit/placelint.py <episode dir>                     # finds tools/specs/<ep>.json

Why: 2026-10-30 → 11-02 every daily render needed one or more re-runs for gates that only exist in CI (textqa dead zones,
hyperframes caption-zone / occlusion, post-render motion). The sandbox has no browser, so this re-implements the geometry:

  L1  map tag labels and pin labels, projected with the same Mercator fit (padding 20 in the 1080×1920 stage, anchor 540,900,
      screen = anchor + (p − cam) · k) for every camera they are visible under, against textqa's dead zones
      (top < 210 · bottom > 1600 · right action column x > 960 for y ≥ 640 · edge x < 40 / > 1040) and the caption band (y ≥ 1190).
  L2  story elements (bars / compare / counter / split) vs the stickers that are on screen in the same beat (occlusion), vs the
      caption band and the right column; counters that would still be fading in while the previous chart fades out.
  L3  camera drift per story beat (QA "static stage": < 40 % of frame-time moving) — WARN when a beat's hold barely moves.
  V1  ordinals 1st–9th in VO: the ASR gate often hears them as words ("fifth") and then misses the numeral — write "November 5".

Label box estimate (measured from CI boxes 2026-11-01): tag width ≈ 32 + 16 × chars, height 56, centred on the anchor;
pin label ≈ 32 + 16 × chars × 0.95, 62 high, to the right (or left with side:left) of the pin head.
Exit 1 on FAIL; WARNs print only. Wired into tools/precheck.py and reelkit/episode.sh preflight.
"""
import json, math, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H, PAD, ANCHOR = 1080, 1920, 20, (540, 900)
# each rule returns how many px the box intrudes (0 = clear); ≤ 35 px is a WARN (box estimates are ±30 px — ep14 London passed CI at ~30)
DEAD = [("top bar", lambda b: 210 - b[1]), ("bottom UI", lambda b: b[3] - 1600),
        ("right action column", lambda b: b[2] - 960 if b[3] > 640 else 0), ("edge margin", lambda b: max(40 - b[0], b[2] - 1040)),
        ("caption band", lambda b: b[3] - 1190)]
MARGIN = 35
SCENES = ["s04", "s05", "s06", "s07"]
def offscreen(b): return b[2] < 0 or b[0] > W or b[3] < 0 or b[1] > H   # textqa only sees what is inside the frame


# ---------------------------------------------------------------- projection (d3.geoMercator().fitExtent on the fit bbox)
def merc(lon, lat):
    lat = max(-85.05, min(85.05, lat))
    return math.radians(lon), -math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def fitter(bbox):
    w0, s0, e0, n0 = bbox
    xs, ys = zip(merc(w0, s0), merc(e0, n0))
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    k = min((W - 2 * PAD) / bw, (H - 2 * PAD) / bh)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    def proj(lon, lat):
        x, y = merc(lon, lat); return W / 2 + (x - cx) * k, H / 2 + (y - cy) * k
    return proj


def screen(proj, cam, lonlat):
    k, (clon, clat) = cam; cx, cy = proj(clon, clat); px, py = proj(*lonlat)
    return ANCHOR[0] + (px - cx) * k, ANCHOR[1] + (py - cy) * k


def tag_box(x, y, text):
    w = 32 + 16 * len(text); return [x - w / 2, y - 28, x + w / 2, y + 28]


def pin_box(x, y, text, side):
    w = 32 + 15 * len(text)
    return [x - 20 - w, y - 30, x - 20, y + 32] if side == "left" else [x + 20, y - 30, x + 20 + w, y + 32]


def scene_index(ref):
    m = re.match(r"s0(\d)", str(ref or "")); return int(m.group(1)) if m else None


def cams_between(cams, s_in, s_out):
    """Camera states a thing is visible under: scenes s_in … s_out−1 (both the move target and the hold)."""
    out = []
    for i in range(s_in, s_out):
        for key in (f"s0{i}", f"s0{i}b"):
            if key in cams: out.append((key, cams[key]))
    return out


# ---------------------------------------------------------------- checks
def check(S):
    F, Wn = [], []
    g = S["geo"]; cams = g["cams"]; proj = fitter(g["fit_bbox"])
    # L1 tags
    for lab in g.get("labels", []):
        s_in = scene_index(lab.get("in")) or 4; s_out = scene_index(lab.get("out")) or 8
        if str(lab.get("out", "")).endswith(".end"): s_out = s_out + 1
        for key, cam in cams_between(cams, s_in, s_out):
            x, y = screen(proj, cam, lab["lonlat"]); b = tag_box(x, y, lab["text"])
            if offscreen(b): continue
            for name, test in DEAD:
                d = test(b)
                if d > 0: (F if d > MARGIN else Wn).append(f"L1 tag {lab['id']!r} '{lab['text']}' at cam {key} → box {[round(v) for v in b]} {d:.0f} px into dead zone '{name}' — move lonlat / shorten / change cam")
    # L1 pins: in at their beat, out at pin_out or the end
    pin_in, pin_out = {}, {}
    for pb in g.get("pin_beats", []):
        (pin_out if pb.get("out") else pin_in).setdefault(pb["pid"], scene_index(pb["at"]))
    for i, st in enumerate(S.get("story", [])):
        for d in st.get("devices", []):
            if d.get("do") == "geo.pin_in": pin_in.setdefault(d["args"]["pid"], 5 + i)
            if d.get("do") == "geo.pin_out": pin_out.setdefault(d["args"]["pid"], 5 + i + (1 if ".end" in str(d.get("at")) else 0))   # out at beat start → not under this scene's cam
    for p in g.get("pins", []):
        if p["id"] not in pin_in: continue
        for key, cam in cams_between(cams, pin_in[p["id"]], pin_out.get(p["id"], 8)):
            x, y = screen(proj, cam, p["lonlat"]); b = pin_box(x, y, p.get("label", ""), p.get("side"))
            if offscreen(b): continue
            for name, test in DEAD:
                d = test(b)
                if d > 0: (F if d > MARGIN else Wn).append(f"L1 pin {p['id']!r} '{p.get('label')}' at cam {key} → label box {[round(v) for v in b]} {d:.0f} px into dead zone '{name}' — side:left/right, pin_out earlier, or change cam")
    # L2 chart boxes (bars / compare / split; counters are rendered allow-overlap) vs stickers on in the same beat and the caption band.
    # CI tolerance measured: ep21 st_shrug overlapping a bars box by 31 % of its area passed, ep23 st_jp with its centre inside a split failed.
    stick = {e["id"]: e for e in S.get("extra_elements", []) if e.get("type") == "sticker"}
    for i, st in enumerate(S.get("story", [])):
        sc = f"s0{5 + i}"; on = {d["id"] for d in st.get("devices", []) if d.get("do") == "sticker_in" and d.get("id") in stick}
        for el in st.get("elements", []) or []:
            t = el.get("type"); x, y = el.get("x", 60), el.get("y", 300)
            if t == "bars": w, h = el.get("w", 900), len(el.get("rows", [])) * (el.get("bar_h", 74) + el.get("gap", 26) + 40) - el.get("gap", 26)
            elif t == "compare": w, h = el.get("w", 960), el.get("max_h", 700) + 120   # compare text is allow-overlap (charts.py) — CI accepted stickers on it (ep14, ep17)
            elif t == "split": w, h = el.get("w", 620), el.get("h", 540)
            else: continue
            b = [x, y, x + w, y + h]; on_here = on if t != "compare" else set()
            if b[3] > 1190: F.append(f"L2 {sc} {t} {el['id']!r} bottom {round(b[3])} enters the caption band (>= 1190) — raise y or shrink")
            for sid in on_here:
                s_ = stick[sid]; half = s_.get("size", 160) / 2; sb = [s_["x"] - half, s_["y"] - half, s_["x"] + half, s_["y"] + half]
                ox = max(0, min(sb[2], b[2]) - max(sb[0], b[0])); oy = max(0, min(sb[3], b[3]) - max(sb[1], b[1]))
                share = ox * oy / ((2 * half) ** 2); inside = b[0] <= s_["x"] <= b[2] and b[1] <= s_["y"] <= b[3]
                if inside or share > 0.4:
                    F.append(f"L2 {sc} sticker {sid!r} ({s_['x']},{s_['y']} x{s_.get('size')}) sits on {t} {el['id']!r} box {[round(v) for v in b]} ({share:.0%} covered) — move it to the right column (x ~ 820-860) or below the chart")
                elif share > 0.15: Wn.append(f"L2 {sc} sticker {sid!r} overlaps {t} {el['id']!r} by {share:.0%} — passed CI before at ~31 %, but closer is a risk")
    # L3 camera drift
    for i, st in enumerate(S.get("story", [])):
        cam, hold = st.get("cam"), st.get("cam_hold")
        if not (cam and hold): continue
        k0, k1 = cam[0], hold[0]; x0, y0 = screen(proj, cam, cam[1]); x1, y1 = screen(proj, cam, hold[1])
        px = math.hypot(x1 - x0, y1 - y0) * 1.0; ratio = max(k1, k0) / max(1e-9, min(k1, k0))
        if px < 40 and ratio < 1.04: Wn.append(f"L3 s0{5 + i} hold barely moves ({px:.0f} px, ×{ratio:.3f}) — QA wants ≥ 40 % of frame-time moving; drift ≥ 40 px or k ≥ ×1.04, or add pulses")
    # V2 pause_after must sit inside the tone's range (reelkit/voice.py TONES) — CI voice gate FAILs otherwise (ep18, 11-03)
    try:
        sys.path.insert(0, str(ROOT / "reelkit")); from voice import TONES
        for i, st in enumerate(S.get("story", [])):
            t = st.get("tone"); pa = st.get("pause_after")
            if t in TONES and pa is not None:
                lo, hi = TONES[t]["after"]
                if not (lo <= pa <= hi): F.append(f"V2 s0{5 + i}: pause_after {pa}s outside {t} range {lo}–{hi}")
    except Exception as ex: Wn.append(f"V2 skipped ({ex})")
    # V1 ordinals
    for key, v in S.get("voice", {}).items():
        txt = v.get("text") if isinstance(v, dict) else None
        if not txt: continue
        for m in re.finditer(r"\b([1-9])(st|nd|rd|th)\b", txt):
            F.append(f"V1 {key}: '{m.group(0)}' — single-digit ordinals come back from the ASR as words (no numeral) → write '<Month> {m.group(1)}' or 'day {m.group(1)}'")
    return F, Wn


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    p = Path(a[0])
    if p.is_dir(): p = ROOT / "tools/specs" / (p.name + ".json")
    if not p.exists(): print(f"placelint: no spec at {p} (pre-v4 episode) — skipped"); return
    S = json.loads(p.read_text()); F, Wn = check(S)
    for w in Wn: print(f"  WARN  {w}")
    for f in F: print(f"  FAIL  {f}")
    print(f"placelint: {p.name} → {'FAIL ' + str(len(F)) if F else 'OK'} · WARN {len(Wn)}")
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
