"""engine/props.py — animated PROPS for story episodes (owner 2026-11-19: "animate the actual objects, process and output").

A prop is an inline-SVG rig (`rig` element in visuals.json) with named sub-parts the devices can move:
  sat      satellite with two astronauts in the cupola — arms {id}_armL / {id}_armR wave
  fallsat  small spacecraft with a re-entry flame {id}_flame
  splash   impact rings {id}_r1 / {id}_r2
  person   little figure, waving arm {id}_arm, red cross {id}_x (hidden until prop.cross)
  flag     flag on a pole; cloth {id}_cloth is a flag-icons SVG (assets/geo/flags/<cc>.svg)
  tag      small text tag (one word) — for "?" / "NO" / years
Devices (visuals.json beats, do = "prop.<verb>", stage = the geo stage they anchor to):
  prop.anchor  t0..t1  keep the prop glued to a lon/lat (+dx,dy px) while the camera moves
  prop.pop / prop.out  show / hide (pop = scale burst, rise = grows from its baseline)
  prop.orbit   t0..t1  fly from lonlat A to lonlat B on an arc `height` px high, rolling slightly
  prop.wave    t0..t1  arms wave (any list of part ids with a pivot)
  prop.fall    t..t+dur  drop onto a lon/lat from (dx,dy) px away with the flame on, then vanish; optional splash rig id
  prop.cross   t  stamp the red cross of a person rig
  prop.flutter t0..t1  cloth skews back and forth
  prop.hop     t0..t1  little bounce (people on a coast)
Everything positions through GeoRT.toScreen() each frame (geo-runtime.js), so props stay on their spot through every camera move.
All JS is deterministic (no Date / random / timers) — reelkit/hfstatic.mjs runs it headless.
"""
import html

def f(x): return f"{x:.3f}"
ALLOW = ' data-layout-allow-overlap="true" data-layout-allow-occlusion="true"'

# ---------------------------------------------------------------- rigs (viewBox -100 -100 200 200 unless noted · pivots in that space)
def _sat(i):
    return (f'<rect x="-34" y="-30" width="68" height="64" rx="10" fill="#d9dde3" stroke="#2b2f36" stroke-width="5"/>'
            f'<rect x="-96" y="-16" width="56" height="36" rx="4" fill="#2a5bd7" stroke="#10223f" stroke-width="4"/><path d="M-82 -16v36M-68 -16v36M-54 -16v36M-96 2h56" stroke="#9cc0ff" stroke-width="2.5"/>'
            f'<rect x="40" y="-16" width="56" height="36" rx="4" fill="#2a5bd7" stroke="#10223f" stroke-width="4"/><path d="M54 -16v36M68 -16v36M82 -16v36M40 2h56" stroke="#9cc0ff" stroke-width="2.5"/>'
            f'<circle cx="0" cy="-56" r="18" fill="#fff" stroke="#2b2f36" stroke-width="5"/><path d="M0 -40v12" stroke="#2b2f36" stroke-width="5"/>'
            f'<rect x="-26" y="-22" width="52" height="40" rx="8" fill="#0b2a4a" stroke="#2b2f36" stroke-width="4"/>'   # cupola window
            f'<circle cx="-12" cy="-4" r="11" fill="#fff" stroke="#2b2f36" stroke-width="3"/><circle cx="-12" cy="-2" r="6" fill="#2b2f36"/>'
            f'<circle cx="13" cy="-4" r="11" fill="#fff" stroke="#2b2f36" stroke-width="3"/><circle cx="13" cy="-2" r="6" fill="#2b2f36"/>'
            f'<g id="{i}_armL"><path d="M-22 10 L-40 -18" stroke="#fff" stroke-width="9" stroke-linecap="round"/><circle cx="-41" cy="-21" r="8" fill="#fff" stroke="#2b2f36" stroke-width="3"/></g>'
            f'<g id="{i}_armR"><path d="M22 10 L40 -18" stroke="#fff" stroke-width="9" stroke-linecap="round"/><circle cx="41" cy="-21" r="8" fill="#fff" stroke="#2b2f36" stroke-width="3"/></g>'
            f'<path d="M-30 40h60" stroke="#2b2f36" stroke-width="5" stroke-linecap="round"/><path d="M-10 40v18M10 40v18" stroke="#2b2f36" stroke-width="5"/>')

