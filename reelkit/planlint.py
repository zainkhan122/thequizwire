#!/usr/bin/env python3
"""Plan linter: catches slideshow drift, silent fallbacks, broken promises and a samey series look.

  python3 reelkit/planlint.py <ep> [--hf <hf_dir>] [--report out/planlint.json] [--today YYYY-MM-DD]

Inputs: <ep>/shots.json (shot plan), timeline.json, clips.json, media.json, episode.json (promise),
        decisions.jsonl (approved exceptions), sibling episodes' shots.json (cross-episode), <hf>/index.html.

FAIL
  shots      every timeline scene has exactly one shot with subject, shot_size, motion, a concrete
             information_role and reason (≥ 6 words each), and its primary source exists in media.json
  repetition adjacent shots with the same subject AND shot size; one primary visual used in two scenes
  truth      a shot claiming motion "clip"/"film" whose file isn't in media.json; a clip declared in
             clips.json for a scene that is shown as a still (= silent fallback) without an approved
             clip_fallback decision
  promise    weighted motion share below episode.json promise.min_motion without an approved, unexpired
             promise_exception (motion weights: clip/film 1, graphic/parallax 0.5, kenburns/still/text 0)
  text       text-only scenes > 35 % of runtime
  prompts    generic words in generator prompts (stunning, cinematic, modern, "a person", …)
             + clips.py lint: pending Wan clips need the 5-slot `shot` template (200–400 words, ≥ 2 motion steps,
             one camera move, no on-screen-text words, prompt == compose(shot)); AI clips must pin a seed
  holds      a still visual static for > 1.75× its tone's limit (urgent 2.5 s … tender/reverent 7 s; voice.json),
             measured from the build (no tween starts on non-caption elements)
  series     same format 3 episodes running; a fingerprint ≥ 70 % identical to one of the last 3 episodes;
             the same hook_type as both previous episodes
  risk       slideshow_risk ≥ 4.0 (6 dimensions 0–5: repetition, decorative, weak motion, weak intent,
             typography, static holds)
WARN: > 4 transition types, the same transition 3× running, 3 equal shot sizes running, holds over the tone limit,
      slideshow_risk ≥ 3, same hook/opening/music as the previous episode, live exceptions (listed each run).
"""
import argparse, datetime, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decide

SIZES = ["EWS", "WS", "MS", "MCU", "CU", "ECU", "INSERT", "GRAPHIC"]
MOTION_W = {"clip": 1.0, "film": 1.0, "maptile": 1.0, "globe": 1.0, "map": 0.75, "graphic": 0.5, "chart": 0.5, "parallax": 0.5, "kenburns": 0.0, "still": 0.0, "text": 0.0}
GENERIC = ["stunning", "breathtaking", "cinematic", "modern", "futuristic", "cutting-edge", "cutting edge", "dynamic",
           "vibrant", "seamless", "revolutionary", "epic", "beautiful", "amazing", "a person", "high quality", "4k", "8k",
           "masterpiece", "ultra realistic", "hyperrealistic"]
# longest acceptable static visual per tone of the scene's narration (voice.json); FAIL above 1.75× (abs. max 10 s)
TONE_HOLD = {"urgent": 2.5, "tense": 4.0, "neutral": 4.5, "resolute": 4.5, "revelatory": 5.0, "suspense": 6.0,
             "somber": 6.0, "tender": 7.0, "reverent": 7.0}
HOLD_WARN = 4.5
NOISE = re.compile(r"^#(grain|tear|bug|cap\d+|c\d+_\d+|fx_leak.*)$|^\.cap")   # captions/grain/transitions aren't visual beats


def words(s):
    return len(re.findall(r"[A-Za-z0-9']+", s or ""))


def events(index_html: Path):
    """Start times of visual tweens (captions, grain and transitions excluded)."""
    t = []
    for m in re.finditer(r"tl\.(?:to|from|fromTo|set)\('([^']+)'.*?,\s*(-?[0-9.]+)\)\s*;", index_html.read_text()):
        sel, pos = m.group(1), float(m.group(2))
        first = sel.split(",")[0].strip()
        if NOISE.match(first):
            continue
        t.append(pos)
    return sorted(set(round(x, 2) for x in t))


