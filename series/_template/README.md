# Episode folder (created from series/_template by tools/new_episode.py)

| file | owner | what |
|---|---|---|
| episode.json | author | id, series, number, difficulty, the quiz (question/options/correct), post copy, promise |
| voice.json | author | performance plan: one line per scene, role, tone, cue words; `silence` lines for the countdown |
| research.json | author | claims ledger — every spoken/shown fact with ≥ 2 sources (gate: factcheck) |
| geo.json | author | map scenes: projection (+ reason), fit, layers, pins (with Wikidata `qid`), labels, scalebar, disputed (gate: geolint) |
| visuals.json | author | stages, elements and timed beats; the only "build script" an episode needs (engine/compose.py) |
| clips.json | author | optional motion clips: `maptile` (VersaTiles docker), `globe` (reelkit/globe.py), `url` archive, Wan/LTX |
| timeline.json | generated | reelkit/plan.py (— `--estimate` in the sandbox, real whisper timing in CI) |
| words.json, vo/ | generated | CI `tts` stage: Kokoro am_michael takes + whisper word times (never committed; media release) |
| media.json | generated | provenance for every file in the video (gate: provenance) |
| POST_KIT.md | generated+author | title/description/credits/AI disclosure for the manual upload |

Pipeline: `bash reelkit/episode.sh <ep> plan geo build quizlint geolint facts provenance` locally, then
`python3 reelkit/cloud.py render <ep> --wait` for tts → render → encode → qa on GitHub Actions.
