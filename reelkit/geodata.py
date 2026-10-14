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
        extras = []
        for L in spec.get("layers", []):                                   # admin-1 layers: {"kind": "highlight", "source": "us-states", "ids": ["25"]}
            src = L.get("source")
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
        s = json.dumps(data, separators=(",", ":"))
        (out / f"{sid}.json").write_text(s)
        gen[f"geo/{sid}.json"] = {"kind": "data", "licence": "PD", "provider": "Natural Earth", "by": "reelkit/geodata.py",
                                  "source": f"world-atlas {WORLD_ATLAS_VER} {res}" + (" + ne_10m_admin_0_disputed_areas" if spec.get("disputed") else "")
                                            + "".join(f" + {EXTRA_ATLASES[x]['pkg']} {EXTRA_ATLASES[x]['ver']} ({EXTRA_ATLASES[x]['licence']})" for x in extras),
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
