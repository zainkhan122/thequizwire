"""engine/geo.py — vector map scenes for HyperFrames builds (Python -> HTML/CSS/GSAP strings, runtime = geo-runtime.js).

Usage in an episode build.py (see series/_template/build.py):
    sys.path.insert(0, str(REPO / "engine")); import geo
    G = geo.Geo(J, HF, REPO)                                   # J = js-line appender; copies the runtime into HF
    m = G.scene("s03", GEO["scenes"]["s03"], box=(0, 230, 1080, 1100), z=10)   # spec straight from geo.json
    body.append(m.html())                                      # <div> + inline data + mount script (runs at load)
    m.cam_set(0, k=1)                                          # camera keyframes (flat: zoom k about a lon/lat or bbox)
    m.cam_to(t0, t1, k=3.2, lonlat=[73.05, 33.69])             #   -> single GSAP proxy tween, labels stay unscaled
    m.pin_in(t, "isb"); m.label_in(t, "arab"); m.highlight_in(t, "356"); m.route_draw(t0, t1, "r1")
    m.disputed_in(t, "kashmir")                                # dashed line + "Administered by / Claimed by" plates
    m.spin(t0, t1, lon=-20, lat=-25)                           # globe only (orthographic): rotate to a lon/lat
    CSS += geo.CSS; HEAD += geo.head_scripts()

geo.json is the SSOT for every map beat (geolint reads it): scenes[sid] = {projection, fit, layers, pins, labels,
routes, disputed, scalebar, source, anchor}. Data for a scene comes from HF/assets/geo/<sid>.json when geodata.py has
prepared it (Natural Earth 10m/50m clipped to the scene bbox) and falls back to the vendored world-atlas 110m so a
sandbox preview never blocks on a download (the fallback is flagged in meta so geolint can refuse it for release).

Rules honoured: one paused timeline; fromTo has immediateRender:false; hidden elements get autoAlpha; no Date/random.
"""
import json, html, shutil
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
VENDOR = ["d3-array.min.js", "d3-geo.min.js", "topojson-client.min.js"]
RUNTIME = "geo-runtime.js"
STUTTER_FPS = 12          # map-animation-skills doctrine: pins/labels pop on a 12 fps grid, camera moves stay smooth

# palette (plan §2): sea / land / sand / red / cream
SEA, LAND, SAND, RED, CREAM, INK, CYAN = "#0F2A3A", "#1D3A4A", "#E3A72F", "#C8102E", "#EFE6D2", "#0B1620", "#4FD1E0"


def f(x): return f"{x:.3f}"


def head_scripts():
    return "".join(f'<script src="{v}"></script>' for v in VENDOR) + f'<script src="{RUNTIME}"></script>'


def _inline_json(obj):
    # inline JSON inside <script type=application/json>: only "</" needs escaping
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


class Geo:
    def __init__(self, J, hf, repo, data_dir=None):
        self.J, self.hf, self.repo = J, Path(hf), Path(repo)
        self.data_dir = Path(data_dir) if data_dir else self.hf / "assets" / "geo"
        self.scenes = {}
        self.hf.mkdir(parents=True, exist_ok=True)
        for v in VENDOR + [RUNTIME]:
            src = ENGINE / "vendor" / v if v != RUNTIME else ENGINE / RUNTIME
            shutil.copy(src, self.hf / v)

    def scene(self, sid, spec, box=(0, 230, 1080, 1100), z=10, anchor=None):
        s = Scene(self, sid, spec, box, z, anchor)
        self.scenes[sid] = s
        return s

    def credits(self):
        """On-screen data credit line (geolint requires it whenever a map scene exists)."""
        srcs = {"Natural Earth"}
        for s in self.scenes.values():
            srcs.update(s.sources)
        return " · ".join(sorted(srcs, key=lambda x: (x != "Natural Earth", x)))


