"""engine/charts.py — data graphics for the non-map series (Body & Brain, Sports Sprint, Wild Files, Cosmic, Time Vault).

All procedural (licence "own"), deterministic, text in `tu` units, numbers animated through GSAP proxy objects
(onUpdate writes textContent — the same pattern engine/geo.py uses for the camera, seek-safe).

    import charts
    CH = charts.Charts(J)
    body.append(CH.bars("b1", [("Cheetah", 112, "112 km/h"), ("Pronghorn", 88, "88 km/h")], y=300, unit="km/h"))
    CH.bars_in(t, "b1")                                     # bars grow, values count up
    body.append(CH.counter("c1", 0, 206, y=520, label="bones in an adult body", fmt="int")); CH.counter_run(t0, t1, "c1")
    body.append(CH.compare("s1", [("Blue whale", 30, "30 m"), ("Bus", 12, "12 m")], y=320, max_h=700)); CH.compare_in(t, "s1")
    body.append(CH.callouts("k1", "assets/brain.png", [(420, 300, "Frontal lobe"), ...], y=240)); CH.callouts_in(t, "k1")
    body.append(CH.strip("tl1", [(1896, "Athens"), (1924, "Paris")], y=900)); CH.strip_in(t, "tl1")
    CSS += charts.CSS
"""
import html

SAND, RED, CREAM, INK = "#E3A72F", "#C8102E", "#EFE6D2", "#0B1620"


def f(x): return f"{x:.3f}"
def esc(s): return html.escape(str(s))


