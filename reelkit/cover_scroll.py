#!/usr/bin/env python3
"""Scroll-stopper covers — PRODUCTION RULE (owner 2026-11-20): every short ships with a custom-made cover: one bespoke hero
illustration per episode + giant punchy headline, tilted badge, starburst/✕ shapes and Twemoji stickers. The cover is burned in
as frame 0 of the master (dispatch.sh) and set as the YouTube thumbnail (yt_enrich). Both read <ep>/cover/:

  <ep>/cover/spec.json   authored with the episode (author_story.py writes the stub; the agent fills hero_prompt + layout)
  <ep>/cover/hero.png    the hero art generated from spec.hero_prompt (9:16, NO text in the art — type is set here)
  <ep>/cover/cover.jpg   the rendered, owner-approved cover (spec.approved = "<date> owner") — what gets burned/uploaded

cover.py (the publish path) refuses to template a cover when these are missing: `cover.py --burn` exits 1 → dispatch.sh
"NOT posting". postkit.py check fails the episode at authoring time for the same reason. Spec fields:

  {"bg": "path.png", "head": "WIDER THAN *THE MOON*?!", "badge": "AUSTRALIA  vs  MOON", "badge_color": "#FF2D2D",
   "stickers": [["1f92f", 300, [700, 1180], -12]], "burst": {"text": "3,474 KM", "xy": [860, 420], "r": 150},
   "marks": [{"x": [155, 1090], "size": 150}], "head_size": 176, "anchor": [0.5, 0.35]}

  python3 reelkit/cover_scroll.py <ep> [spec.json] --out PNG [--jpg JPG]     # spec defaults to <ep>/cover/spec.json
  python3 reelkit/cover_scroll.py <ep> --check                               # gate: spec + hero + approved → exit 0
"""
import argparse, json, math, re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cover as CV

W, H = CV.W, CV.H
hex_rgb = CV.hex_rgb


def layer(): return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def badge(im, text, xy, color, tilt=-4, size=58, fg=(16, 16, 20)):
    """Tilted solid tag with hard black shadow — the 'sticker label' look."""
    f = CV.anton(size); tw = int(f.getlength(text)); w, h = tw + 72, size + 40
    tag = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0)); d = ImageDraw.Draw(tag)
    d.rounded_rectangle((12, 18, 12 + w, 18 + h), 14, fill=(0, 0, 0, 255))
    d.rounded_rectangle((0, 0, w, h), 14, fill=color + (255,))
    d.text((36, 18), text, font=f, fill=fg + (255,))
    tag = tag.rotate(tilt, resample=Image.BICUBIC, expand=True)
    im.alpha_composite(tag, xy); return tag.size


def starburst(im, text, center, r=150, color=CV.YELLOW, fg=(16, 16, 20), points=16, tilt=-10, size=None):
    cx, cy = center; pts = []
    for i in range(points * 2):
        a = math.pi * i / points + math.radians(tilt); rr = r if i % 2 == 0 else r * 0.78
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    L = layer(); d = ImageDraw.Draw(L)
    d.polygon([(x + 8, y + 12) for x, y in pts], fill=(0, 0, 0, 255)); d.polygon(pts, fill=color + (255,))
    lines = text.split("\n"); size = size or int(r * (0.52 if len(lines) == 1 else 0.40)); f = CV.lilita(size)
    th = len(lines) * size * 1.02; y = cy - th / 2
    for ln in lines:
        tw = f.getlength(ln); d.text((cx - tw / 2, y), ln, font=f, fill=fg + (255,)); y += size * 1.02
    im.alpha_composite(L.rotate(tilt, resample=Image.BICUBIC, center=(cx, cy)))


def red_x(im, xy, size=150, color=(255, 45, 45)):
    x, y = xy; L = layer(); d = ImageDraw.Draw(L); s = size // 2; wdt = max(18, size // 7)
    for dx, dy, col in ((6, 8, (0, 0, 0, 255)), (0, 0, color + (255,))):
        d.line((x - s + dx, y - s + dy, x + s + dx, y + s + dy), fill=col, width=wdt)
        d.line((x - s + dx, y + s + dy, x + s + dx, y - s + dy), fill=col, width=wdt)
    im.alpha_composite(L)


def headline(im, head, top, size, max_w=960, left=60):
    kw = " ".join(re.findall(r"\*([^*]+)\*", head)); text = head.replace("*", "")
    f, lines = CV.fit_question(text, kw, size, max_w, 4, min_size=110)
    # black slab glow behind the type for legibility on busy art
    glow = layer(); CV.draw_question(glow, lines, f, top, (0, 0, 0, 255), (0, 0, 0, 255), 26, (0, 0, 0, 255), align="left", left=left, max_w=max_w, line_h=0.94, shadow=False)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    return CV.draw_question(im, lines, f, top, CV.WHITE + (255,), CV.YELLOW + (255,), 12, (8, 8, 12, 255), align="left", left=left, max_w=max_w, line_h=0.94)


def spec_path(ep): return Path(ep) / "cover" / "spec.json"


