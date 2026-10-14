#!/usr/bin/env python3
"""STATE.json helper — the machine-readable half of the resume contract (RESUME.md is the human half).
  python3 tools/state.py show            compact resume pack (≤ ~3 KB) for a fresh session
  python3 tools/state.py stamp           refresh updated_at + episode inventory (called by tools/sync.sh)
  python3 tools/state.py set <key> <json-value>      e.g. set next '["render ep02"]'
"""
import json, sys, datetime, subprocess
from pathlib import Path
R = Path(__file__).resolve().parents[1]; P = R / "STATE.json"
S = json.loads(P.read_text()) if P.exists() else {}

def inventory():
    eps = {}
    for ej in sorted(R.glob("series/*/*/episode.json")):
        e = json.loads(ej.read_text()); eps[str(ej.parent.relative_to(R))] = {k: e.get(k) for k in ("title", "status", "release", "updated")}
    return eps

cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
if cmd == "stamp":
    S["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    S["episodes"] = inventory()
    P.write_text(json.dumps(S, indent=1, ensure_ascii=False) + "\n")
elif cmd == "set":
    S[sys.argv[2]] = json.loads(sys.argv[3]); P.write_text(json.dumps(S, indent=1, ensure_ascii=False) + "\n")
else:
    head = subprocess.run(["git", "-C", str(R), "log", "-1", "--format=%h %s"], capture_output=True, text=True).stdout.strip()
    print(f"# RESUME PACK  (git {head})\nupdated: {S.get('updated_at')}\n")
    print("## now:", S.get("now", "?"))
    print("\n## next:"); [print(f"  {i+1}. {n}") for i, n in enumerate(S.get("next", []))]
    print("\n## episodes:"); [print(f"  {k}: {v['status']} · {v.get('release') or '-'}") for k, v in S.get("episodes", {}).items()]
    print("\n## owner rules:"); [print(f"  - {r}") for r in S.get("owner_rules", [])]
    print("\n## blockers:", ", ".join(S.get("blockers", [])) or "none")
