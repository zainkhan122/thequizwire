#!/usr/bin/env python3
"""storylint — format gate for Geo Stories (episode.json format "story-v1"; docs/STORY_GUIDELINES.md §8).
    python3 reelkit/storylint.py <ep> [--hf <hf_dir>] [--release] [--report out/storylint.json]
quizlint delegates here for story-v1. Checks (FAIL unless noted):
  S1 structure: series geo-stories · story block {place, headline, close, cover} · roles hook, story×2–5(+close), cta · headline has one *keyword*
  S2 narration: 110–155 words (WARN outside 120–150) · total ≤ 60 s · close shares a key noun with the open line
  S3 text: ≥ 1 text element (kw / counter / card) per story scene (close exempt) · ONE text element at a time (no overlap) · kw ≤ 5 words · ≤ 2 highlight layers lit per scene
  S4 cues: every geo.highlight_in / pin_in / label_in beat is anchored to a cue word or scene start (not a bare number)
  S5 cover: title + place only — no cover_emoji, no twist word (the close's keyword) on the cover headline
  S6 copy: spoilers (post.copy.spoilers) absent from every channel copy · each channel copy present
  S7 research: ≥ 2 sources per claim · every claim source id exists
  S8 motion: ≥ 8 motion beats / 10 s (same proxy as quizlint Q11)
  S9 release: --release refuses an ESTIMATED timeline
"""
import argparse, json, re, sys
from pathlib import Path

MOTION = {"geo.cam_to", "geo.highlight_in", "geo.highlight_pulse", "geo.pin_in", "geo.label_in", "geo.route_draw", "geo.travel", "geo.rise",
          "sticker_in", "sticker_pulse", "photo_in", "fact_in", "kw_in", "kw_pulse", "kw_out", "title_in", "title_out", "close_in", "cta_in"}
STOP = set("the a an of in on at to for with and or but it its is was has had have not no from by as this that these those one two more than every still so up here where who".split())
words = lambda s: re.findall(r"[A-Za-z0-9'’-]+", s or "")
nouns = lambda s: {w.lower().strip("'’-") for w in words(s) if w.lower() not in STOP and len(w) > 3}