def fetch(url):
    """GET a hosted cover asset. api.github.com release assets (private repo) need GH_TOKEN/GITHUB_TOKEN + octet-stream."""
    import os, urllib.request
    hdr = {"User-Agent": "TheQuizWire-reelkit/1"}
    if "api.github.com" in url:
        tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or (lambda p: p.read_text().strip() if p.exists() else "")(Path.home() / ".cache/secrets/gh_token")
        hdr.update({"Authorization": f"Bearer {tok}", "Accept": "application/octet-stream"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=120) as r: return r.read()


def hero_path(ep, spec):
    """Local <ep>/cover/<bg> if present, else the hosted copy (spec.hero_url, uploaded by `mediahost.py cover <ep>`) cached under
    ~/.cache/cover. The repo carries no media (repo_guard: no images > 1 MB) — the public media repo hosts hero + approved cover."""
    ep = Path(ep); bg = spec.get("bg") or "hero.jpg"
    loc = Path(bg) if Path(bg).is_absolute() else ep / "cover" / bg
    if loc.exists(): return loc
    url = spec.get("hero_url")
    if url:
        import hashlib
        c = CV.CACHE / f"hero_{hashlib.sha1(url.encode()).hexdigest()[:12]}.img"
        if not c.exists(): c.write_bytes(fetch(url))
        return c
    return None


def approved_cover_bytes(ep):
    """Bytes of the approved cover JPG: local <ep>/cover/cover.jpg, else spec.cover_url (hosted). None if neither."""
    ep = Path(ep); loc = ep / "cover" / "cover.jpg"
    if loc.exists(): return loc.read_bytes()
    sp = spec_path(ep)
    if sp.exists():
        url = json.loads(sp.read_text()).get("cover_url")
        if url: return fetch(url)
    return None


def check(ep, need_approval=True):
    """Return a list of problems (empty = the episode has a production cover)."""
    ep = Path(ep); sp = spec_path(ep); bad = []
    if not sp.exists(): return [f"{ep.name}: cover/spec.json missing — author the cover spec (hero_prompt + head/badge/stickers)"]
    try: spec = json.loads(sp.read_text())
    except Exception as e: return [f"{ep.name}: cover/spec.json unreadable ({e})"]
    for k in ("head", "bg"):
        if not spec.get(k): bad.append(f"{ep.name}: cover/spec.json has no '{k}'")
    if spec.get("bg") and not (ep / "cover" / spec["bg"]).exists() and not spec.get("hero_url"): bad.append(f"{ep.name}: cover/{spec['bg']} missing — generate the hero art from spec.hero_prompt (then `mediahost.py cover <ep>` to host it)")
    if spec.get("status") == "draft": bad.append(f"{ep.name}: cover spec is still a draft stub")
    if need_approval and not spec.get("approved"): bad.append(f"{ep.name}: cover not approved — render, show the owner the contact sheet, then set spec.approved")
    if need_approval and not (ep / "cover" / "cover.jpg").exists() and not spec.get("cover_url"): bad.append(f"{ep.name}: cover/cover.jpg missing — render the approved cover (cover_scroll.py <ep> --jpg <ep>/cover/cover.jpg) and host it (mediahost.py cover <ep>)")
    return bad


def build(ep, spec):
    spec = dict(spec); hp = hero_path(ep, spec)
    if not hp: sys.exit(f"cover_scroll: {Path(ep).name}: no hero art (cover/{spec.get('bg')} or spec.hero_url)")
    spec["bg"] = str(hp)
    E = json.loads((Path(ep) / "episode.json").read_text())
    reg = json.loads((CV.ROOT / "series/series.json").read_text())["series"]
    S = next(s for s in reg if s["slug"] == E["series"]); color = hex_rgb(S["color"])
    bg = Image.open(spec["bg"]).convert("RGB")
    bg = ImageEnhance.Color(bg).enhance(spec.get("sat", 1.15)); bg = ImageEnhance.Contrast(bg).enhance(1.06)
    im = CV.cover_fit(bg, spec.get("scale", 1.0), anchor=tuple(spec.get("anchor", [0.5, 0.4]))).convert("RGBA")
    CV.darken(im, 0, 240, 110, 0)
    y0 = spec.get("fade_from", 1040); CV.darken(im, y0, H, 0, 235)                       # headline bed
    CV.series_chip(im, (60, 96), S, E["number"], color)
    for m in spec.get("marks", []): red_x(im, m["x"], m.get("size", 150))
    if spec.get("burst"): b = spec["burst"]; starburst(im, b["text"], b["xy"], b.get("r", 150), hex_rgb(b.get("color", "#FFD400")), tilt=b.get("tilt", -10))
    if spec.get("badge"): badge(im, spec["badge"], tuple(spec.get("badge_xy", [60, spec.get("head_top", 1180) - 120])), hex_rgb(spec.get("badge_color", "#FF2D2D")), spec.get("badge_tilt", -4))
    bottom = headline(im, spec["head"], spec.get("head_top", 1180), spec.get("head_size", 170))
    for cp, size, xy, rot in spec.get("stickers", []): im.alpha_composite(CV.sticker(cp, size, rotate=rot), tuple(xy))
    CV.logo_bug(im, (60, min(bottom + 44, 1800)), 84, align="left")
    return im.convert("RGB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("spec", nargs="?"); ap.add_argument("--out"); ap.add_argument("--jpg")
    ap.add_argument("--check", action="store_true", help="gate only: spec + hero art + approval present")
    a = ap.parse_args()
    if a.check:
        bad = check(a.episode)
        for b in bad: print("cover_scroll: FAIL", b)
        sys.exit(1 if bad else print(f"cover_scroll: OK {Path(a.episode).name} has an approved production cover"))
    sp = Path(a.spec) if a.spec else spec_path(a.episode)
    if not sp.exists(): sys.exit(f"cover_scroll: {sp} missing")
    a.out = a.out or str(Path(a.episode) / "cover" / "cover.png")
    im = build(a.episode, json.loads(sp.read_text()))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); im.save(a.out)
    if a.jpg:
        q = 92
        while True:
            im.save(a.jpg, quality=q, optimize=True)
            if Path(a.jpg).stat().st_size < 1_900_000 or q <= 60: break
            q -= 6
    print("cover_scroll:", a.out)
