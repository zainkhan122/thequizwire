#!/usr/bin/env python3
"""motionlint.py — owner rules 2026-11-20 for Geo Stories: (1) NO text over the map action, (2) no cuts / shaky camera.

  python3 reelkit/motionlint.py <episode-dir> [--step 0.25] [--json out.json]

Loads the built composition (~/.cache/build/<ep>/hf/index.html), seeks the GSAP timeline every `step` seconds and samples
  • camera k / x / y of every geo scene → reports CUTS (a jump between samples far larger than the neighbours) and JITTER
    (sign flips of the per-frame velocity while the camera is moving: the tell-tale of two tweens fighting or a hook lag)
  • the boxes of every visible text unit (.skw .sclose .fact3 .counter .stitle) against the map action: pins, labels,
    props (.prop3, stickers), and points sampled along every visible route / neon outline → OVERLAP rows
Exit 1 when anything fails. Runs headless Chromium through Playwright (LD_LIBRARY_PATH as local_render)."""
import argparse, json, os, pathlib, sys

JS_SAMPLE = r"""
(args) => {
  const t = args.t, tl = window.__timelines.main; tl.pause(); tl.seek(t, false);
  const st = document.querySelector('.stage3') || document.body, R = st.getBoundingClientRect(), sx = 1080 / R.width, sy = 1920 / R.height;
  const box = e => { const r = e.getBoundingClientRect(); return [(r.left - R.left) * sx, (r.top - R.top) * sy, (r.right - R.left) * sx, (r.bottom - R.top) * sy]; };
  const vis = e => { const c = getComputedStyle(e); if (c.visibility === 'hidden' || c.display === 'none' || parseFloat(c.opacity) < 0.05) return false;
                     for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const q = getComputedStyle(p); if (q.visibility === 'hidden' || q.display === 'none' || parseFloat(q.opacity) < 0.05) return false; } return true; };
  const texts = [];
  document.querySelectorAll('.skw, .sclose, .fact3, .chart.counter, .stitle').forEach(e => { if (vis(e)) { const b = box(e); if (b[2] - b[0] > 4 && b[3] - b[1] > 4) texts.push({id: e.id, box: b}); } });
  const action = [];   // {id, kind, box} boxes or {id, kind, pts:[[x,y]..]} for strokes
  document.querySelectorAll('.geo-pin, .geo-label, .prop3, .sticker3, .photo3').forEach(e => { if (!vis(e)) return; const b = box(e); if (b[2] - b[0] > 2 && b[3] - b[1] > 2) action.push({id: e.id || e.className, kind: 'box', box: b}); });
  document.querySelectorAll('.geo path.g-route, .geo g.g-route, .geo path.g-highlight, .geo g.g-highlight, .geo path.g-area.highlight, .geo g.g-area.highlight, .geo .g-feature.draw, .geo g.g-feature').forEach(e => {
    if (!vis(e)) return; let p = e.tagName === 'g' ? e.querySelector('path:last-child') : e; if (!p || !p.getTotalLength) return;
    const L = p.getTotalLength(); if (!L) return; const M = p.getScreenCTM(); const pts = [];
    const da = getComputedStyle(p).strokeDasharray, off = parseFloat(getComputedStyle(p).strokeDashoffset) || 0;  // route_draw: only the drawn part exists
    let drawn = 1; if (da && da !== 'none' && /^1000(px)?[, ]/.test(da)) drawn = Math.max(0, Math.min(1, 1 - off / 1000));
    const N = 160; for (let i = 0; i <= N * drawn; i++) { const q = p.getPointAtLength(L * i / N).matrixTransform(M); const x = (q.x - R.left) * sx, y = (q.y - R.top) * sy; if (x >= 0 && y >= 0 && x <= 1080 && y <= 1920) pts.push([Math.round(x), Math.round(y)]); }
    if (pts.length) action.push({id: e.id, kind: 'stroke', pts});
  });
  const cams = {}; for (const id in GeoRT.scenes) { const c = GeoRT.scenes[id].cam; cams[id] = [c.k, c.x, c.y]; }
  return {t, cams, texts, action};
}
"""


