#!/usr/bin/env python3
"""Find licence-safe archival media: metadata only, never downloads media (sandbox-safe; CI trims the picks).
  python3 reelkit/find.py search <ep> "<query>" [--type video|image] [--src commons,nasa,ia] [--limit 8] [--min-h 720]
  python3 reelkit/find.py show   <ep> [--all]                    saved candidates (survive sandbox restarts: <ep>/candidates.json)
  python3 reelkit/find.py add    <ep> <cand> --id arch_x --in 2 --out 9 --scene s03 [--use insert|bleed] [--grade none|film]
                                                                  -> url clip in clips.json with every provenance field filled
Sources and how far their licence can be trusted:
  commons  Wikimedia Commons. Licence from structured file metadata (LicenseShortName/License). Best source.
  nasa     images.nasa.gov. NASA media is generally not copyrighted; a description mentioning ©/courtesy/credit to a
           non-NASA party is flagged for review (third-party material).
  ia       Internet Archive. Licences are UPLOADER-DECLARED (a 2026 news podcast marked "public domain" exists):
           every IA candidate is review-only and `add` refuses it unless --accept-review.
Licence mapping follows reelkit/provenance.py ALLOWED; share-alike / NC / ND / unknown are refused here already.
Resolution policy (`add --use`): insert (framed, ≤ ~1000 px tall on screen) needs ≥ 1080 px source height; bleed
(full-screen 9:16 crop) needs ≥ 1920. The smallest rendition that satisfies it is chosen (Commons transcodes /
NASA ~large); originals above 2160 px get max_h 2160 so the CI trim stays inside runner memory."""
import argparse, hashlib, html, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance import ALLOWED, REFUSED  # noqa: E402  (one licence policy for search and gate)

UA = "QuizWireFinder/1.0 (https://github.com/zainkhan122/quizwire; research use)"   # Wikimedia API policy: identify yourself
NEED_H = {"insert": 1080, "bleed": 1920}
CAP_H = 2160


