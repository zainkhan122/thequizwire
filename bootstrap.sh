#!/usr/bin/env bash
# Fresh-session bootstrap (Arena sandbox). From an EMPTY workspace:
#   1. save the GitHub token:  mkdir -p ~/.cache/secrets && printf %s "$TOKEN" > ~/.cache/secrets/gh_token
#   2. git clone https://github.com/zainkhan122/thequizwire.git ~/thequizwire   (use the token if the repo is private)
#   3. source ~/thequizwire/bootstrap.sh
# Restores the toolchain into ~/.cache (not persisted, not counted against the workspace budget),
# wires git auth to the token file, pulls nothing heavy until an episode needs it, then prints the resume pack.
HROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod 700 "$HOME/.cache/secrets" 2>/dev/null || true
# Arena snapshots drop .git/config -> restore remote + identity + auth every session (idempotent)
SLUG="$(cat "$HROOT/.repo")"
git -C "$HROOT" remote get-url origin >/dev/null 2>&1 || git -C "$HROOT" remote add origin "https://github.com/$SLUG.git"
git -C "$HROOT" config user.name  >/dev/null || git -C "$HROOT" config user.name "zainkhan122"
git -C "$HROOT" config user.email >/dev/null || git -C "$HROOT" config user.email "zainkhan122@users.noreply.github.com"
git -C "$HROOT" config branch.main.remote origin; git -C "$HROOT" config branch.main.merge refs/heads/main
if [ -s "$HOME/.cache/secrets/gh_token" ]; then
  chmod 600 "$HOME/.cache/secrets/gh_token"
  git -C "$HROOT" config credential.helper '!f() { echo username=x-access-token; echo "password=$(cat $HOME/.cache/secrets/gh_token)"; }; f'
  git -C "$HROOT" fetch -q origin main && git -C "$HROOT" merge -q --ff-only origin/main 2>/dev/null; \
  echo "repo @ $(git -C "$HROOT" rev-parse --short HEAD) (origin/main $(git -C "$HROOT" rev-parse --short origin/main))"
  [ -n "$(git -C "$HROOT" status --porcelain)" ] && echo "!! uncommitted local changes — review, then: bash tools/sync.sh"
else
  echo "!! no token at ~/.cache/secrets/gh_token — read-only mode (ask the owner for the token)"
fi
# shellcheck disable=SC1091
source "$HROOT/reelkit/setup.sh"
python3 "$HROOT/tools/state.py" show
echo; echo "Next: read $HROOT/RESUME.md (full context) — then continue with the first item under 'next'."

# --- local browser toolchain (optional, ~2 min, not persisted): HyperFrames snapshots/check/textqa + Playwright comps in the sandbox ---
# usage: bash bootstrap.sh --browser
if [ "${1:-}" = "--browser" ]; then
  export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 DO_NOT_TRACK=1 HYPERFRAMES_SKIP_SKILLS=1
  N=$HOME/.cache/node/node-v22.12.0-linux-x64
  [ -x "$N/bin/node" ] || { mkdir -p ~/.cache/node && curl -sL https://nodejs.org/dist/v22.12.0/node-v22.12.0-linux-x64.tar.xz | tar -xJ -C ~/.cache/node; }
  export PATH=$N/bin:$PATH
  command -v hyperframes >/dev/null && hyperframes --version 2>/dev/null | grep -q 0.8.137 || npm i -g --silent hyperframes@0.8.137
  pip install -q playwright 2>/dev/null; sudo -n python3 -m playwright install-deps chromium >/dev/null 2>&1 || true
  python3 -m playwright install chromium >/dev/null 2>&1; hyperframes browser ensure >/dev/null 2>&1
  echo "browser toolchain: node $(node -v) · hyperframes $(hyperframes --version 2>/dev/null | tail -1) · snapshots: (cd <build>/hf && hyperframes snapshot --at 0.5,9,20 --no-end -o out/)"
  echo "remember: export PATH=$N/bin:\$PATH in every shell that calls hyperframes"
fi