class Scene:
    def __init__(self, G, sid, spec, box, z, anchor):
        self.G, self.sid, self.box, self.z = G, sid, box, z
        self.id = f"geo_{sid}"
        self.spec = {**spec}
        self.spec["w"], self.spec["h"] = box[2], box[3]
        self.spec["anchor"] = anchor or spec.get("anchor") or [box[2] / 2, box[3] * 0.5]
        self.spec.setdefault("layers", [{"kind": "land"}, {"kind": "borders"}])
        self.sources = set(spec.get("sources", []))
        self.data, self.data_quality = self._load_data()
        self._lengths = {}

    # ---------------------------------------------------------------- data
    def _load_data(self):
        p = self.G.data_dir / f"{self.sid}.json"
        if p.exists():
            d = json.loads(p.read_text()); self.sources.update(d.get("sources", []))
            if d.get("basemap"):                                            # v3 raster: ship it with the build, reference it relative to index.html
                src = self.G.data_dir / d["basemap"]["src"]; dst = self.G.hf / "assets" / "geo" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.exists() and (not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime): shutil.copy(src, dst)
                d["basemap"]["src"] = f"assets/geo/{src.name}"
            for cc, rel in list((d.get("flags") or {}).items()):          # flag-icons SVGs used by lifts / characters
                src = self.G.data_dir / rel; dst = self.G.hf / "assets" / "geo" / "flags" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.exists() and not dst.exists(): shutil.copy(src, dst)
                d["flags"][cc] = f"assets/geo/flags/{src.name}"
            return d, d.get("quality", "scene")
        # preview fallback: vendored world-atlas 110m (Natural Earth, public domain)
        topo = json.loads((ENGINE / "data" / "countries-110m.json").read_text())
        geo = {}
        for L in self.spec.get("layers", []):
            if L.get("source") and L.get("source") in self.spec.get("geo", {}):
                geo[L["source"]] = self.spec["geo"][L["source"]]
        return {"topo": topo, "geo": {**geo, **self.spec.get("geo", {})}}, "preview-110m"

    # ---------------------------------------------------------------- html
    def html(self):
        x, y, w, h = self.box
        data_id = f"{self.id}_data"
        spec_js = _inline_json({k: v for k, v in self.spec.items() if k not in ("geo",)})
        spec_id = f"{self.id}_spec"     # JSON (not a JS literal) so factcheck/geolint can read every run-time label without a browser
        return (f'<div id="{self.id}" class="geo" data-quality="{self.data_quality}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;z-index:{self.z}"></div>'
                f'<script type="application/json" id="{spec_id}">{spec_js}</script>'
                f'<script type="application/json" id="{data_id}">{_inline_json(self.data)}</script>'
                f'<script>GeoRT.mount("{self.id}", JSON.parse(document.getElementById("{spec_id}").textContent), JSON.parse(document.getElementById("{data_id}").textContent));</script>')

    # ---------------------------------------------------------------- camera
    def _cam_vars(self, k=None, lonlat=None, bbox=None, xy=None, lon=None, lat=None, ease="power2.inOut", dur=0.0, fit_pad=None):
        v = {"duration": round(dur, 3), "ease": ease}
        if k is not None: v["k"] = k
        if lonlat is not None: v["lonlat"] = lonlat
        if bbox is not None: v["bbox"] = bbox
        if xy is not None: v["xy"] = xy
        if lon is not None: v["lon"] = lon
        if lat is not None: v["lat"] = lat
        if fit_pad is not None: v["fitPad"] = fit_pad
        return json.dumps(v)

    def cam_set(self, t, **kw):
        """Instant camera state at time t (use at scene start)."""
        self.G.J(f"tl.set(GeoRT.cam('{self.id}'), GeoRT.camTarget('{self.id}', {self._cam_vars(dur=0, **kw)}), {f(t)});")

    def cam_to(self, t0, t1, **kw):
        """Smooth camera move t0->t1 (k = zoom factor about the anchor; lonlat|bbox|xy = focus). Globe: lonlat rotates to it."""
        self.G.J(f"tl.to(GeoRT.cam('{self.id}'), GeoRT.camTarget('{self.id}', {self._cam_vars(dur=t1 - t0, **kw)}), {f(t0)});")

    def spin(self, t0, t1, lon, lat=None, k=None, ease="power1.inOut"):
        """Globe rotation (orthographic): bring lon/lat (degrees) to the centre."""
        self.cam_to(t0, t1, lonlat=[lon, lat if lat is not None else 0], k=k, ease=ease)

    # ---------------------------------------------------------------- beats
    def _steps(self, dur): return f"steps({max(1, round(dur * STUTTER_FPS))})"

    def pin_in(self, t, pid, dur=0.35, stutter=True):
        ease = self._steps(dur) if stutter else "back.out(2.2)"
        self.G.J(f"tl.fromTo('#{self.id}_pin_{pid}',{{autoAlpha:0,scale:0.2}},{{autoAlpha:1,scale:1,duration:{f(dur)},ease:'{ease}',immediateRender:false}},{f(t)});")

    def pin_out(self, t, pid, dur=0.2):
        self.G.J(f"tl.to('#{self.id}_pin_{pid}',{{autoAlpha:0,duration:{f(dur)},ease:'power1.in'}},{f(t)});")

    def label_in(self, t, lid, dur=0.3, stutter=True):
        ease = self._steps(dur) if stutter else "power2.out"
        self.G.J(f"tl.fromTo('#{self.id}_lbl_{lid}',{{autoAlpha:0,y:12}},{{autoAlpha:1,y:0,duration:{f(dur)},ease:'{ease}',immediateRender:false}},{f(t)});")

    def label_out(self, t, lid, dur=0.2):
        self.G.J(f"tl.to('#{self.id}_lbl_{lid}',{{autoAlpha:0,duration:{f(dur)},ease:'power1.in'}},{f(t)});")

    def _layer(self, lid):
        for L in self.spec.get("layers", []):
            if (L.get("id") or L.get("kind")) == lid: return L
        return {}

    def highlight_in(self, t, fid, dur=0.5, layer="highlight", opacity=1):
        """Fade a per-feature layer path in (highlight_<id>); CSS sets the colours. Lifted layers (v3 `lift`) pop in with a scale."""
        sel = f"#{self.id}_{layer}_{fid}"
        if self._layer(layer).get("lift"):
            self.G.J(f"tl.fromTo('{sel}',{{opacity:0,scale:0.86,svgOrigin:GeoRT.centroid('{self.id}','{layer}_{fid}')}},{{opacity:1,scale:1,duration:{f(max(dur, 0.45))},ease:'back.out(1.6)',immediateRender:false}},{f(t)});")   # lifts are always solid
            return
        self.G.J(f"tl.fromTo('{sel}',{{opacity:0}},{{opacity:{opacity},duration:{f(dur)},ease:'power2.out',immediateRender:false}},{f(t)});")

    def highlight_out(self, t, fid, dur=0.4, layer="highlight"):
        self.G.J(f"tl.to('#{self.id}_{layer}_{fid}',{{opacity:0,duration:{f(dur)},ease:'power1.in'}},{f(t)});")

    def route_out(self, t, rid, dur=0.4, layer="route"):
        self.G.J(f"tl.to('#{self.id}_{layer}_{rid}',{{opacity:0,duration:{f(dur)},ease:'power1.in'}},{f(t)});")

    def clear(self, t, dur=0.5):
        """Loop-frame reset (Plan v2 Q12): fade every per-feature highlight/route path, pin and label of this scene (scalebar stays),
        so the last frame matches the first. Policy plates (disputed) are kept — they must stay while the border is on screen."""
        for L in self.spec.get("layers", []):
            kind = L.get("kind")
            if kind not in ("highlight", "route", "area", "feature"): continue
            lid = L.get("id") or kind
            fids = [str(x) for x in (L.get("ids") or [])]
            gj = L.get("geojson") or {}
            fids += [str(ft.get("id", i)) for i, ft in enumerate(gj.get("features", []))] if gj else []
            if L.get("perFeature") is False or not fids:
                self.G.J(f"tl.to('#{self.id}_{lid}',{{opacity:0,duration:{f(dur)},ease:'power1.in'}},{f(t)});")
            for fid in fids:
                self.G.J(f"tl.to('#{self.id}_{lid}_{fid}',{{opacity:0,duration:{f(dur)},ease:'power1.in'}},{f(t)});")
        for p in self.spec.get("pins", []): self.pin_out(t, p["id"], dur=dur)
        for L in self.spec.get("labels", []):
            if not L.get("for"): self.label_out(t, L["id"], dur=dur)

    def highlight_pulse(self, t, fid, dur=1.2, layer="highlight"):
        if self._layer(layer).get("lift"):                                  # lifted shapes pulse in size, not opacity
            self.G.J(f"tl.fromTo('#{self.id}_{layer}_{fid}',{{scale:1,svgOrigin:GeoRT.centroid('{self.id}','{layer}_{fid}')}},{{scale:1.05,duration:{f(dur / 2)},ease:'sine.inOut',yoyo:true,repeat:1,immediateRender:false}},{f(t)});")
            return
        self.G.J(f"tl.fromTo('#{self.id}_{layer}_{fid}',{{opacity:0.55}},{{opacity:1,duration:{f(dur / 2)},ease:'sine.inOut',yoyo:true,repeat:1,immediateRender:false}},{f(t)});")

    def route_draw(self, t0, t1, rid, layer="route"):
        """Draw-on for a route/line layer path via stroke-dash (length measured in the browser at load)."""
        sel = f"#{self.id}_{layer}_{rid}"
        self.G.J(f"{{const L=GeoRT.pathLength('{self.id}','{layer}_{rid}')||4000;"
                 f"tl.fromTo('{sel}',{{strokeDasharray:L,strokeDashoffset:L,opacity:1}},{{strokeDashoffset:0,duration:{f(t1 - t0)},ease:'power1.inOut',immediateRender:false}},{f(t0)});}}")

    def disputed_in(self, t, did, dur=0.4):
        """Disputed boundary/area: dashed line fades in, then its policy plates (controller / claimants) pop.
        The plates are `labels` entries in geo.json (geolint requires one per disputed feature, see docs/BORDER_POLICY.md)."""
        self.G.J(f"tl.fromTo('#{self.id}_disputed_{did}',{{opacity:0}},{{opacity:1,duration:{f(dur)},ease:'power2.out',immediateRender:false}},{f(t)});")
        for L in self.spec.get("labels", []):
            if L.get("for") == did:
                self.label_in(t + 0.25, L["id"])

    def scalebar_in(self, t, dur=0.3):
        self.G.J(f"tl.fromTo('#{self.id}_scale',{{autoAlpha:0}},{{autoAlpha:1,duration:{f(dur)},immediateRender:false}},{f(t)});")

    def fade(self, t0, t1, to=0.0):
        self.G.J(f"tl.to('#{self.id}',{{opacity:{to},duration:{f(t1 - t0)},ease:'power1.inOut'}},{f(t0)});")


