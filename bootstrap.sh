#!/usr/bin/env bash
# Fresh-session bootstrap (Arena sandbox). From an EMPTY workspace:
#   1. save the GitHub token:  mkdir -p ~/.cache/secrets && printf %s "$TOKEN" > ~/.cache/secrets/gh_token
#   2. git clone https://github.com/zainkhan122/quizwire.git ~/quizwire   (use the token if the repo is private)
#   3. source ~/quizwire/bootstrap.sh
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
