#!/usr/bin/env python3
"""reelkit/quizscore.py — shared score for quiz episodes: VO placement + procedural ticks/sting + light bed → mix.wav.

    python3 reelkit/quizscore.py <ep> [vo_dir] [out_dir]        (defaults: ~/.cache/build/<ep> for both)

Reads timeline.json (scene windows, roles) and the trimmed VO takes (<vo_dir>/<line>.wav from reelkit/trim_vo.py, or
<ep>/vo/<line>.wav). Everything else is synthesised with reelkit/synth.py (seeded, royalty-free, you own it):
  · bed      a soft two-chord pad in the series' key (series.json `key`, default D minor), ducked under VO (follower)
  · ticks    one tick per countdown second (hi/lo alternating) + a soft riser under the ring
  · reveal   a short bell + hit on the reveal scene start
  · cta      the pad resolves on the CTA scene
Final loudness via reelkit/master.py (two-pass loudnorm −14 LUFS, TP −2 dBTP) → <out>/mix.wav + mix_report.json.
An ESTIMATED timeline (no takes yet) produces a VO-less bed so the composition can still be previewed; qa refuses it.
"""
import json, sys
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth as S  # noqa: E402
from synth import note as N, place, SR  # noqa: E402
import master  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _beat_time(expr, TL):
    """Resolve a visuals.json time expression the way engine/compose.T does (s02+0.3 · s03@cue-0.1 · s04.end · end-0.3)."""
    import re
    if isinstance(expr, (int, float)): return float(expr)
    m = re.fullmatch(r"(end|s\w+?)(?:\.(end))?(?:@([\w-]+))?(?:([+-])([\d.]+))?", str(expr).strip())
    if not m: return None
    base, end, cue, sign, off = m.groups()
    SC = {s["id"]: s for s in TL["scenes"]}
    if base == "end": t = TL["total"]
    elif base not in SC: return None
    elif cue:
        t = TL.get("cues", {}).get(f"{base}@{cue}")
        if t is None: return None
    elif end or sign == "-": t = SC[base]["end"]
    else: t = SC[base]["start"]
    if sign and off: t += float(off) * (1 if sign == "+" else -1)
    return round(t, 3)


def story_sfx(sfx, ep, TL, root):
    """Auto-SFX for story-v1 from the visuals beats (docs/STORY_GUIDELINES.md §5 cue map). Quiet, procedural, deterministic:
    cam_to with a real move → whoosh · highlight_in/pulse → soft pop · pin/label → click · route_draw → swish · counter → riser · title/close → hit."""
    vp = ep / "visuals.json"
    if not vp.exists(): return
    X = json.loads(vp.read_text()); last_k, last_pop = None, -9.0
    for b in sorted(X.get("beats", []), key=lambda b: _beat_time(b.get("at", 0), TL) or 0):
        t = _beat_time(b.get("at", 0), TL)
        if t is None or t < 0: continue
        do, args = b.get("do", ""), b.get("args", {})
        if do in ("geo.cam_set",): last_k = args.get("k"); continue
        if do == "geo.cam_to":
            k = args.get("k"); big = last_k is None or k is None or abs(k - last_k) >= 0.25 * max(last_k or 1, 0.1)
            if big and args.get("ease", "power2.inOut") != "none": place(sfx, S.whoosh(d=0.7, level=0.10, up=(k or 1) >= (last_k or 1)), t - 0.05)
            last_k = k
        elif do in ("geo.highlight_in", "geo.highlight_pulse"):
            if t - last_pop > 0.35: place(sfx, S.tick(hi=False, level=0.10), t); last_pop = t
        elif do in ("geo.pin_in", "geo.label_in", "sticker_in", "fact_in", "kw_in"):
            place(sfx, S.tick(hi=True, level=0.07), t)
        elif do == "geo.route_draw":
            t1 = _beat_time(b.get("until", 0), TL) or (t + 1.0)
            place(sfx, S.whoosh(d=min(1.6, max(0.4, t1 - t)), level=0.08, up=True), t)
        elif do == "chart.counter_run":
            t1 = _beat_time(b.get("until", 0), TL) or (t + 1.5)
            place(sfx, S.riser(d=min(2.4, max(0.8, t1 - t)), level=0.09), t)
        elif do in ("title_in", "close_in"):
            place(sfx, S.hit(level=0.16), t + 0.02)
            if do == "close_in": place(sfx, S.bell(root * 4, d=2.0, level=0.09), t + 0.05)


