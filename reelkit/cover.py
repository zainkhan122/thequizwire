#!/usr/bin/env python3
"""Cover image (thumbnail) for an episode — 1080×1920 PNG built from the episode's own frame 0 + brand system.

  python3 reelkit/cover.py <ep> [--style a|b|c] [--frame PNG] [--video MP4] [--out PNG] [--jpg JPG] [--burn MP4]

Variety (so covers are not one template): the card headline is the episode's own HOOK line for story/fact/misconception/
challenge hooks (else the question); sticker side, card tint (ink/navy/series), background crop and blur rotate per
episode seed. Authors can pin any of these in episode.json → post.cover {headline: hook|question, sticker_side, tint,
bg_anchor, blur, highlight:[words], headline_text: 'written hook (digits, dashes)'}.

Why: Instagram/Facebook/X/Threads show frame 0 of a reel as its cover; YouTube picks a frame unless a thumbnail is set.
The approved cover is (1) burned in as the first frames of the master (so every network's auto-cover IS the design) and
(2) uploaded to YouTube as the custom thumbnail by yt_enrich.py (thumbnails.set, once the YT_* secrets exist).

Inputs: episode.json (quiz.question/keyword/options/option_meta, series, number), visuals.json (first sticker emoji),
series/series.json (series name + colour), brand/logo.png, fonts/LilitaOne-Regular.ttf + Anton-Regular.ttf,
background = --frame PNG or frame 0 of --video / <ep>/out/final.mp4 (ffmpeg), else the brand dark.
Stickers: Twemoji SVG (CC-BY 4.0, credited in provenance) · flags: flag-icons (MIT).

Styles (all share fonts, yellow #FFD400, series chip, logo bug):
  a  BIG QUESTION  — satellite frame, question at 150 px with the keyword in yellow, giant "?" + topical sticker, "guess in 3 seconds" pill
  b  QUIZ CARD     — blurred frame behind a dark glass card: question + the three option pills (no answer marked)  ← APPROVED default
  c  TORN SPLIT    — satellite top, torn-paper edge into a yellow panel with the question in black, sticker on the tear, "tap to guess" pill
"""
import argparse, hashlib, json, math, os, random, subprocess, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1920
YELLOW, GREEN, RED, DARK, WHITE = (255, 212, 0), (19, 122, 54), (255, 45, 45), (27, 27, 27), (255, 255, 255)
CACHE = Path(os.environ.get("COVER_CACHE", Path.home() / ".cache/cover")); CACHE.mkdir(parents=True, exist_ok=True)
TWEMOJI = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/{cp}.svg"
FLAGS = "https://cdn.jsdelivr.net/npm/flag-icons@7.2.3/flags/4x3/{cc}.svg"


# ---------------------------------------------------------------- assets
def font(name, size): return ImageFont.truetype(str(ROOT / "fonts" / name), size)
def lilita(size): return font("LilitaOne-Regular.ttf", size)
def anton(size): return font("Anton-Regular.ttf", size)


def fetch(url):
    p = CACHE / hashlib.sha1(url.encode()).hexdigest()[:16]
    if not p.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "TheQuizWire-reelkit/1"})
        with urllib.request.urlopen(req, timeout=60) as r: p.write_bytes(r.read())
    return p


def svg_png(svg_path, width):
    out = CACHE / f"{svg_path.name}_{width}.png"
    if not out.exists():
        import cairosvg
        cairosvg.svg2png(url=str(svg_path), write_to=str(out), output_width=width)
    return Image.open(out).convert("RGBA")


def emoji_cp(e):
    """'⏰' → '23f0'; drops FE0F like Twemoji's filenames do."""
    return "-".join(f"{ord(c):x}" for c in e if ord(c) != 0xFE0F)