def get_json(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code not in (429, 500, 502, 503, 504) or i == tries - 1: raise
            wait = int(e.headers.get("Retry-After") or 0) or 3 * 2 ** i
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tries - 1: raise
            wait = 3 * 2 ** i
        print(f"  … retry {i + 1}/{tries - 1} in {wait}s ({url.split('/')[2]})", file=sys.stderr); time.sleep(wait)


def text(s):  # extmetadata values are HTML fragments
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def norm_licence(short, code=""):
    """-> (licence id or None, ok, reason)."""
    s, c = (short or "").strip(), (code or "").strip().lower()
    if REFUSED.search(s.replace("public domain", "")) and not re.search(r"public domain|^pd", s, re.I):
        return None, False, f"refused ({s})"
    if c.startswith("pd-usgov") or re.search(r"PD-USGov|U\.?S\.? ?gov", s, re.I): return "PD-USGov", True, s
    if re.search(r"^cc0|cc-zero|cc0", s + " " + c, re.I): return "CC0-1.0", True, s
    if re.search(r"public domain|^pd\b|^pd-", s + " " + c, re.I): return "PD", True, s
    m = re.search(r"CC BY (\d\.\d)", s, re.I) or re.search(r"cc-by-(\d\.\d)$", c)
    if m:
        lid = f"CC-BY-{m.group(1)}"
        return (lid, True, s) if lid in ALLOWED else (None, False, f"{s}: not in provenance allow-list {sorted(ALLOWED)[:6]}…")
    return None, False, f"unknown licence ({s or c or 'none'})"


def hms(v):
    """'0:02:12' / '12.5 s' / 12.5 -> seconds (None if unparseable)."""
    if v is None: return None
    t = str(v).strip()
    if re.fullmatch(r"\d+(:\d+){1,2}(\.\d+)?", t):
        sec = 0.0
        for part in t.split(":"): sec = sec * 60 + float(part)
        return round(sec, 1)
    m = re.match(r"([\d.]+)\s*s?$", t)
    return round(float(m.group(1)), 1) if m else None


def cand_id(src, url):
    return f"{src}:{hashlib.sha1(url.encode()).hexdigest()[:8]}"


def strip_q(u):
    return u.split("?")[0]


# ---------------------------------------------------------------- sources
def commons(q, kind, limit):
    ft = "video" if kind == "video" else "bitmap"
    prop = "videoinfo" if kind == "video" else "imageinfo"; P = "vi" if kind == "video" else "ii"
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": limit,
              "gsrsearch": f"{q} filetype:{ft}", "prop": prop,
              f"{P}prop": "url|size|mime|extmetadata" + ("|derivatives" if kind == "video" else ""),
              f"{P}extmetadatafilter": "LicenseShortName|License|Artist|Credit|DateTimeOriginal|ObjectName|ImageDescription"}
    d = get_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)) or {}
    out = []
    for p in sorted(d.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get(prop) or [{}])[0]; em = {k: v.get("value") for k, v in ii.get("extmetadata", {}).items()}
        lid, ok, why = norm_licence(text(em.get("LicenseShortName")), text(em.get("License")))
        artist = text(em.get("Artist")) or text(em.get("Credit")) or "unknown"
        rend = [{"url": strip_q(ii["url"]), "w": ii.get("width"), "h": ii.get("height"), "label": "original"}]
        for dv in ii.get("derivatives", []) if kind == "video" else []:
            if dv.get("height") and "transcoded" in dv.get("src", ""):
                rend.append({"url": strip_q(dv["src"]), "w": dv.get("width"), "h": dv.get("height"), "label": f"{dv['height']}p transcode"})
        out.append({"src": "commons", "title": p["title"].removeprefix("File:"), "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                    "licence": lid, "licence_ok": ok, "licence_raw": why, "author": artist[:120], "date": text(em.get("DateTimeOriginal"))[:20],
                    "w": ii.get("width"), "h": ii.get("height"), "duration": round(ii["duration"], 1) if ii.get("duration") else None,
                    "size_mb": round(ii.get("size", 0) / 1e6, 1), "renditions": rend, "provider": "Wikimedia Commons",
                    "review": None if ok else why, "desc": text(em.get("ImageDescription"))[:200]})
    return out


def nasa(q, kind, limit):
    d = get_json("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": kind, "page_size": limit})) or {}
    out = []
    for it in d.get("collection", {}).get("items", [])[:limit]:
        m = it["data"][0]; nid = m["nasa_id"]; base = f"https://images-assets.nasa.gov/{kind}/{urllib.parse.quote(nid)}"
        files = [x["href"].replace("http://", "https://") for x in (get_json(f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nid)}") or {}).get("collection", {}).get("items", [])]
        meta = get_json(f"{base}/metadata.json") or {}
        def mget(*suffixes):
            for k, v in meta.items():
                if any(k.endswith(s) for s in suffixes): return v
        w, h = mget(":ImageWidth", ":SourceImageWidth"), mget(":ImageHeight", ":SourceImageHeight")
        dur = hms(mget(":Duration", ":TrackDuration"))
        ext = "mp4" if kind == "video" else "jpg"
        rend = [{"url": u, "w": None, "h": None, "label": lbl} for lbl in ("orig", "large", "medium")
                for u in dict.fromkeys(files) if u.endswith(f"~{lbl}.{ext}")]
        rend = [r for i, r in enumerate(rend) if r["label"] not in {x["label"] for x in rend[:i]}]     # one per rendition
        if rend and w and h: rend[0].update(w=int(w), h=int(h))
        desc = text(m.get("description"))
        third = re.search(r"©|copyright|courtesy|credit:\s*(?!NASA)", desc, re.I)
        out.append({"src": "nasa", "title": text(m.get("title")), "page": f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}",
                    "licence": "PD-USGov", "licence_ok": not third, "licence_raw": "NASA media (not copyrighted unless noted)",
                    "author": f"NASA {m.get('center', '')}".strip() + (f" / {m['secondary_creator']}" if m.get("secondary_creator") else ""),
                    "date": str(m.get("date_created", ""))[:10], "w": int(w) if w else None, "h": int(h) if h else None, "duration": dur,
                    "size_mb": None, "renditions": rend, "provider": f"NASA Image and Video Library ({m.get('center', 'NASA')})",
                    "review": "description mentions a third party (©/courtesy/credit): verify before use" if third else None, "desc": desc[:200]})
    return out


