#!/usr/bin/env python3
"""Delivery names come from the story, not the pipeline.
  python3 reelkit/naming.py stem  <episode_dir>   -> The-Day-the-Sky-Ran-the-Telegraph      (file stem for .mp4/.jpg)
  python3 reelkit/naming.py title <episode_dir>   -> Geo Blitz #10 — Which is the longest river in Africa?   (release title)
Source of truth: episode.json `title` (+ `series`, `episode`). GitHub turns spaces in asset names into dots, so the stem
uses hyphens; anything outside [A-Za-z0-9-] is dropped (apostrophes, colons, accents) so the name is safe everywhere."""
import json, re, sys, unicodedata
from pathlib import Path


def meta(ep):
    p = Path(ep) / "episode.json"
    if not p.exists(): sys.exit(f"naming: {p} missing (title is required for delivery names)")
    m = json.loads(p.read_text())
    if not m.get("title"): sys.exit(f"naming: {p} has no 'title'")
    return m


def stem(ep):
    t = unicodedata.normalize("NFKD", meta(ep)["title"]).encode("ascii", "ignore").decode()
    t = re.sub(r"['’`]", "", t)                                   # Didn't -> Didnt (not Didn-t)
    s = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")
    if not s: sys.exit("naming: title has no usable characters")
    return s


def title(ep):
    """Quiz episodes: '<Series Name> #<number> — <question>' (series name from series/series.json when present)."""
    m = meta(ep)
    slug = str(m.get("series", ""))
    name = slug.replace("-", " ").title().replace(" And ", " & ")
    reg = Path(__file__).resolve().parents[1] / "series/series.json"
    if reg.exists():
        for s in json.loads(reg.read_text()).get("series", []):
            if s.get("slug") == slug: name = s.get("name", name)
    n = m.get("number", m.get("episode", ""))
    num = f" #{int(n)}" if str(n).isdigit() and int(n) > 0 else ""
    return f"{name}{num} — {m['title']}" if name else m["title"]


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("stem", "title"): sys.exit(__doc__)
    print({"stem": stem, "title": title}[sys.argv[1]](sys.argv[2]))