def fingerprint_sim(a, b, keys):
    same = [k for k in keys if a.get(k) and str(a.get(k)).strip().lower() == str(b.get(k, "")).strip().lower()]
    return len(same) / len(keys), same


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ep"); ap.add_argument("--hf"); ap.add_argument("--report"); ap.add_argument("--today")
    a = ap.parse_args()
    ep = Path(a.ep).resolve()
    today = a.today or datetime.date.today().isoformat()
    F, W, info = [], [], []
    sp = ep / "shots.json"
    if not sp.exists():
        sys.exit(f"planlint: {sp} missing — every episode needs a shot plan")
    P = json.loads(sp.read_text())
    T = json.loads((ep / "timeline.json").read_text())
    M = json.loads((ep / "media.json").read_text())["files"] if (ep / "media.json").exists() else {}
    C = json.loads((ep / "clips.json").read_text())["clips"] if (ep / "clips.json").exists() else []
    E = json.loads((ep / "episode.json").read_text())
    total = T["total"]
    scenes = {s["id"]: s for s in T["scenes"]}
    shots = P["shots"]

    # ---------- shot completeness ----------
    ids = [s["scene"] for s in shots]
    for sid in scenes:
        if ids.count(sid) != 1:
            F.append(f"shots: scene {sid} has {ids.count(sid)} shot entries (need 1)")
    for s in shots:
        sid = s["scene"]
        if sid not in scenes:
            F.append(f"shots: {sid} not in timeline"); continue
        s["_dur"] = scenes[sid]["end"] - scenes[sid]["start"]
        for k in ("subject", "shot_size", "motion", "primary", "information_role", "reason", "transition_in"):
            if not s.get(k):
                F.append(f"{sid}: missing {k}")
        if s.get("shot_size") not in SIZES:
            F.append(f"{sid}: shot_size '{s.get('shot_size')}' not in {SIZES}")
        if s.get("motion") not in MOTION_W:
            F.append(f"{sid}: motion '{s.get('motion')}' not in {list(MOTION_W)}")
        for k in ("information_role", "reason"):
            if s.get(k) and words(s[k]) < 6:
                F.append(f"{sid}: {k} too vague (< 6 words): '{s[k]}'")
        for src in [s.get("primary")] + s.get("secondary", []) + [i["source"] for i in s.get("inserts", [])]:
            if src and not str(src).startswith("build:") and src not in M:     # build:<id> = procedural graphic drawn by build.py
                F.append(f"{sid}: source {src} not in media.json")

    # ---------- truth: motion claims vs files; silent fallbacks ----------
    for s in shots:
        sid = s["scene"]
        if s.get("motion") in ("clip", "film") and not str(s.get("primary", "")).startswith("clips/"):
            F.append(f"{sid}: claims motion '{s['motion']}' but primary is a still ({s.get('primary')})")
        for i in s.get("inserts", []):
            if i.get("motion") in ("clip", "film") and i["source"] not in M:
                F.append(f"{sid}: insert {i['source']} missing")
        for c in C:
            if c.get("scene") != sid or c.get("engine") == "url":
                continue
            have = f"clips/{c['id']}.mp4" in M
            if not have and s.get("motion") not in ("clip",):
                ok, why = decide.approval(ep, "clip_fallback", c["id"], today)
                (W if ok else F).append(f"{sid}: clip {c['id']} declared but missing → shown as {s.get('motion')} "
                                        f"({'exception ' + why if ok else 'SILENT FALLBACK: ' + why})")
            if have and s.get("motion") != "clip" and s.get("primary") != f"clips/{c['id']}.mp4":
                W.append(f"{sid}: clip {c['id']} exists but the shot plan doesn't use it")

    # ---------- repetition ----------
    for x, y in zip(shots, shots[1:]):
        if x.get("subject", "").lower() == y.get("subject", "").lower() and x.get("shot_size") == y.get("shot_size"):
            F.append(f"{x['scene']}→{y['scene']}: same subject and shot size ({x['shot_size']} {x['subject']})")
    prim = [s.get("primary") for s in shots]
    for p in {p for p in prim if prim.count(p) > 1}:
        F.append(f"primary visual {p} used in {prim.count(p)} scenes")
    run_sz = run_tr = 1; rep = 0
    for x, y in zip(shots, shots[1:]):
        run_sz = run_sz + 1 if x["shot_size"] == y["shot_size"] else 1
        run_tr = run_tr + 1 if x["transition_in"] == y["transition_in"] else 1
        if run_sz == 3:
            W.append(f"shot size {y['shot_size']} three times running (…{y['scene']})"); rep += 1
        if run_tr == 3:
            W.append(f"transition '{y['transition_in']}' three times running (…{y['scene']})"); rep += 1
    trans = sorted({s["transition_in"] for s in shots[1:]})
    if len(trans) > 4:
        W.append(f"{len(trans)} transition types {trans} (house style: ≤ 4)")

    # ---------- motion share + promise ----------
    weighted, text_t, rows = 0.0, 0.0, []
    for s in shots:
        if "_dur" not in s:
            continue
        ins = sum(i["seconds"] for i in s.get("inserts", []))
        w = MOTION_W.get(s.get("motion"), 0) * (s["_dur"] - ins) + sum(MOTION_W.get(i["motion"], 0) * i["seconds"] for i in s.get("inserts", []))
        weighted += w
        if s.get("motion") == "text":
            text_t += s["_dur"]
        rows.append({"scene": s["scene"], "dur": round(s["_dur"], 2), "motion": s.get("motion"), "motion_s": round(w, 2)})
    ratio = round(weighted / total, 3)
    pr = E.get("promise") or {}
    if not pr:
        F.append("episode.json has no delivery promise (promise: {type, min_motion, locked})")
    elif ratio < pr.get("min_motion", 0):
        ok, why = decide.approval(ep, "promise_exception", "min_motion", today)
        d = decide.latest(ep, "promise_exception", "min_motion")
        if ok and d and ratio + 1e-9 < float(d.get("value", 1)):
            ok, why = False, f"exception accepts ≥ {d.get('value')} but measured {ratio}"
        (W if ok else F).append(f"promise '{pr.get('type')}': motion share {ratio:.0%} < {pr['min_motion']:.0%} "
                                f"({'exception ' + why if ok else why})")
    if text_t / total > 0.35:
        F.append(f"text-only scenes {text_t / total:.0%} of runtime (> 35 %)")

    # ---------- generator prompts ----------
    for c in C:
        p = (c.get("prompt") or "").lower()
        bad = [g for g in GENERIC if re.search(r"(?<![a-z])" + re.escape(g) + r"(?![a-z])", p)]
        if bad:
            F.append(f"clips.json {c['id']}: generic prompt words {bad} — describe what is in frame instead")
    # Wan 5-slot template, seeds, overlay words, single camera move (rules live in clips.py so gen and lint agree)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import clips as _clips
    for lv, m in _clips.lint_episode(ep):
        if lv == "FAIL": F.append(f"clips.json {m}")
        elif lv == "WARN": W.append(f"clips.json {m}")

    # ---------- static holds from the build ----------
    holds = {}
    tones = {}
    if (ep / "voice.json").exists():
        tones = {l["scene"]: l["tone"] for l in json.loads((ep / "voice.json").read_text())["lines"]}
    hf = Path(a.hf) if a.hf else Path.home() / ".cache/build" / ep.name / "hf"
    if (hf / "index.html").exists():
        ev = events(hf / "index.html")
        for s in shots:
            sc = scenes.get(s["scene"])
            if not sc:
                continue
            pts = [sc["start"]] + [t for t in ev if sc["start"] < t < sc["end"]] + [sc["end"]]
            gaps = [(round(b - a_, 2), round(a_, 2)) for a_, b in zip(pts, pts[1:])]
            g, at = max(gaps)
            holds[s["scene"]] = {"max_static": g, "at": at, "events": len(pts) - 2}
            moving = s.get("motion") in ("clip", "film")
            tone = tones.get(s["scene"], "neutral")
            lim = TONE_HOLD.get(tone, HOLD_WARN); hard = min(10.0, lim * 1.75)
            holds[s["scene"]].update(tone=tone, limit=lim)
            if g > hard and not moving:
                F.append(f"{s['scene']}: static for {g}s from {at}s (> {hard:.1f}s for {tone}) — add a visual beat")
            elif g > lim and not moving:
                W.append(f"{s['scene']}: static for {g}s from {at}s (> {lim}s for {tone})")
    else:
        W.append(f"{hf}/index.html not built — static holds not measured")

    # ---------- slideshow risk ----------
    dims = {
        "repetition": min(5.0, rep + 2 * sum(1 for p in set(prim) if prim.count(p) > 1)),
        "decorative": 5.0 * sum(1 for s in shots if words(s.get("information_role")) < 6) / len(shots),
        "weak_motion": round(5.0 * (1 - ratio), 2),
        "weak_intent": 5.0 * sum(1 for s in shots if words(s.get("reason")) < 6) / len(shots),
        "typography": round(5.0 * min(1.0, (text_t / total) / 0.35), 2),
        "static": round(5.0 * sum(1 for h in holds.values() if h["max_static"] > h.get("limit", HOLD_WARN)) / max(1, len(holds)), 2),
    }
    risk = round(sum(dims.values()) / len(dims), 2)
    band = "strong" if risk < 2 else "ok" if risk < 3 else "revise" if risk < 4 else "fail"
    if risk >= 4:
        F.append(f"slideshow_risk {risk} ({band})")
    elif risk >= 3:
        W.append(f"slideshow_risk {risk} ({band})")

    # ---------- cross-episode (series template drift) ----------
    fp = P.get("fingerprint", {})
    keys = ["format", "hook_type", "opening_shot", "music", "climax_device", "structure"]
    for k in keys:
        if not fp.get(k):
            F.append(f"fingerprint.{k} missing (needed for cross-episode checks)")
    prev = []
    for sib in sorted(ep.parent.iterdir()):
        if sib == ep or not (sib / "shots.json").exists() or not (sib / "episode.json").exists():
            continue
        n = json.loads((sib / "episode.json").read_text()).get("episode", 0)
        if n < E.get("episode", 0):
            prev.append((n, sib.name, json.loads((sib / "shots.json").read_text()).get("fingerprint", {})))
    prev.sort()
    series = []
    for n, name, f2 in prev[-3:]:
        sim, same = fingerprint_sim(fp, f2, keys)
        series.append({"episode": name, "similarity": round(sim, 2), "same": same})
        if sim >= 0.7:
            F.append(f"template look: {sim:.0%} of the fingerprint equals {name} ({same})")
    if prev:
        last = prev[-1][2]
        for k in ("hook_type", "opening_shot", "music"):
            if fp.get(k) and str(fp[k]).lower() == str(last.get(k, "")).lower():
                W.append(f"same {k} as {prev[-1][1]}: '{fp[k]}'")
    if len(prev) >= 2 and all(str(fp.get("hook_type", "")).lower() == str(f2.get("hook_type", "")).lower() for _, _, f2 in prev[-2:]):
        F.append(f"hook_type '{fp.get('hook_type')}' used 3 episodes running")
    if len(prev) >= 2 and all(str(fp.get("format", "")).lower() == str(f2.get("format", "")).lower() for _, _, f2 in prev[-2:]):
        F.append(f"format '{fp.get('format')}' 3 episodes running — rotate (docs/CONTENT_STRATEGY.md)")

    # ---------- report ----------
    rep_ = {"motion_ratio": ratio, "promise": pr, "slideshow_risk": risk, "risk_band": band, "dims": dims,
            "scenes": rows, "holds": holds, "series": series, "fails": F, "warns": W}
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(rep_, ensure_ascii=False, indent=1))
    print(f"{'scene':<6}{'dur':>6}  {'motion':<9}{'max static':>11}")
    for r in rows:
        h = holds.get(r["scene"], {})
        print(f"{r['scene']:<6}{r['dur']:>6}  {r['motion']:<9}{(str(h.get('max_static', '—')) + 's'):>11}")
    for x in F:
        print("  FAIL ", x)
    for x in W:
        print("  WARN ", x)
    print(f"planlint: motion {ratio:.0%} (promise {pr.get('min_motion', 0):.0%}) · slideshow_risk {risk} {band} · "
          f"{len(series)} earlier episode(s) compared · FAIL {len(F)} · WARN {len(W)}")
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
