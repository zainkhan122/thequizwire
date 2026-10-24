#!/usr/bin/env bash
# One-command episode pipeline — identical in the sandbox and on GitHub Actions.
#   bash reelkit/episode.sh <episode_dir> [stage...]
# stages (default: all):
#   pull      media.json → local files (release assets: plates, cached clips, VO takes)
#   tts       Kokoro am_michael takes for lines without a take (voice.py kokoro) — CI, or sandbox after setup.sh
#   words     whisper word times for the takes (voice.py words) → words.json
#   trim      trim VO takes (reelkit/trim_vo.py) into $BUILD
#   plan      timeline.json (reelkit/plan.py; falls back to --estimate when words.json is missing and ESTIMATE=1)
#   voice     voice gate (takes vs performance plan)
#   geo       map data per geo.json scene (reelkit/geodata.py prep → $BUILD/geo)
#   score     VO + ticks + bed → $BUILD/mix.wav (reelkit/quizscore.py; episodes may override with their own score.py)
#   assets    clips: cache-only gen + prep into $HF/assets/clips (maptile / url / AI engines)
#   build     composition (engine/compose.py, or the episode's own build.py when present) → $HF
#   static    browser-less composition run (reelkit/hfstatic.mjs): selectors, runtime errors, determinism   [sandbox]
#   quizlint  quiz format gate · geolint  map honesty + border policy gate
#   facts provenance planlint check textqa layout snap render encode qa   (as in the history system)
#   preflight = plan geo score build static quizlint geolint facts provenance (+ check layout when hyperframes is installed)
# RELEASE=1 makes quizlint/geolint refuse estimated timelines and preview map data (CI sets it).
# Build dir: $BUILD (default ~/.cache/build/<episode-name>) — never inside the repo. out/ is scratch.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EP="$(cd "$1" && pwd)"; shift || true
NAME="$(basename "$EP")"
BUILD="${BUILD:-$HOME/.cache/build/$NAME}"; HF="$BUILD/hf"
STAGES="${*:-pull tts words trim plan voice geo score assets build static quizlint geolint facts provenance check textqa render encode qa}"
_st=""; for _w in $STAGES; do [ "$_w" = lint ] && _w=check
  if [ "$_w" = preflight ]; then _w="plan geo score build static quizlint geolint facts provenance"; command -v hyperframes >/dev/null 2>&1 && _w="$_w check layout"; fi
  _st="$_st $_w"; done; STAGES=" $_st "
KNOWN="pull tts words trim plan voice geo score assets build static quizlint geolint facts provenance planlint check textqa layout snap render encode qa"
for _w in $STAGES; do [[ " $KNOWN " == *" $_w "* ]] || { echo "episode.sh: unknown stage '$_w' (known: $KNOWN)" >&2; exit 2; }; done
FPS="${FPS:-30}"; CRF="${CRF:-18}"; WORKERS="${WORKERS:-auto}"; REL=""; [ "${RELEASE:-0}" = 1 ] && REL="--release"
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 DO_NOT_TRACK=1 HYPERFRAMES_SKIP_SKILLS=1
export PATH="$HOME/.cache/bin:$HOME/.cache/node/bin:$HOME/.cache/npm-global/bin:/usr/local/bin:$PATH"
# quiz layout: the caption band is the question card (y 1190–1600); card elements declare data-layout-allow-caption-zone
export CAPTION_ZONE="${CAPTION_ZONE:-x0=0;y0=0.62;x1=1;y1=0.835;severity=error;seek=.25,.5,.75}"
mkdir -p "$BUILD" "$HOME/.cache/tmp/hftmp" "$EP/out"; export TMPDIR="$HOME/.cache/tmp/hftmp"
log() { printf '\n== [%s] %s\n' "$NAME" "$*"; }
has() { [[ "$STAGES" == *" $1 "* ]]; }

