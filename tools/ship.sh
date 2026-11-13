#!/usr/bin/env bash
# ship.sh — the ONLY way to send backlog/re-render episodes to CI from the sandbox.
#   tools/ship.sh [--tag TAG] [--dispatch] [--msg "commit message"] <episode-id-or-path> ...
# Encodes the 2026-11-11 lessons:
#   • preflight for EVERY episode must exit 0 before anything is committed, pushed or dispatched (a `;` chain once pushed a FAIL and burned a run)
#   • render.yml receives series-qualified paths; bare ids cost a whole run ("cd: ep27-…: No such file")
#   • status is set to "ready" and the plan estimate is refreshed, so the repo state matches what CI will build
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
TAG="backlog-$(date -u +%F)"; DISPATCH=false; MSG=""; EPS=()
while [ $# -gt 0 ]; do case "$1" in
  --tag) TAG="$2"; shift 2;; --dispatch) DISPATCH=true; shift;; --msg) MSG="$2"; shift 2;; *) EPS+=("$1"); shift;; esac; done
[ ${#EPS[@]} -gt 0 ] || { echo "usage: tools/ship.sh [--tag TAG] [--dispatch] [--msg MSG] <episode> ..."; exit 2; }
TOKEN_FILE="${GH_TOKEN_FILE:-$HOME/.secrets/gh_token}"; [ -s "$TOKEN_FILE" ] || TOKEN_FILE="$HOME/.cache/secrets/gh_token"
[ -s "$TOKEN_FILE" ] || { echo "ship: no PAT at ~/.secrets/gh_token"; exit 2; }
PATHS=()
for e in "${EPS[@]}"; do                                     # resolve bare ids → series/<series>/<id>
  if [ -d "$e" ]; then p="${e%/}"; else p="$(ls -d series/*/"$e" 2>/dev/null | head -1 || true)"; fi
  [ -n "$p" ] && [ -f "$p/episode.json" ] || { echo "ship: episode not found: $e"; exit 2; }
  PATHS+=("$p")
done
echo "== ship: ${PATHS[*]}  tag=$TAG dispatch=$DISPATCH"
FAILS=0
for p in "${PATHS[@]}"; do
  id="$(basename "$p")"; spec="tools/specs/$id.json"
  if [ -f "$spec" ]; then
    python3 reelkit/placelint.py "$spec" | tail -1 | grep -q "FAIL" && { echo "  ✗ $id placelint FAIL"; python3 reelkit/placelint.py "$spec" | grep "  FAIL" | head -5; FAILS=$((FAILS+1)); continue; }
  fi
  python3 - "$p" <<'PY'
import json,sys; f=sys.argv[1]+'/episode.json'; e=json.load(open(f)); e['status']='ready'; json.dump(e,open(f,'w'),indent=1,ensure_ascii=False)
PY
  python3 reelkit/plan.py "$p" --estimate >/dev/null 2>&1 || true
  if bash reelkit/episode.sh "$p" preflight > "/tmp/pf_$id.log" 2>&1; then echo "  ✓ $id preflight 0"
  else echo "  ✗ $id preflight FAILED (/tmp/pf_$id.log)"; grep -E "^  FAIL|FAIL  " "/tmp/pf_$id.log" | head -6; FAILS=$((FAILS+1)); fi
done
[ "$FAILS" -eq 0 ] || { echo "ship: $FAILS episode(s) failed preflight — nothing committed, pushed or dispatched"; exit 1; }
git add -A series tools reelkit docs .github 2>/dev/null || true   # episode files AND any gate/tool change made alongside them
if ! git diff --cached --quiet; then git commit -qm "${MSG:-ship: ${PATHS[*]}}"; fi
URL="https://x-access-token:$(cat "$TOKEN_FILE")@github.com/zainkhan122/thequizwire.git"
git pull -q --rebase "$URL" main || { echo "ship: rebase onto origin/main failed — resolve and re-run"; exit 1; }   # the daily cron commits dispatch/*.json
git push -q "$URL" HEAD:main
SHA="$(git rev-parse HEAD)"
code=$(curl -s -o /tmp/ship_dispatch.out -w "%{http_code}" -X POST -H "Authorization: Bearer $(cat "$TOKEN_FILE")" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/zainkhan122/thequizwire/actions/workflows/render.yml/dispatches \
  -d "$(python3 -c "import json,sys;print(json.dumps({'ref':'main','inputs':{'episodes':' '.join(sys.argv[2:]),'tag':sys.argv[1],'dispatch':'$DISPATCH','sha':'$SHA'}}))" "$TAG" "${PATHS[@]}")")
[ "$code" = "204" ] || { echo "ship: dispatch HTTP $code"; cat /tmp/ship_dispatch.out; exit 1; }
echo "== ship: pushed $SHA, render.yml dispatched (tag $TAG). Check: GET /actions/workflows/render.yml/runs?per_page=1"
