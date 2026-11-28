#!/usr/bin/env python3
"""Cover gate with NO third-party imports — safe on a bare runner (daily.yml pick job, quizlint/postkit inside daily_pick).
2026-11-28: cover_scroll imports Pillow at module level; the pick job had no Pillow → every episode SKIPped → "backlog empty".

  python3 reelkit/cover_check.py <ep>      # exit 0 = spec + hero art + approval + rendered cover present
"""
import json, sys
from pathlib import Path

def spec_path(ep): return Path(ep) / "cover" / "spec.json"


def check(ep, need_approval=True):
    """Return a list of problems (empty = the episode has a production cover)."""
    ep = Path(ep); sp = spec_path(ep); bad = []
    if not sp.exists(): return [f"{ep.name}: cover/spec.json missing — author the cover spec (hero_prompt + head/badge/stickers)"]
    try: spec = json.loads(sp.read_text())
    except Exception as e: return [f"{ep.name}: cover/spec.json unreadable ({e})"]
    for k in ("head", "bg"):
        if not spec.get(k): bad.append(f"{ep.name}: cover/spec.json has no '{k}'")
    if spec.get("bg") and not (ep / "cover" / spec["bg"]).exists() and not spec.get("hero_url"): bad.append(f"{ep.name}: cover/{spec['bg']} missing — generate the hero art from spec.hero_prompt (then `mediahost.py cover <ep>` to host it)")
    if spec.get("status") == "draft": bad.append(f"{ep.name}: cover spec is still a draft stub")
    if need_approval and not spec.get("approved"): bad.append(f"{ep.name}: cover not approved — render, show the owner the contact sheet, then set spec.approved")
    if need_approval and not (ep / "cover" / "cover.jpg").exists() and not spec.get("cover_url"): bad.append(f"{ep.name}: cover/cover.jpg missing — render the approved cover (cover_scroll.py <ep> --jpg <ep>/cover/cover.jpg) and host it (mediahost.py cover <ep>)")
    return bad


if __name__ == "__main__":
    bad = check(sys.argv[1])
    for b in bad: print("cover_check: FAIL", b)
    sys.exit(1 if bad else print(f"cover_check: OK {Path(sys.argv[1]).name} has an approved production cover"))
