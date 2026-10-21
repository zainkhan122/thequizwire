"""reelkit/photos.py — real photos of the subject from Wikimedia Commons, with licence captured for provenance (P2, 2026-10-21).

    python3 reelkit/photos.py prep <episode_dir> <build_dir>     # every {"type":"photo","commons":"File:X.jpg"} in visuals.json → <build>/photos/<id>.jpg
    python3 reelkit/photos.py find "<search terms>" [--n 8]      # editor helper: candidate files with licence + size, SA/NC/ND filtered out

Rules (reelkit/provenance.py): only CC0 / public domain / CC BY are usable (share-alike, NC, ND refused for monetised video);
every photo carries credit + screen_credit, and the credit must be visible in the composition (engine/quiz.py photo frame).
"""
import hashlib, json, pathlib, re, shutil, sys, urllib.parse, urllib.request
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "thequizwire-photos/1.0 (github zainkhan122/thequizwire)"}
CACHE = pathlib.Path.home() / ".cache" / "photos"
OK = re.compile(r"^(cc0|public domain|pd|cc by( \d\.\d)?|cc-by(-\d\.\d)?|attribution)$", re.I)
BAD = re.compile(r"sa|nc|nd|share|noncommercial|fair", re.I)

def api(**params):
    import time
    q = urllib.parse.urlencode({"format": "json", **params})
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=30) as r: return json.loads(r.read())
        except urllib.error.HTTPError as ex:
            if ex.code != 429 or i == 4: raise
            time.sleep(2 * (i + 1))

def infos(titles, width=1400):
    """One API call for many titles (Commons rate-limits per request, not per title)."""
    out = {}
    for k in range(0, len(titles), 20):
        d = api(action="query", prop="imageinfo", titles="|".join(titles[k:k + 20]), iiprop="url|extmetadata|size|mime", iiurlwidth=width)
        for page in d["query"]["pages"].values():
            if "imageinfo" not in page: continue
            ii = page["imageinfo"][0]; md = ii.get("extmetadata", {}); g = lambda k: re.sub(r"<[^>]+>", "", md.get(k, {}).get("value", "")).strip()
            out[page["title"]] = {"title": page["title"], "thumb": ii.get("thumburl") or ii["url"], "page": ii["descriptionurl"], "licence": g("LicenseShortName"),
                                  "licence_url": g("LicenseUrl"), "artist": g("Artist") or g("Credit") or "Wikimedia Commons", "w": ii.get("width"), "h": ii.get("height"), "mime": ii.get("mime")}
    return out

def info(title, width=1400):
    r = infos([title], width)
    if not r: raise SystemExit(f"photos: {title} not found on Commons")
    return next(iter(r.values()))

def licence_ok(l):
    l = l.strip()
    return bool(OK.match(l)) and not BAD.search(l.replace("Attribution", ""))

def fetch(url):
    CACHE.mkdir(parents=True, exist_ok=True); dst = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".jpg")
    if not dst.exists():
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: dst.write_bytes(r.read())
    return dst

def prep(ep, build):
    ep, build = pathlib.Path(ep), pathlib.Path(build); V = json.loads((ep / "visuals.json").read_text())
    photos = [e for e in V.get("elements", []) if e.get("type") == "photo"]
    if not photos: return []
    out = build / "photos"; out.mkdir(parents=True, exist_ok=True)
    mp = ep / "media.json"; man = json.loads(mp.read_text()) if mp.exists() else {"files": {}}; gen = man.setdefault("generated", {})
    I = infos([e["commons"] for e in photos])
    for e in photos:
        i = I.get(e["commons"]) or I.get(e["commons"].replace("_", " ")) or info(e["commons"]); lic = i["licence"]
        if not licence_ok(lic): raise SystemExit(f"photos: {e['id']} {i['title']} licence '{lic}' is not usable (CC0 / PD / CC BY only) — pick another file")
        if i["mime"] not in ("image/jpeg", "image/png"): raise SystemExit(f"photos: {e['id']} {i['title']} is {i['mime']} — jpeg/png only")
        src = fetch(i["thumb"]); dst = out / f"{e['id']}.jpg"; shutil.copy(src, dst)
        short = re.split(r"[,(;/]", i["artist"])[0].strip()[:32] or "Wikimedia Commons"; screen = f"📷 {short} · {lic}"
        e["credit"] = screen                                                  # written into the frame by engine/quiz.py photo()
        gen[f"photos/{e['id']}.jpg"] = {"kind": "photo", "licence": lic if lic.lower() != "public domain" else "PD", "provider": "Wikimedia Commons", "source": i["page"],
                                         "credit": f"{i['artist']} — {lic} — {i['page']}", "screen_credit": screen, "licence_url": i["licence_url"], "bytes": dst.stat().st_size, "by": "reelkit/photos.py"}
    (ep / "visuals.json").write_text(json.dumps(V, indent=1, ensure_ascii=False) + "\n")
    mp.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n")
    print(f"photos: {len(photos)} → {out}"); return photos

def find(q, n=8):
    d = api(action="query", list="search", srsearch=f"{q} filetype:bitmap", srnamespace=6, srlimit=n * 3)
    I = infos([h["title"] for h in d["query"]["search"]], 400)
    for i in I.values():
        ok = licence_ok(i["licence"]); print(("  OK " if ok else "  -- ") + f"{i['title']} · {i['licence']} · {i['w']}x{i['h']} · {i['artist'][:30]}")
        n -= ok
        if n <= 0: break

if __name__ == "__main__":
    if sys.argv[1] == "prep": prep(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "find": find(" ".join(a for a in sys.argv[2:] if not a.startswith("--")), int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 8)