def main():
    ep = Path(sys.argv[1]).resolve()
    vo_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / ".cache/build" / ep.name
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.home() / ".cache/build" / ep.name
    out.mkdir(parents=True, exist_ok=True)
    TL = json.loads((ep / "timeline.json").read_text()); E = json.loads((ep / "episode.json").read_text())
    reg = json.loads((REPO / "series" / "series.json").read_text())
    series = next((s for s in reg["series"] if s["slug"] == E["series"]), {})
    key = series.get("key", "D3")
    S.seed(int(E.get("seed", 2026)))
    total = TL["total"]; n = int((total + 0.5) * SR)
    vo, music, sfx = (np.zeros((n, 2), np.float32) for _ in range(3))
    scenes = TL["scenes"]

    # ---- VO
    missing = []
    for s in scenes:
        if not s.get("vo"): continue
        p = next((q for q in (vo_dir / f"{s['vo']}.wav", ep / "vo" / f"{s['vo']}.wav", ep / "vo" / f"{s['vo']}.mp3") if q.exists()), None)
        if not p:
            if s.get("role") != "countdown": missing.append(s["vo"])
            continue
        x, sr = sf.read(p, dtype="float32")
        if x.ndim > 1: x = x.mean(1)
        if sr != SR:
            idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr)); x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
        place(vo, x, s["start"], gain=1.0)

    # ---- bed: root + fifth pad, re-triggered per section so it breathes; resolves on the CTA
    root = N(key); fifth = root * 1.5; third_min = root * 2 ** (3 / 12); third_maj = root * 2 ** (4 / 12)
    story = E.get("format") == "story-v1"
    if story:                                                                 # Geo Stories: low drone under the pad (docs/STORY_GUIDELINES.md §5 "bed:drone")
        place(music, S.drone(root / 2, total + 0.5, cutoff=320, level=0.10), 0.0)
    for s in scenes:
        d = max(0.8, s["end"] - s["start"] + 1.2)
        chord = [root, fifth, third_maj * 2] if s.get("role") == "cta" else [root, fifth, third_min * 2]
        lvl = {"hook": 0.14, "options": 0.12, "countdown": 0.10, "reveal": 0.16, "story": 0.13, "cta": 0.15}.get(s.get("role"), 0.12)
        place(music, S.pad(chord, d, cutoff=1200 if s.get("role") != "reveal" else 1800, a=0.8, r=1.4, level=lvl), s["start"] - 0.15)
    # ---- countdown ticks + riser, reveal sting
    for s in scenes:
        if s.get("role") == "countdown":
            secs = int(round(s["end"] - s["start"]))
            for i in range(secs): place(sfx, S.tick(hi=(i % 2 == 0), level=0.16), s["start"] + i)
            place(sfx, S.riser(d=min(2.6, max(1.0, secs - 0.4)), level=0.14), s["start"] + 0.2)
        if s.get("role") == "reveal":
            place(sfx, S.bell(root * 4, d=2.2, level=0.14), s["start"])
            place(sfx, S.hit(level=0.28), s["start"] + 0.02)
        if s.get("role") == "cta":
            place(sfx, S.whoosh(d=0.6, level=0.16, up=True), s["start"] - 0.2)
    if story: story_sfx(sfx, ep, TL, root)
    # ---- duck music/sfx under speech
    env = S.follower(vo.mean(1))
    duck_m = 1.0 - 0.72 * np.clip(env / (np.max(env) + 1e-6), 0, 1)
    duck_s = 1.0 - 0.35 * np.clip(env / (np.max(env) + 1e-6), 0, 1)
    music *= duck_m[:, None]; sfx *= duck_s[:, None]
    mix = vo + music + sfx
    import shutil
    if shutil.which("ffmpeg"):
        rep = master.finish(mix, out, vo=vo, music=music, sfx=sfx)
    else:   # sandbox without ffmpeg: peak-normalised preview mix (NOT −14 LUFS mastered; qa refuses it in CI anyway)
        peak = float(np.max(np.abs(mix)) or 1.0); mix = (mix / peak * 0.89).astype(np.float32)
        sf.write(out / "mix.wav", mix, SR, subtype="PCM_16")
        rep = {"mastered": False, "note": "no ffmpeg: peak-normalised preview mix", "peak_dbfs": -1.0, "warnings": ["unmastered preview"]}
    rep["missing_vo"] = missing; rep["estimated_timeline"] = bool(TL.get("estimated"))
    mp = ep / "media.json"; man = json.loads(mp.read_text()) if mp.exists() else {"files": {}}
    man.setdefault("generated", {})["mix.wav"] = {"kind": "mix", "licence": "own", "by": "reelkit/quizscore.py (procedural bed/ticks/sting) + Kokoro VO takes",
                                                  "derived_from": "procedural reelkit/synth.py + Kokoro takes vo/*", "provider": "build", "ai_voice": "Kokoro am_michael"}
    mp.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    (out / "mix_report.json").write_text(json.dumps(rep, indent=1))
    print(f"quizscore: mix.wav {total}s · VO takes missing: {missing or 'none'}" + ("  [ESTIMATED timeline — preview only]" if TL.get("estimated") else ""))


if __name__ == "__main__":
    main()