def sticker(cp, size, outline=18, rotate=0.0):
    """Twemoji rasterised with a white die-cut outline + soft shadow, rotated — the same language as the in-video stickers."""
    base = svg_png(fetch(TWEMOJI.format(cp=cp)), size).resize((size, size), Image.LANCZOS)
    pad = outline * 3; can = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0)); can.paste(base, (pad, pad), base)
    a = can.getchannel("A")
    for _ in range(2): a = a.filter(ImageFilter.MaxFilter(outline // 2 * 2 + 1))
    white = Image.new("RGBA", can.size, WHITE + (255,)); white.putalpha(a)
    shadow = Image.new("RGBA", can.size, (0, 0, 0, 150)); shadow.putalpha(a.filter(ImageFilter.GaussianBlur(14)))
    out = Image.new("RGBA", can.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (0, 16)); out.alpha_composite(white); out.alpha_composite(can)
    return out.rotate(rotate, resample=Image.BICUBIC, expand=True) if rotate else out


def flag(cc, w=84, h=63, r=10):
    im = svg_png(fetch(FLAGS.format(cc=cc)), w).resize((w, h), Image.LANCZOS)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255); im.putalpha(m)
    return im


def frame0(ep, video=None):
    v = Path(video) if video else Path(ep) / "out/final.mp4"
    if not v.exists(): return None
    out = CACHE / f"frame0_{hashlib.sha1(str(v.resolve()).encode()).hexdigest()[:10]}.png"
    if not out.exists():
        try: import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError: ff = "ffmpeg"
        subprocess.run([ff, "-loglevel", "error", "-y", "-ss", "0", "-i", str(v), "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


# ---------------------------------------------------------------- drawing helpers
def cover_fit(im, scale=1.0, anchor=(0.5, 0.5)):
    """Scale-to-cover the canvas (optionally zoomed) and crop around an anchor (fractions)."""
    s = max(W / im.width, H / im.height) * scale
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x = int((im.width - W) * anchor[0]); y = int((im.height - H) * anchor[1])
    return im.crop((x, y, x + W, y + H))


def gradient_mask(h, top, bottom):
    """Vertical L mask from alpha `top` to `bottom` (0–255)."""
    m = Image.new("L", (1, h)); px = [int(top + (bottom - top) * i / max(1, h - 1)) for i in range(h)]; m.putdata(px)
    return m.resize((W, h))


def darken(im, y0, y1, a0, a1):
    layer = Image.new("RGBA", (W, y1 - y0), (0, 0, 0, 255)); layer.putalpha(gradient_mask(y1 - y0, a0, a1))
    im.alpha_composite(layer, (0, y0))


def vignette(im, strength=160):
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    d.ellipse((-W * 0.25, -H * 0.12, W * 1.25, H * 1.12), fill=255); m = ImageOps.invert(m).filter(ImageFilter.GaussianBlur(160))
    m = m.point(lambda v: int(v * strength / 255)); layer = Image.new("RGBA", (W, H), (0, 0, 0, 255)); layer.putalpha(m); im.alpha_composite(layer)


def words_of(question, keyword):
    """[(token, is_keyword, trailing_punct)] — keyword matched case-insensitively, punctuation drawn in the base colour."""
    out = []
    keys = {k.upper() for k in (keyword or "").replace("-", " ").split() if k.lower() not in STOPWORDS}   # phrase keywords: every word except and/of/the…
    for tok in question.split():
        core = tok.rstrip("?!.,:;"); punct = tok[len(core):]
        out.append((core.upper(), core.upper() in keys, punct))
    return out


STOPWORDS = {"and", "or", "of", "the", "a", "an", "in", "on", "to", "&"}


def wrap(words, fnt, max_w):
    lines, cur = [], []
    def width(ws): return fnt.getlength(" ".join(w + p for w, _, p in ws))
    for w in words:
        if cur and width(cur + [w]) > max_w: lines.append(cur); cur = [w]
        else: cur.append(w)
    if cur: lines.append(cur)
    return lines


def fit_question(question, keyword, size, max_w, max_lines, min_size=84):
    words = words_of(question, keyword)
    while size > min_size:
        f = lilita(size); lines = wrap(words, f, max_w)
        if len(lines) <= max_lines and all(f.getlength(w + p) <= max_w for w, _, p in words): return f, lines
        size -= 6
    f = lilita(min_size); return f, wrap(words, f, max_w)


def draw_question(im, lines, fnt, top, fill, key_fill, stroke, stroke_fill, align="center", left=0, max_w=W, line_h=1.0, shadow=True):
    """Word-by-word so the keyword gets its own colour; one blurred shadow layer under the whole block. Returns bottom y."""
    size = fnt.size; lh = int(size * line_h)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    y = top
    for ln in lines:
        text = " ".join(w + p for w, _, p in ln); tw = fnt.getlength(text)
        x = left if align == "left" else left + (max_w - tw) / 2
        for w, is_key, p in ln:
            for t, col in ((w, key_fill if is_key else fill), (p, fill)):
                if not t: continue
                if shadow: ds.text((x, y), t, font=fnt, fill=(0, 0, 0, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                d.text((x, y), t, font=fnt, fill=col, stroke_width=stroke, stroke_fill=stroke_fill)
                x += fnt.getlength(t)
            x += fnt.getlength(" ")
        y += lh
    if shadow:
        sh = sh.filter(ImageFilter.GaussianBlur(16)); sh.putalpha(sh.getchannel("A").point(lambda v: int(v * 0.75))); im.alpha_composite(sh, (0, 14))
    im.alpha_composite(layer)
    return y


def pill(im, xy, text, fnt, fill, color, pad=(44, 22), radius=None, icon=None, gap=18, stroke=None):
    """Rounded pill with centred text (and an optional RGBA icon on the left). xy = centre. Returns bbox."""
    tw = fnt.getlength(text); th = fnt.size; iw = icon.width + gap if icon else 0
    w = int(tw + iw + pad[0] * 2); h = int(th * 1.15 + pad[1] * 2); x, y = int(xy[0] - w / 2), int(xy[1] - h / 2)
    d = ImageDraw.Draw(im); d.rounded_rectangle((x, y, x + w, y + h), radius or h // 2, fill=fill, outline=stroke, width=4 if stroke else 0)
    cx = x + pad[0]
    if icon: im.alpha_composite(icon, (cx, y + (h - icon.height) // 2)); cx += iw
    d.text((cx, y + h / 2 - th * 0.62), text, font=fnt, fill=color)
    return (x, y, x + w, y + h)


def series_chip(im, xy, series, number, color):
    """'GEO BLITZ · #14' in the series colour — same idea as the in-video bug (top-left)."""
    f = anton(40); text = f"{series['name'].upper()}  ·  #{number}"
    tw = f.getlength(text); w = int(tw + 64); h = 72; x, y = xy
    d = ImageDraw.Draw(im); d.rounded_rectangle((x, y, x + w, y + h), 18, fill=color)
    d.text((x + 32, y + 12), text, font=f, fill=(20, 20, 20))
    return (x, y, x + w, y + h)


def logo_bug(im, xy, size=92, text="TheQuizWire", color=WHITE, align="left"):
    logo = Image.open(ROOT / "brand/logo.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    f = anton(int(size * 0.56)); tw = f.getlength(text); total = size + 22 + tw
    x = xy[0] - (total if align == "right" else total / 2 if align == "center" else 0); y = xy[1]
    im.alpha_composite(logo, (int(x), int(y))); ImageDraw.Draw(im).text((int(x + size + 22), int(y + size * 0.16)), text, font=f, fill=color)


def hex_rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def question_mark(im, xy, size, rotate=12, alpha=235):
    f = lilita(size); layer = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    d.text((size * 0.55, size * 0.3), "?", font=f, fill=YELLOW + (255,), stroke_width=int(size * 0.045), stroke_fill=(20, 20, 20, 255))
    layer = layer.rotate(rotate, resample=Image.BICUBIC)
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0)); sh.putalpha(layer.getchannel("A").filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.6)))
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha / 255)))
    im.alpha_composite(sh, (xy[0] - size, xy[1] - size + 24)); im.alpha_composite(layer, (xy[0] - size, xy[1] - size))


# ---------------------------------------------------------------- episode context
def context(ep, frame=None, video=None):
    ep = Path(ep); E = json.loads((ep / "episode.json").read_text()); Q = E["quiz"]
    reg = json.loads((ROOT / "series/series.json").read_text())["series"]
    S = next((s for s in reg if s["slug"] == E["series"]), {"name": E["series"].title(), "color": "#E3A72F"})
    stickers = []
    vp = ep / "visuals.json"
    if vp.exists():
        V = json.loads(vp.read_text())
        stickers = [el["emoji"] for el in V.get("elements", []) if el.get("type") == "sticker" and el.get("emoji")]
    pub = json.loads((ROOT / "config/publishing.json").read_text())["series"].get(E["series"], {})
    emoji = (E.get("post") or {}).get("cover_emoji")
    cp = emoji_cp(emoji) if emoji else (stickers[0] if stickers else emoji_cp(pub.get("emoji", "❓")))
    bg = Image.open(frame).convert("RGB") if frame else frame0(ep, video)
    if bg is None: bg = Image.new("RGB", (W, H), DARK)
    hook = ""
    vp = ep / "voice.json"
    if vp.exists():
        for l in json.loads(vp.read_text()).get("lines", []):
            if l.get("role") == "hook": hook = (l.get("text") or "").strip(); break
    seed = int(E.get("seed", 1)); rnd = random.Random(seed)
    cv = dict((E.get("post") or {}).get("cover") or {})                       # authored overrides (post.cover) win over the seed
    cv.setdefault("headline", "hook" if (E.get("hook_type") in ("story", "fact-first", "misconception", "challenge") and 24 <= len(hook) <= 90) else "question")
    cv.setdefault("sticker_side", rnd.choice(["right", "left"]))
    cv.setdefault("tint", rnd.choice(["ink", "ink", "series", "navy"]))
    cv.setdefault("bg_anchor", rnd.choice([(0.5, 0.5), (0.35, 0.45), (0.65, 0.55), (0.5, 0.3)]))
    cv.setdefault("blur", rnd.choice([5, 7, 9]))
    cv.setdefault("highlight", [])
    return {"E": E, "Q": Q, "S": S, "cp": cp, "bg": bg, "number": E.get("number", ""), "seed": seed, "hook": hook, "cover": cv,
            "options": Q.get("options", []), "meta": Q.get("option_meta") or [{} for _ in Q.get("options", [])]}


def headline_of(C):
    """What the card says. 'hook' = the episode's own opening line (its strong opening, not the generic question);
    the quiz keyword (or post.cover.highlight words) go yellow. Falls back to the question."""
    cv = C["cover"]
    if cv.get("headline_text"):                                   # written form of the hook (numbers as digits, etc.)
        text = cv["headline_text"]; kw = " ".join(cv["highlight"]) or (C["Q"].get("keyword") or "")
        return text, kw
    if cv["headline"] == "hook" and C["hook"]:
        text = C["hook"].rstrip()
        kw = " ".join(cv["highlight"]) if cv["highlight"] else (C["Q"].get("keyword") or "")
        if not kw or not any(w.upper() in text.upper().split() for w in kw.split()):
            # pick the most 'loaded' word of the hook: longest word that is not a stopword/number
            cand = [w.strip(".,!?:;") for w in text.split() if w.strip(".,!?:;").lower() not in STOPWORDS and len(w) > 3]
            kw = max(cand, key=len) if cand else ""
        return text, kw
    return C["Q"]["question"], C["Q"].get("keyword")


# ---------------------------------------------------------------- styles
def style_a(C):
    im = cover_fit(C["bg"], 1.12).convert("RGBA")
    darken(im, 0, 760, 150, 40); darken(im, 1180, H, 0, 215); vignette(im, 150)
    color = hex_rgb(C["S"]["color"]); series_chip(im, (60, 96), C["S"], C["number"], color)
    f, lines = fit_question(C["Q"]["question"], C["Q"].get("keyword"), 156, 960, 4)
    bottom = draw_question(im, lines, f, 300, WHITE + (255,), YELLOW + (255,), 10, (18, 18, 18, 255), line_h=0.98)
    question_mark(im, (820, min(bottom + 330, 1330)), 500, rotate=14)
    st = sticker(C["cp"], 400, rotate=-12); im.alpha_composite(st, (40, min(bottom + 70, 1040)))
    clock = sticker("23f1", 64, outline=6)
    pill(im, (W // 2, 1600), "GUESS IN 3 SECONDS", anton(56), YELLOW, (20, 20, 20), icon=clock)
    logo_bug(im, (W // 2, 1735), 88, align="center")
    return im


def style_b(C):
    """APPROVED 2026-10-16 (owner): quiz card without the 3-second ring/sub-lines — question + the three options, nothing else."""
    cv = C["cover"]
    bg = cover_fit(C["bg"], 1.28, anchor=tuple(cv["bg_anchor"])).filter(ImageFilter.GaussianBlur(cv["blur"])); im = bg.convert("RGBA"); darken(im, 0, H, 120, 170)
    color = hex_rgb(C["S"]["color"])
    card_fill = {"ink": (16, 17, 22, 222), "navy": (12, 22, 44, 226), "series": tuple(int(c * 0.22) for c in color) + (228,)}[cv["tint"]]
    cx0, cx1 = 64, W - 64
    text, kw = headline_of(C)
    f, lines = fit_question(text, kw, 118, 820, 4)
    text_h = int(f.size * 1.02) * len(lines)
    card_h = 236 + text_h + 56 + 2 * 150 + 118 + 72                                       # chip/sticker head · question · 3 pills · padding
    cy0 = max(230, (H - card_h) // 2 - 80); cy1 = cy0 + card_h                            # card sits a little above centre, logo beneath
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)        # translucent shapes are blended via a layer
    d.rounded_rectangle((cx0, cy0, cx1, cy1), 60, fill=card_fill, outline=(255, 255, 255, 60), width=3)
    d.rounded_rectangle((cx0 + 48, cy0, cx1 - 48, cy0 + 12), 6, fill=color + (255,))
    im.alpha_composite(layer)
    if cv["sticker_side"] == "left":
        chip_w = int(anton(40).getlength(f"{C['S']['name'].upper()}  ·  #{C['number']}") + 64); series_chip(im, (cx1 - 52 - chip_w, cy0 + 56), C["S"], C["number"], color)
    else: series_chip(im, (cx0 + 52, cy0 + 56), C["S"], C["number"], color)
    y = draw_question(im, lines, f, cy0 + 236, WHITE + (255,), YELLOW + (255,), 6, (10, 10, 12, 255), left=cx0 + 48, max_w=cx1 - cx0 - 96, line_h=1.02, shadow=False)
    y += 56
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    fo = anton(56); fl = lilita(48)
    for i, (name, meta) in enumerate(zip(C["options"], C["meta"])):
        py = y + i * 150; d.rounded_rectangle((cx0 + 60, py, cx1 - 60, py + 118), 59, fill=(255, 255, 255, 30), outline=(255, 255, 255, 110), width=3)
        d.ellipse((cx0 + 78, py + 14, cx0 + 168, py + 104), fill=WHITE + (255,)); d.text((cx0 + 123 - fl.getlength("ABC"[i]) / 2, py + 26), "ABC"[i], font=fl, fill=(20, 20, 20, 255))
        tx = cx0 + 196
        if meta.get("flag"): fg = flag(meta["flag"]); layer.alpha_composite(fg, (tx, py + 28)); tx += fg.width + 22
        d.text((tx, py + 24), name, font=fo, fill=WHITE + (255,))
    im.alpha_composite(layer)
    if cv["sticker_side"] == "left": st = sticker(C["cp"], 250, rotate=-12); im.alpha_composite(st, (-24, cy0 - 150))
    else: st = sticker(C["cp"], 250, rotate=12); im.alpha_composite(st, (W - st.width + 24, cy0 - 150))   # clears the first question line
    logo_bug(im, (W // 2, min(cy1 + 90, 1740)), 84, align="center")
    return im


def torn_mask(y_left, y_right, seed, amp=22):
    rnd = random.Random(seed); pts = [(0, H), (0, y_left)]
    x = 0
    while x < W:
        x += rnd.randint(18, 46); t = x / W; base = y_left + (y_right - y_left) * t
        pts.append((min(x, W), base + rnd.uniform(-amp, amp)))
    pts += [(W, y_right), (W, H)]
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def style_c(C):
    im = cover_fit(C["bg"], 1.18, anchor=(0.5, 0.35)).convert("RGBA"); darken(im, 0, 420, 120, 0); vignette(im, 110)
    color = hex_rgb(C["S"]["color"])
    mask = torn_mask(1040, 900, C["seed"])
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.7)))
    im.alpha_composite(shadow, (0, -18))
    paper = Image.new("RGBA", (W, H), YELLOW + (255,)); paper.putalpha(mask); im.alpha_composite(paper)
    edge = mask.filter(ImageFilter.MaxFilter(7)); edge = Image.eval(edge, lambda v: v) ; rim = Image.new("RGBA", (W, H), (255, 246, 190, 255))
    rim_mask = Image.eval(edge, lambda v: v); rim_mask.paste(0, (0, 0, W, H), mask.filter(ImageFilter.MinFilter(3)).point(lambda v: 255 if v else 0)); rim.putalpha(rim_mask); im.alpha_composite(rim)
    # tape label (top-left) · series chip (top-right)
    tape = Image.new("RGBA", (420, 110), (0, 0, 0, 0)); td = ImageDraw.Draw(tape); td.rectangle((0, 0, 419, 109), fill=(20, 20, 20, 240))
    ft = anton(64); td.text((210 - ft.getlength("CAN YOU GUESS?") / 2, 16), "CAN YOU GUESS?", font=ft, fill=YELLOW)
    tape = tape.rotate(-5, resample=Image.BICUBIC, expand=True); im.alpha_composite(tape, (44, 96))
    chip_w = int(anton(40).getlength(f"{C['S']['name'].upper()}  ·  #{C['number']}") + 64); series_chip(im, (W - 60 - chip_w, 110), C["S"], C["number"], color)
    f, lines = fit_question(C["Q"]["question"], C["Q"].get("keyword"), 144, 940, 3, min_size=96)
    bottom = draw_question_c(im, lines, f, 1085)
    st = sticker(C["cp"], 380, rotate=-9); im.alpha_composite(st, (W - 470, 560))
    pill(im, (W // 2, min(bottom + 80, 1640)), "TAP · GUESS IN 3 SECONDS · SEE THE MAP", anton(46), (20, 20, 20), YELLOW)
    logo_bug(im, (W // 2, 1735), 84, text="thequizwire.com", color=(20, 20, 20), align="center")
    return im


def draw_question_c(im, lines, fnt, top):
    """Black type on the yellow panel: no stroke on black words; the keyword is white with a black stroke (comic lettering)."""
    lh = int(fnt.size * 0.98); d = ImageDraw.Draw(im); y = top
    for ln in lines:
        text = " ".join(w + p for w, _, p in ln); x = (W - fnt.getlength(text)) / 2
        for w, is_key, p in ln:
            if is_key: d.text((x, y), w, font=fnt, fill=WHITE, stroke_width=9, stroke_fill=(20, 20, 20))
            else: d.text((x, y), w, font=fnt, fill=(20, 20, 20))
            x += fnt.getlength(w)
            if p: d.text((x, y), p, font=fnt, fill=(20, 20, 20)); x += fnt.getlength(p)
            x += fnt.getlength(" ")
        y += lh
    return y


STYLES = {"a": style_a, "b": style_b, "c": style_c}
DEFAULT_STYLE = "b"          # owner-approved 2026-10-16 (quiz card, no timer ring); a/c kept as alternates


def ffmpeg_exe():
    try: import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError: return "ffmpeg"


def burn(video, cover, out, secs=0.3, fps=30):
    """Prepend the cover as the first `secs` of the master (audio delayed to match) so frame 0 of the reel IS the cover
    on Instagram/Facebook/X/Threads. Re-encodes (libx264 crf 18, AAC) with faststart; sizes stay within a few MB."""
    ms = int(secs * 1000)
    cmd = [ffmpeg_exe(), "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", f"{secs}", "-i", str(cover), "-i", str(video),
           "-filter_complex", f"[0:v]scale={W}:{H},format=yuv420p,setsar=1[c];[1:v]format=yuv420p,setsar=1[m];[c][m]concat=n=2:v=1:a=0[v];[1:a]adelay={ms}|{ms}[a]",
           "-map", "[v]", "-map", "[a]", "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("--style", default=DEFAULT_STYLE, choices=list(STYLES))
    ap.add_argument("--frame"); ap.add_argument("--video"); ap.add_argument("--out"); ap.add_argument("--all", action="store_true", help="render every style")
    ap.add_argument("--jpg", help="also save a JPG copy (YouTube thumbnail, < 2 MB)")
    ap.add_argument("--burn", help="write a copy of --video with the cover as its first 0.3 s to this path")
    a = ap.parse_args()
    C = context(a.episode, a.frame, a.video)
    for s in (STYLES if a.all else [a.style]):
        im = STYLES[s](C).convert("RGB")
        out = Path(a.out) if (a.out and not a.all) else Path(a.episode) / "out" / ("cover.png" if (s == DEFAULT_STYLE and not a.all) else f"cover_{s}.png")
        out.parent.mkdir(parents=True, exist_ok=True); im.save(out, optimize=True)
        print(f"cover {s}: {out} ({im.width}×{im.height}) · sticker {C['cp']} · headline={C['cover']['headline']} tint={C['cover']['tint']} sticker={C['cover']['sticker_side']}")
        if a.jpg and not a.all: im.save(a.jpg, quality=92, optimize=True); print(f"  jpg → {a.jpg}")
        if a.burn and not a.all and a.video: burn(a.video, out, a.burn); print(f"  burned → {a.burn}")


if __name__ == "__main__":
    main()
