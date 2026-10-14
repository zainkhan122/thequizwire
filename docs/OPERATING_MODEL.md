# OPERATING_MODEL.md — who does what: the agent (sandbox) · GitHub Actions · the owner

This is the contract every session and every workflow follows. If a task is not in the column of the actor doing it, it is being
done in the wrong place. Companion: `docs/PHASE_PROTOCOL.md` (how the agent chunks its work so nothing times out).

## 1 · The three actors and their hard limits

| actor | machine | can | cannot / must not | cost |
|---|---|---|---|---|
| **Agent** (Arena sandbox, "I") | 2 vCPU · ~2 GB RAM · Python 3 + NumPy/SciPy/Pillow · Node 20 · network (sometimes flaky) · persistent only under `/home/user` (128 MB snapshot) · `~/.cache` wiped on restart · every tool call times out (keep ≤ 3 min) | think, research, write, decide, ask; author episode JSON; run the **offline gates in seconds**; preview maps as PNG; preview the mix; orchestrate CI; read CI reports; commit + push | render video, decode/encode media, run Chrome/HyperFrames, run docker, run whisper, keep anything only in `~/.cache`, hold secrets in files inside the repo, post anywhere | my time |
| **GitHub Actions** (ubuntu-latest, **private repo**) | **2 vCPU · 7 GB RAM** (measured 2026-10-14; public repos would get 4 / 16) · ffmpeg · Chrome (via hyperframes) · docker · Node 22 · 6 h per job · 10 GB cache · Releases for media | everything heavy and everything that must be byte-reproducible: TTS takes, whisper timing, mastering, map-tile flyovers, HyperFrames check/render/encode, textqa, QA, Release publishing, cache warming | judge content, change an episode, commit to git, post to YouTube, hold any secret except its own `GITHUB_TOKEN` | **free within 2,000 Linux-minutes / month** (GitHub Free, private repo; resets on the 1st) — `cloud.py minutes` is the ledger, `cloud.py render` refuses to dispatch below a 60-min reserve |
| **Owner** | browser + YouTube Studio | create the repo + PAT, decide (series, topics, exceptions, go/no-go), review the finished mp4 on the Release page, upload with `POST_KIT.md`, report metrics | — | attention |

Rule of thumb: **the sandbox is the brain, Actions are the muscle, Releases are the warehouse, git is the memory.**

## 2 · Division of labour by activity

| activity | agent (sandbox) | GitHub Actions | owner |
|---|---|---|---|
| Strategy, series, topics, format rotation | proposes with evidence (`docs/PLAN.md`, `CHANNEL_BASELINE.md`) | — | decides |
| Research, claims ledger (`research.json`), guardrails | **does** (web, Wikidata, Factbook; ≥ 2 publishers per claim) | re-checks links (`factcheck --online`) in the render job | may veto a topic |
| Episode authoring (`episode/voice/geo/visuals/clips.json`) | **does** via `tools/new_episode.py` + editing; previews map scenes as PNG | — | reviews previews on request |
| Offline gates (plan · geo · build · static · quizlint · geolint · facts · provenance · clips lint · selftest) | **runs in seconds, fixes, re-runs** before every commit | re-runs on every push (`check`) as the safety net | — |
| TTS takes (Kokoro `am_michael`) | optional *auditions* only (`SETUP_TTS=1`, never canonical) | **canonical takes** (`tts` stage) → pushed to the `media-<ep>` Release so re-renders are identical | picks a voice direction if asked |
| Word timing, voice performance check | — | **does** (whisper `words`, `voice check`) | — |
| Score / mix | preview mix (unmastered, `quizscore.py`) to judge pacing | **mastered** −14 LUFS mix (`master.finish`) | — |
| Map data | prep at 110m for previews; declares `resolution` 50m/10m for release | fetches/caches 50m/10m, builds release data, Wikidata pin check (`geolint --online`) | — |
| Map-tile flyovers (`maptile` clips), archive trims, AI clips | declares them in `clips.json`, lints | **generates** (docker / ffmpeg / Spaces) once, caches in `cache-clips` | approves any AI clip use |
| Composition (HTML/GSAP) | builds + static-checks it (`compose.py`, `hfstatic.mjs`) | HyperFrames `check`, caption-zone, `textqa`, frames | — |
| Render · encode · QA · deliverables | never | **does**; publishes `<Question>.mp4` + `cover.jpg` + every gate report to a Release | downloads, watches, uploads |
| Code and gate changes (`reelkit/`, `engine/`) | **does**, with `tests/selftest.py` green before commit | proves it on a real runner (`selftest` workflow) | — |
| State and memory (`RESUME.md`, `STATE.json`, commits) | **owns**; syncs at every phase end | — | — |
| Secrets | keeps the PAT only at `~/.cache/secrets/gh_token` | uses `GITHUB_TOKEN` only | issues/revokes the PAT |
| Publishing | prepares `POST_KIT.md` | — | **uploads manually**; nothing auto-posts |

