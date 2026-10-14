# reelkit — the QuizWire pipeline and gates

One entry point: `bash reelkit/episode.sh <episode_dir> [stages…]` (header lists stages + env flags). Everything below is a stage,
a gate, or a helper it calls. Files marked *history* came from the owner's history repo and are used as-is.

| file | role | runs where |
|---|---|---|
| `episode.sh` | stage runner (`preflight` = the offline set) | both |
| `plan.py` | `timeline.json` from `voice.json` (+ `words.json` on CI; `--estimate` locally) | both |
| `geodata.py` | fetch / prep / disputed / check — Natural Earth via world-atlas + NE disputed areas → per-scene clipped TopoJSON | both |
| `quizscore.py` | procedural score + VO placement → `mix.wav`, `mix_report.json` (`synth.py` instruments, `master.py` loudness on CI) | both (mastered on CI) |
| `quizlint.py` | quiz format gate Q1–Q7 | both |
| `geolint.py` | map honesty + border policy gate P1–P6 (`docs/border_registry.json`, `--online` Wikidata pin check) | both |
| `factcheck.py` *history + quiz rules* | claims ledger ↔ narration + on-screen text (incl. map labels/plates) | both |
| `provenance.py` *history + geodata rules* | licence/origin of every shipped file, credits | both |
| `hfstatic.mjs` | runs the composition in Node (vm + minimal DOM): selectors, runtime errors, determinism | both |
| `geopreview.mjs` + `svgraster.py` | browser-less PNG preview of a map scene (`docs/img/`) | sandbox |
| `planlint.py` `hfcheck.py` `textqa.py`+`textqa.cjs` `qa.py` *history* | motion promise · HyperFrames validity + caption zone · readability · final-file QA | CI |
| `voice.py` *history* + `tts_kokoro.py` + `trim_vo.py` | Kokoro `am_michael` takes, whisper word times, performance check | CI (`tts`, `words`, `voice` stages) |
| `clips.py` *history + `maptile`* + `clipcache.py` | declared clips → cached mp4s (VersaTiles docker, archive URLs, Wan/LTX) | CI |
| `cloud.py` `media.py` `naming.py` *history* | dispatch/monitor the render workflow · Release media store · delivery names | sandbox |
| `find.py` *history* | Wikimedia/Commons media finder (metadata only) | sandbox |
| `decide.py` *history* | `decisions.jsonl` (approved exceptions, read by planlint) | sandbox |
| `script.py` *history* | text normalisation used by `tts_kokoro.py` | both |
| `ci_setup.sh` / `setup.sh` | runner toolchain / sandbox light toolkit | CI / sandbox |

Reports land in `<episode>/out/*.json` (+ `sources.md`, `credits.md`) and travel with the Release.
