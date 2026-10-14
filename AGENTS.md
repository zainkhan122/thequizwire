# AGENTS.md — read this first (any AI agent, any session)

This repo is the **single source of truth** for the owner's TheQuizWire Shorts system. The Arena workspace is a disposable working
copy; if it isn't in git or in a GitHub Release, it doesn't exist.

**Two documents bind every session:** `docs/OPERATING_MODEL.md` (who does what — agent / GitHub Actions / owner, stage by stage) and
`docs/PHASE_PROTOCOL.md` (every task is a ≤ 15-min phase with a phase card, ≤ 3-min tool calls, checkpoint commits, exit check, sync, report).

## Session start (empty workspace)
1. Ask the owner for the GitHub token if `~/.cache/secrets/gh_token` is missing; store it there (chmod 600). Never write tokens into
   the repo, the workspace or logs.
2. `[ -d ~/thequizwire ] || git clone https://github.com/$(cat .repo 2>/dev/null || echo zainkhan122/thequizwire).git ~/thequizwire; source ~/thequizwire/bootstrap.sh`
   (Arena drops `.git/config` from snapshots; bootstrap restores it from `.repo`).
3. Read `RESUME.md`, continue from its **Next** list. `python3 tools/state.py show` is the short version. `python3 tests/selftest.py`
   proves the toolchain still works (15 s) before you touch anything.

## Session end, or after any meaningful change
Update `RESUME.md` and `STATE.json` (`tools/state.py set …`), then `bash tools/sync.sh "what changed"` (media → Releases, code → git).
Work in bounded phases: one phase per session, sync at the end — the sandbox times out and is wiped.

## Operator model
| Sandbox (agent) | GitHub Actions (private repo, 4 vCPU / 16 GB, 2,000 free min/month) |
|---|---|
| research, writing, decisions, asking the owner | the repo = SSOT; Releases = all media (`media-<ep>`, `cache-clips`, finals) |
| `tools/new_episode.py`, editing the five episode JSONs | `tts` stage: Kokoro `am_michael` takes + whisper word times (`voice.py words`) |
| `episode.sh <ep> plan geo build static quizlint geolint facts provenance` (seconds, no browser, no ffmpeg) | `score` (mastered −14 LUFS), `assets` (maptile docker clips), `check`, `textqa`, `render`, `encode`, `qa`, Release publish |
| map previews: `node reelkit/geopreview.mjs <ep> <scene> out.png` (SVG → PNG, no browser) | `selftest` workflow = the only full end-to-end proof incl. render |
| `cloud.py render <ep> --tag … --wait` / `status` / `fetch` / `why` | `check` workflow on every push: compile, repo guard, selftest, every episode's offline gates |
Never render video, decode media, or install HyperFrames/Chrome in the sandbox (2 GB RAM, /tmp is RAM). Builds live in `~/.cache/build/`.

## Hard rules
- **Phases, always.** Fill the phase card in `RESUME.md` before starting; commit per step; sync per phase; report in the §6 format (`docs/PHASE_PROTOCOL.md`).
- **Minutes are a budget.** Private repo ⇒ 2,000 Linux-minutes/month. `cloud.py minutes` before planning renders; `selftest`/`geodata` are manual; never add a cron without the owner.
- **Heavy work is CI work.** Anything > 3 min of compute (render, whisper, TTS batches, docker, big downloads) is dispatched to Actions, never run here (`docs/OPERATING_MODEL.md §3–4`).
- **No media in git** (`tools/repo_guard.py`: no media extensions, no file > 1 MB, repo < 15 MB). `docs/img/*.png` previews are the only exception.
- **No videos until the owner says so.** Phase 1 delivered tools only; Phase 2 starts with the owner's go and `docs/PLAN.md §4`.
- **Four series, feed numbering** — `series/series.json` is the counter; only `tools/new_episode.py` bumps it. Cosmic Quiz / Time Vault stay inactive.
- **Narrator is Kokoro `am_michael`** (speed per tone from `voice.json`); Arena `generate_speech` is not used for this channel.
- **Borders:** `docs/BORDER_POLICY.md` — show the dispute, label controller + claimants, date it, never "owns". geolint P4 enforces; the registry is the SSOT.
- **Facts:** every spoken or shown fact → `research.json` claim with ≥ 2 publishers (core: + primary/scholarly). Map pins, labels and policy plates count as on-screen text (factcheck reads the inline scene spec). Wrong options are `data-fc="distractor"` (exempt); option letters are `data-fc="skip"`; the option read-out and the CTA are `vo_exempt` regexes.
- **Honest maps:** size claim → equal-area + `projection_reason`; distance → scale bar at the claim's latitude; `resolution` 50m/10m for release (110m is preview); Natural Earth credit always; OSM/VersaTiles/Copernicus credit with any `maptile` clip.
- **Data layout:** world-atlas ids are 3-char zero-padded ISO numeric strings (`"356"` India, `"586"` Pakistan); Bahrain exists only at 50m/10m; `engine/data/` ships 110m only, `~/.cache/geodata/` holds 50m/10m + NE disputed (offline fallback: `GEO_FIXTURE=tests/fixtures/ne_disputed_kashmir.geojson`).
- **Compositions** are built by `engine/compose.py` from `visuals.json` — no per-episode build scripts. Time expressions: `s03`, `s03+0.4`, `s03.end`, `s03@cue`, `end-2`. Geo beats need `stage`; every element needs an `*_in`; facts need `until`.
- **Layout:** stage y 0–1180, question card 1190–1600 (caption-safe band), nothing below 1600; `hfcheck --caption-zone` and textqa dead zones enforce it.
- **Clips** (`clips.json`): `maptile` (VersaTiles docker, CI only, ≤ 8 s, `args` per docs/MAPTILE.md), `url` archive (licence fields required), Wan/LTX only if a clip is truly needed (history rules). Everything goes through the clip cache; a clip is generated once.
- **Provenance allow-list** (`reelkit/provenance.py`): PD, PD-USGov, CC0, CC BY 3.0/4.0, OFL, Apache-2.0, ISC, MIT, BSD-3, ODbL (maps, attribution), Copernicus, own/own-ai/own-tts, GSAP-Standard. SA/NC/ND/unknown/fair-use refused.
- **svgraster.py limits:** the browser-less PNG preview renders paths, circles, rects, text (basic) — no filters, gradients or foreignObject; it is a preview, not a frame check (HyperFrames snaps on CI are).
- **Deliverables** are named after the question (`reelkit/naming.py` from `episode.json.title`); never `final.mp4` in a Release.
- **Secrets** only in `~/.cache/secrets/`; nothing posts to YouTube; the owner uploads from `POST_KIT.md`.

## Map of the code
`reelkit/episode.sh` (stages) · `plan.py` (timeline) · `geodata.py` (fetch/prep/disputed/check) · `engine/compose.py` → `engine/quiz.py`
+ `engine/geo.py` + `engine/geo-runtime.js` + `engine/charts.py` + `engine/fx.py` · `quizscore.py` + `synth.py` + `master.py` ·
gates `quizlint.py` `geolint.py` `factcheck.py` `provenance.py` `planlint.py` `hfcheck.py` `textqa.py` `qa.py` `hfstatic.mjs` ·
`voice.py` + `tts_kokoro.py` + `trim_vo.py` · `clips.py` + `clipcache.py` · `cloud.py` + `media.py` + `naming.py` · `tests/selftest.py`.
