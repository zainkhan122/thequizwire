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
- **Docs** `README.md`, `AGENTS.md`, `docs/OPERATING_MODEL.md`, `docs/PHASE_PROTOCOL.md`, `docs/PLAN.md` (the phased plan + decision overrides), `docs/BORDER_POLICY.md` (+ registry table generated from JSON), `docs/DATA_SOURCES.md`, `docs/MAPTILE.md`, `docs/CHANNEL_BASELINE.md`, `series/<slug>/SERIES.md` ×6, `docs/img/preview_*.png` (browser-less map previews).

## Current phase
```
Phase 1.5 — Connect
goal        : repo on GitHub, first push, `check` workflow green
entry       : owner has created the PRIVATE repo (default zainkhan122/thequizwire → edit .repo if different) and issued a fine-grained
              PAT (this repo only: Contents + Actions + Workflows read/write; Metadata read is automatic)
steps       : 1) store PAT at ~/.cache/secrets/gh_token (chmod 600); `source bootstrap.sh` → remote wired
              2) `bash tools/sync.sh "phase 1: system"` → push
              3) poll the `check` run (≤ 60-s calls) → read the step summary
exit check  : Actions → check → success (compile, repo guard, runtime tests, selftest, template gates)
rollback    : nothing to roll back (first push)
next        : Phase 1.6 — Runner proof (dispatch `selftest`, poll, read Kokoro smoke / template render / animator --help)
```
Operating model: `docs/OPERATING_MODEL.md` (agent authors + offline gates + orchestration; Actions do TTS/whisper/master/docker/
render/encode/QA/Release; owner decides + uploads). Phase roadmap with entry/exit criteria: `docs/PHASE_PROTOCOL.md §7`.

## Next (in order)
1. **Phase 1.5 Connect** — needs the owner's private repo + PAT (above). Phase 1.4.1 (private-repo mode) is done.
2. **Phase 1.6 Runner proof** — `selftest` workflow once: toolchain install, Kokoro `am_michael` smoke, `_template` render artifact,
   map-animator `--help`. Reds become Phase 1.6.x, one fix per phase.
3. **Phase 1.7 Actuals** — write measured CI timings into `docs/OPERATING_MODEL.md §3`, paste the animator CLI into `docs/MAPTILE.md`,
   adjust `clips.py gen_maptile` if flags differ.
4. **Phase 2.x (only on the owner's "make videos")** — 2.1 pilot research (Geo Blitz #10) → 2.2 authoring + previews → 2.3 cloud
   render → 2.4 owner review; then 2.5+ one engine per phase: `callouts`/`counter` (Body & Brain), `strip`/`compare` (Sports Sprint),
   `compare` + GBIF range (Wild Files), raster globe, `geofacts.py`.
5. Soft spots to watch on the first runner: `voice.py words` on Kokoro takes, `master.finish` VO-over-music ≥ 15 dB for the quiz bed,
   `hfcheck --caption-zone` against the answer card at y 960.

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
| 2026-10-14 | Repo is **private** (GitHub Free: 2,000 Actions min/month); crons off, `check` main-only, `cloud.py` budget guard | owner |
| 2026-10-14 | Vector maps (d3-geo + Natural Earth) are the default stage; VersaTiles flyovers are cached hero clips; Blue Marble globe deferred | agent |