def _t(T, expr):
    """Resolve a visuals.json time expression against timeline.json (same grammar as engine/compose.py T()); None if unresolvable."""
    try:
        if isinstance(expr, (int, float)): return float(expr)
        m = re.fullmatch(r"(end|s\w+?)(?:\.(end))?(?:@([\w-]+))?(?:([+-])([\d.]+))?", str(expr).strip())
        if not m: return None
        base, end, cue, sign, off = m.groups()
        if base == "end": t = T["total"]
        else:
            s = next(x for x in T["scenes"] if x["id"] == base)
            if cue: t = T["cues"][f"{base}@{cue}"]
            elif end or sign == "-": t = s["end"]
            else: t = s["start"]
        if sign and off: t += float(off) * (1 if sign == "+" else -1)
        return round(t, 3)
    except Exception: return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("--hf"); ap.add_argument("--release", action="store_true")
    ap.add_argument("--allow-inactive", action="store_true"); ap.add_argument("--report"); a = ap.parse_args()
    ep = Path(a.ep).resolve(); F, W = [], []
    E = json.loads((ep / "episode.json").read_text()); V = json.loads((ep / "voice.json").read_text())
    X = json.loads((ep / "visuals.json").read_text()) if (ep / "visuals.json").exists() else {"elements": [], "beats": []}
    R = json.loads((ep / "research.json").read_text()) if (ep / "research.json").exists() else {}
    T = json.loads((ep / "timeline.json").read_text()) if (ep / "timeline.json").exists() else None
    if E.get("format") != "story-v1": F.append("S1: format must be story-v1")
    if E.get("series") != "geo-stories": F.append("S1: series must be geo-stories")
    st = E.get("story") or {}
    for k in ("place", "headline", "close", "cover"):
        if not st.get(k): F.append(f"S1: story.{k} missing")
    if len(re.findall(r"\*[^*]+\*", st.get("headline", ""))) != 1: F.append("S1: story.headline needs exactly one *keyword*")
    lines = V.get("lines", []); roles = [l.get("role") for l in lines]
    seq = [r for i, r in enumerate(roles) if i == 0 or r != roles[i - 1]]
    if seq != ["hook", "story", "cta"]: F.append(f"S1: roles {seq} must read hook · story… · cta")
    n_story = roles.count("story")
    if not 3 <= n_story <= 6: F.append(f"S1: {n_story} story lines — need 2–5 beats + close (3–6)")
    # S2
    text = " ".join(l.get("text", "") for l in lines if l.get("role") != "cta"); n = len(words(text))
    if not 110 <= n <= 155: F.append(f"S2: {n} narration words (hard 110–155)")
    elif not 120 <= n <= 150: W.append(f"S2: {n} narration words (aim 120–150)")
    if T and T["total"] > 60.0: F.append(f"S2: total {T['total']:.1f} s > 60 s")
    openl = next((l for l in lines if l.get("role") == "hook"), {}); closel = [l for l in lines if l.get("role") == "story"][-1] if n_story else {}
    if openl and closel and not (nouns(openl.get("text")) & nouns(closel.get("text"))): F.append("S2: close line shares no key noun with the opening line")
    # S3
    scenes = {l["scene"]: l for l in lines}; story_scenes = [l["scene"] for l in lines if l.get("role") == "story"][:-1]
    # owner 2026-11-19 ("too much text on screen"): ONE text element at a time — a scene's text may be a kw caption, a counter or a fact card,
    # and no two of them may overlap in time.
    scene_of = lambda b: str(b.get("at", "")).split("+")[0].split("@")[0].split(".")[0].split("-")[0]
    TEXT_IN = {"kw_in", "fact_in", "chart.counter_run"}
    kw_scenes = {scene_of(b) for b in X.get("beats", []) if b.get("do") in TEXT_IN | {"geo.pin_in", "geo.label_in"}}   # a labelled pin is this scene's text
    for s in story_scenes:
        if s not in kw_scenes: F.append(f"S3: scene {s} has no text element (kw_in / fact_in / chart.counter_run / labelled pin)")
    if T and T.get("scenes"):
        tx = []
        for b in X.get("beats", []):
            if b.get("do") not in TEXT_IN: continue
            t0 = _t(T, b.get("at")); outs = {"kw_in": ("kw_out",), "fact_in": ("hide",), "chart.counter_run": ("chart.out", "hide")}[b["do"]]
            t1 = _t(T, b["until"]) if b.get("until") and b["do"] == "kw_in" else None
            if t1 is None:
                cands = [_t(T, o.get("at")) for o in X.get("beats", []) if o.get("do") in outs and o.get("id") == b.get("id")]
                cands = [c for c in cands if c is not None and t0 is not None and c > t0]; t1 = min(cands) if cands else None
            if t0 is not None and t1 is not None: tx.append((t0, t1, b.get("id")))
        tx.sort()
        for i in range(1, len(tx)):
            if tx[i][0] < tx[i - 1][1] - 0.05: F.append(f"S3: two text elements on screen at once — {tx[i - 1][2]} until {tx[i - 1][1]:.1f}s overlaps {tx[i][2]} from {tx[i][0]:.1f}s (one text at a time)")
    for el in X.get("elements", []):
        if el.get("type") == "kw" and len([w for w in el.get("text", "").split() if re.search(r"\w", w)]) > 5: F.append(f"S3: kw {el['id']} > 5 words")
    lit = {}
    for b in X.get("beats", []):
        if b.get("do") in ("geo.highlight_in", "geo.highlight_pulse"):
            sc = re.match(r"(s\d+|end)", str(b.get("at", ""))); lit.setdefault(sc.group(1) if sc else "?", set()).add((b.get("args") or {}).get("layer", "highlight"))
    for sc, layers in lit.items():
        if len(layers) > 2: F.append(f"S3: scene {sc} lights {len(layers)} highlight layers {sorted(layers)} (≤ 2 colours)")
    # S4
    for b in X.get("beats", []):
        if b.get("do") in ("geo.highlight_in", "geo.pin_in", "geo.label_in") and isinstance(b.get("at"), (int, float)): F.append(f"S4: {b['do']} at bare number {b['at']} — anchor to a cue word or scene")
    # S5
    post = E.get("post") or {}
    if post.get("cover_emoji"): F.append("S5: stories carry no cover emoji")
    cover = st.get("cover") or {}
    twist = {w.lower() for w in words(" ".join(re.findall(r"\*([^*]+)\*", st.get("close", ""))))} - STOP
    bad = (twist & {w.lower() for w in words(cover.get("headline", ""))}) - {w.lower() for w in words(st.get("headline", ""))}
    if bad: F.append(f"S5: cover headline carries the twist word {sorted(bad)}")
    # S6
    copy = post.get("copy") or {}; sp = [s.lower() for s in copy.get("spoilers", [])]
    for ch in ("youtube", "instagram", "facebook", "twitter", "threads"):
        c = copy.get(ch)
        if not c: F.append(f"S6: post.copy.{ch} missing"); continue
        blob = json.dumps(c).lower()
        for s_ in sp:
            if s_ and s_ in blob: F.append(f"S6: spoiler '{s_}' in {ch} copy")
    # S7
    srcs = R.get("sources") or {}
    for c in R.get("claims", []):
        ids = c.get("sources", [])
        if len(ids) < 2: F.append(f"S7: claim {c.get('id')} has {len(ids)} source(s); need ≥ 2")
        for i in ids:
            if i not in srcs: F.append(f"S7: claim {c.get('id')} cites unknown source '{i}'")
    # S8
    if T:
        beats = X.get("beats", []); nm = sum(1 for b in beats if b.get("do") in MOTION or str(b.get("do", "")).startswith(("fx.", "chart.")))
        dens = nm / max(T["total"], 1) * 10
        if dens < 8: F.append(f"S8: {nm} motion beats in {T['total']:.0f} s = {dens:.1f}/10 s (need ≥ 8)")
    # S9
    if a.release and (not T or T.get("estimated")): F.append("S9: release needs a real (non-estimated) timeline")
    for x in F: print("  FAIL ", x)
    for x in W: print("  WARN ", x)
    print(f"storylint: {len(F)} fail · {len(W)} warn · {n} words" + (f" · {T['total']:.1f} s" if T else ""))
    if a.report: Path(a.report).parent.mkdir(parents=True, exist_ok=True); Path(a.report).write_text(json.dumps({"fails": F, "warns": W, "words": n}, indent=1))
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