class Charts:
    def __init__(self, J):
        self.J = J
        self.items = {}

    # ---------------------------------------------------------------- horizontal bars
    def bars(self, bid, rows, y=300, x=60, w=900, unit="", max_value=None, bar_h=74, gap=26):
        mx = max_value or max(r[1] for r in rows)
        self.items[bid] = {"rows": rows, "max": mx}
        out = [f'<div id="{bid}" class="chart bars" style="left:{x}px;top:{y}px;width:{w}px">']
        for i, (label, val, disp) in enumerate(rows):
            top = i * (bar_h + gap + 40)
            frac = max(0.04, val / mx)
            out.append(f'<div class="brow" style="top:{top}px"><div class="blabel tu">{esc(label)}</div>'
                       f'<div class="btrack"><div class="bfill" id="{bid}_f{i}" style="width:{frac * 100:.1f}%"></div></div>'
                       f'<div class="bval tu" id="{bid}_v{i}" data-tq-dwell="off">{esc(disp)}</div></div>')
        out.append("</div>")
        return "".join(out)

    def bars_in(self, t, bid, dur=0.9, stagger=0.18):
        rows = self.items[bid]["rows"]
        self.J(f"tl.fromTo('#{bid}',{{autoAlpha:0}},{{autoAlpha:1,duration:0.3,immediateRender:false}},{f(t)});")
        for i, (label, val, disp) in enumerate(rows):
            t0 = t + i * stagger
            self.J(f"tl.fromTo('#{bid}_f{i}',{{scaleX:0}},{{scaleX:1,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t0)});")
            self.J(f"tl.fromTo('#{bid}_v{i}',{{autoAlpha:0,x:-20}},{{autoAlpha:1,x:0,duration:0.3,immediateRender:false}},{f(t0 + dur * 0.55)});")

    # ---------------------------------------------------------------- big counter
    def counter(self, cid, start, end, y=520, label="", fmt="int", x=60, w=960, suffix="", size=190):
        self.items[cid] = {"start": start, "end": end, "fmt": fmt, "suffix": suffix}
        return (f'<div id="{cid}" class="chart counter" style="left:{x}px;top:{y}px;width:{w}px" data-layout-allow-overlap="true" data-layout-allow-caption-zone="true">'
                f'<div class="cnumber tu" id="{cid}_n" data-tq-dwell="off" data-layout-allow-overlap="true" data-layout-allow-occlusion="true" style="font-size:{int(size)}px">{self._fmt(start, fmt)}{esc(suffix)}</div>'
                + (f'<div class="clabel2 tu" data-layout-allow-overlap="true" data-layout-allow-occlusion="true">{esc(label)}</div>' if label else "") + "</div>")

    def counter_run(self, t0, t1, cid, ease="power2.out", steps=None):
        it = self.items[cid]
        fmt_js = {"int": "Math.round(v).toLocaleString('en-US')", "float1": "v.toFixed(1)", "float2": "v.toFixed(2)", "raw": "String(Math.round(v))"}[it["fmt"]]
        ease_s = f"steps({steps})" if steps else ease
        self.J(f"tl.fromTo('#{cid}',{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:0.3,immediateRender:false}},{f(t0 - 0.2)});")
        self.J(f"{{const o={{v:{it['start']}}},e=document.getElementById('{cid}_n');"
               f"tl.to(o,{{v:{it['end']},duration:{f(t1 - t0)},ease:'{ease_s}',onUpdate:()=>{{const v=o.v;e.textContent={fmt_js}+'{esc(it['suffix'])}';}}}},{f(t0)});}}")

    def out(self, t, cid, dur=0.3):
        """Hide any chart (counter/bars/compare/strip) — e.g. before a fact takes the same band."""
        self.J(f"tl.to('#{cid}',{{autoAlpha:0,y:-24,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    # ---------------------------------------------------------------- scale comparison (silhouette bars)
    def compare(self, sid, items, y=320, x=60, w=960, max_h=700, shapes=None):
        """items = [(label, value, display)], drawn as proportional blocks from a common baseline (height = value).
        shapes (optional) = {label: svg_path_d in a 100x100 box} for a silhouette instead of a block."""
        mx = max(v for _, v, _ in items)
        n = len(items); col = w / n
        self.items[sid] = {"items": items}
        out = [f'<div id="{sid}" class="chart compare" style="left:{x}px;top:{y}px;width:{w}px;height:{max_h + 120}px">']
        for i, (label, val, disp) in enumerate(items):
            h = max(12, max_h * val / mx); cx = i * col
            shape = (shapes or {}).get(label)
            body = (f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" style="width:{col - 40:.0f}px;height:{h:.0f}px"><path d="{shape}" fill="{SAND if i == 0 else CREAM}"/></svg>'
                    if shape else f'<div class="cblock" style="width:{col - 40:.0f}px;height:{h:.0f}px"></div>')
            out.append(f'<div class="ccol" id="{sid}_c{i}" style="left:{cx:.0f}px;width:{col:.0f}px;height:{max_h}px">'
                       f'<div class="cstack" id="{sid}_s{i}">{body}</div></div>'
                       f'<div class="cval tu" id="{sid}_v{i}" data-layout-allow-overlap="true" style="left:{cx:.0f}px;width:{col:.0f}px;top:{max_h + 8}px">{esc(disp)}</div>'
                       f'<div class="clab tu" data-layout-allow-overlap="true" style="left:{cx:.0f}px;width:{col:.0f}px;top:{max_h + 62}px">{esc(label)}</div>')
        out.append(f'<div class="cbase" style="top:{max_h}px;width:{w}px"></div></div>')
        return "".join(out)

    def compare_in(self, t, sid, dur=0.8, stagger=0.2):
        n = len(self.items[sid]["items"])
        self.J(f"tl.fromTo('#{sid}',{{autoAlpha:0}},{{autoAlpha:1,duration:0.3,immediateRender:false}},{f(t)});")
        for i in range(n):
            self.J(f"tl.fromTo('#{sid}_s{i}',{{scaleY:0}},{{scaleY:1,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t + i * stagger)});")
            self.J(f"tl.fromTo('#{sid}_v{i}',{{autoAlpha:0,y:10}},{{autoAlpha:1,y:0,duration:0.3,immediateRender:false}},{f(t + i * stagger + dur * 0.6)});")

    # ---------------------------------------------------------------- image + callouts (anatomy, equipment)
    def callouts(self, kid, image, points, y=240, x=0, w=1080, h=940, img_style=""):
        """points = [(px, py, text, side)] in the image box's pixel space; side 'l'|'r' puts the label plate left/right."""
        self.items[kid] = {"points": points}
        out = [f'<div id="{kid}" class="chart callouts" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
               f'<img src="{esc(image)}" style="position:absolute;left:0;top:0;width:{w}px;height:{h}px;object-fit:contain;{img_style}">'
               f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="position:absolute;left:0;top:0">']
        for i, p in enumerate(points):
            px, py, text = p[0], p[1], p[2]; side = p[3] if len(p) > 3 else ("l" if px < w / 2 else "r")
            lx = 70 if side == "l" else w - 70
            out.append(f'<line id="{kid}_l{i}" x1="{px}" y1="{py}" x2="{lx}" y2="{py}" stroke="{CREAM}" stroke-width="3"/>'
                       f'<circle id="{kid}_d{i}" cx="{px}" cy="{py}" r="10" fill="{RED}" stroke="{CREAM}" stroke-width="3"/>')
        out.append("</svg>")
        for i, p in enumerate(points):
            px, py, text = p[0], p[1], p[2]; side = p[3] if len(p) > 3 else ("l" if px < w / 2 else "r")
            style = f"left:40px;top:{py - 30}px" if side == "l" else f"right:40px;top:{py - 30}px;left:auto"
            out.append(f'<div class="kplate tu" id="{kid}_p{i}" style="{style}">{esc(text)}</div>')
        out.append("</div>")
        return "".join(out)

    def callouts_in(self, t, kid, stagger=0.35):
        for i in range(len(self.items[kid]["points"])):
            t0 = t + i * stagger
            self.J(f"tl.fromTo('#{kid}_d{i}',{{scale:0,transformOrigin:'50% 50%'}},{{scale:1,duration:0.25,ease:'back.out(3)',immediateRender:false}},{f(t0)});")
            self.J(f"tl.fromTo('#{kid}_l{i}',{{opacity:0}},{{opacity:1,duration:0.25,immediateRender:false}},{f(t0 + 0.1)});")
            self.J(f"tl.fromTo('#{kid}_p{i}',{{autoAlpha:0,x:0}},{{autoAlpha:1,duration:0.3,ease:'power2.out',immediateRender:false}},{f(t0 + 0.2)});")

    # ---------------------------------------------------------------- timeline strip (Time Vault / records history)
    def strip(self, tid, events, y=900, x=60, w=960):
        self.items[tid] = {"events": events}
        n = len(events); step = (w - 120) / max(1, n - 1)
        out = [f'<div id="{tid}" class="chart strip" style="left:{x}px;top:{y}px;width:{w}px"><div class="sline" id="{tid}_line"></div>']
        for i, (year, label) in enumerate(events):
            cx = 60 + i * step
            out.append(f'<div class="snode" id="{tid}_n{i}" style="left:{cx:.0f}px"><div class="sdot"></div>'
                       f'<div class="syear tu">{esc(year)}</div><div class="slab tu">{esc(label)}</div></div>')
        out.append("</div>")
        return "".join(out)

    def strip_in(self, t, tid, stagger=0.3):
        self.J(f"tl.fromTo('#{tid}',{{autoAlpha:0}},{{autoAlpha:1,duration:0.2,immediateRender:false}},{f(t)});")
        self.J(f"tl.fromTo('#{tid}_line',{{scaleX:0}},{{scaleX:1,duration:{f(stagger * len(self.items[tid]['events']))},ease:'none',immediateRender:false}},{f(t)});")
        for i in range(len(self.items[tid]["events"])):
            self.J(f"tl.fromTo('#{tid}_n{i}',{{autoAlpha:0,y:16}},{{autoAlpha:1,y:0,duration:0.3,ease:'power2.out',immediateRender:false}},{f(t + i * stagger)});")

    @staticmethod
    def _fmt(v, fmt):
        return {"int": f"{int(round(v)):,}", "float1": f"{v:.1f}", "float2": f"{v:.2f}", "raw": str(int(round(v)))}[fmt]


CSS = f"""
.chart{{position:absolute;z-index:40;visibility:hidden;opacity:0}}
.bars .brow{{position:absolute;left:0;width:100%;height:120px}}
.bars .blabel{{font-family:'Oswald';font-weight:600;font-size:34px;letter-spacing:.06em;color:{CREAM};margin-bottom:8px}}
.bars .btrack{{position:relative;height:74px;background:rgba(239,230,210,.12);border-radius:8px;overflow:hidden}}
.bars .bfill{{position:absolute;left:0;top:0;height:74px;background:{SAND};transform-origin:0 50%;border-radius:8px}}
.bars .brow:first-child .bfill{{background:{RED}}}
.bars .bval{{position:absolute;right:18px;top:48px;font-family:'Anton';font-size:44px;color:{CREAM};text-shadow:0 2px 8px rgba(0,0,0,.6)}}
.counter{{text-align:center;background:rgba(11,22,32,.72);border-radius:18px;padding:14px 20px 18px;box-shadow:0 12px 40px rgba(0,0,0,.35)}}   /* legible over a map */
.cnumber{{font-family:'Anton';font-size:190px;line-height:1;color:{SAND};text-shadow:0 10px 40px rgba(0,0,0,.5)}}
.clabel2{{font-family:'Oswald';font-weight:500;font-size:42px;letter-spacing:.1em;text-transform:uppercase;color:{CREAM};margin-top:10px}}
.v3 .counter{{background:none;padding:0;box-shadow:none}}
.v3 .cnumber{{font-family:'Anton';line-height:1.3;color:#FFD400;letter-spacing:.01em;text-shadow:0 4px 0 #1b1b1b,0 12px 36px rgba(0,0,0,.55)}}
.v3 .clabel2{{font-family:'Anton';font-weight:400;font-size:56px;letter-spacing:.04em;color:#fff;margin-top:2px;text-shadow:0 3px 0 #1b1b1b,0 10px 30px rgba(0,0,0,.5)}}
.compare .ccol{{position:absolute;top:0;display:flex;align-items:flex-end;justify-content:center}}
.compare .cstack{{transform-origin:50% 100%}}
.compare .cblock{{background:{SAND};border-radius:10px 10px 0 0;opacity:.9}}
.compare .ccol:not(:first-of-type) .cblock{{background:{CREAM}}}
.compare .cbase{{position:absolute;left:0;height:4px;background:{CREAM}}}
.compare .cval{{position:absolute;text-align:center;font-family:'Anton';font-size:48px;color:{SAND};visibility:hidden;opacity:0}}
.compare .clab{{position:absolute;text-align:center;font-family:'Oswald';font-weight:500;font-size:32px;letter-spacing:.08em;text-transform:uppercase;color:{CREAM}}}
.callouts .kplate{{position:absolute;font-family:'Oswald';font-weight:600;font-size:34px;color:{INK};background:{CREAM};padding:8px 18px 6px;border-left:8px solid {RED};white-space:nowrap;visibility:hidden;opacity:0}}
.strip .sline{{position:absolute;left:60px;right:60px;top:20px;height:6px;background:{CREAM};transform-origin:0 50%}}
.strip .snode{{position:absolute;top:0;width:0;visibility:hidden;opacity:0}}
.strip .sdot{{position:absolute;left:-14px;top:9px;width:28px;height:28px;border-radius:50%;background:{RED};border:4px solid {CREAM}}}
.strip .syear{{position:absolute;left:-90px;top:56px;width:180px;text-align:center;font-family:'Anton';font-size:40px;color:{SAND}}}
.strip .slab{{position:absolute;left:-110px;top:108px;width:220px;text-align:center;font-family:'Oswald';font-size:28px;line-height:1.15;color:{CREAM}}}
"""
