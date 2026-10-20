#!/usr/bin/env python3
"""reelkit/geodata.py — map data for an episode's geo.json scenes (Natural Earth, public domain). Stdlib only.

    python3 reelkit/geodata.py fetch [--res 50m,10m]        download sources into ~/.cache/geodata (CI caches the dir)
    python3 reelkit/geodata.py prep <ep> [--out DIR]        per scene: TopoJSON filtered to the scene + disputed features
                                                            -> DIR/<scene>.json (default ~/.cache/build/<ep>/geo), and
                                                            `generated` provenance entries in <ep>/media.json
    python3 reelkit/geodata.py disputed [substring]         list Natural Earth disputed areas (BRK_NAME · ADMIN · NOTE_BRK)
    python3 reelkit/geodata.py check <ep>                   offline: every disputed/ids reference in geo.json resolves

Design (plan §3): scene data is a pure function of geo.json + the pinned Natural Earth release, so it is NOT stored in
git or the media release — CI rebuilds it in seconds (`episode.sh geo`). The sandbox falls back to the vendored 110m
atlas (engine/data) for previews; geolint refuses that quality for a release build.

Sources (all public domain, credit "Natural Earth" on screen):
  world-atlas 2.0.2 (TopoJSON of Natural Earth 1:110m/50m/10m) via jsDelivr, fallback npm tarball
  Natural Earth 10m admin-0 disputed areas + disputed boundary lines (GeoJSON from nvkelso/natural-earth-vector)
"""
import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("GEODATA_CACHE", Path.home() / ".cache/geodata"))
WORLD_ATLAS_VER = "2.0.2"
RES_FILES = {"110m": ["countries-110m.json", "land-110m.json"], "50m": ["countries-50m.json", "land-50m.json"], "10m": ["countries-10m.json", "land-10m.json"]}
WA_URLS = [f"https://cdn.jsdelivr.net/npm/world-atlas@{WORLD_ATLAS_VER}/{{f}}", f"https://unpkg.com/world-atlas@{WORLD_ATLAS_VER}/{{f}}"]
NE_RAW = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{f}.geojson"
US_ATLAS_VER = "3.0.1"                                   # admin-1 for the USA: Census Bureau cartographic boundaries (ISC-licensed TopoJSON)
EXTRA_ATLASES = {"us-states": {"file": "states-10m.json", "object": "states", "pkg": "us-atlas", "ver": US_ATLAS_VER, "credit": "US Census Bureau",
                               "licence": "ISC", "urls": [f"https://cdn.jsdelivr.net/npm/us-atlas@{US_ATLAS_VER}/{{f}}", f"https://unpkg.com/us-atlas@{US_ATLAS_VER}/{{f}}"]}}
NE_FILES = ["ne_10m_admin_0_disputed_areas", "ne_10m_admin_0_boundary_lines_disputed_areas"]
ENGINE_DATA = Path(__file__).resolve().parents[1] / "engine" / "data"
SOURCES = {"natural-earth": {"name": "Natural Earth", "licence": "PD", "url": "https://www.naturalearthdata.com/about/terms-of-use/"},
           "world-atlas": {"name": "world-atlas (TopoJSON of Natural Earth)", "licence": "ISC", "url": f"https://www.npmjs.com/package/world-atlas/v/{WORLD_ATLAS_VER}"}}


def fetch(url, dst, tries=3):
    dst.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "quizwire-geodata/1"}), timeout=120) as r, open(dst, "wb") as f:
                f.write(r.read())
            return dst
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(2 + 3 * i)
    raise SystemExit(f"geodata: download failed {url}: {err}")


def atlas_path(res, kind="countries"):
    fn = f"{kind}-{res}.json"
    if res == "110m" and (ENGINE_DATA / fn).exists(): return ENGINE_DATA / fn
    p = CACHE / "world-atlas" / fn
    if not p.exists():
        for u in WA_URLS:
            try: fetch(u.format(f=fn), p); break
            except SystemExit: continue
        if not p.exists(): sys.exit(f"geodata: could not fetch {fn} — run `geodata.py fetch` with network")
    return p