def _fallsat(i):
    return (f'<g id="{i}_flame"><path d="M0 -10 C-40 -40 -30 -110 -10 -150 C0 -110 14 -100 10 -60 C30 -90 36 -120 30 -150 C60 -100 40 -40 0 -10Z" fill="#ff9f1a" opacity=".95"/>'
            f'<path d="M0 -14 C-18 -40 -14 -80 -4 -104 C4 -80 16 -70 12 -40 C18 -60 20 -70 18 -90 C32 -60 18 -36 0 -14Z" fill="#ffe66d"/></g>'
            f'<rect x="-22" y="-10" width="44" height="40" rx="7" fill="#c9ced6" stroke="#2b2f36" stroke-width="4"/>'
            f'<rect x="-66" y="0" width="38" height="22" rx="3" fill="#2a5bd7" stroke="#10223f" stroke-width="3"/><rect x="28" y="0" width="38" height="22" rx="3" fill="#2a5bd7" stroke="#10223f" stroke-width="3"/>'
            f'<circle cx="0" cy="-20" r="10" fill="#fff" stroke="#2b2f36" stroke-width="4"/>')

def _splash(i):
    return (f'<circle id="{i}_r1" r="40" fill="none" stroke="#fff" stroke-width="8" opacity=".95"/>'
            f'<circle id="{i}_r2" r="22" fill="rgba(255,255,255,.55)"/>')

def _person(i, shirt):
    return (f'<circle cx="0" cy="-58" r="24" fill="#f3c9a8" stroke="#2b2f36" stroke-width="5"/>'
            f'<path d="M-30 -20 h60 l-8 70 h-44z" fill="{shirt}" stroke="#2b2f36" stroke-width="5" stroke-linejoin="round"/>'
            f'<path d="M-18 50v46M18 50v46" stroke="#2b2f36" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M-28 -12 L-52 30" stroke="{shirt}" stroke-width="12" stroke-linecap="round"/>'
            f'<g id="{i}_arm"><path d="M28 -12 L50 -56" stroke="{shirt}" stroke-width="12" stroke-linecap="round"/><circle cx="53" cy="-62" r="10" fill="#f3c9a8" stroke="#2b2f36" stroke-width="4"/></g>'
            f'<g id="{i}_x" opacity="0"><path d="M-70 -90 L70 70 M70 -90 L-70 70" stroke="#e5322d" stroke-width="22" stroke-linecap="round"/></g>')

def _flag(i, cc):
    return (f'<path d="M-60 96 L-60 -96" stroke="#2b2f36" stroke-width="10" stroke-linecap="round"/><circle cx="-60" cy="-98" r="9" fill="#ffd400" stroke="#2b2f36" stroke-width="4"/>'
            f'<g id="{i}_cloth"><image href="assets/geo/flags/{cc.lower()}.svg" x="-56" y="-92" width="150" height="100" preserveAspectRatio="none"/>'
            f'<rect x="-56" y="-92" width="150" height="100" fill="none" stroke="#2b2f36" stroke-width="5"/></g>')

def _tag(i, text, color):
    t = html.escape(text, quote=False)
    return (f'<rect x="-90" y="-46" width="180" height="92" rx="20" fill="{color}" stroke="#1b1b1b" stroke-width="6"/>'
            f'<text class="tu" data-fc="skip" data-tq-dwell="off" x="0" y="22" text-anchor="middle" font-family="Barlow Condensed, Impact, sans-serif" font-weight="900" font-size="66" fill="#fff" stroke="#1b1b1b" stroke-width="2">{t}</text>')

