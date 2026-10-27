#!/usr/bin/env bash
# today.sh — the whole daily production from one command (owner 2026-10-27: "generate today's videos" is the only input).
#
#   tools/today.sh prep            1. channel stats (24 h / 7 d) → slots   2. signals sheet   3. how many episodes today
#                                  prints what the agent must author (count, series rotation) — the ONLY human-judgment step
#   tools/today.sh ship            4. lint every `ready` episode against the CI-only traps (tools/precheck.py) + preflight
#                                  5. commit + push   6. plan today (daily_pick)   7. render.yml with dispatch=true
#                                  8. wait, print the Buffer schedule — or the FAIL lines, one round at a time
#   tools/today.sh status          what is scheduled today, what failed, what is in the air
#
# Everything after authoring is unattended; the GitHub cron (07:00 / 09:30 UTC) runs the same steps without the agent.
set -euo pipefail
cd "$(dirname "$0")/.."
T="${GH_TOKEN:-$(cat "$HOME/.secrets/gh_token" 2>/dev/null || cat "$HOME/.cache/secrets/gh_token")}"
API="https://api.github.com/repos/zainkhan122/thequizwire"
gh_api() { curl -s -H "Authorization: Bearer $T" -H "Accept: application/vnd.github+json" "$@"; }
push() { git pull -q --rebase "https://x-access-token:$T@github.com/zainkhan122/thequizwire.git" main && git push -q "https://x-access-token:$T@github.com/zainkhan122/thequizwire.git" HEAD:main; }
DAY="$(date -u +%F)"

case "${1:-status}" in
prep)
  echo "== stats (our channels, last 24 h / 7 d)"; python3 tools/stats.py snapshot 2>&1 | tail -2; python3 tools/slots.py apply 2>&1
  echo "== signals"; python3 tools/signals.py --out review/signals.md 2>&1 | tail -1
  N="$(python3 - <<'EOF'
import json, random, datetime
plan = json.load(open("dispatch/daily.json"))["days"]; day = datetime.date.today().isoformat()
prev = sorted(d for d in plan if d < day); last = len(plan[prev[-1]]) if prev else None
print(random.Random(day).choice([k for k in (1, 2, 3) if k != last] or [1]))
EOF
)"
  READY="$(python3 tools/daily_pick.py --dry 2>/dev/null | wc -w)"
  echo "== today: $N episode(s) (yesterday's count excluded); ready backlog: $READY"
  python3 - "$N" <<'EOF'
import json, sys, pathlib
from collections import defaultdict
n = int(sys.argv[1]); L = json.load(open("dispatch/ledger.json"))["posts"]; last = defaultdict(str)
for p in L:
    if p.get("state") in ("scheduled", "sent"):
        for ej in pathlib.Path("series").glob(f"*/{p['episode']}/episode.json"): last[ej.parent.parent.name] = max(last[ej.parent.parent.name], p.get("due_at") or "")
order = sorted(["geo-blitz", "wild-files", "sports-sprint", "body-brain"], key=lambda s: last[s])
print("== series that have waited longest:", " > ".join(order))
print("== author", n, "episode(s) from review/signals.md (topic.md → brief.md → spec → author_v4), then: tools/today.sh ship")
EOF
  ;;
ship)
  echo "== precheck (CI-only traps) + preflight on every ready, unscheduled episode"
  EPS="$(python3 tools/daily_pick.py --dry 2>/dev/null)"; [ -n "$EPS" ] || { echo "nothing ready — author first (tools/today.sh prep)"; exit 1; }
  for e in $EPS; do
    python3 tools/precheck.py "$e" || exit 1
    bash reelkit/episode.sh "$e" preflight 2>&1 | grep -E "FAIL  |Traceback" | grep -v "FAIL 0" && { echo "preflight FAIL: $e"; exit 1; } || true
  done
  python3 tools/repo_guard.py >/dev/null && python3 tests/selftest.py --quick >/dev/null
  git checkout -- dispatch/stats.json dispatch/stats_summary.json dispatch/stats.md config/publishing.json 2>/dev/null || true   # CI owns the stats files (publish-sync commits them); local snapshots only inform the agent
  git add -A; git diff --cached --quiet || git commit -qm "daily $DAY: authored episodes"; push
  PICK="$(python3 tools/daily_pick.py)"; git add dispatch/daily.json; git diff --cached --quiet || git commit -qm "daily: plan $DAY [skip ci]"; push
  echo "== plan $DAY: $PICK"
  SHA="$(git rev-parse HEAD)"
  gh_api -o /dev/null -w "render.yml dispatched (%{http_code})\n" -X POST "$API/actions/workflows/render.yml/dispatches" \
    -d "{\"ref\":\"main\",\"inputs\":{\"episodes\":\"$PICK\",\"tag\":\"daily-$DAY-$(date -u +%H%M)\",\"dispatch\":\"true\",\"sha\":\"$SHA\"}}"
  sleep 40; R="$(gh_api "$API/actions/workflows/render.yml/runs?per_page=1" | python3 -c 'import json,sys;print(json.load(sys.stdin)["workflow_runs"][0]["id"])')"
  for i in $(seq 1 20); do
    S="$(gh_api "$API/actions/runs/$R" | python3 -c 'import json,sys;r=json.load(sys.stdin);print(r["status"],r["conclusion"])')"
    echo "$(date -u +%H:%M) run $R: $S"; case "$S" in completed*) break;; esac; sleep 90
  done
  gh_api "$API/actions/runs/$R/jobs" | python3 -c '
import json,sys,subprocess,os
T=os.environ["T"]
for j in json.load(sys.stdin)["jobs"]:
    print(" ", j["name"], j["conclusion"])
    if j["conclusion"]=="failure" and j["name"].startswith("render"):
        log=subprocess.run(["curl","-sL","-H","Authorization: Bearer "+T,f"https://api.github.com/repos/zainkhan122/thequizwire/actions/jobs/{j[\"id\"]}/logs"],capture_output=True,text=True).stdout
        for line in log.splitlines():
            if ("FAIL  " in line or "pace " in line or "motion " in line) and "FAIL 0" not in line: print("     ", line[29:260])' 
  exec "$0" status
  ;;
status)
  git pull -q --rebase "https://x-access-token:$T@github.com/zainkhan122/thequizwire.git" main 2>/dev/null || true
  python3 - <<'EOF'
import json, datetime
day = datetime.date.today().isoformat(); plan = json.load(open("dispatch/daily.json"))["days"].get(day, [])
L = json.load(open("dispatch/ledger.json"))["posts"]
print(f"== {day}: planned {len(plan)} →", ", ".join(p.split('/')[-1] for p in plan) or "nothing yet")
for ep in plan:
    name = ep.split("/")[-1]; rows = [p for p in L if p["episode"] == name]
    print(f"   {name}: " + (", ".join(f"{p['platform']} {p['state']} {p['due_at'][5:16]}Z" for p in rows) if rows else "NOT scheduled (render failed or still running)"))
EOF
  ;;
esac
