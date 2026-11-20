#!/usr/bin/env python3
"""Scroll-stopper covers (owner 2026-11-20): one bespoke hero illustration per short + giant punchy headline, tilted badge,
starburst/underline shapes and Twemoji stickers. Spec is a JSON per episode (see review/v2/covers3/specs.json):

  {"bg": "path.png", "head": "WIDER THAN *THE MOON*?!", "badge": "AUSTRALIA  vs  MOON", "badge_color": "#FF2D2D",
   "stickers": [["1f92f", 300, [700, 1180], -12]], "burst": {"text": "3,474 KM", "xy": [860, 420], "r": 150},
   "marks": [{"x": [155, 1090], "size": 150}], "head_size": 176, "anchor": [0.5, 0.35]}

  python3 reelkit/cover_scroll.py <ep> <spec.json> --out PNG [--jpg JPG]
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


def build(ep, spec):
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
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("spec"); ap.add_argument("--out", required=True); ap.add_argument("--jpg")
    a = ap.parse_args(); im = build(a.episode, json.loads(Path(a.spec).read_text()))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); im.save(a.out)
    if a.jpg:
        q = 92
        while True:
            im.save(a.jpg, quality=q, optimize=True)
            if Path(a.jpg).stat().st_size < 1_900_000 or q <= 60: break
            q -= 6
    print("cover_scroll:", a.out)