CSS = f"""
.geo{{position:absolute;overflow:hidden;background:{SEA}}}
.geo .geo-svg{{position:absolute;left:0;top:0}}
.geo .geo-ui{{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}}
.geo .g-sphere{{fill:{SEA};stroke:none}}
.geo .g-grat{{fill:none;stroke:rgba(239,230,210,.14);stroke-width:1}}
.geo .g-land{{fill:{LAND};stroke:none}}
.geo.has-basemap .g-land,.geo.has-basemap .g-countries{{fill:none}}                    /* v3: the raster is the land */
.geo.has-basemap .g-border{{stroke:rgba(255,255,255,.55);stroke-width:1.4}}
.geo.has-basemap .geo-basemap{{image-rendering:auto}}
.geo .g-countries{{fill:{LAND};stroke:none}}
.geo .g-border{{fill:none;stroke:rgba(239,230,210,.38);stroke-width:1.2;stroke-linejoin:round}}
.geo .g-highlight{{fill:{SAND};stroke:{CREAM};stroke-width:1.6;opacity:0}}
.geo .g-lift{{opacity:0}}                                                            /* v3 lifted highlight: shadow + flag/colour + white outline */
.geo .g-lift .lift-shadow{{fill:#ffffff}}
.geo .g-lift .lift-fill{{stroke:none}}
.geo .g-lift .lift-outline{{fill:none;stroke:#ffffff;stroke-width:7;stroke-linejoin:round}}
.geo .g-highlight.alt{{fill:{RED}}}
.geo .g-area{{fill:rgba(227,167,47,.35);stroke:{SAND};stroke-width:1.4}}
.geo .g-feature{{fill:none;stroke:{CREAM};stroke-width:2}}
.geo .g-feature.faint{{stroke:rgba(239,230,210,.32);stroke-width:1.2;stroke-dasharray:6 5}}
.geo .g-route{{fill:none;stroke:{SAND};stroke-width:4;stroke-linecap:round;opacity:0}}
.geo .g-route.river{{stroke:{CYAN};stroke-width:5;stroke-linejoin:round}}   /* rivers read over a sand highlight */
.geo .g-disputed{{fill:none;stroke:{CREAM};stroke-width:3;stroke-dasharray:10 8;stroke-linecap:round;opacity:0}}
.geo .g-disputed.area{{fill:rgba(239,230,210,.16);stroke-width:2}}
.geo .geo-pin{{position:absolute;width:0;height:0;transform-origin:0 0}}
.geo .geo-pin .pinhead{{position:absolute;left:-13px;top:-13px;width:26px;height:26px;border-radius:50%;background:{RED};border:4px solid {CREAM};box-shadow:0 4px 14px rgba(0,0,0,.45)}}
.geo .geo-pin .pinlabel{{position:absolute;left:22px;top:-24px;white-space:nowrap;font-family:'Oswald';font-weight:600;font-size:36px;letter-spacing:.04em;color:{CREAM};background:{INK};padding:4px 14px 2px;border-left:6px solid {RED}}}
.geo .geo-pin.left .pinlabel{{left:auto;right:22px;border-left:0;border-right:6px solid {RED}}}   /* pins {{"side": "left"}}: label runs west of the head (avoids a neighbour to the east) */
.geo .geo-pin.back,.geo .geo-label.back{{visibility:hidden!important}}
.geo .geo-label{{position:absolute;width:0;height:0}}
.geo .geo-label .lbl,.geo .geo-label>span{{position:absolute;left:0;top:0;transform:translate(-50%,-50%);white-space:nowrap}}
.geo .geo-label.al>span{{transform:translate(0,-50%)}}      /* cls "al": label starts at the anchor (runs east) */
.geo .geo-label.ar>span{{transform:translate(-100%,-50%)}}  /* cls "ar": label ends at the anchor (runs west)  */
.geo .geo-label{{font-family:'Oswald';font-weight:500;font-size:30px;letter-spacing:.14em;text-transform:uppercase;color:rgba(239,230,210,.85)}}
.geo .geo-label.ink{{color:{INK};opacity:1;text-shadow:none}}   /* plain label over a sand highlight */
.geo .geo-label.sea{{font-style:italic;font-family:'DM Serif';text-transform:none;letter-spacing:.06em;font-size:32px;color:rgba(239,230,210,.7)}}
.geo .geo-label.policy{{text-transform:none;letter-spacing:.02em;font-size:30px;line-height:1.15;color:{CREAM}}}
.geo .geo-label.policy .plate{{position:absolute;left:0;top:0;transform:translate(-50%,-50%);white-space:normal;width:max-content;max-width:520px;background:rgba(11,22,32,.92);border:2px solid {CREAM};padding:10px 18px 8px;text-align:left}}   /* long controller strings wrap instead of running into the right-hand UI column */
.geo .geo-label.policy .plate b{{display:block;font-weight:700;color:{SAND};font-size:26px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:2px}}
.geo .geo-label.policy .plate i{{display:block;font-style:normal;color:rgba(239,230,210,.8);font-size:26px;margin-top:4px}}
.geo .geo-label.policy.small{{font-size:22px}}                                  /* continental scale: plate_cls "small" */
.geo .geo-label.policy.small .plate{{max-width:380px;padding:8px 12px 6px}}
.geo .geo-label.policy.small .plate b{{font-size:20px}} .geo .geo-label.policy.small .plate i{{font-size:19px}}
.geo .geo-scale{{position:absolute;left:40px;bottom:36px;font-family:'Oswald';font-size:24px;letter-spacing:.08em;color:{CREAM};visibility:hidden;opacity:0;background:rgba(11,22,32,.72);padding:6px 10px 4px;border-radius:6px}}   /* readable over a sand highlight (textqa contrast) */
.geo .geo-scale span{{display:block;line-height:36px;height:36px;white-space:nowrap}}   /* HF text_box_overflow: the tight global line-height clipped the 24-px text */
.geo .geo-scale .bar{{height:8px;background:{CREAM};border-left:3px solid {CREAM};border-right:3px solid {CREAM};margin-bottom:6px}}
"""


def policy_label_html(name, controller, claimants, note=""):
    """Disputed-border plate text per docs/BORDER_POLICY.md: name · Administered by X · Claimed by Y, Z (· note)."""
    cl = ", ".join(claimants) if isinstance(claimants, (list, tuple)) else str(claimants)
    al = 'data-layout-allow-overlap="true" data-layout-allow-occlusion="true"'
    extra = f"<i {al}>{html.escape(note)}</i>" if note else ""
    return (f'<div class="plate" {al}><b {al}>{html.escape(name)}</b><span {al}>Administered by {html.escape(controller)}'
            f'<br>Claimed by {html.escape(cl)}</span>{extra}</div>')


def policy_labels(disputed):
    """geo.json `disputed` entries -> `labels` entries (id = pl_<id>, for = <id>) ready for the scene spec."""
    out = []
    for d in disputed:
        if d.get("plate") is False: continue                      # outline only; its policy text lives on the plate named in `plate_group`
        out.append({"id": f"pl_{d['id']}", "for": d["id"], "lonlat": d["label_at"], "cls": ("policy " + d["plate_cls"]).strip() if d.get("plate_cls") else "policy",
                    "html": policy_label_html(d["name"], d["controller"], d["claimants"], d.get("note", ""))})
    return out
