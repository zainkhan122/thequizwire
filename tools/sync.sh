#!/usr/bin/env bash
# Sync EVERYTHING to the repo (SSOT): media → release assets (manifests), code/docs → git commit + push.
#   bash tools/sync.sh "commit message"
# Run after every meaningful change so a fresh session can resume exactly here.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
MSG="${1:-sync: $(date -u +%Y-%m-%dT%H:%MZ)}"
# 1) media: any dir that has (or should have) a media.json
for d in $(git ls-files '*/media.json' | xargs -r -n1 dirname) ${EXTRA_MEDIA_DIRS:-}; do
  python3 reelkit/media.py push "$d" | tail -1
done
# 2) refresh the machine-readable state stamp
python3 tools/state.py stamp >/dev/null
# 3) guard + commit + push
git add -A
python3 tools/repo_guard.py
if git diff --cached --quiet; then echo "nothing to commit"; else git commit -q -m "$MSG" && echo "committed: $MSG"; fi
git push -q origin HEAD:main && echo "pushed → origin/main @ $(git rev-parse --short HEAD)"
