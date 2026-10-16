#!/usr/bin/env bash
# Dispatch rendered episodes to Buffer queues (YouTube · Instagram · Facebook · X · Threads).
#   bash reelkit/dispatch.sh [--tag <release-tag>] [--run <render run number>] [--live] [--channels youtube,instagram,facebook,twitter,threads] <episode_dir> [...]
# Renders are looked up in release --tag, else in the per-episode release <episode>-r<run> that render.yml creates when no tag is given.
# Per episode: release → out/final.mp4 → postkit (SEO copy + lint) → mediahost push (public Pages URL, verified)
#              → buffer dispatch (addToQueue; ledger dispatch/ledger.json). Dry-run unless --live.
# Phase 1 copies + postkits every episode and git-pushes all media in ONE commit; phase 2 waits for Pages once, then queues.
# Episodes whose MP4 is not in the release are skipped (a failed render never reaches Buffer). Exit 1 if any
# requested episode failed to dispatch; already-queued episodes are reported and count as success.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG=""; RUN=""; LIVE=""; CHANNELS=""; EPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    --run) RUN="$2"; shift 2;;
    --live) LIVE="--live"; shift;;
    --channels) CHANNELS="--channels $2"; shift 2;;
    *) EPS+=("$1"); shift;;
  esac
done
[ -n "$TAG$RUN" ] || { echo "dispatch: --tag <release> or --run <n> required"; exit 2; }
[ ${#EPS[@]} -gt 0 ] || { echo "dispatch: no episodes"; exit 2; }
fetch_release() {  # $1 tag → dir (cached per tag); empty on failure
  local d="${RUNNER_TEMP:-/tmp}/release-$1"
  [ -d "$d" ] || python3 "$REPO/reelkit/cloud.py" fetch "$1" "$d" >/dev/null 2>&1 || { rm -rf "$d"; return 1; }
  echo "$d"
}
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "### Dispatch · release \`${TAG:-<episode>-r$RUN}\` · ${LIVE:-dry-run}" >> "$SUMMARY"; echo "| episode | media | youtube | instagram | facebook | x | threads |" >> "$SUMMARY"; echo "|---|---|---|---|---|---|---|" >> "$SUMMARY"
FAILS=0; CAND=(); READY=()
# ---- phase 1: copy + upload every render (no waiting), so one Pages deploy covers them all
for EP in "${EPS[@]}"; do
  NAME="$(basename "$EP")"; STEM="$(python3 "$REPO/reelkit/naming.py" stem "$EP")"
  echo "== $NAME"
  MP4=""
  for T in ${TAG:+"$TAG"} ${RUN:+"$NAME-r$RUN"}; do
    REL="$(fetch_release "$T" || true)"; [ -n "$REL" ] && [ -f "$REL/$STEM.mp4" ] && { MP4="$REL/$STEM.mp4"; echo "   render: release $T"; break; }
  done
  if [ -z "$MP4" ]; then echo "   no $STEM.mp4 in release(s) — not rendered, skipping"; echo "| $NAME | not rendered | — | — | — | — | — |" >> "$SUMMARY"; continue; fi
  mkdir -p "$EP/out"; cp "$MP4" "$EP/out/final.mp4"
  if ! python3 "$REPO/reelkit/postkit.py" build "$EP" > "$EP/out/postkit.log" 2>&1; then echo "   postkit FAIL"; tail -5 "$EP/out/postkit.log"; echo "| $NAME | postkit FAIL | — | — | — | — | — |" >> "$SUMMARY"; FAILS=$((FAILS+1)); continue; fi
  grep -E "WARN|FAIL" "$EP/out/postkit.log" | sed 's/^/   /'
  rm -f "$EP/out/media_url.txt"; CAND+=("$EP")
done
# one git push for every candidate (one commit → one Pages deploy); each episode gets out/media_url.txt
if [ ${#CAND[@]} -gt 0 ]; then
  python3 "$REPO/reelkit/mediahost.py" push "${CAND[@]}" --no-wait 2>&1 | tee "${RUNNER_TEMP:-/tmp}/mediahost.log" | grep -v "^MEDIA_URL "
  for EP in "${CAND[@]}"; do
    NAME="$(basename "$EP")"
    if [ -s "$EP/out/media_url.txt" ]; then READY+=("$EP"); else echo "   $NAME: mediahost FAIL"; echo "| $NAME | media FAIL | — | — | — | — | — |" >> "$SUMMARY"; FAILS=$((FAILS+1)); fi
  done
fi
# ---- phase 2: wait for the hosted files (one Pages deploy; after the first timeout the rest are probed once), then queue
WAIT="${MEDIA_WAIT:-900}"
for EP in "${READY[@]}"; do
  NAME="$(basename "$EP")"; URL="$(cat "$EP/out/media_url.txt")"
  echo "== $NAME → Buffer"
  if ! python3 "$REPO/reelkit/mediahost.py" verify "$URL" --wait "$WAIT" | tee -a "$EP/out/mediahost.log" | tail -1; then
    [ "$WAIT" != 0 ] && echo "::warning::$URL not live after ${WAIT}s — is GitHub Pages enabled on the media repo (Settings → Pages → main / root)? Files are pushed; rerun once the site answers."
    WAIT=0; echo "   media not live"; echo "| $NAME | media not live | — | — | — | — | — |" >> "$SUMMARY"; FAILS=$((FAILS+1)); continue
  fi
  # shellcheck disable=SC2086
  if python3 "$REPO/reelkit/buffer.py" dispatch "$EP" --media-url "$URL" $LIVE $CHANNELS | tee "$EP/out/dispatch.log"; then
    row="| $NAME | ok |"; for p in youtube instagram facebook twitter threads; do
      st="$(grep -E "^ +$p " "$EP/out/dispatch.log" | sed -E 's/^ +[a-z]+ +//' | head -1 | cut -c1-48)"; row="$row ${st:-—} |"; done
    echo "$row" >> "$SUMMARY"
  else
    echo "   buffer FAIL"; echo "| $NAME | buffer FAIL | — | — | — | — | — |" >> "$SUMMARY"; FAILS=$((FAILS+1))
  fi
done
echo "dispatch: done · failures $FAILS"
exit $(( FAILS > 0 ? 1 : 0 ))