has pull   && { log "pull media (release assets -> $EP)"; python3 "$REPO/reelkit/media.py" pull "$EP"; }
has tts    && { log "Kokoro takes (am_michael) for lines without one"
  _need=""; for _l in $(python3 -c "import json,sys;print(' '.join(l['id'] for l in json.load(open('$EP/voice.json'))['lines'] if l.get('silence') is None))"); do
    [ -f "$EP/vo/$_l.wav" ] || [ -f "$EP/vo/$_l.mp3" ] || _need="$_need,$_l"; done
  if [ -n "$_need" ]; then python3 "$REPO/reelkit/voice.py" kokoro "$EP" --only "${_need#,}"; else echo "  all takes present"; fi; }
has words  && { log "whisper word times"; python3 "$REPO/reelkit/voice.py" words "$EP"; }
has trim   && { log "trim VO"; python3 "$REPO/reelkit/trim_vo.py" "$EP/vo" "$BUILD" --check "$EP/words.json"; }
has plan   && { log "timeline"
  if [ -f "$EP/words.json" ]; then python3 "$REPO/reelkit/plan.py" "$EP"
  elif [ "${ESTIMATE:-1}" = 1 ] && [ "${RELEASE:-0}" != 1 ]; then python3 "$REPO/reelkit/plan.py" "$EP" --estimate
  else echo "episode.sh: no words.json (run tts + words) and estimates are not allowed for a release" >&2; exit 1; fi; }
has voice  && { log "voice gate (takes vs performance plan)"; python3 "$REPO/reelkit/voice.py" check "$EP" --report "$EP/out/voice.json"; }
has geo    && { if [ -f "$EP/geo.json" ]; then log "map data (Natural Earth → $BUILD/geo)"; python3 "$REPO/reelkit/geodata.py" prep "$EP" --out "$BUILD/geo" ${GEO_FIXTURE:+--fixture "$GEO_FIXTURE"}; fi
                python3 "$REPO/reelkit/stickers.py" prep "$EP" "$BUILD"; python3 "$REPO/reelkit/brand.py" prep "$EP" "$BUILD"; python3 "$REPO/reelkit/photos.py" prep "$EP" "$BUILD"; }
has score  && { log "score + SFX + mix"; if [ -f "$EP/score.py" ]; then python3 "$EP/score.py" "$BUILD" "$BUILD"; else python3 "$REPO/reelkit/quizscore.py" "$EP" "$BUILD" "$BUILD"; fi; cp "$BUILD/mix_report.json" "$EP/out/" 2>/dev/null || true; }
has assets && { if [ -f "$EP/clips.json" ] && python3 -c "import json,sys;sys.exit(0 if json.load(open('$EP/clips.json'))['clips'] else 1)"; then
  log "clips (cache-only gen + prep)"; python3 "$REPO/reelkit/clips.py" gen "$EP" --cache-only || log "some clips not cached (never spends GPU here)"; python3 "$REPO/reelkit/clips.py" prep "$EP" "$HF"; fi
  [ -f "$EP/make_assets.py" ] && { log "episode assets"; python3 "$EP/make_assets.py" "$HF"; } || true; }
has build  && { log "composition"; if [ -f "$EP/build.py" ]; then python3 "$EP/build.py" "$HF"; else python3 "$REPO/engine/compose.py" "$EP" "$HF"; fi
  mkdir -p "$HF/assets"; [ -f "$BUILD/mix.wav" ] && cp "$BUILD/mix.wav" "$HF/assets/mix.wav" || true
  # mix.wav is referenced only when present at compose time: rebuild once so the <audio> tag is in
  [ -f "$HF/assets/mix.wav" ] && ! grep -q 'id="mix"' "$HF/index.html" && { if [ -f "$EP/build.py" ]; then python3 "$EP/build.py" "$HF"; else python3 "$REPO/engine/compose.py" "$EP" "$HF" >/dev/null; fi; } || true; }
