#!/usr/bin/env python3
"""Geo Stories cover, style "story2" (owner 2026-11-20: "colourful, professional"): a clean, text-free key frame from the
master shown full-bleed and saturated, a deep colour gradient (series colour → night) only where the headline sits, a
yellow accent slash, the hook headline with the keyword in yellow, series chip + logo bug. No blur, no ghost text.

  python3 reelkit/cover_story2.py <ep> --video <master.mp4> --t <sec> [--anchor 0.5,0.4] [--out PNG] [--jpg JPG]

The background time is authored per episode (post.cover.key_t) and must be a moment with NO kinetic text on screen
(reelkit/motionlint.py --json lists text-free samples); the headline band covers y ≥ 1180 so lower-third captions under
it are not an issue, but numbers/counters in the upper half would leak through — pick the frame, then look at it.
"""
import argparse, json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cover as CV                                       # fonts, chip, logo, text fitting, fit/crop helpers

W, H = CV.W, CV.H


def frame(video, t):
    try: import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError: ff = "ffmpeg"
    out = CV.CACHE / f"s2_{Path(video).stem}_{t:.2f}.png"
    if not out.exists():
        subprocess.run([ff, "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


def gradient_band(im, color, y0=1060, y1=1500, top_alpha=0, mid_alpha=255):
    """Series-colour night gradient: transparent at y0, deep (colour mixed 25 % with near-black) by y1."""
    base = tuple(int(c * 0.25 + 10 * 0.75) for c in color)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); px = layer.load()
    for y in range(y0, H):
        f = (y - y0) / max(1, (y1 - y0)); f = min(1.0, f) ** 0.7
        a = int(top_alpha + (mid_alpha - top_alpha) * f)
        for x in range(W): px[x, y] = base + (a,)
    im.alpha_composite(layer)


def slash(im, color, y=1120, h=26, tilt=-3):
    """Yellow accent bar with a tilted series-colour shadow bar behind it — the one 'designed' element."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    d.polygon([(60, y + tilt * 2), (W - 60, y - tilt * 2), (W - 60, y - tilt * 2 + h), (60, y + tilt * 2 + h)], fill=color + (230,))
    d.polygon([(60, y - 18), (W - 60, y - 18 + tilt * 4), (W - 60, y - 18 + tilt * 4 + h), (60, y - 18 + h)], fill=CV.YELLOW + (255,))
    im.alpha_composite(layer)


def build(ep, video, t, anchor=(0.5, 0.42), scale=1.08, sat=1.35):
    E = json.loads((Path(ep) / "episode.json").read_text())
    reg = json.loads((CV.ROOT / "series/series.json").read_text())["series"]
    S = next(s for s in reg if s["slug"] == E["series"]); color = CV.hex_rgb(S["color"])
    st = E.get("story") or {}; cv = st.get("cover") or {}
    head = cv.get("headline") or st.get("headline") or E.get("title", "")
    kw = " ".join(__import__("re").findall(r"\*([^*]+)\*", head)); text = head.replace("*", "")

    bg = frame(video, t)
    bg = ImageEnhance.Color(bg).enhance(sat); bg = ImageEnhance.Contrast(bg).enhance(1.08)
    im = CV.cover_fit(bg, scale, anchor=anchor).convert("RGBA")
    CV.darken(im, 0, 260, 120, 0)                                             # a little weight under the chip
    gradient_band(im, color)
    slash(im, color)
    CV.series_chip(im, (60, 96), S, E["number"], color)
    f, lines = CV.fit_question(text, kw, 156, 960, 3, min_size=104)
    bottom = CV.draw_question(im, lines, f, 1200, CV.WHITE + (255,), CV.YELLOW + (255,), 10, (10, 10, 14, 255), align="left", left=60, max_w=960, line_h=0.96)
    CV.logo_bug(im, (60, min(bottom + 56, 1780)), 84, align="left")
    return im.convert("RGB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("--video", required=True); ap.add_argument("--t", type=float, required=True)
    ap.add_argument("--anchor", default="0.5,0.42"); ap.add_argument("--scale", type=float, default=1.08); ap.add_argument("--out"); ap.add_argument("--jpg")
    a = ap.parse_args(); ax, ay = (float(v) for v in a.anchor.split(","))
    im = build(a.episode, a.video, a.t, (ax, ay), a.scale)
    out = Path(a.out or (Path(a.episode) / "out" / "cover_story2.png")); out.parent.mkdir(parents=True, exist_ok=True); im.save(out)
    if a.jpg:
        q = 92
        while True:
            im.save(a.jpg, quality=q, optimize=True)
            if Path(a.jpg).stat().st_size < 1_900_000 or q <= 60: break
            q -= 6
    print(f"cover_story2: {out}" + (f" · {a.jpg}" if a.jpg else ""))
