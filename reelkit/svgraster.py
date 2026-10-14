#!/usr/bin/env python3
"""reelkit/svgraster.py — rasterise the SVG subset our map previews emit (M/L/Z paths, rect, circle, text) with PIL.

    python3 reelkit/svgraster.py in.svg out.png [--scale 1]

Why: the sandbox has no Chromium and ImageMagick's internal SVG renderer silently drops large clipped paths. This is a
preview aid for authors and tests (geometry, camera, palette) — the real frames come from HyperFrames/Chromium in CI.
Limits: polygon holes are filled (lakes look like land), no curves, no CSS classes (inline style only).
"""
import argparse, re, sys
from PIL import Image, ImageDraw, ImageFont

COL = re.compile(r"rgba?\(([^)]+)\)|#([0-9a-fA-F]{6})")


def color(s, default=None):
    if not s or s == "none": return default
    m = COL.search(s)
    if not m: return default
    if m.group(2): return tuple(int(m.group(2)[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    parts = [float(x) for x in m.group(1).split(",")]
    a = int(round(parts[3] * 255)) if len(parts) > 3 else 255
    return (int(parts[0]), int(parts[1]), int(parts[2]), a)


def style(st):
    d = {}
    for kv in st.split(";"):
        if ":" in kv: k, v = kv.split(":", 1); d[k.strip()] = v.strip()
    return d


def subpaths(d):
    out, cur = [], []
    for cmd, args in re.findall(r"([MLZmlz])([^MLZmlz]*)", d):
        nums = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", args)]
        if cmd in "Mm":
            if cur: out.append(cur)
            cur = [(nums[0], nums[1])]
            for i in range(2, len(nums) - 1, 2): cur.append((nums[i], nums[i + 1]))
        elif cmd in "Ll":
            for i in range(0, len(nums) - 1, 2): cur.append((nums[i], nums[i + 1]))
        elif cmd in "Zz":
            if cur: out.append(cur + [cur[0]]); cur = []
    if cur: out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("svg"); ap.add_argument("png"); ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args(); s = open(a.svg).read(); S = a.scale
    W = int(float(re.search(r'<svg[^>]*\swidth="([\d.]+)"', s).group(1)) * S); H = int(float(re.search(r'<svg[^>]*\sheight="([\d.]+)"', s).group(1)) * S)
    img = Image.new("RGBA", (W, H), (15, 42, 58, 255)); draw = ImageDraw.Draw(img, "RGBA")
    # one group transform (camera matrix) is supported
    m = re.search(r'<g transform="matrix\(([^)]+)\)">', s)
    k, _, _, _, tx, ty = [float(x) for x in m.group(1).split()] if m else (1, 0, 0, 1, 0, 0)
    gstart, gend = (m.end(), s.index("</g>", m.end())) if m else (0, 0)

    def T(p, inside): x, y = p; return ((x * k + tx) * S, (y * k + ty) * S) if inside else (x * S, y * S)
    for el in re.finditer(r"<(path|rect|circle|text)\b([^>]*)(?:/>|>(.*?)</\1>)", s, re.S):
        tag, attrs, inner = el.group(1), el.group(2), el.group(3) or ""; inside = gstart <= el.start() < gend
        A = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs)); st = style(A.get("style", ""))
        fill = color(st.get("fill", A.get("fill")), None if tag == "path" and "fill" in st else color(A.get("fill"), (0, 0, 0, 255)))
        if tag == "path" and "fill" not in st and "fill" not in A: fill = (0, 0, 0, 255)
        stroke = color(st.get("stroke", A.get("stroke"))); sw = float(st.get("stroke-width", A.get("stroke-width", 1)))
        sw = max(1, int(round(sw * S)))   # vector-effect: non-scaling-stroke semantics
        if tag == "path":
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer, "RGBA")
            for sp in subpaths(A.get("d", "")):
                pts = [T(p, inside) for p in sp]
                if fill and len(pts) >= 3: ld.polygon(pts, fill=fill)
                if stroke and len(pts) >= 2:
                    if "stroke-dasharray" in st:
                        on = True; acc = 0.0; seg = [pts[0]]; dash = [float(x) for x in re.findall(r"[\d.]+", st["stroke-dasharray"])][:2] or [10, 8]
                        for p, q in zip(pts, pts[1:]):
                            L = ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5; t = 0.0
                            while L - t > 1e-6:
                                need = (dash[0] if on else dash[1]) - acc; step = min(need, L - t)
                                r0, r1 = p, (p[0] + (q[0] - p[0]) * (t + step) / L, p[1] + (q[1] - p[1]) * (t + step) / L)
                                if on: ld.line([(p[0] + (q[0] - p[0]) * t / L, p[1] + (q[1] - p[1]) * t / L), r1], fill=stroke, width=sw)
                                t += step; acc += step
                                if acc >= (dash[0] if on else dash[1]) - 1e-9: on = not on; acc = 0.0
                    else: ld.line(pts, fill=stroke, width=sw)
            img.alpha_composite(layer)
        elif tag == "rect":
            x, y, w, h = [float(A.get(kk, 0)) for kk in ("x", "y", "width", "height")]
            p0, p1 = T((x, y), inside), T((x + w, y + h), inside)
            draw.rectangle([p0, p1], fill=fill)
        elif tag == "circle":
            cx, cy, r = [float(A.get(kk, 0)) for kk in ("cx", "cy", "r")]; c = T((cx, cy), inside); r *= S
            draw.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=fill, outline=stroke, width=sw if stroke else 0)
        elif tag == "text":
            x, y = float(A.get("x", 0)) * S, float(A.get("y", 0)) * S; size = int(float(A.get("font-size", 24)) * S)
            txt = re.sub(r"<[^>]+>", "", inner).replace("&amp;", "&").replace("&lt;", "<")
            try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans" + ("-Bold" if A.get("font-weight") == "bold" else "") + ".ttf", size)
            except OSError: font = ImageFont.load_default()
            col = color(A.get("fill"), (239, 230, 210, 255)); op = float(A.get("opacity", 1)); col = col[:3] + (int(col[3] * op),)
            anchor = {"middle": "ms", "end": "rs"}.get(A.get("text-anchor"), "ls")
            draw.text((x, y), txt, fill=col, font=font, anchor=anchor)
    img.convert("RGB").save(a.png); print("wrote", a.png, f"{W}x{H}")


if __name__ == "__main__":
    main()
