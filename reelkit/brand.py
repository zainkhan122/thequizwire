"""reelkit/brand.py — channel brand assets for the v3 outro (logo, social icons, click cursor).

    python3 reelkit/brand.py prep <episode_dir> <build_dir>   # brand/* → <build>/brand/* and media.json 'generated' entries

Files (committed in brand/, all tiny):
  logo.png        the owner-supplied transparent TheQuizWire "Q" pin (512 px, 8 % padding)       licence own
  facebook.svg instagram.svg x.svg threads.svg   Simple Icons (https://simpleicons.org, CC0 1.0)   licence CC0-1.0
  cursor.svg      hand-drawn arrow cursor for the "click → subscribed" animation                licence own
Brand marks of third-party platforms are used only to indicate where the channel can be found (nominative use).
"""
import json, pathlib, shutil, sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "brand"
META = {
    "logo.png":      {"licence": "own", "provider": "TheQuizWire (channel brand, owner-supplied 2026-10-15)", "credit": "TheQuizWire", "source": "owner upload logo-The-Quiz-Wire-icon-transparent.png"},
    "cursor.svg":    {"licence": "own", "provider": "thequizwire (hand-made)", "credit": "thequizwire", "source": "brand/cursor.svg"},
}
SIMPLE = {"licence": "CC0-1.0", "provider": "Simple Icons", "credit": "Simple Icons", "source": "https://github.com/simple-icons/simple-icons"}


def prep(ep, build):
    ep, build = pathlib.Path(ep), pathlib.Path(build)
    E = json.loads((ep / "episode.json").read_text())
    if E.get("format") != "quiz-v3": return []
    out = build / "brand"; out.mkdir(parents=True, exist_ok=True)
    mp = ep / "media.json"; man = json.loads(mp.read_text()) if mp.exists() else {"files": {}}; gen = man.setdefault("generated", {})
    done = []
    for p in sorted(SRC.iterdir()):
        if p.suffix not in (".png", ".svg"): continue
        dst = out / p.name
        if not dst.exists() or dst.stat().st_size != p.stat().st_size: shutil.copy(p, dst)
        gen[f"brand/{p.name}"] = {"kind": "image", "by": "reelkit/brand.py", **META.get(p.name, SIMPLE), "bytes": p.stat().st_size}
        done.append(p.name)
    mp.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    print(f"  ✓ brand: {len(done)} files → {out}")
    return done


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "prep": prep(sys.argv[2], sys.argv[3])
    else: sys.exit(__doc__)
