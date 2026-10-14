# RESUME.md — where this repo is and what happens next

_Updated 2026-10-14 (end of Phase 1 session). Owner decisions: free tools only · phases per session · four feed series · Kokoro
`am_michael` · disputed borders shown with controller/claimant plates · **no videos until the owner says go**._

## Now
**Phase 1 — "get the tools and make the system" — is built and self-tested offline.** `python3 tests/selftest.py` is green
(map runtime tests; `series/_template` and `tests/fixtures/ep-disputed` through plan → geo → compose → hfstatic → quizlint →
geolint → factcheck → provenance; three negative cases; the procedural mix). Nothing has been rendered on a runner yet, and no
episode has been produced — by instruction.

What exists (all new unless noted; history-repo toolkit reused where it fit):
- **Pipeline** `reelkit/episode.sh` with quiz stages `pull tts words trim plan voice geo score assets build static quizlint geolint facts provenance planlint check textqa layout snap render encode qa` (+ `preflight`), env `RELEASE GEO_FIXTURE GEOLINT_ONLINE ESTIMATE`.
- **Engines** `engine/compose.py` (data-driven assembler from `visuals.json`), `engine/quiz.py` (card/options/countdown/reveal/fact/CTA; wrong options `data-fc=distractor`, letters `data-fc=skip`), `engine/geo.py` + `engine/geo-runtime.js` (d3-geo projections, fit, layers, pins, labels, scale bar, disputed plates, camera; spec/data inline as JSON), `engine/charts.py` (bars), `engine/fx.py` (history), vendored GSAP/d3/topojson + 110m atlas.
- **Data** `reelkit/geodata.py fetch|prep|disputed|check` (world-atlas 110/50/10m + NE disputed areas → `~/.cache/geodata`, 8.6 MB warm; offline fixture for Kashmir).
- **Audio** `reelkit/quizscore.py` (takes per timeline + pad bed in the series key + ticks/riser/bell/hit/whoosh + ducking; `master.finish` on CI, peak-normalised preview without ffmpeg); `reelkit/tts_kokoro.py --selftest`; `voice.py kokoro|words|check` (history).
- **Gates** `quizlint.py` (Q1–Q7), `geolint.py` (P1–P6, `docs/border_registry.json` = 29 regions), `factcheck.py` (history + quiz conventions: distractor/skip units, `vo_exempt`, map text from the inline scene spec), `provenance.py` (allow-list += ISC/MIT/BSD-3/ODbL/Copernicus, kind `data`, vendor JS), `hfstatic.mjs`, `planlint/hfcheck/textqa/qa` (history).
- **Clips** `clips.py` engine `maptile` (VersaTiles animator via docker on CI; lint/spec/cache/provenance wired; CLI flags to verify on first CI run — `docs/MAPTILE.md`).
- **Scaffolding** `tools/new_episode.py <series> "<question>" --options A B C D --correct i` (bumps `series/series.json` counters; produces a folder that fails only on the TODOs).
- **CI** `.github/workflows/check.yml` (compile, guard, runtime tests, selftest, every episode's offline gates), `render.yml` (full pipeline → Release, RELEASE=1 GEOLINT_ONLINE=1), `selftest.yml` (toolchain + Kokoro smoke + template render + animator `--help`), `geodata.yml` (weekly cache warm); `reelkit/ci_setup.sh` installs ffmpeg, chrome libs, hyperframes@0.8.137, kokoro-onnx + model files, faster-whisper, geodata.
- **Docs** `README.md`, `AGENTS.md`, `docs/PLAN.md` (the phased plan + decision overrides), `docs/BORDER_POLICY.md` (+ registry table generated from JSON), `docs/DATA_SOURCES.md`, `docs/MAPTILE.md`, `docs/CHANNEL_BASELINE.md`, `series/<slug>/SERIES.md` ×6, `docs/img/preview_*.png` (browser-less map previews).

## Next (in order)
1. **Owner:** create the empty public repo (default `zainkhan122/quizwire` — change `.repo` if different) and hand over a fine-grained
   PAT (contents: read/write, actions: read/write, workflows) → `~/.cache/secrets/gh_token`. Then `source bootstrap.sh && bash tools/sync.sh "phase 1"`.
2. **First CI proof (Phase 1 → 2 hand-off, ~25 min of runner time, zero sandbox risk):** Actions → `selftest` → Run. Expect: toolchain
   installs, Kokoro selftest OK, `_template` renders (`series/_template/out/final.mp4` artifact), animator `--help` printed.
   Fix anything red in `reelkit/ci_setup.sh` / `episode.sh`; paste the animator CLI into `docs/MAPTILE.md` and adjust `gen_maptile` if flags differ.
3. **Phase 2 (only when the owner says "make videos"):** pilot episode per `docs/PLAN.md §4` — Geo Blitz #10 via
   `tools/new_episode.py`, real research ledger, `geo.json` at 50m/10m, `cloud.py render … --wait`, review snaps/QA, owner uploads from POST_KIT.
   Then Body & Brain #4 (needs `callouts`/`counter` in `engine/charts.py`), Sports Sprint #9 (`strip`/`compare`), Wild Files #7 (`compare`, GBIF range layer).
4. **Phase 2 engine backlog:** `callouts`, `counter`, `compare`, `strip` in `engine/charts.py` + compose actions; raster globe (Blue Marble) stage; `geofacts.py`
   (Wikidata/Factbook → draft claims); `textqa` caption-zone profile for the quiz card; `cloud.py` adaptation check against the new workflow inputs.
5. Known soft spots to watch on the first runner: `voice.py words` on Kokoro takes (trim thresholds), `master.finish` levels for the quiz bed
   (VO-over-music ≥ 15 dB), HyperFrames caption-zone (`hfcheck --caption-zone` severity error) against the answer card at y 960.

## Secrets / accounts
- GitHub PAT: not yet provided for this repo (needed for step 1). Stored only at `~/.cache/secrets/gh_token`.
- No other accounts needed: VersaTiles tiles + animator image are public; Kokoro/whisper models download from GitHub/HF anonymously; Wikidata is open.

## Decisions log
| date | decision | by |
|---|---|---|
| 2026-10-14 | New repo `quizwire` for all four feed topics (not a geo-only repo, not the history repo) | owner |
| 2026-10-14 | Narrator Kokoro `am_michael` | owner |
| 2026-10-14 | Sensitive borders included and labelled with controller + claimants (policy + registry + geolint P4) | owner |
| 2026-10-14 | Phase 1 = tools/system only; no episode production | owner |
| 2026-10-14 | Geo Blitz / Body & Brain / Sports Sprint / Wild Files active; Cosmic Quiz, Time Vault registered inactive | agent (from feed), to confirm |
| 2026-10-14 | Vector maps (d3-geo + Natural Earth) are the default stage; VersaTiles flyovers are cached hero clips; Blue Marble globe deferred | agent |