has static && { log "browser-less composition run (selectors · runtime · determinism)"; node "$REPO/reelkit/hfstatic.mjs" "$HF"; }
has quizlint && { log "quiz format gate"; python3 "$REPO/reelkit/quizlint.py" "$EP" --hf "$HF" $REL --report "$EP/out/quizlint.json"; }
has geolint  && { log "map honesty + border policy gate"; ONL=""; [ "${GEOLINT_ONLINE:-0}" = 1 ] && ONL="--online"; python3 "$REPO/reelkit/geolint.py" "$EP" --hf "$HF" $REL $ONL --report "$EP/out/geolint.json"; }
has facts  && { log "fact gate (claims ledger ↔ narration + on-screen text)"; python3 "$REPO/reelkit/factcheck.py" "$EP" --hf "$HF" --report "$EP/out/factcheck.json" --sources-md "$EP/out/sources.md"; }
has provenance && { log "provenance gate (origin + licence of every shipped file, credits, AI disclosure)"; python3 "$REPO/reelkit/provenance.py" "$EP" --hf "$HF" --report "$EP/out/provenance.json" --credits-md "$EP/out/credits.md"; }
has planlint && { if [ -f "$EP/shots.json" ]; then log "plan lint (story-format episodes with shots.json)"; python3 "$REPO/reelkit/planlint.py" "$EP" --hf "$HF" --report "$EP/out/planlint.json"
  else log "plan lint skipped — quiz format has no shots.json (quizlint Q5/Q6 cover beats, holds and motion)"; fi; }
has check  && { log "composition check (lint + runtime + layout collisions)"; python3 "$REPO/reelkit/hfcheck.py" "$HF" --report "$EP/out/check.json"; }
has textqa && { log "readability gate (every on-screen text ≥ 3:1, target 4.5:1)"; python3 "$REPO/reelkit/textqa.py" "$HF" --report "$EP/out/textqa.json" --sheet "$BUILD/textqa_fails.jpg"; }
has layout && { log "layout gate (dead zones + reading time, DOM only)"; python3 "$REPO/reelkit/textqa.py" "$HF" --layout-only; }
has snap   && { log "snapshots"
  # default: 0.8 s into every scene (hook, options, countdown, reveal, story…, cta), clamped inside the episode
  AT="${SNAP_AT:-$(python3 -c "import json;T=json.load(open('$EP/timeline.json'));print(','.join(str(round(min(s['start']+0.8,T['total']-0.5),1)) for s in T['scenes']))")}"
  (cd "$HF" && hyperframes snapshot --at "$AT" --no-end --timeout 30000 -o "$BUILD/snaps" >/dev/null 2>&1) || log "snapshot failed (non-fatal)"
  ls "$BUILD/snaps" 2>/dev/null || true; }
has render && { log "render ${FPS}fps crf $CRF workers $WORKERS"; (cd "$HF" && hyperframes render -f "$FPS" -w "$WORKERS" --crf "$CRF" -o "$BUILD/render.mp4" 2>&1 | grep -vE "@hf-progress|Render:trace|^\s+█" | tail -12); }
has encode && { log "upload master (H.264 High 4.2, ${MASTER_BITRATE:-10M} target / ${MASTER_MAXRATE:-12M} cap, AAC 256k, faststart)"
  # Constrained ABR, not CRF: flat vector quiz frames at CRF 18 land near 0.7 Mbps, which YouTube's transcoder then
  # softens (text edges). A 10 Mbps target keeps every master upload-grade and makes qa.py's ≥ 5 Mbps floor a real check.
  ffmpeg -hide_banner -loglevel error -y -i "$BUILD/render.mp4" -i "$BUILD/mix.wav" -map 0:v -map 1:a -c:v libx264 -preset "${PRESET:-faster}" \
    -b:v "${MASTER_BITRATE:-10M}" -maxrate "${MASTER_MAXRATE:-12M}" -bufsize "${MASTER_BUFSIZE:-24M}" -pix_fmt yuv420p -profile:v high -level 4.2 \
    -r "$FPS" -g "$((FPS * 2))" -bf 2 -threads "${THREADS:-2}" -c:a aac -b:a 256k -ar 48000 -movflags +faststart -shortest "$EP/out/final.mp4"
  ffmpeg -hide_banner -loglevel error -y -ss "${COVER_AT:-1.3}" -i "$BUILD/render.mp4" -frames:v 1 -q:v 2 "$EP/out/cover.jpg"; ls -la "$EP/out"; }
has qa     && { log "QA"; python3 "$REPO/reelkit/qa.py" "$EP/out/final.mp4" --words "$EP/timeline.json" --report "$EP/out/qa.json"; }
log "done → $EP/out"
