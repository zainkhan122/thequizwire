"""Shared professional FX for HyperFrames builds (Python -> HTML/CSS/GSAP strings). Deterministic: seeded LCG only.

Usage in an episode build.py:
    sys.path.insert(0, str(REPO / "engine")); import fx
    FX = fx.FX(J, HERE / "clips.json", SC)         # J = js-line appender, SC = scenes by id
    FX.plate("s03_console")                         # <img> plate, plus a timed <video> layer if clips.json animates it
    clip("ins", t0, t1, FX.film_insert("ins", "arch_minuteman", t0, t1, "U.S. ICBM LAUNCH · USAF FILM"), z=60)
    FX.flash(t) · FX.light_leak(t, dur) · FX.film_burn(t)       (global overlays; call FX.overlays() once for their HTML)
    CSS += fx.CSS

Rules honoured (HyperFrames): one paused timeline; every fromTo has immediateRender:false; elements that start hidden
get autoAlpha in the destination; no two tweens animate the same property of one element at the same time.
"""
import json
from pathlib import Path


def f(x): return f"{x:.3f}"


class _Rng:
    def __init__(self, seed): self.s = seed & 0x7FFFFFFF
    def __call__(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF; return self.s / 0x7FFFFFFF


class FX:
    def __init__(self, J, clips_json=None, scenes=None, seed=1983, hf=None):
        self.hf = Path(hf) if hf else None
        self.J, self.rng, self.clips, self.scenes = J, _Rng(seed), {}, scenes or {}
        if clips_json and Path(clips_json).exists():
            self.clips = {c["id"]: c for c in json.load(open(clips_json))["clips"]}
        self.layers = []

    # ---------------------------------------------------------------- motion plates
    def clip_window(self, cid):
        c = self.clips.get(cid)
        if not c or c.get("engine") == "url" or c.get("scene") not in self.scenes: return None
        if self.hf and not (self.hf / "assets/clips" / f"{cid}.mp4").exists(): return None   # not generated yet -> still plate
        s = self.scenes[c["scene"]]
        return s["start"], s["end"] - s["start"]        # exactly the scene window (neighbour scenes may be transparent)

    def plate(self, img, kbid, w=1296, h=2322):
        """Still plate, or (when clips.json animates it) an empty slot + a top-level timed <video> layer.
        HyperFrames forbids <video data-start> inside a timed element, so videos live at root level directly
        beneath their scene (z 9 < scene z 10); overlays inside the scene stay on top. Use kb_targets()/shake_targets()
        so camera moves and shakes drive the plate wrapper and its video together."""
        win = self.clip_window(img)
        if not win:
            return f'<img src="assets/{img}.jpg" style="position:absolute;left:0;top:0;width:{w}px;height:{h}px" alt="">'
        t0, d = win; self.layers.append((kbid, img, t0, d, w, h, self.clips[img]["scene"]))
        return ""

    def footage(self, kbid, cid, t0, t1, box=None):
        """Archival (url) clip as a FULL-BLEED moving layer — same root-level timed <video> mechanism as plate().
        box=(left, top, w, h) places it instead of the 1.2x Ken Burns frame (e.g. a 1080x1080 globe).
        Returns False (caller draws a fallback) when the clip was not prepped into hf/assets/clips."""
        if cid not in self.clips: return False
        if self.hf and not (self.hf / "assets/clips" / f"{cid}.mp4").exists(): return False
        W, H = (box[2], box[3]) if box else (1296, 2322)
        self.layers.append((kbid, cid, t0, t1 - t0, W, H, self.clips[cid].get("scene"), box))
        return True

    def video_layers(self):
        out = []
        for kbid, img, t0, d, w, h, _sc, *rest in self.layers:
            box = rest[0] if rest else None
            pos = f' style="left:{box[0]}px;top:{box[1]}px;width:{w}px;height:{h}px"' if box else ""
            out.append(f'<div id="{kbid}_vs" class="fxvs"><div id="{kbid}_vw" class="kb"{pos}>'
                       f'<video id="v_{img}" src="assets/clips/{img}.mp4" muted playsinline preload="auto" data-start="{f(t0)}" '
                       f'data-duration="{f(d)}" data-media-start="0" data-track-index="1" '
                       f'style="position:absolute;left:0;top:0;width:{w}px;height:{h}px;object-fit:cover"></video></div></div>')
        return "\n".join(out)

    def kb_targets(self, sel):
        """'#kb03' -> '#kb03,#kb03_vw' when that plate is animated."""
        return sel + "".join(f",#{k}_vw" for k, *_ in self.layers if f"#{k}" == sel)

    def shake_targets(self, sel):
        """'#sc03' -> also shake the video wrappers belonging to scene s03."""
        sc = sel.lstrip("#").replace("sc", "s", 1)
        return sel + "".join(f",#{L[0]}_vs" for L in self.layers if L[6] == sc)

    # ---------------------------------------------------------------- archival film insert
    def film_insert(self, id_, cid, t0, t1, label, credit="", dy=0):
        """Projected archive film: dark backing, sprocketed frame, gate weave, exposure flicker, typed label."""
        c = self.clips[cid]; W, H = c.get("fit", [1000, 562]); d = t1 - t0
        top = 960 - H // 2 - 40 + dy           # dy < 0 lifts the frame (keeps the credit clear of the caption band)
        html = (f'<div class="wash" style="background:radial-gradient(ellipse at 50% 48%,#2a241c 0%,#0c0a08 78%)"></div>'
                f'<div id="{id_}_f" class="filmframe" style="left:{540 - W // 2 - 26}px;top:{top}px;width:{W + 52}px;height:{H + 52}px">'
                f'<div id="{id_}_w" class="filmweave"><video id="{id_}_v" src="assets/clips/{cid}.mp4" muted playsinline preload="auto" '
                f'data-start="{f(t0)}" data-duration="{f(d)}" data-media-start="0" style="width:{W}px;height:{H}px;display:block"></video>'
                f'<div id="{id_}_k" class="filmflick"></div></div>'
                f'<div class="sprk l"></div><div class="sprk r"></div></div>'
                + (f'<div id="{id_}_l" class="filmlabel" style="top:{top - 92}px">{label}</div>' if label else "")
                + (f'<div class="filmcredit" data-tq-dwell="off" style="top:{top + H + 70}px">{credit}</div>' if credit else ""))
        J = self.J
        J(f"tl.fromTo('#{id_}_f',{{scale:1.12,rotation:-2.2,autoAlpha:0}},{{scale:1,rotation:-0.8,autoAlpha:1,duration:0.22,ease:'power3.out',immediateRender:false}},{f(t0)});")
        J(f"tl.to('#{id_}_f',{{scale:1.035,duration:{f(max(0.1, d - 0.22))},ease:'none'}},{f(t0 + 0.22)});")
        if label: J(f"tl.fromTo('#{id_}_l',{{autoAlpha:0,x:-30}},{{autoAlpha:1,x:0,duration:0.2,ease:'power2.out',immediateRender:false}},{f(t0 + 0.06)});")
        t = t0                                  # gate weave + flicker at ~12 Hz (film is never perfectly still)
        while t < t1 - 0.05:
            J(f"tl.set('#{id_}_w',{{x:{f((self.rng() - .5) * 3)},y:{f((self.rng() - .5) * 5)}}},{f(t)});")
            J(f"tl.set('#{id_}_k',{{opacity:{f(0.02 + self.rng() * 0.10)}}},{f(t)});")
            t += 1 / 12
        return html

    # ---------------------------------------------------------------- global overlays
    def overlays(self):
        return ('<div id="fx_leak" class="fxlayer" style="opacity:0;mix-blend-mode:screen">'
                '<div class="lk a"></div><div class="lk b"></div><div class="lk c"></div></div>'
                '<div id="fx_burn" class="fxlayer" style="opacity:0;mix-blend-mode:screen"></div>'
                '<div id="fx_flash" class="fxlayer" style="opacity:0;background:#FFF8EC"></div>')

    def flash(self, t, peak=0.85, hold=0.04, out=0.22):
        self.J(f"tl.fromTo('#fx_flash',{{opacity:0}},{{opacity:{peak},duration:0.04,ease:'none',immediateRender:false}},{f(t - 0.04)});")
        self.J(f"tl.to('#fx_flash',{{opacity:0,duration:{out},ease:'power2.out'}},{f(t + hold)});")

    def light_leak(self, t, dur=2.4, peak=0.75):
        """Organic warm leak drifting across the frame (memory / revelation beats)."""
        J = self.J
        J(f"tl.fromTo('#fx_leak',{{opacity:0}},{{opacity:{peak},duration:{f(dur * .3)},ease:'sine.out',immediateRender:false}},{f(t)});")
        J(f"tl.to('#fx_leak',{{opacity:0,duration:{f(dur * .45)},ease:'sine.in'}},{f(t + dur * .55)});")
        J(f"tl.fromTo('#fx_leak .a',{{xPercent:-25,rotation:-4}},{{xPercent:20,rotation:3,duration:{f(dur)},ease:'sine.inOut',immediateRender:false}},{f(t)});")
        J(f"tl.fromTo('#fx_leak .b',{{xPercent:22,yPercent:-6}},{{xPercent:-18,yPercent:6,duration:{f(dur)},ease:'sine.inOut',immediateRender:false}},{f(t)});")
        J(f"tl.fromTo('#fx_leak .c',{{xPercent:-30}},{{xPercent:26,duration:{f(dur)},ease:'sine.inOut',immediateRender:false}},{f(t)});")

    def film_burn(self, t, dur=0.5):
        """Hot orange burn-out (end of an archival insert)."""
        self.J(f"tl.fromTo('#fx_burn',{{opacity:0,scale:0.6}},{{opacity:1,scale:1.5,duration:{f(dur * .55)},ease:'power2.in',immediateRender:false}},{f(t - dur * .55)});")
        self.J(f"tl.to('#fx_burn',{{opacity:0,duration:{f(dur * .45)},ease:'power1.out'}},{f(t)});")


CSS = """
.fxvs{position:absolute;left:0;top:0;width:1080px;height:1920px;z-index:9;overflow:hidden}
.fxlayer{position:absolute;left:0;top:0;width:1080px;height:1920px;pointer-events:none;z-index:880}
#fx_flash{z-index:890}
#fx_leak .lk{position:absolute;left:-30%;top:-20%;width:160%;height:140%}
#fx_leak .a{background:radial-gradient(ellipse 50% 60% at 12% 55%,rgba(255,236,190,.9),transparent 55%),radial-gradient(ellipse 70% 80% at 22% 50%,rgba(255,128,60,.7),transparent 70%);filter:blur(30px)}
#fx_leak .b{background:radial-gradient(ellipse 55% 60% at 80% 32%,rgba(255,80,60,.65),rgba(255,40,90,.22) 50%,transparent 76%);filter:blur(40px)}
#fx_leak .c{background:linear-gradient(104deg,transparent 25%,rgba(255,150,60,.3) 40%,rgba(255,246,205,.7) 51%,rgba(255,120,48,.2) 62%,transparent 78%);filter:blur(22px)}
#fx_burn{background:radial-gradient(circle at 70% 40%,rgba(255,250,230,1) 0%,rgba(255,170,60,.95) 22%,rgba(200,60,10,.8) 45%,transparent 70%);transform-origin:70% 40%}
.filmframe{position:absolute;background:#0b0a09;padding:26px;box-shadow:0 30px 70px rgba(0,0,0,.7);visibility:hidden;opacity:0}
.filmweave{position:relative;overflow:hidden}
.filmflick{position:absolute;left:0;top:0;width:100%;height:100%;background:#fff6e0;mix-blend-mode:screen;opacity:0}
.sprk{position:absolute;top:0;width:14px;height:100%;background:repeating-linear-gradient(to bottom,transparent 0 10px,#e8dcc4 10px 22px,transparent 22px 34px);opacity:.55}
.sprk.l{left:6px}.sprk.r{right:6px}
.filmlabel{position:absolute;left:70px;font-family:'Elite',monospace;font-size:38px;color:#141414;background:#F3EAD3;padding:10px 20px 8px;
  transform:rotate(-1.2deg);box-shadow:0 6px 14px rgba(0,0,0,.45);white-space:nowrap;visibility:hidden;opacity:0}
.filmcredit{position:absolute;left:120px;width:840px;text-align:center;font-family:'Elite',monospace;font-size:25px;color:#EFE6D2;text-shadow:0 2px 6px #000}
"""
