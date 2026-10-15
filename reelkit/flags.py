"""reelkit/flags.py — country flags for lifted highlights, option chips and flag-ball characters.

Source: flag-icons (github.com/lipis/flag-icons, MIT) — 4:3 SVGs by ISO 3166-1 alpha-2 (lowercase), plus a few
sub-national codes flag-icons ships (gb-eng, gb-sct, gb-wls, es-ct, …). Cached in ~/.cache/flags/<cc>.svg.

    from flags import ensure; p = ensure("nz", dest_dir)   # copies <dest_dir>/nz.svg, returns the path (None if unknown)
    python3 reelkit/flags.py nz ch cl                       # warm the cache
"""
import pathlib, re, shutil, sys, urllib.request

CACHE = pathlib.Path.home() / ".cache" / "flags"
RAW = "https://raw.githubusercontent.com/lipis/flag-icons/main/flags/4x3/{cc}.svg"
UA = "quizwire/1 (github zainkhan122/thequizwire)"
LICENCE = {"licence": "MIT", "provider": "flag-icons (lipis)", "credit": "flag-icons", "source": "https://github.com/lipis/flag-icons"}


def fetch(cc):
    cc = cc.lower()
    if not re.fullmatch(r"[a-z]{2}(-[a-z]{2,3})?", cc): raise SystemExit(f"flags: bad code {cc!r}")
    CACHE.mkdir(parents=True, exist_ok=True); p = CACHE / f"{cc}.svg"
    if not p.exists():
        try: p.write_bytes(urllib.request.urlopen(urllib.request.Request(RAW.format(cc=cc), headers={"User-Agent": UA}), timeout=30).read())
        except Exception as e: raise SystemExit(f"flags: no flag for {cc!r} ({e})")
    return p


def ensure(cc, dest_dir):
    src = fetch(cc); dest_dir = pathlib.Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    dst = dest_dir / src.name
    if not dst.exists() or dst.stat().st_size != src.stat().st_size: shutil.copy(src, dst)
    return dst


if __name__ == "__main__":
    for c in sys.argv[1:]: print(fetch(c))