def overlaps(texts, action, pad=6):
    hits = []
    for T in texts:
        x0, y0, x1, y1 = T["box"]; x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
        for A in action:
            if A["kind"] == "box":
                a = A["box"]
                if a[0] < x1 and a[2] > x0 and a[1] < y1 and a[3] > y0: hits.append((T["id"], A["id"]))
            else:
                n = sum(1 for x, y in A["pts"] if x0 <= x <= x1 and y0 <= y <= y1)
                if n >= 2: hits.append((T["id"], A["id"]))
    return hits


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("--step", type=float, default=0.125); ap.add_argument("--json")
    ap.add_argument("--cut", type=float, default=0.18, help="k-relative or px/frame jump that counts as a cut (fraction of the viewport per step)")
    a = ap.parse_args()
    ep = pathlib.Path(a.episode); name = ep.name
    html = pathlib.Path(os.environ.get("BUILD", pathlib.Path.home() / ".cache/build" / name)) / "hf/index.html"
    if not html.exists(): sys.exit(f"motionlint: no build at {html} — run episode.sh <ep> build first")
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=0.25)
        pg.goto(html.as_uri(), wait_until="load"); pg.wait_for_function("() => !!(window.__timelines && window.__timelines.main)")
        try: total = float(json.loads((ep / "timeline.json").read_text())["total"])
        except Exception: total = min(pg.evaluate("() => window.__timelines.main.duration()"), 120)
        t = 0.0
        while t <= total + 1e-6:
            rows.append(pg.evaluate(JS_SAMPLE, {"t": t})); t += a.step
        br.close()
    fails = 0
    # ---- overlaps
    seen = {}
    for r in rows:
        for tid, aid in overlaps(r["texts"], r["action"]):
            seen.setdefault((tid, aid), []).append(r["t"])
    if seen:
        print("OVERLAP (text over map action):")
        for (tid, aid), ts in sorted(seen.items(), key=lambda kv: kv[1][0]):
            lvl = "WARN" if tid == "title" else "FAIL"                           # the title sits over the plunge; the subject outline may pass under it
            print(f"  {lvl}  {tid:>8} × {aid:<28} {ts[0]:6.2f}–{ts[-1]:6.2f}s  ({len(ts)} samples)"); fails += lvl == "FAIL"
    # ---- camera cuts / jitter
    for sid in rows[0]["cams"]:
        ks = [r["cams"][sid] for r in rows]
        def d(i):                                                                 # motion between sample i-1 and i: (log-zoom, pan px on screen)
            k0, x0, y0 = ks[i - 1]; k1, x1, y1 = ks[i]
            import math; return abs(math.log(max(k1, 1e-6) / max(k0, 1e-6))), ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 * k1
        for i in range(2, len(ks) - 1):
            zk, zp = d(i); pk, pp = d(i - 1); nk, np_ = d(i + 1)
            # a cut = this step moves far more than BOTH neighbours (an eased tween ramps; a jump does not) and is big in absolute terms
            if (zk > 0.25 and zk > 3 * max(pk, nk) + 0.05) or (zp > 220 and zp > 3 * max(pp, np_) + 40):
                print(f"  FAIL  CUT   {sid} at {rows[i]['t']:.2f}s  k {ks[i-1][0]:.2f}→{ks[i][0]:.2f}  pan {zp:.0f}px  (neighbours {max(pk,nk):.2f}/{max(pp,np_):.0f}px)"); fails += 1
        # whip pans / zooms (owner: "movement is shaky", "animation is cutting"): calibrated on the approved st08 (peaks 3.05 /s zoom, 1.55 vh/s pan)
        import math
        whips = []
        for i in range(1, len(ks)):
            dt = rows[i]["t"] - rows[i - 1]["t"]; k0, x0, y0 = ks[i - 1]; k1, x1, y1 = ks[i]
            zr = abs(math.log(max(k1, 1e-6) / max(k0, 1e-6))) / dt; pr = math.hypot(x1 - x0, y1 - y0) * k1 / 1920 / dt
            if zr > 3.3 or pr > 1.7: whips.append((rows[i]["t"], zr, pr))
        if whips:
            grp = []; 
            for w in whips:
                if grp and w[0] - grp[-1][-1][0] <= 0.5: grp[-1].append(w)
                else: grp.append([w])
            for g in grp:
                print(f"  FAIL  WHIP  {sid} {g[0][0]:.2f}–{g[-1][0]:.2f}s  zoom {max(w[1] for w in g):.1f}/s  pan {max(w[2] for w in g):.2f} vh/s  (limits 3.3 · 1.7)"); fails += 1
        # jitter: velocity sign flips of k or x/y across 3 consecutive steps while moving
        flips = []
        for i in range(2, len(ks)):
            for j, nm in ((0, "k"), (1, "x"), (2, "y")):
                v1 = ks[i - 1][j] - ks[i - 2][j]; v2 = ks[i][j] - ks[i - 1][j]
                scale = ks[i][0] if j else 1
                if abs(v1) * (scale if j else 1 / max(ks[i][0], 1e-6)) > (1.5 if j else 0.004) and abs(v2) * (scale if j else 1 / max(ks[i][0], 1e-6)) > (1.5 if j else 0.004) and (v1 > 0) != (v2 > 0):
                    flips.append((rows[i]["t"], nm))
        # a deliberate reversal (zoom in then out) is a single flip; shaky = several flips within 1.5 s
        shaky = [f for n, f in enumerate(flips) if any(abs(g[0] - f[0]) <= 1.5 and g is not f for g in flips)]
        if shaky:
            ts = sorted({round(f[0], 2) for f in shaky}); print(f"  FAIL  SHAKY {sid}: velocity reversals at {ts[:12]}{' …' if len(ts) > 12 else ''}"); fails += 1
    if a.json: pathlib.Path(a.json).write_text(json.dumps(rows))
    print(f"motionlint: {name} · {len(rows)} samples @ {a.step}s → {'FAIL ' + str(fails) if fails else 'OK'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