## 3 · The pipeline stage by stage (`reelkit/episode.sh`)

"S" = runs in the sandbox, "CI" = runs on Actions, "S→CI" = sandbox runs the cheap version, CI the authoritative one.

| stage | where | what | input → output | sandbox time | CI time |
|---|---|---|---|---|---|
| `pull` | CI | restore takes/clips from Releases | `media.json` → `vo/`, `clips/` | — | 10 s |
| `tts` | CI | Kokoro `am_michael` takes per `voice.json` line | → `vo/<id>.wav` | (audition only) | ~1–2 min / 50 s VO |
| `words` | CI | whisper word times | `vo/` → `words.json` | — | ~1 min |
| `trim` | CI | silence-trim takes | `vo/` → trimmed | — | 10 s |
| `plan` | S→CI | timeline | `voice.json` (+`words.json`) → `timeline.json` (`--estimate` in S) | < 1 s | < 1 s |
| `voice` | CI | performance gate (fidelity, pace, pauses) | takes ↔ plan | — | ~1 min |
| `geo` | S→CI | Natural Earth prep per scene | `geo.json` → `build/geo/<scene>.json` | 1–2 s | 2 s |
| `score` | S→CI | mix (S: peak-normalised preview · CI: mastered) | takes + timeline → `mix.wav`, `mix_report.json` | 12 s | 30 s |
| `assets` | CI | `clips.py gen` (maptile docker, archive trims, cached) | `clips.json` → `clips/*.mp4` | lint only | 0–8 min per new clip, cached after |
| `build` | S→CI | `engine/compose.py` → HyperFrames project | all JSON → `hf/index.html` | < 1 s | < 1 s |
| `static` | S→CI | browser-less composition run | `hf/` → OK/FAIL | 1 s | 1 s |
| `quizlint` | S→CI | Q1–Q7 (CI: `--release`) | → `out/quizlint.json` | < 1 s | < 1 s |
| `geolint` | S→CI | P1–P6 (CI: `--online` Wikidata, `--release`) | → `out/geolint.json` | < 1 s | 5–20 s |
| `facts` | S→CI | ledger ↔ VO + screen (incl. map plates) | → `out/factcheck.json`, `sources.md` | < 1 s | < 1 s |
| `provenance` | S→CI | licence/origin of every shipped file | → `out/provenance.json`, `credits.md` | < 1 s | < 1 s |
| `planlint` | CI | motion promise, holds, fingerprint drift | → `out/planlint.json` | — | 10 s |
| `check` | CI | `hyperframes check` + caption zone | — | — | 30 s |
| `textqa` | CI | readability of every text unit (Chrome) | → `out/textqa.json` | — | 1–2 min |
| `layout`/`snap` | CI | frame snapshots for review | → `snaps/*.jpg` | — | 1 min |
| `render` | CI | HyperFrames frames → master | → `out/master.mp4` | — | 6–10 min |
| `encode` | CI | delivery encode | → `out/final.mp4`, `cover.jpg` | — | 1 min |
| `qa` | CI | loudness, bitrate, ASR of the final | → `out/qa.json` | — | 1 min |
| publish | CI | Release `<tag>`: mp4 + jpg + reports + POST_KIT; takes → `media-<ep>` | — | — | 30 s |

Budget: **sandbox ≈ 20 s per full offline pass; CI ≈ 30–40 min per episode on the 2-vCPU private-repo runner** (the stage times above are
4-vCPU history figures — Phase 1.7 replaces them with measured actuals), up to 4 episodes in parallel. `ci_setup.sh` adds
~1 min warm / ~6 min cold (cache key = `ci_setup.sh` + `geodata.py` hash).

## 4 · Hand-offs — what crosses the boundary, and only that

| direction | carrier | content | never |
|---|---|---|---|
| agent → CI | git commit at a pinned `sha` + `workflow_dispatch` inputs (`episodes`, `tag`, `sha`, `crf`) | episode JSON, code, docs | uncommitted files, secrets, media |
| agent → Releases | `reelkit/media.py push` | any media the agent legitimately made (plates, audition takes) with `media.json` provenance | files without provenance |
| CI → Releases | render job | `<Question>.mp4`, `cover.jpg`, `out/*.json`, `sources.md`, `credits.md`, `POST_KIT.md`; `media-<ep>`: `vo/*.wav`, `words.json`; `cache-clips`: generated clips | — |
| CI → agent | Release assets + failure artifacts (snaps, `index.html`, `pipeline.log`, 5-day retention) + step summary | **small things only**: reports, a few snaps, logs (`cloud.py fetch/why`) | the mp4 (the agent never needs it) |
| CI → owner | Release page | mp4 + jpg to download, POST_KIT to paste | — |
| owner → agent | chat | decisions, repo + PAT, metrics, feedback | — |