def ia(q, kind, limit):
    mt = "movies" if kind == "video" else "image"
    lic = r"(licenseurl:*publicdomain* OR licenseurl:*creativecommons.org\/licenses\/by\/*)"     # '/' is Lucene syntax: escape
    qs = urllib.parse.urlencode({"q": f"({q}) AND mediatype:{mt} AND {lic}", "fl[]": ["identifier", "title", "licenseurl", "year", "creator"],
                                 "rows": limit, "output": "json"}, doseq=True)
    d = get_json("https://archive.org/advancedsearch.php?" + qs) or {}
    if d.get("error"): raise RuntimeError(f"archive.org: {d['error']}")
    out = []
    for x in d.get("response", {}).get("docs", []):
        lu = x.get("licenseurl", ""); lid = "CC0-1.0" if "zero" in lu else "PD" if "publicdomain" in lu else \
            (f"CC-BY-{m.group(1)}" if (m := re.search(r"/by/(\d\.\d)", lu)) else None)
        out.append({"src": "ia", "title": text(x.get("title")), "page": f"https://archive.org/details/{x['identifier']}",
                    "licence": lid if lid in ALLOWED else None, "licence_ok": False, "licence_raw": lu,
                    "author": text(x.get("creator")) or "unknown", "date": str(x.get("year", "")), "w": None, "h": None, "duration": None,
                    "size_mb": None, "renditions": [], "provider": "Internet Archive",
                    "review": "uploader-declared licence: verify the rights holder (and pick a file on the item page)", "desc": ""})
    return out


SOURCES = {"commons": commons, "nasa": nasa, "ia": ia}


# ---------------------------------------------------------------- store
def store(ep): return Path(ep) / "candidates.json"


def load(ep):
    p = store(ep)
    return json.loads(p.read_text()) if p.exists() else {"note": "find.py candidates (metadata only). Picks go to clips.json via `find.py add`.", "candidates": []}


def save(ep, d):
    store(ep).write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def row(c):
    res = f"{c['w'] or '?'}x{c['h'] or '?'}"; dur = f"{c['duration']:.0f}s" if c.get("duration") else "  ?"
    flag = "OK " if c["licence_ok"] else ("REV" if c.get("licence") else "NO ")
    return f"  {c['id']:<17} {flag} {c.get('licence') or '-':<9} {res:>10} {dur:>5}  {c['title'][:58]}"


def cmd_search(a):
    d = load(a.ep); have = {c["id"]: c for c in d["candidates"]}; found = []
    for s in a.src.split(","):
        try: res = SOURCES[s](a.query, a.type, a.limit)
        except Exception as e: print(f"  ! {s}: {type(e).__name__} {str(e)[:120]}"); continue
        print(f"  {s}: {len(res)} result(s)" + ("  (NASA search is AND-keyword: try fewer words)" if s == "nasa" and not res else ""))
        for c in res:
            key_url = c["renditions"][0]["url"] if c["renditions"] else c["page"]
            c["id"] = cand_id(s, key_url); c["type"] = a.type; c["query"] = a.query
            if c.get("h") and c["h"] < a.min_h: continue
            have[c["id"]] = {**have.get(c["id"], {}), **c}; found.append(have[c["id"]])
    d["candidates"] = list(have.values()); save(a.ep, d)
    print(f"{len(found)} candidate(s) for {a.query!r} ({a.type}) → {store(a.ep)}  [OK = licence allowed · REV = review first · NO = refused]")
    for c in sorted(found, key=lambda c: (not c["licence_ok"], -(c.get("h") or 0))): print(row(c))


def cmd_show(a):
    for c in load(a.ep)["candidates"]:
        if a.all or c["licence_ok"]: print(row(c) + (f"\n      review: {c['review']}" if c.get("review") else ""))


