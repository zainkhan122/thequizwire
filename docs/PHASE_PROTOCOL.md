# PHASE_PROTOCOL.md — how every task is chunked so nothing times out and nothing is lost

Owner rule (2026-10-14): *every modification or task is done in phases to avoid time-outs.* This file makes that mechanical.
It binds the agent in every session; `AGENTS.md` points here.

## 1 · Definitions
- **Phase** = one deliverable with a verifiable exit check, finished and committed inside one sitting.
  Budget: **≤ 15 min of sandbox wall time**, **≤ 3 min per tool call**, **≤ 10 files touched** unless they are generated together.
- **Step** = one tool call or one small group of calls that ends in a state worth committing.
- **Checkpoint** = a local commit (`git add -A && git commit -m "phase N.M step k: …"`); squash later if wanted.
- **Sync** = `bash tools/sync.sh "phase N.M: …"` (media → Releases, code → `origin/main`). Mandatory at phase end.
- Numbering: `N.M` where N = plan phase (`docs/PLAN.md §4`, 1 = system, 2 = pilot episode, 3 = batch …) and M = session-sized slice;
  fixes discovered while running a phase become `N.M.x`.

## 2 · Phase card (fill this before starting any phase; keep it in `RESUME.md` → "Current phase")
```
Phase N.M — <name>
goal        : one sentence, one deliverable
entry       : what must already be true (previous phase synced, selftest green, owner decision X)
steps       : 1) … (≤ 3 min)  2) … (≤ 3 min)  3) …        ← each ends in a committable state
exit check  : the exact command(s) + expected output (e.g. `python3 tests/selftest.py` → "selftest: OK")
rollback    : `git checkout -- <paths>` / `git revert <sha>` / "nothing to roll back"
next        : Phase N.M+1 — <name>
```

## 3 · The loop inside a phase
1. **Read** — `RESUME.md` → "Current phase"; `python3 tools/state.py show`; `python3 tests/selftest.py` (12 s) if code is touched.
2. **Change** — one step at a time; after each step run the narrowest check that proves it (a single gate, a unit test, `bash -n`).
3. **Verify** — the phase's exit check, verbatim.
4. **Record** — `RESUME.md` (Now / Current phase / Next), `STATE.json` (`tools/state.py set now|next …`), decisions table if a decision was taken.
5. **Sync** — `tools/sync.sh`. Then report (§6).
If the sandbox dies at any point: the last checkpoint + `RESUME.md` restore the position; nothing is redone from memory.

## 4 · Sizing rules (what goes where)
| if the step… | then |
|---|---|
| takes > 3 min of compute (render, whisper, TTS batch, docker, big downloads) | it is **not a sandbox step** — it is a CI job dispatched with `cloud.py` or a workflow; the sandbox only dispatches and later reads results |
| must wait on CI (15–25 min) | dispatch, write the run id into `STATE.json`, **do other steps or end the phase**; poll with short calls (`cloud.py status`, ≤ 60 s each) — never one long blocking call |
| downloads data (geodata, models) | split by resolution/file; each fetch ≤ 10 MB per call; cache under `~/.cache` and verify with a `check` command |
| edits many episodes or many files mechanically | write a small script under `tools/` and run it per directory, committing per batch |
| is exploratory (unknown CLI, unknown API) | first a probe step (`--help`, `curl -I`, one tiny request) with a 20-s timeout, then the real step |
| would change a policy (borders, licences, format) | stop; ask the owner with options; record the answer before touching code |

## 5 · Standing tool-call budgets (sandbox)
- `bash`: set `timeout` explicitly; default 30 s, use 120–180 s only for selftest/score/geodata fetch; never 1800 s.
- Background servers/watchers: `start_process`, never `bash`.
- Any single file write: complete content, then a syntax check (`python3 -m py_compile`, `bash -n`, `node --check`, `json.load`).
- Commit after every step that compiles; push at phase end only (one green `check` run per phase, not per step).

## 6 · Phase report (end of every phase, in chat and in `RESUME.md`)
```
Phase N.M — <name>: DONE | PARTIAL | BLOCKED
verified by : <command → output>
changed     : <files / behaviours>
not done    : <explicit>
next        : Phase N.M+1 — <name> (needs: <owner input or nothing>)
```

## 7 · Roadmap of the next phases (entry/exit criteria; agent minutes are sandbox wall time)

| phase | goal | entry | exit check | agent | CI |
|---|---|---|---|---|---|
| **1.5 Connect** | repo on GitHub, `check` green | owner: public repo + PAT | `tools/sync.sh` pushed; `check` run = success | 10 min | 3 min |
| **1.6 Runner proof** | toolchain proven on a real runner | 1.5 | `selftest` workflow success: Kokoro smoke OK, `_template` `final.mp4` artifact exists, animator `--help` captured | 10 min + polls | 25 min |
| 1.6.x Fixes | each red item from 1.6 | 1.6 red | the failing step green on re-run | ≤ 15 min each | ≤ 25 min each |
| **1.7 Actuals** | OPERATING_MODEL §3 timings + MAPTILE "CLI (verified)" filled from the run | 1.6 green | docs updated, committed | 10 min | — |
| **2.1 Pilot research** (owner's go) | Geo Blitz #10 topic + ledger (≥ 5 sources, claims, guardrails, landscape) | 1.7 | `factcheck --hf /nonexistent` on the scaffold passes the brief checks | 15 min | — |
| **2.2 Pilot authoring** | voice/geo/visuals written; offline gates green; map previews shown to owner | 2.1 | `episode.sh <ep> preflight` → all OK; `docs/img/<ep>_*.png` | 15 min | — |
| **2.3 Pilot render** | first Release | 2.2 synced | `cloud.py render --wait` success; `qa.json` pass; owner can download | 10 min + polls | 25 min |
| **2.4 Pilot review** | owner feedback → fixes → v2 if needed | 2.3 | owner approves or a v2 tag is green | 15 min | 25 min |
| 2.5+ Series engines | `callouts`/`counter` (Body & Brain), `strip`/`compare` (Sports), `compare` + GBIF range (Wild Files) — one engine per phase, each with a selftest extension | 2.4 | `tests/selftest.py` covers the engine; a fixture episode passes preflight | 15 min each | selftest run |
| 3.x Batch | one episode per phase per series, rotating hooks | engines ready | Release per episode | 15 min each | 25 min each |

## 8 · What "done" never means
- "Done" never means "ran in my head" — every exit check is a command with output pasted in the report.
- "Done" never means "in the sandbox only" — unsynced work does not exist.
- "Done" never includes a video unless the owner has said "make videos".
