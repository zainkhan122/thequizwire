"""engine/story.py — Geo Stories (format "story-v1", docs/STORY_GUIDELINES.md) screen furniture on top of engine/quiz.py:
  title block   = PLACE kicker + headline (one yellow *keyword*), lands word by word like the v4 hook, leaves on the first story beat
  keyword caption = 2–5-word white phrase with one yellow *keyword* in the caption band (y 1380), one per beat
  close line    = the sentence that answers the opening line, big, before the outro
Cards, stickers, photos, characters, outro, scrims come from Quiz (shared look). Everything here is a `.tu` text unit for textqa/factcheck.
"""
import html, re

ALLOW = ' data-layout-allow-overlap="true" data-layout-allow-occlusion="true"'
CAPZ = ' data-layout-allow-caption-zone="true"'


def f(x): return f"{x:.3f}"
def esc(s): return html.escape(str(s), quote=False)


def mark(text):
    """*word* → <b>word</b> (yellow), !word! → <i>word</i> (red). Returns plain text and html."""
    plain = re.sub(r"[*!](.+?)[*!]", r"\1", text)
    h = re.sub(r"\*(.+?)\*", lambda m: f"<b{ALLOW}>{esc(m.group(1))}</b>", esc(text))
    h = re.sub(r"!(.+?)!", lambda m: f"<i{ALLOW}>{m.group(1)}</i>", h)
    return plain, h


class Story:
    def __init__(self, J): self.J = J

    # ---------------------------------------------------------------- title block
    def title(self, tid, place, headline):
        plain, _ = mark(headline); parts, tag = [], None                        # per-word spans; *…* / !…! may span several words
        for w in headline.split(" "):
            if w.startswith("*"): tag = "b"
            elif w.startswith("!"): tag = "i"
            core = w.strip("*!")
            parts.append(f'<span class="w"><{tag}{ALLOW}>{esc(core)}</{tag}></span>' if tag else f'<span class="w">{esc(core)}</span>')
            if w.endswith(("*", "!")) and len(w) > 1: tag = None
        words = " ".join(parts); n = len(plain); size = "s" if n > 44 else "m" if n > 30 else ""
        return (f'<div id="{tid}" class="stitle {size}"{ALLOW}>'
                f'<div class="st-place tu" id="{tid}_place"{ALLOW}>{esc(place)}</div>'
                f'<div class="st-head tu" id="{tid}_head"{ALLOW}>{words}</div></div>')

    def title_in(self, t, tid="title", dur=0.5):
        self.J(f"tl.fromTo('#{tid}',{{autoAlpha:0}},{{autoAlpha:1,duration:0.2,immediateRender:false}},{f(t)});")
        self.J(f"tl.fromTo('#{tid}_place',{{autoAlpha:0,x:-30}},{{autoAlpha:1,x:0,duration:{f(dur * 0.7)},ease:'power2.out',immediateRender:false}},{f(t)});")
        self.J(f"tl.fromTo('#{tid}_head .w',{{autoAlpha:0,y:30,scale:0.7}},{{autoAlpha:1,y:0,scale:1,duration:0.3,ease:'back.out(2)',stagger:0.07,immediateRender:false}},{f(t + 0.15)});")
        if t > 0: self.J(f"tl.to('#scrimtop',{{opacity:1,duration:0.4}},{f(t - 0.2)});")

    def title_out(self, t, tid="title", dur=0.35):
        self.J(f"tl.to('#{tid}',{{autoAlpha:0,y:-50,scale:0.96,duration:{f(dur)},ease:'power2.in'}},{f(t)});")
        self.J(f"tl.to('#scrimtop',{{opacity:0,duration:0.5}},{f(t)});")

    # ---------------------------------------------------------------- keyword captions
    def kw(self, kid, text, y=1380):
        _, hh = mark(text)
        self.J(f"tl.set('#{kid}',{{xPercent:-50}},0);")                                      # centred on x=540 with a shrink-wrapped box (textqa samples the box)
        return f'<div id="{kid}" class="skw tu" style="top:{y}px"{ALLOW}{CAPZ}>{hh}</div>'

    def kw_in(self, t0, t1, kid, dur=0.3):
        self.J(f"tl.fromTo('#{kid}',{{autoAlpha:0,y:24,scale:0.9}},{{autoAlpha:1,y:0,scale:1,duration:{f(dur)},ease:'back.out(1.6)',immediateRender:false}},{f(t0)});")
        if t1 is not None: self.J(f"tl.to('#{kid}',{{autoAlpha:0,y:-16,duration:0.25,ease:'power2.in'}},{f(max(t0 + dur + 0.2, t1))});")

    # ---------------------------------------------------------------- close line
    def close(self, cid, text, y=760):
        _, hh = mark(text)
        n = len(re.sub(r"<[^>]+>", "", hh)); size = "s" if n > 60 else "m" if n > 42 else ""
        return f'<div id="{cid}" class="sclose tu {size}" style="top:{y}px"{ALLOW}>{hh}</div>'

    def kw_pulse(self, t, kid, dur=0.4):
        """Cue breath: the keyword caption swells a little on a spoken cue (keeps the frame alive between bigger moves)."""
        self.J(f"tl.fromTo('#{kid}',{{scale:1}},{{scale:1.06,duration:{f(dur / 2)},ease:'sine.inOut',yoyo:true,repeat:1,immediateRender:false}},{f(t)});")

    def kw_out(self, t, kid, dur=0.25):
        self.J(f"tl.to('#{kid}',{{autoAlpha:0,duration:{f(dur)}}},{f(t)});")

    def close_in(self, t0, t1, cid="close", dur=0.45):
        self.J(f"tl.fromTo('#{cid}',{{autoAlpha:0,scale:0.9,y:20}},{{autoAlpha:1,scale:1,y:0,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t0)});")
        if t1 is not None: self.J(f"tl.to('#{cid}',{{autoAlpha:0,duration:0.3}},{f(t1)});")