def rig_html(el):
    """visuals.json element {id, type:'rig', rig, x, y, size, rot?, z?, shirt?, flag?, text?, color?}. Positioned with its CENTRE at (x,y)
    via negative margins (GSAP owns transform; the anchor device owns left/top)."""
    i, kind, size = el["id"], el["rig"], int(el.get("size", 200))
    body = {"sat": lambda: _sat(i), "fallsat": lambda: _fallsat(i), "splash": lambda: _splash(i),
            "person": lambda: _person(i, el.get("shirt", "#2a9d8f")), "flag": lambda: _flag(i, el["flag"]),
            "tag": lambda: _tag(i, el.get("text", "?"), el.get("color", "#e5322d"))}[kind]()
    vb = "-100 -160 200 260" if kind == "fallsat" else "-100 -100 200 200"
    h = int(size * 1.3) if kind == "fallsat" else size
    return (f'<svg id="{i}" class="prop3" data-rig="{kind}" style="left:{el.get("x", 540)}px;top:{el.get("y", 900)}px;width:{size}px;height:{h}px;margin-left:{-size // 2}px;margin-top:{-h // 2}px;'
            f'z-index:{el.get("z", 61)};--rot:{el.get("rot", 0)}deg" viewBox="{vb}" overflow="visible"{ALLOW}>{body}</svg>')

CSS = """
.v3 .prop3{position:absolute;overflow:visible;filter:drop-shadow(0 10px 16px rgba(0,0,0,.55));transform:rotate(var(--rot,0deg));visibility:hidden;opacity:0}
"""

