"""reelkit/stickers.py — emoji stickers (Twemoji, CC-BY 4.0) for v3 beats and option pills.

    python3 reelkit/stickers.py prep <episode_dir> <build_dir>   # every {"emoji": "1f3d4"} in visuals.json / episode.json → <build>/stickers/1f3d4.svg
Codepoints are lowercase hex joined by '-' (Twemoji file names), e.g. "1f3d4" 🏔, "1f427" 🐧, "1f3c6" 🏆, "1f1f3-1f1ff" is NOT used (flags come from flag-icons).
"""
import json, pathlib, re, shutil, sys, urllib.request

CACHE = pathlib.Path.home() / ".cache" / "stickers"
CDN = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/{cp}.svg"
UA = "quizwire/1 (github zainkhan122/thequizwire)"
LICENCE = {"licence": "CC-BY-4.0", "provider": "Twemoji (Twitter, Inc. and other contributors)", "credit": "Twemoji", "source": "https://github.com/twitter/twemoji"}


def fetch(cp):
    cp = cp.lower()
    if not re.fullmatch(r"[0-9a-f]{4,6}(-[0-9a-f]{4,6})*", cp): raise SystemExit(f"stickers: bad codepoint {cp!r}")
    CACHE.mkdir(parents=True, exist_ok=True); p = CACHE / f"{cp}.svg"
    if not p.exists():
        try: p.write_bytes(urllib.request.urlopen(urllib.request.Request(CDN.format(cp=cp), headers={"User-Agent": UA}), timeout=30).read())
        except Exception as e: raise SystemExit(f"stickers: no Twemoji for {cp!r} ({e})")
    return p


def walk(o, out):
    if isinstance(o, dict):
        if isinstance(o.get("emoji"), str): out.add(o["emoji"].lower())
        for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)


def prep(ep, build):
    ep, build = pathlib.Path(ep), pathlib.Path(build); want = set()
    for fn in ("visuals.json", "episode.json"):
        if (ep / fn).exists(): walk(json.loads((ep / fn).read_text()), want)
    if not want: return []
    out = build / "stickers"; out.mkdir(parents=True, exist_ok=True)
    mp = ep / "media.json"; man = json.loads(mp.read_text()) if mp.exists() else {"files": {}}; gen = man.setdefault("generated", {})
    for cp in sorted(want):
        src = fetch(cp); dst = out / src.name
        if not dst.exists(): shutil.copy(src, dst)
        gen[f"stickers/{src.name}"] = {"kind": "image", "by": "reelkit/stickers.py", **LICENCE, "bytes": src.stat().st_size}
    mp.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    print(f"  ✓ stickers: {len(want)} Twemoji → {out}")
    return sorted(want)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "prep": prep(sys.argv[2], sys.argv[3])
    else: sys.exit(__doc__)
