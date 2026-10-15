#!/usr/bin/env python3
"""reelkit/geolint.py — map honesty + border policy gate (docs/BORDER_POLICY.md, docs/border_registry.json).

    python3 reelkit/geolint.py <ep> [--hf <hf_dir>] [--online] [--release] [--report out/geolint.json]

FAIL (exit 1)
  P1 projection honesty   a scene whose script/screen text makes a size/area claim uses a conformal projection
                          (Mercator & co.); every scene needs `projection_reason`
  P2 distances            a distance claim ("km", "miles", "far") with no `scalebar` in the scene
  P3 coordinates          pin/label lon/lat out of range; with --online a pin with `qid` farther than 25 km from the
                          Wikidata coordinate (P625); any disputed entry whose `label_at` is missing
  P4 border policy        a sensitive region (registry) named in the question/VO/screen text, or inside a zoomed
                          scene's bbox, without a `disputed` entry; a disputed entry missing controller / claimants /
                          as_of / source; controller listed among claimants; the built index.html lacking the
                          "Administered by …" / "Claimed by …" plate text for it
  P5 data quality         built scene data is the 110m preview fallback (--release), or inline data > 400 KB
  P6 credit               built composition without the "Natural Earth" credit (or "OpenStreetMap" when maptile clips exist)
WARN: pins without `qid`, highlight ids that are not 3-char ISO numerics, as_of older than 18 months, registry
      regions whose Natural Earth note contradicts the registry (data drift).
"""
import argparse, datetime, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
REG = json.loads((REPO / "docs" / "border_registry.json").read_text())
CONFORMAL = {"mercator", "conicConformal", "stereographic"}
EQUAL_AREA = {"equalEarth", "azimuthalEqualArea", "conicEqualArea", "albers"}
KNOWN = CONFORMAL | EQUAL_AREA | {"naturalEarth1", "equirectangular", "orthographic"}
SIZE_RE = re.compile(r"\b(largest|biggest|smallest|bigger|smaller|larger|area|km²|km2|square (kilomet|mile)|sq\.? ?(km|mi)|size|twice the size|as big as)\b", re.I)
DIST_RE = re.compile(r"\b(\d[\d,\.]*\s?(km|kilomet\w*|miles?|mi)\b|how far|distance|farthest|furthest|longest (river|border|coastline|road))", re.I)
MAX_KM = 25.0


def norm(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(s))).strip().lower()


def haversine(a, b):
    import math
    la1, lo1, la2, lo2 = map(math.radians, [a[1], a[0], b[1], b[0]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(min(1, math.sqrt(h)))


def wikidata_coord(qid):
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetclaims", "entity": qid, "property": "P625", "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "quizwire-geolint/1 (github.com/zainkhan122)"}), timeout=30) as r:
        d = json.loads(r.read())
    cl = d.get("claims", {}).get("P625", [])
    if not cl: return None
    v = cl[0]["mainsnak"]["datavalue"]["value"]; return [v["longitude"], v["latitude"]]


def episode_text(ep):
    """Everything the audience hears or reads: question, options, answer, VO lines, facts/answers in visuals."""
    bits = []
    E = json.loads((ep / "episode.json").read_text()); q = E.get("quiz", {})
    bits += [E.get("title", ""), q.get("question", ""), q.get("answer_line", ""), q.get("answer_sub", "")] + q.get("options", [])
    vp = ep / "voice.json"
    if vp.exists(): bits += [l.get("text", "") for l in json.loads(vp.read_text())["lines"]]
    vs = ep / "visuals.json"
    if vs.exists():
        for el in json.loads(vs.read_text()).get("elements", []): bits += [el.get("text", ""), el.get("sub", ""), el.get("kicker", "")]
    return " ".join(norm(b) for b in bits if b)


def regions_mentioned(text):
    hits = []
    for r in REG["regions"]:
        for nm in [r["name"]] + r.get("aliases", []):
            if re.search(r"\b" + re.escape(nm.lower()) + r"\b", text): hits.append((r, nm)); break
    return hits