# ---------------------------------------------------------------- devices
class Props:
    def __init__(self, J, stages): self.J, self.stages = J, stages      # stages: {stage_id: geo.Scene}

    def _scene(self, stage):
        sc = self.stages[stage]; return sc.id, sc.box[0], sc.box[1]

    def _put(self, eid, stage, lonlat, var="o"):
        """JS snippet: a put() closure moving #eid to lonlat (+var.dx/dy, scene px -> stage px)."""
        sid, bx, by = self._scene(stage)
        return (f"const el=document.getElementById('{eid}');const put=()=>{{if(!el||!window.GeoRT||!GeoRT.toScreen)return;const p=GeoRT.toScreen('{sid}',[{lonlat[0]},{lonlat[1]}]);if(!p)return;"
                f"el.style.left=({bx}+p[0]+{var}.dx)+'px';el.style.top=({by}+p[1]+{var}.dy)+'px';}};")

    def anchor(self, t0, t1, eid, stage, lonlat, dx=0, dy=0):
        self.J("{const o={dx:%s,dy:%s,k:0};%s tl.to(o,{k:1,duration:%s,ease:'none',onStart:put,onUpdate:put},%s);}" % (dx, dy, self._put(eid, stage, lonlat), f(max(0.05, t1 - t0)), f(t0)))

    def pop(self, t, eid, dur=0.45, frm="pop"):
        if frm == "rise": self.J(f"tl.fromTo('#{eid}',{{autoAlpha:0,scaleY:0.05,scaleX:0.7,transformOrigin:'50% 100%'}},{{autoAlpha:1,scaleY:1,scaleX:1,duration:{f(max(dur, 0.5))},ease:'back.out(1.7)',immediateRender:false}},{f(t)});")
        elif frm == "drop": self.J(f"tl.fromTo('#{eid}',{{autoAlpha:0,y:-160,scale:1.3}},{{autoAlpha:1,y:0,scale:1,duration:{f(dur)},ease:'bounce.out',immediateRender:false}},{f(t)});")
        else: self.J(f"tl.fromTo('#{eid}',{{autoAlpha:0,scale:0.2}},{{autoAlpha:1,scale:1,duration:{f(dur)},ease:'back.out(2)',immediateRender:false}},{f(t)});")

    def out(self, t, eid, dur=0.3):
        self.J(f"tl.to('#{eid}',{{autoAlpha:0,scale:0.6,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    def orbit(self, t0, t1, eid, stage, a, b, height=320, roll=10, dy=0):
        """Fly #eid from lonlat a to lonlat b along a parabolic arc (screen space, re-sampled each frame) and roll gently."""
        sid, bx, by = self._scene(stage)
        self.J("{const o={p:0};const el=document.getElementById('%s');const put=()=>{if(!el||!window.GeoRT||!GeoRT.toScreen)return;const A=GeoRT.toScreen('%s',[%s,%s]),B=GeoRT.toScreen('%s',[%s,%s]);if(!A||!B)return;"
               "const x=A[0]+(B[0]-A[0])*o.p,y=A[1]+(B[1]-A[1])*o.p-%s*Math.sin(Math.PI*o.p)+%s;el.style.left=(%s+x)+'px';el.style.top=(%s+y)+'px';};"
               "tl.to(o,{p:1,duration:%s,ease:'none',onStart:put,onUpdate:put},%s);}" % (eid, sid, a[0], a[1], sid, b[0], b[1], height, dy, bx, by, f(t1 - t0), f(t0)))
        if roll: self.J(f"tl.fromTo('#{eid}',{{rotation:{-roll}}},{{rotation:{roll},duration:{f((t1 - t0) / 2)},ease:'sine.inOut',yoyo:true,repeat:1,immediateRender:false}},{f(t0)});")

    def wave(self, t0, t1, eid, parts=("armL", "armR"), pivots=((-22, 10), (22, 10)), swing=28, period=0.5):
        n = max(1, int((t1 - t0) / (period / 2)))
        for part, (px, py) in zip(parts, pivots):
            self.J(f"tl.fromTo('#{eid}_{part}',{{rotation:{-swing},svgOrigin:'{px} {py}'}},{{rotation:{swing},duration:{f(period / 2)},ease:'sine.inOut',yoyo:true,repeat:{n - 1},immediateRender:false}},{f(t0)});")

    def hop(self, t0, t1, eid, lift=14, period=0.5):
        n = max(1, int((t1 - t0) / (period / 2)))
        self.J(f"tl.to('#{eid}',{{y:{-lift},duration:{f(period / 2)},ease:'sine.inOut',yoyo:true,repeat:{n - 1}}},{f(t0)});")

    def cross(self, t, eid, dur=0.35):
        self.J(f"tl.fromTo('#{eid}_x',{{opacity:0,scale:2.4,svgOrigin:'0 -10'}},{{opacity:1,scale:1,duration:{f(dur)},ease:'power3.in',immediateRender:false}},{f(t)});")
        self.J(f"tl.to('#{eid}',{{rotation:'+=8',duration:0.08,yoyo:true,repeat:3}},{f(t + dur)});")

    def flutter(self, t0, t1, eid, part="cloth", skew=7, period=0.7):
        n = max(1, int((t1 - t0) / (period / 2)))
        self.J(f"tl.fromTo('#{eid}_{part}',{{skewY:{-skew},scaleX:1,svgOrigin:'-56 -42'}},{{skewY:{skew},scaleX:0.94,duration:{f(period / 2)},ease:'sine.inOut',yoyo:true,repeat:{n - 1},immediateRender:false}},{f(t0)});")

    def fall(self, t, eid, stage, lonlat, dx=360, dy=-900, dur=1.1, splash=None, spin=50):
        """Re-entry: #eid streaks from (dx,dy) px away onto the lon/lat, flame on, shrinking as it comes down; at touchdown it
        vanishes and the splash rig (if given) rings out on the same spot."""
        self.J("{const o={dx:%s,dy:%s};%s tl.fromTo('#%s',{autoAlpha:0,scale:1.2,rotation:%s},{autoAlpha:1,duration:0.15,immediateRender:false},%s);"
               "tl.to('#%s',{scale:0.7,rotation:%s,duration:%s,ease:'power1.in'},%s);"
               "tl.to(o,{dx:0,dy:0,duration:%s,ease:'power1.in',onStart:put,onUpdate:put},%s);tl.to('#%s',{autoAlpha:0,scale:0.2,duration:0.12},%s);}"
               % (dx, dy, self._put(eid, stage, lonlat), eid, -spin, f(t), eid, -spin + 18, f(dur), f(t), f(dur), f(t), eid, f(t + dur)))
        self.J(f"tl.fromTo('#{eid}_flame',{{opacity:0.4,scaleY:0.5,svgOrigin:'0 -10'}},{{opacity:1,scaleY:1.15,duration:{f(dur * 0.5)},ease:'power1.out',immediateRender:false}},{f(t)});")
        if splash:
            self.anchor(t + dur - 0.02, t + dur + 0.9, splash, stage, lonlat)
            self.J(f"tl.fromTo('#{splash}',{{autoAlpha:1,scale:0.15}},{{autoAlpha:0,scale:1.8,duration:0.8,ease:'power2.out',immediateRender:false}},{f(t + dur)});")
            self.J(f"tl.fromTo('#{splash}_r2',{{scale:1,svgOrigin:'0 0'}},{{scale:0.1,duration:0.6,ease:'power2.out',immediateRender:false}},{f(t + dur)});")
