# quizwire — the TheQuizWire Shorts system

Faceless 9:16 quiz Shorts (45–60 s) for **@thequizwire-com** in four series — **Geo Blitz** (maps), **Body & Brain**, **Sports Sprint**,
**Wild Files** — generated from JSON episode folders by a free toolchain: HyperFrames (HTML + GSAP) compositions, **Kokoro `am_michael`**
narration, a d3-geo / Natural Earth map engine, a procedural score, and nine quality gates. Heavy work runs on **GitHub Actions**
(public repo = free runners); the Arena sandbox authors, builds HTML and runs the offline gates. Nothing here uploads to YouTube.

> Phase 1 (this commit) = tooling, engines, gates, templates, docs. **No episodes have been produced yet** — by owner instruction.
> `RESUME.md` says what to do next; `docs/PLAN.md` is the full phased plan.

## 60-second tour
```bash
source bootstrap.sh                                  # git auth from ~/.cache/secrets/gh_token, light toolkit, resume pack
python3 tests/selftest.py                            # ~15 s: map runtime tests, both fixture episodes through every offline gate, negative cases
python3 tools/new_episode.py geo-blitz "Which is the longest river in Africa?" --options Nile Congo Niger Zambezi --correct 0
bash reelkit/episode.sh series/geo-blitz/ep10-… plan geo build static quizlint geolint facts provenance   # offline gates
python3 reelkit/cloud.py render series/geo-blitz/ep10-… --tag ep10-v1 --wait                             # CI: tts → render → encode → qa → Release
```

## How an episode flows
```
episode.json  voice.json  research.json  geo.json  visuals.json  clips.json      ← authored (tools/new_episode.py scaffolds them)
      │            │            │            │          │            │
   plan.py ──── timeline.json (estimate locally; whisper word times on CI after the tts stage)
      │                                       │
 geodata.py prep ── Natural Earth → ~/.cache/build/<ep>/geo/<scene>.json (clipped TopoJSON, disputed polygons)
      │                                       │
 engine/compose.py ── hf/index.html (quiz card, map stage via engine/geo-runtime.js, charts, beats → one paused GSAP timeline)
      │
 quizscore.py ── mix.wav (Kokoro takes placed per timeline + procedural bed/ticks/sting; mastered −14 LUFS on CI)
      │
 gates: hfstatic · quizlint · geolint · factcheck · provenance · planlint · hyperframes check · textqa · qa
      │
 CI render → <Question>.mp4 + cover.jpg + every gate report → GitHub Release (media never enters git)
```
`bash reelkit/episode.sh <ep> [stages]` runs any subset; stage list and env flags are in the script header.

## The gates (a FAIL blocks the render)
| gate | file | what it refuses |
|---|---|---|
| quizlint | `reelkit/quizlint.py` | not exactly 4 options, answer_line ≠ correct option, wrong scene order, countdown < 2 s silence, > 60 s, story < 25 %, text over length, beats that don't resolve, stage that never moves, motion share < promise, estimated timeline on `--release` |
| geolint | `reelkit/geolint.py` | conformal projection under a size claim, distance claim without scale bar, pins off their Wikidata coordinates (`--online`), registry region without `disputed` plates (docs/BORDER_POLICY.md), preview-quality data on release, missing "Natural Earth"/OSM credit |
| facts | `reelkit/factcheck.py` | any narrated or on-screen fact (incl. map pins/labels/policy plates) not anchored in `research.json`, thin sourcing per evidence tier, guardrail wording (sovereignty terms, contested names) |
| provenance | `reelkit/provenance.py` | any shipped file without kind/licence/provider/source; licences off the allow-list; missing credits |
| static | `reelkit/hfstatic.mjs` | selectors that don't exist, runtime errors, non-determinism — without a browser |
| voice | `reelkit/voice.py check` | takes that skip words / misread numbers / rush a tone band (whisper, CI) |
| planlint · check · textqa · qa | history toolkit | motion promise, HyperFrames validity, caption-zone collisions, unreadable text, loudness/bitrate/ASR of the final |

## Repo map
```
reelkit/   pipeline + gates (episode.sh, plan, geodata, quizscore, quizlint, geolint, factcheck, provenance, clips[maptile], voice, tts_kokoro, cloud, media…)
engine/    composition: compose.py (data-driven assembler), quiz.py (card), geo.py + geo-runtime.js (maps), charts.py, fx.py, vendor/ (gsap, d3-geo, topojson), data/ (110m atlas)
series/    series.json (channel + series registry + counters), _template/ (fixture episode), <slug>/SERIES.md
docs/      PLAN.md · BORDER_POLICY.md + border_registry.json · DATA_SOURCES.md · MAPTILE.md · CHANNEL_BASELINE.md · img/ (map previews)
tests/     selftest.py, test_geo_runtime.mjs, fixtures/ (ep-disputed = Kashmir path, ne_disputed_kashmir.geojson)
tools/     new_episode.py, sync.sh, state.py, repo_guard.py
.github/   check (every push) · render (per episode) · selftest (weekly/manual, real runner) · geodata (cache warm)
```

## Owner decisions baked in
Free tools only · public-repo Actions + sandbox · Kokoro `am_michael` · disputed borders shown with *Administered by / Claimed by*
plates, never hidden, never "owned" · every fact sourced twice · media in Releases, never git · no auto-posting · four feed series,
numbering continues from the feed (Geo Blitz #10, Body & Brain #4, Sports Sprint #9, Wild Files #7).

Licences: code in this repo is the owner's; vendored runtime in `engine/vendor/LICENSES.md`; fonts in `fonts/LICENSES.md`; data
and media rules in `docs/DATA_SOURCES.md`.