def regions_in_bbox(spec):
    fit = spec.get("fit") or {}
    if fit.get("type") != "bbox": return []
    w, s, e, n = fit["bbox"]
    if (e - w) > 40: return []                       # continent/world scale: borders are a hairline, no plate needed
    return [r for r in REG["regions"] if w <= r["center"][0] <= e and s <= r["center"][1] <= n]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("--hf"); ap.add_argument("--online", action="store_true")
    ap.add_argument("--release", action="store_true"); ap.add_argument("--report")
    a = ap.parse_args(); ep = Path(a.ep).resolve()
    F, W, info = [], [], {}
    gp = ep / "geo.json"
    if not gp.exists():
        print("geolint: no geo.json — nothing to check"); return
    G = json.loads(gp.read_text()); text = episode_text(ep)
    size_claim, dist_claim = bool(SIZE_RE.search(text)), bool(DIST_RE.search(text))
    mentioned = regions_mentioned(text)
    info.update({"size_claim": size_claim, "distance_claim": dist_claim, "regions_mentioned": [nm for _, nm in mentioned]})
    hf = Path(a.hf) if a.hf else Path.home() / ".cache/build" / ep.name / "hf"
    built = (hf / "index.html").read_text() if (hf / "index.html").exists() else ""
    btext = norm(built)
    today = datetime.date.today()

    covered = set()
    for sid, sp in G["scenes"].items():
        pj = sp.get("projection", "equalEarth")
        if pj not in KNOWN: F.append(f"{sid}: unknown projection '{pj}'")
        if not sp.get("projection_reason"): F.append(f"{sid}: projection_reason missing (say why this projection is honest for this claim)")
        if size_claim and pj in CONFORMAL: F.append(f"{sid}: size/area claim in the episode but projection '{pj}' is conformal — use equalEarth / conicEqualArea (P1)")
        if dist_claim and not sp.get("scalebar"): F.append(f"{sid}: distance claim in the episode but no scalebar (P2)")
        for p in sp.get("pins", []) + sp.get("labels", []):
            ll = p.get("lonlat")
            if not ll or not (-180 <= ll[0] <= 180 and -90 <= ll[1] <= 90): F.append(f"{sid}: {p.get('id')} lon/lat invalid {ll}")
        for p in sp.get("pins", []):
            if not p.get("qid"): W.append(f"{sid}: pin {p['id']} has no Wikidata qid (coordinate cannot be cross-checked)")
            elif a.online:
                try:
                    wd = wikidata_coord(p["qid"])
                    if wd:
                        d = haversine(wd, p["lonlat"]); info[f"{sid}/{p['id']}"] = round(d, 1)
                        if d > MAX_KM: F.append(f"{sid}: pin {p['id']} is {d:.0f} km from Wikidata {p['qid']} {wd} (limit {MAX_KM:.0f} km)")
                    else: W.append(f"{sid}: {p['qid']} has no P625 coordinate")
                except Exception as e:  # noqa: BLE001
                    W.append(f"{sid}: Wikidata lookup failed for {p['qid']}: {e}")
        for L in sp.get("layers", []):
            for i in L.get("ids", []) or []:
                if re.fullmatch(r"\d{1,2}", str(i)): W.append(f"{sid}: layer id '{i}' — world-atlas ids are 3-char zero-padded ISO numerics ('0{i}'?)")
        # ---- border policy
        for d in sp.get("disputed", []):
            did = d.get("id", "?")
            grouped = d.get("plate") is False
            if grouped:
                host = next((x for x in sp.get("disputed", []) if x.get("id") == d.get("plate_group") and x.get("plate") is not False), None)
                if not host: F.append(f"{sid}: disputed '{did}' has plate:false but no `plate_group` pointing at an entry that carries a plate (P4)")
                elif norm(d.get("controller", "")) and norm(d.get("controller", "")).split(" (")[0] not in norm(host.get("controller", "")):
                    F.append(f"{sid}: group plate '{host.get('id')}' does not name '{did}' controller '{d.get('controller')}' (P4)")
            for k in ("id", "name", "controller", "claimants", "as_of", "source", "label_at"):
                if grouped and k == "label_at": continue
                if d.get(k) in (None, "", []) and not (k == "claimants" and d.get("claimants") == [] and d.get("no_claimant_ok")):
                    F.append(f"{sid}: disputed '{did}' missing {k} (P4)")
            if d.get("controller") and d.get("controller") in (d.get("claimants") or []): F.append(f"{sid}: disputed '{did}': controller also listed as claimant")
            try:
                y, m = map(int, str(d.get("as_of", "")).split("-")[:2]); age = (today.year - y) * 12 + today.month - m
                if age > 18: W.append(f"{sid}: disputed '{did}' as_of {d['as_of']} is {age} months old — re-verify")
            except ValueError:
                if d.get("as_of"): F.append(f"{sid}: disputed '{did}' as_of must be YYYY-MM")
            if built:
                for need in ((norm(d.get('controller', '')).split(" (")[0], "claimed by") if grouped else (f"administered by {norm(d.get('controller', ''))}", "claimed by")):
                    if d.get("controller") and need not in btext: F.append(f"{sid}: built composition lacks the plate text '{need}' for '{did}' (P4)")
            for r in REG["regions"]:
                if d.get("ne_name", d.get("name")) in r.get("ne_names", []) or d.get("name") == r["name"]:
                    covered.add(r["id"])
                    part = next((p for p in r["parts"] if p.get("ne_name") == d.get("ne_name", d.get("name"))), None)
                    if part and d.get("controller") and norm(part["controller"]).split(" (")[0] not in norm(d["controller"]):
                        W.append(f"{sid}: '{did}' controller '{d['controller']}' differs from registry '{part['controller']}' — update one of them with a source")
        for r in regions_in_bbox(sp):
            if r["id"] not in covered and not any(dd.get("ne_name", dd.get("name")) in r.get("ne_names", []) for dd in sp.get("disputed", [])):
                F.append(f"{sid}: zoomed scene covers {r['name']} but has no `disputed` entry — the map will show a border there without saying who administers it (P4)")
    for r, nm in mentioned:
        if r["id"] not in covered: F.append(f"episode names '{nm}' ({r['name']}) but no map scene carries a `disputed` entry for it (P4)")
    # ---- built output
    if built:
        q = re.findall(r'data-quality="([^"]+)"', built)
        if any(x == "preview-110m" for x in q): (F if a.release else W).append("built with the 110m preview fallback — run `reelkit/geodata.py prep` (P5)")
        for m in re.finditer(r'<script type="application/json" id="(geo_\w+_data)">([\s\S]*?)</script>', built):
            if len(m.group(2)) > 400_000: F.append(f"{m.group(1)}: {len(m.group(2)) // 1024} KB inline map data (> 400 KB) — tighten bbox/resolution (P5)")
        if G["scenes"] and "natural earth" not in btext: F.append("no 'Natural Earth' credit in the composition (P6)")
        cj = ep / "clips.json"
        if cj.exists() and any(c.get("engine") == "maptile" for c in json.loads(cj.read_text()).get("clips", [])) and "openstreetmap" not in btext:
            F.append("maptile clip used but no '© OpenStreetMap contributors' credit on screen (P6)")
    else:
        W.append(f"{hf}/index.html not built — plate text, credit and data quality not checked")
    for w in W: print("  WARN ", w)
    for f in F: print("  FAIL ", f)
    print(f"geolint: {len(G['scenes'])} scene(s) · size claim {size_claim} · distance claim {dist_claim} · regions {info['regions_mentioned'] or '—'} → {'FAIL ' + str(len(F)) if F else 'OK'}")
    if a.report: Path(a.report).write_text(json.dumps({"fails": F, "warns": W, "info": info}, indent=1))
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