## 5 · Failure ownership

| symptom | owner of the fix | how |
|---|---|---|
| a gate FAILs in CI (`check` or `render`) | agent | `cloud.py why` → edit JSON/code → offline gates green → commit → re-dispatch with the next `-vN` tag |
| infra flake (apt/npm/HF download, tile server) | CI (retries in `ci_setup.sh`/`media.py`), then agent re-runs the job | re-run failed jobs from the Actions page or `cloud.py render` again with the same sha |
| a tool's CLI differs from what the code assumes (e.g. map animator flags) | agent | one function (`clips.py gen_maptile`), verified by the `selftest` workflow, documented in `docs/MAPTILE.md` |
| voice gate fails (misread number, rushed line) | agent | rewrite the line in `voice.json` (digits → words, shorter clause) and re-render; never hand-edit takes |
| border/credit/licence findings | agent | fix in `geo.json` / `research.json` / `media.json`; policy changes go to `docs/BORDER_POLICY.md` + registry with a source |
| content/strategy question | owner | agent asks with options; records the decision in `RESUME.md` |
| sandbox wiped mid-task | agent | `bootstrap.sh` → `RESUME.md` → last commit; nothing of value lives outside git/Releases |

## 6 · Budgets and quotas (all free tier)

| resource | limit | our use |
|---|---|---|
| Actions minutes (private repo, GitHub Free) | **2,000 / month** (Linux ×1) | ~30–40 min per episode render (2-vCPU runner) · ~1–2 min per `check` (main only, doc pushes skipped, superseded runs cancelled) · `selftest` ≈ 25 min **manual only** · `geodata` manual. Capacity ≈ 50–60 renders/month ≈ 1–2 per day incl. re-renders. If cadence must exceed that: flip the repo to public (unlimited) — nothing else changes. |
| Job / workflow duration | 6 h / 35 days | render job `timeout-minutes: 60` |
| Concurrent jobs | 20 | render matrix `max-parallel: 4` |
| Actions cache | 10 GB per repo (LRU, 7-day eviction) | ~1.3 GB: hyperframes + Chrome, pip (faster-whisper/ctranslate2), whisper `base.en`, Kokoro 90 MB, geodata 9 MB |
| Artifacts / packages storage | 500 MB (private repo) | failure debug bundles + selftest artifact, 5–7 day retention → a few hundred MB at peak |
| Releases | 2 GB per asset | mp4 ≈ 20–40 MB, takes ≈ 5 MB per episode, clips ≈ 10 MB each |
| Sandbox snapshot | 128 MB / 10 k files | repo ≈ 2.5 MB; builds and caches stay in `~/.cache` |
| Sandbox tool call | times out | ≤ 3 min per call; long waits are polled, not blocked on (`PHASE_PROTOCOL.md`) |

## 7 · Security and trust boundaries
- The PAT lives only at `~/.cache/secrets/gh_token` (chmod 600), is re-entered by the owner each new sandbox, and is used for
  git push, `workflow_dispatch`, Release uploads and reading run logs — nothing else. Scope: this repo only (Contents, Actions, Workflows).
- Workflows use the ephemeral `GITHUB_TOKEN` (`permissions: contents: write` for Releases). No YouTube credentials exist anywhere.
- Private repo (owner decision 2026-10-14): ledgers, scripts and the topic backlog stay private. Still: no PII, no analytics exports
  in git — a repo can be flipped public later without a history rewrite only if nothing sensitive was ever committed.
- Owner's PAT (fine-grained, this repo only): **Contents R/W** (push, Releases) · **Actions R/W** (dispatch, logs, timings for the
  minutes ledger) · **Workflows R/W** (pushing `.github/workflows/*`) · Metadata R (automatic). Nothing else. 90-day expiry; the agent
  warns before it lapses (`cloud.py` token_expiry_warning).

## 8 · What the next two phases look like under this model
- **Phase 1.5 — Connect** (agent ≈ 10 min, CI ≈ 3 min): owner creates the **private** repo + PAT → agent stores the token, runs
  `bootstrap.sh`, `tools/sync.sh "phase 1"` → `check` workflow runs → agent reports green/red.
- **Phase 1.6 — Runner proof** (agent ≈ 10 min, CI ≈ 25 min): agent dispatches `selftest` → polls → reads toolchain timings,
  Kokoro smoke, template render artifact, map-animator `--help` → records actuals in §3, fills `docs/MAPTILE.md`, fixes any red in
  one small phase each. Only after this is green does Phase 2 (the first real episode) start — on the owner's go.