def pick_rendition(c, use):
    need = NEED_H[use]; rs = [r for r in c["renditions"] if r.get("h")] or c["renditions"]
    ok = sorted([r for r in rs if (r.get("h") or 0) >= need], key=lambda r: r["h"])
    r = ok[0] if ok else max(rs, key=lambda r: r.get("h") or 0)
    return r, (r.get("h") or 0) >= need


def cmd_add(a):
    d = load(a.ep); c = next((x for x in d["candidates"] if x["id"] == a.cand), None)
    if not c: sys.exit(f"no candidate {a.cand} (run `find.py show {a.ep} --all`)")
    if c["type"] != "video": sys.exit("add handles video (url clips). For stills: download the file, then declare it in media.json with these fields:\n"
                                      + json.dumps({k: c[k] for k in ("page", "licence", "author", "provider")}, indent=1, ensure_ascii=False))
    if not c.get("licence") or (not c["licence_ok"] and not a.accept_review):
        sys.exit(f"refused: {c.get('review') or c.get('licence_raw')}  (verify, then re-run with --accept-review)")
    if not c["renditions"]: sys.exit("no direct file URL for this candidate (open its page and pick a file)")
    if c.get("duration") and a.out > c["duration"]: sys.exit(f"--out {a.out} beyond the clip duration {c['duration']} s")
    r, sharp = pick_rendition(c, a.use)
    cf = Path(a.ep) / "clips.json"; cl = json.loads(cf.read_text()) if cf.exists() else {"clips": []}
    if any(x["id"] == a.id for x in cl["clips"]): sys.exit(f"clips.json already has {a.id}")
    lic_label = {"PD": "Public Domain", "PD-USGov": "Public Domain", "CC0-1.0": "CC0"}.get(c["licence"], c["licence"].replace("-", " ").replace("CC BY", "CC BY"))
    short = re.sub(r"\.(webm|ogv|mpg|mp4|mov)$", "", c["title"], flags=re.I)[:48]
    clip = {"id": a.id, "engine": "url", "scene": a.scene, "in": a.in_, "out": a.out, "grade": a.grade, "url": r["url"], "source": c["page"],
            "credit": f"{c['title']}. {c['author']}, {c['provider']}. {c['licence_raw']}.",
            "licence": c["licence"], "provider": c["provider"],
            "screen_credit": f"Archive: {short} · {c['author'].split(' / ')[0][:40]} · {lic_label}",
            "credit_authors": [c["author"]]}
    if (r.get("h") or 0) > CAP_H: clip["max_h"] = CAP_H
    cl["clips"].append(clip); cf.write_text(json.dumps(cl, indent=1, ensure_ascii=False) + "\n")
    print(f"+ {a.id}: {r['label']} {r.get('w')}x{r.get('h')} ({'sharp enough' if sharp else 'BELOW ' + str(NEED_H[a.use]) + ' px for ' + a.use + ': soft'}) → clips.json")
    print(f"  screen_credit: {clip['screen_credit']!r}  (edit freely: build.py shows it verbatim, provenance checks it)")
    print(f"  next: clips.py lint {a.ep} · shots.json · media.py push after CI trims it (render job: clips.py gen --cache-only)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search"); s.add_argument("ep"); s.add_argument("query"); s.add_argument("--type", choices=("video", "image"), default="video")
    s.add_argument("--src", default="commons,nasa,ia"); s.add_argument("--limit", type=int, default=8); s.add_argument("--min-h", type=int, default=0)
    s = sp.add_parser("show"); s.add_argument("ep"); s.add_argument("--all", action="store_true")
    s = sp.add_parser("add"); s.add_argument("ep"); s.add_argument("cand"); s.add_argument("--id", required=True)
    s.add_argument("--in", dest="in_", type=float, required=True); s.add_argument("--out", type=float, required=True); s.add_argument("--scene", required=True)
    s.add_argument("--use", choices=tuple(NEED_H), default="insert"); s.add_argument("--grade", default="none"); s.add_argument("--accept-review", action="store_true")
    a = ap.parse_args(); {"search": cmd_search, "show": cmd_show, "add": cmd_add}[a.cmd](a)