def ne_path(name):
    p = CACHE / "natural-earth" / f"{name}.geojson"
    if not p.exists(): fetch(NE_RAW.format(f=name), p)
    return p


def cmd_fetch(a):
    for res in ("110m,50m,10m" if a.all else a.res).split(","):
        for kind in ("countries", "land"): print("  ✓", atlas_path(res, kind))
    for n in NE_FILES: print("  ✓", ne_path(n))


def _slug(x):
    return re.sub(r"[^a-z0-9]+", "_", str(x).lower()).strip("_")


def ne_features(spec_ne):
    """Pull named features out of any Natural Earth GeoJSON (PD) into a FeatureCollection for a layer `source`.
    geo.json layer: {"source": "ne-rivers", "ne": {"file": "ne_50m_rivers_lake_centerlines", "names": [...]}}            → one feature per name
                    {"source": "ne-rivers", "ne": {"file": ..., "groups": {"white": ["Victoria Nile", "Bahr el Jebel"]}}}  → one merged MultiLineString per group
    Line groups are ordered south→north and each segment oriented the same way, so a stroke-dash draw-on runs like a north-flowing river
    (set "flow": "north"|"south"|"east"|"west"|"chain"|"none"; "chain" joins nearest ends starting at "start" [lon,lat]). Polygons (lakes) are kept as-is. Matching is on name / name_en / name_alt (case-insensitive)."""
    src = json.loads(ne_path(spec_ne["file"]).read_text())
    def names_of(f):
        pr = f.get("properties") or {}
        return {str(pr.get(k) or "").strip().lower() for k in ("name", "name_en", "name_alt", "name_long")} - {""}
    groups = spec_ne.get("groups") or {_slug(n): [n] for n in spec_ne.get("names", [])}
    flow = spec_ne.get("flow", "north"); out = []
    for gid, want in groups.items():
        w = {x.strip().lower() for x in want}
        feats = [f for f in src["features"] if names_of(f) & w]
        if not feats: sys.exit(f"geodata: ne '{spec_ne['file']}' has no feature named {want} (names are case-insensitive; check name_en)")
        gtypes = {f["geometry"]["type"] for f in feats}
        if gtypes <= {"LineString", "MultiLineString"}:
            segs = []
            for f in feats:
                g = f["geometry"]; segs += [g["coordinates"]] if g["type"] == "LineString" else list(g["coordinates"])
            ax, sign = {"north": (1, 1), "south": (1, -1), "east": (0, 1), "west": (0, -1)}.get(flow, (None, 1))
            if flow == "chain" and segs:                                   # greedy chaining from `start` (lon,lat): nearest free end joins the tail
                st = spec_ne.get("start") or min((c for sg in segs for c in (sg[0], sg[-1])), key=lambda c: c[0])
                d2 = lambda a, b: (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                rest, out_segs, tail = list(segs), [], st
                while rest:
                    sg, rev = min(((sg, rv) for sg in rest for rv in (False, True)), key=lambda x: d2(tail, x[0][-1] if x[1] else x[0][0]))
                    rest.remove(sg); sg = list(reversed(sg)) if rev else sg; out_segs.append(sg); tail = sg[-1]
                segs = out_segs
            elif ax is not None:
                segs = [s if (s[-1][ax] - s[0][ax]) * sign >= 0 else list(reversed(s)) for s in segs]
                segs.sort(key=lambda s: sign * min(c[ax] for c in s))
            geom = {"type": "MultiLineString", "coordinates": [[[round(c[0], 4), round(c[1], 4)] for c in s] for s in segs]}
        elif len(feats) == 1: geom = feats[0]["geometry"]
        else: geom = {"type": "GeometryCollection", "geometries": [f["geometry"] for f in feats]}
        out.append({"type": "Feature", "id": gid, "properties": {"name": want[0], "ne_names": sorted({n for f in feats for n in names_of(f)})}, "geometry": geom})
    return {"type": "FeatureCollection", "features": out}


def extra_atlas_path(name):
    a = EXTRA_ATLASES[name]; p = CACHE / a["pkg"] / a["file"]
    if not p.exists():
        for u in a["urls"]:
            try: fetch(u.format(f=a["file"]), p); break
            except Exception: continue
        if not p.exists(): sys.exit(f"geodata: could not fetch {a['pkg']}/{a['file']} — needs network once (cached under {CACHE})")
    return p


def topo_features(topo, obj, ids=None):
    """TopoJSON object → GeoJSON features (pure python; used for admin-1 sources the runtime reads from data.geo[source])."""
    def ring(arcs):
        pts = []
        for i in arcs:
            seg = _decode_arc(topo, i if i >= 0 else ~i)
            if i < 0: seg = seg[::-1]
            pts += seg[1:] if pts and pts[-1] == seg[0] else seg
        return [list(pt) for pt in pts]
    def geom(g):
        t = g["type"]
        if t == "Polygon": return {"type": t, "coordinates": [ring(r) for r in g["arcs"]]}
        if t == "MultiPolygon": return {"type": t, "coordinates": [[ring(r) for r in poly] for poly in g["arcs"]]}
        if t == "LineString": return {"type": t, "coordinates": ring(g["arcs"])}
        if t == "MultiLineString": return {"type": t, "coordinates": [ring(l) for l in g["arcs"]]}
        return None
    want = {str(i) for i in ids} if ids else None
    out = []
    for g in topo["objects"][obj]["geometries"]:
        fid = str(g.get("id", "")); name = (g.get("properties") or {}).get("name", "")
        if want and fid not in want and name not in want: continue
        gj = geom(g)
        if gj: out.append({"type": "Feature", "id": fid, "properties": {"name": name}, "geometry": gj})
    return out


# ---------------------------------------------------------------- TopoJSON filtering (pure python)
def _decode_arc(topo, idx):
    arc = topo["arcs"][idx if idx >= 0 else ~idx]
    pts, x, y = [], 0, 0
    tr = topo.get("transform")
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((x * tr["scale"][0] + tr["translate"][0], y * tr["scale"][1] + tr["translate"][1]) if tr else (x, y))
    return pts


def _geom_arcs(g):
    t = g["type"]
    if t == "Polygon": return [i for ring in g["arcs"] for i in ring]
    if t == "MultiPolygon": return [i for poly in g["arcs"] for ring in poly for i in ring]
    if t == "LineString": return list(g["arcs"])
    if t == "MultiLineString": return [i for line in g["arcs"] for i in line]
    if t == "GeometryCollection": return [i for gg in g["geometries"] for i in _geom_arcs(gg)]
    return []


def _geom_bbox(topo, g, cache):
    xs, ys = [], []
    for i in _geom_arcs(g):
        k = i if i >= 0 else ~i
        if k not in cache:
            pts = _decode_arc(topo, k); cache[k] = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        b = cache[k]; xs += [b[0], b[2]]; ys += [b[1], b[3]]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def filter_topo(topo, bbox=None, ids=None, keep_objects=("countries",)):
    """Keep geometries that intersect bbox [w,s,e,n] (or whose id is in ids); re-index arcs. Returns a new TopoJSON."""
    cache, used, objects = {}, [], {}
    for name in keep_objects:
        if name not in topo["objects"]: continue
        geoms = []
        for g in topo["objects"][name]["geometries"]:
            keep = True
            if ids is not None and str(g.get("id")) not in set(map(str, ids)): keep = False
            if keep and bbox is not None:
                b = _geom_bbox(topo, g, cache)
                keep = bool(b) and not (b[2] < bbox[0] or b[0] > bbox[2] or b[3] < bbox[1] or b[1] > bbox[3])
            if keep: geoms.append(g)
        objects[name] = {"type": "GeometryCollection", "geometries": geoms}
        for g in geoms: used += [i if i >= 0 else ~i for i in _geom_arcs(g)]
    order = sorted(set(used)); remap = {old: new for new, old in enumerate(order)}

    def rearc(a):
        if isinstance(a, int): return remap[a] if a >= 0 else ~remap[~a]
        return [rearc(x) for x in a]
    for name, obj in objects.items():
        for g in obj["geometries"]:
            if "arcs" in g: g["arcs"] = rearc(g["arcs"])
            if "geometries" in g:
                for gg in g["geometries"]: gg["arcs"] = rearc(gg["arcs"])
    out = {"type": "Topology", "objects": objects, "arcs": [topo["arcs"][i] for i in order]}
    if "transform" in topo: out["transform"] = topo["transform"]
    if "bbox" in topo and bbox is None: out["bbox"] = topo["bbox"]
    return out


# ---------------------------------------------------------------- disputed areas
def parse_note(note):
    """'Admin. by India; Claimed by Pakistan' -> (controller, [claimants]). Self-administered -> 'self-administered'."""
    note = note or ""; ctl, cl = None, []
    m = re.search(r"Admin\.? by ([^;,.]+)", note, re.I)
    if m: ctl = m.group(1).strip()
    if re.search(r"Self admin", note, re.I): ctl = "self-administered (de facto authority)"
    m = re.search(r"Claimed by ([^;.]+)", note, re.I)
    if m: cl = [x.strip() for x in re.split(r",| and ", m.group(1)) if x.strip()]
    return ctl, cl


def disputed_index(extra=None):
    """BRK_NAME -> feature from Natural Earth disputed areas (cached download) plus any extra GeoJSON files (fixtures)."""
    idx = {}
    paths = [Path(p) for p in (extra or [])]
    try: paths.append(ne_path("ne_10m_admin_0_disputed_areas"))
    except SystemExit as e:
        if not paths: raise
        print(f"  ! {e} — using fixtures only")
    for p in paths:
        fc = json.loads(p.read_text())
        for ft in fc["features"]:
            pr = ft["properties"]; idx[pr.get("BRK_NAME") or ft.get("id")] = ft
    return idx


def resolve_disputed(d, idx):
    """geo.json disputed entry -> entry with geometry + Natural Earth default policy fields (author fields win)."""
    ft = idx.get(d.get("ne_name", d.get("name")))
    out = dict(d)
    if ft:
        out["geometry"] = d.get("geometry") or ft["geometry"]
        ctl, cl = parse_note(ft["properties"].get("NOTE_BRK"))
        out.setdefault("ne_note", ft["properties"].get("NOTE_BRK"))
        out.setdefault("controller", ctl or ft["properties"].get("ADMIN"))
        out.setdefault("claimants", cl)
        if not out.get("label_at") and ft["properties"].get("LABEL_X") is not None:
            out["label_at"] = [ft["properties"]["LABEL_X"], ft["properties"]["LABEL_Y"]]
    return out


# ---------------------------------------------------------------- prep
def scene_bbox(spec):
    fit = spec.get("fit") or {}
    if fit.get("type") == "bbox":
        w, s, e, n = fit["bbox"]; pw, ph = (e - w) * 0.6 + 2, (n - s) * 0.6 + 2
        return [max(-180, w - pw), max(-90, s - ph), min(180, e + pw), min(90, n + ph)]
    return None


def pick_res(spec):
    if spec.get("resolution"): return spec["resolution"]
    b = scene_bbox(spec)
    if not b: return "50m" if spec.get("projection") != "orthographic" else "110m"
    w = b[2] - b[0]
    return "10m" if w < 25 else ("50m" if w < 110 else "110m")     # continent-wide scenes: 110m is plenty at 1080 px


def prep(ep: Path, out: Path, fixtures=None, quiet=False):
    G = json.loads((ep / "geo.json").read_text())
    out.mkdir(parents=True, exist_ok=True)
    mp = ep / "media.json"; man = json.loads(mp.read_text()) if mp.exists() else {"files": {}}
    gen = man.setdefault("generated", {})
    idx = None; report = {}
    for sid, spec in G["scenes"].items():
        res = pick_res(spec)
        topo = json.loads(atlas_path(res, "countries").read_text())
        ids = None
        if (spec.get("fit") or {}).get("type") == "features" and spec.get("clip_to_fit"): ids = spec["fit"]["ids"]
        ft = filter_topo(topo, bbox=scene_bbox(spec), ids=ids) if (scene_bbox(spec) or ids) and spec.get("projection") != "orthographic" else topo
        data = {"topo": ft, "geo": dict(spec.get("geo", {})), "sources": ["Natural Earth"], "quality": f"ne-{res}", "resolution": res}
        extras, ne_extra = [], []
        for L in spec.get("layers", []):                                   # admin-1 layers: {"kind": "highlight", "source": "us-states", "ids": ["25"]}
            src = L.get("source")
            if L.get("ne") and src and src not in data["geo"]:                   # any Natural Earth file (rivers, lakes, …) by feature name
                data["geo"][src] = ne_features(L["ne"]); ne_extra.append(L["ne"]["file"])
                continue
            if src in EXTRA_ATLASES and src not in data["geo"]:
                xt = json.loads(extra_atlas_path(src).read_text())
                data["geo"][src] = {"type": "FeatureCollection", "features": topo_features(xt, EXTRA_ATLASES[src]["object"], L.get("ids"))}
                extras.append(src); data["sources"].append(EXTRA_ATLASES[src]["credit"])
        if spec.get("disputed"):
            idx = idx or disputed_index(fixtures)
            feats = []
            for d in spec["disputed"]:
                r = resolve_disputed(d, idx)
                if not r.get("geometry"): sys.exit(f"geodata: {sid}: disputed '{d.get('name')}' not found in Natural Earth (try `geodata.py disputed {d.get('name', '')[:6]}`) and no geometry given")
                feats.append({"type": "Feature", "id": d["id"], "properties": {k: r.get(k) for k in ("name", "controller", "claimants", "ne_note")}, "geometry": r["geometry"]})
                d.update({k: r[k] for k in ("controller", "claimants", "label_at") if k in r and k not in d})
            data["geo"]["disputed"] = {"type": "FeatureCollection", "features": feats}
        bm = spec.get("basemap")                                           # v3: raster under the vector layers (Mercator scenes)
        if bm:
            bm = {"layer": bm} if isinstance(bm, str) else dict(bm)
            if spec.get("projection") != "mercator": sys.exit(f"geodata: {sid}: basemap needs \"projection\": \"mercator\" (raster tiles are Web Mercator)")
            bb = bm.get("bbox") or (spec.get("fit") or {}).get("bbox")                 # basemap.bbox: explicit raster extent (world / rotated scenes)
            if not bb and (spec.get("fit") or {}).get("type", "world") == "world": bb = [-180, -60, 180, 75]
            if not bb: sys.exit(f"geodata: {sid}: basemap needs a bbox fit (or basemap.bbox)")
            sys.path.insert(0, str(Path(__file__).resolve().parent)); import basemap as _bm
            kmax = float(bm.get("k_max", 2.5)); width = int(spec.get("w", 1080) * kmax * 1.1)
            pad = float(bm.get("pad_deg", 0.0)) or (0.0 if bm.get("bbox") else 0.35 * max(bb[2] - bb[0], bb[3] - bb[1]))   # the 1080×1180 fit + camera pans show more than the bbox
            meta = _bm.stitch([bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad], width, out / f"{sid}_basemap.jpg", bm.get("layer", "bluemarble"))
            data["basemap"] = {"src": f"{sid}_basemap.jpg", **{k: meta[k] for k in ("scale", "translate", "size", "zoom", "credit", "layer")}}
            far = bm.get("far")                                                 # v3 hook views: a coarse, wide raster under the detailed one (camera k < 1)
            if far:
                fb = list(far["bbox"]); kmin = float(far.get("k_min", 0.35))
                ppd = spec.get("w", 1080) / max(bb[2] - bb[0], 1e-6)            # ≈ frame px per degree at k = 1 (lon-fitted scenes)
                # Owner 2026-10-20: the opening zoom must never show bare background at the frame edges. Grow the far raster so the
                # 1080×1920 viewport of EVERY camera in visuals.json (k, lonlat) stays inside it, with a 12 % margin.
                import math as _m
                cams = []
                if (ep / "visuals.json").exists():
                    for b in json.loads((ep / "visuals.json").read_text()).get("beats", []):
                        a = b.get("args") or {}
                        if b.get("do") in ("geo.cam_set", "geo.cam_to") and a.get("lonlat") and a.get("k"): cams.append((float(a["k"]), a["lonlat"]))
                for k, (lon, lat) in cams:
                    hw = 540 / (ppd * k) * 1.12; hh = 960 * _m.cos(_m.radians(min(abs(lat), 80))) / (ppd * k) * 1.12
                    fb = [min(fb[0], lon - hw), min(fb[1], lat - hh), max(fb[2], lon + hw), max(fb[3], lat + hh)]
                fb = [max(-180, fb[0]), max(-82, fb[1]), min(180, fb[2]), min(82, fb[3])]
                if fb != list(far["bbox"]) and not quiet: print(f"  · {sid}: far bbox grown to cover every camera → {[round(v, 1) for v in fb]}")
                fw = int(min(max((fb[2] - fb[0]) * ppd * kmin * 1.15, 1200), 6000))
                fmeta = _bm.stitch(fb, fw, out / f"{sid}_basemap_far.jpg", bm.get("layer", "bluemarble"))
                data["basemap"]["far"] = {"src": f"{sid}_basemap_far.jpg", **{k: fmeta[k] for k in ("scale", "translate", "size", "zoom")}}
                gen[f"geo/{sid}_basemap_far.jpg"] = {"kind": "image", "licence": "PD-USGov", "provider": "NASA GIBS", "by": "reelkit/basemap.py",
                                                     "source": f"{fmeta['layer']} z{fmeta['zoom']} ({fmeta['tiles']} tiles)", "credit": fmeta["credit"], "bytes": fmeta["bytes"]}
                if not quiet: print(f"  ✓ {sid}: far basemap z{fmeta['zoom']} {fmeta['size'][0]}×{fmeta['size'][1]} · {fmeta['bytes'] // 1024} KB")
            data["sources"].append(meta["credit"])
            gen[f"geo/{sid}_basemap.jpg"] = {"kind": "image", "licence": "PD-USGov", "provider": "NASA GIBS", "by": "reelkit/basemap.py",
                                             "source": f"{meta['layer']} z{meta['zoom']} ({meta['tiles']} tiles)", "credit": meta["credit"], "bytes": meta["bytes"]}
            if not quiet: print(f"  ✓ {sid}: basemap {meta['layer']} z{meta['zoom']} {meta['size'][0]}×{meta['size'][1]} · {meta['bytes'] // 1024} KB")
        want = {L["flag"].lower() for L in spec.get("layers", []) if L.get("flag")}
        def _walk(o):                                                          # flags of characters / option pills (visuals.json, episode.json)
            if isinstance(o, dict):
                if isinstance(o.get("flag"), str) and len(o["flag"]) <= 6: want.add(o["flag"].lower())
                for v in o.values(): _walk(v)
            elif isinstance(o, list):
                for v in o: _walk(v)
        for fn in ("visuals.json", "episode.json"):
            if (ep / fn).exists(): _walk(json.loads((ep / fn).read_text()))
        if want:
            sys.path.insert(0, str(Path(__file__).resolve().parent)); import flags as _fl
            data["flags"] = {}
            for cc in sorted(want):
                fp = _fl.ensure(cc, out / "flags"); data["flags"][cc] = f"flags/{fp.name}"
                gen[f"geo/flags/{fp.name}"] = {"kind": "image", "by": "reelkit/flags.py", **_fl.LICENCE, "bytes": fp.stat().st_size}
            data["sources"].append("flag-icons")
        s = json.dumps(data, separators=(",", ":"))
        (out / f"{sid}.json").write_text(s)
        gen[f"geo/{sid}.json"] = {"kind": "data", "licence": "PD", "provider": "Natural Earth", "by": "reelkit/geodata.py",
                                  "source": f"world-atlas {WORLD_ATLAS_VER} {res}" + (" + ne_10m_admin_0_disputed_areas" if spec.get("disputed") else "")
                                            + "".join(f" + {EXTRA_ATLASES[x]['pkg']} {EXTRA_ATLASES[x]['ver']} ({EXTRA_ATLASES[x]['licence']})" for x in extras)
                                            + "".join(f" + {x}" for x in sorted(set(ne_extra))),
                                  "credit": " · ".join(["Natural Earth"] + [EXTRA_ATLASES[x]["credit"] for x in extras]), "bytes": len(s)}
        report[sid] = {"res": res, "kb": len(s) // 1024, "countries": len(ft["objects"].get("countries", {}).get("geometries", [])), "disputed": len(spec.get("disputed", []))}
        if not quiet: print(f"  ✓ {sid}: {res} · {len(s) // 1024} KB · {report[sid]['countries']} countries · {report[sid]['disputed']} disputed")
        if len(s) > 400_000: print(f"  ! {sid}: {len(s) // 1024} KB inline data — tighten the bbox or set \"resolution\": \"50m\"")
    (ep / "geo.json").write_text(json.dumps(G, indent=1, ensure_ascii=False) + "\n")     # write back resolved policy defaults
    mp.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    return report


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    fe = sp.add_parser("fetch"); fe.add_argument("--res", default="50m,10m"); fe.add_argument("--all", action="store_true", help="every resolution (110m,50m,10m)")
    pr = sp.add_parser("prep"); pr.add_argument("ep"); pr.add_argument("--out"); pr.add_argument("--fixture", action="append")
    di = sp.add_parser("disputed"); di.add_argument("q", nargs="?", default="")
    ch = sp.add_parser("check"); ch.add_argument("ep", nargs="?"); ch.add_argument("--fixture", action="append")
    a = ap.parse_args()
    if a.cmd == "fetch": cmd_fetch(a)
    elif a.cmd == "prep":
        ep = Path(a.ep).resolve(); prep(ep, Path(a.out) if a.out else Path.home() / ".cache/build" / ep.name / "geo", a.fixture)
    elif a.cmd == "disputed":
        for name, ft in sorted(disputed_index().items()):
            p = ft["properties"]
            if a.q.lower() in (name or "").lower() or a.q.lower() in (p.get("NOTE_BRK") or "").lower():
                print(f"  {name:32} admin={p.get('ADMIN'):18} {p.get('TYPE'):14} {p.get('NOTE_BRK') or ''}")
    elif a.cmd == "check" and not a.ep:      # cache audit (CI geodata workflow): every file present + parseable
        bad = 0
        for res in ("110m", "50m", "10m"):
            for kind in ("countries", "land"):
                fn = f"{kind}-{res}.json"; p = ENGINE_DATA / fn if res == "110m" and (ENGINE_DATA / fn).exists() else CACHE / "world-atlas" / fn
                try: json.loads(p.read_text()); print("  ✓", p)
                except Exception as x: print("  ✗", p, x); bad += 1
        for n in NE_FILES:
            p = CACHE / "natural-earth" / f"{n}.geojson"
            try: json.loads(p.read_text()); print("  ✓", p)
            except Exception as x: print("  ✗", p, x); bad += 1
        sys.exit(1 if bad else 0)
    elif a.cmd == "check":
        ep = Path(a.ep).resolve(); G = json.loads((ep / "geo.json").read_text()); idx = disputed_index(a.fixture); bad = 0
        for sid, spec in G["scenes"].items():
            for d in spec.get("disputed", []):
                if not (d.get("geometry") or idx.get(d.get("ne_name", d.get("name")))): print(f"  ✗ {sid}: disputed '{d.get('name')}' unresolved"); bad += 1
        print("geodata check:", "OK" if not bad else f"{bad} problem(s)"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