CSS = """
.v3 .stitle{position:absolute;left:60px;top:250px;width:900px;z-index:72;visibility:hidden;opacity:0}
.v3 .st-place{display:inline-block;font-family:'Oswald';font-weight:600;font-size:40px;letter-spacing:.22em;text-transform:uppercase;color:#FFD400;background:rgba(11,22,32,.86);
  border-left:8px solid #FFD400;padding:10px 22px 8px;border-radius:6px;margin-bottom:26px;box-shadow:0 8px 20px rgba(0,0,0,.4)}
.v3 .st-head{font-family:'Lilita';font-size:96px;line-height:1.04;text-transform:uppercase;color:#fff;-webkit-text-stroke:3px #141414;paint-order:stroke fill;
  text-shadow:0 7px 0 rgba(0,0,0,.6),0 0 22px rgba(0,0,0,.9),0 16px 32px rgba(0,0,0,.7)}
.v3 .stitle.m .st-head{font-size:82px} .v3 .stitle.s .st-head{font-size:70px}
.v3 .st-head .w{display:inline-block;will-change:transform,opacity} .v3 .st-head b{color:#FFD400;font-weight:400}
.v3 .skw{position:absolute;left:540px;width:auto;max-width:880px;white-space:nowrap;text-align:center;font-family:'Anton';font-size:62px;line-height:1.15;text-transform:uppercase;color:#fff;letter-spacing:.02em;
  -webkit-text-stroke:2px #141414;paint-order:stroke fill;text-shadow:0 5px 0 rgba(0,0,0,.55),0 0 18px rgba(0,0,0,.9);z-index:71;visibility:hidden;opacity:0;pointer-events:none}
.v3 .skw{background:rgba(11,22,32,.86);padding:8px 26px 6px;border-radius:12px;box-shadow:0 8px 20px rgba(0,0,0,.35)}  /* plate: readable over yellow land fills (textqa ≥ 3:1) */
.v3 .skw b{color:#FFD400;font-weight:400} .v3 .skw i{color:#FF5A4E;font-style:normal}
.v3 .sclose{position:absolute;left:60px;width:880px;text-align:center;font-family:'Lilita';font-size:84px;line-height:1.06;text-transform:uppercase;color:#fff;-webkit-text-stroke:3px #141414;
  paint-order:stroke fill;text-shadow:0 7px 0 rgba(0,0,0,.6),0 0 22px rgba(0,0,0,.9);z-index:72;visibility:hidden;opacity:0}
.v3 .sclose.m{font-size:72px} .v3 .sclose.s{font-size:62px} .v3 .sclose b{color:#FFD400;font-weight:400}
.v3 .scredit{position:absolute;left:60px;width:960px;top:1760px;text-align:center;font-family:'Oswald';font-size:22px;letter-spacing:.04em;color:rgba(255,255,255,.78);text-shadow:0 2px 6px rgba(0,0,0,.9);z-index:95;visibility:hidden;opacity:0}
.geo .g-highlight.tint{fill:rgba(95,182,242,.5);stroke:#fff;stroke-width:2.2}
/* custom-polygon areas used as highlights (geo.json extra_layers kind:area, cls "highlight …"): same palette as g-highlight, hidden until highlight_in */
.geo .g-area.highlight{opacity:0}
.geo .g-area.highlight.tint{fill:rgba(95,182,242,.5);stroke:#fff;stroke-width:2.2}
.geo .g-area.highlight.solid{fill:#F39A1E;stroke:#fff;stroke-width:2.4}
.geo .g-area.highlight.neon{fill:rgba(255,230,0,.04);stroke:#FFE600;stroke-width:4}
.geo .g-area.highlight.neonblue{fill:rgba(54,201,255,.04);stroke:#36C9FF;stroke-width:4}
.geo .g-highlight.solid{fill:#F39A1E;stroke:#fff;stroke-width:2.4}
.geo .g-highlight.neon{fill:rgba(255,230,0,.04);stroke:#FFE600;stroke-width:4}
.geo .g-highlight.neonblue{fill:rgba(54,201,255,.04);stroke:#36C9FF;stroke-width:4}
.geo .g-highlight.glow{fill:rgba(255,138,30,.72);stroke:#FFD9A0;stroke-width:2.4;filter:drop-shadow(0 0 10px rgba(255,138,30,.95)) drop-shadow(0 0 26px rgba(255,120,0,.6))}
.geo .g-highlight.zone1{fill:rgba(63,157,232,.62);stroke:#fff;stroke-width:1.8} .geo .g-highlight.zone2{fill:rgba(92,196,90,.62);stroke:#fff;stroke-width:1.8}
.geo .g-highlight.zone3{fill:rgba(240,162,60,.62);stroke:#fff;stroke-width:1.8} .geo .g-highlight.zone4{fill:rgba(236,91,91,.62);stroke:#fff;stroke-width:1.8}
.geo .g-highlight.zone5{fill:rgba(242,223,120,.62);stroke:#fff;stroke-width:1.8} .geo .g-highlight.zone6{fill:rgba(196,139,227,.62);stroke:#fff;stroke-width:1.8}
"""
