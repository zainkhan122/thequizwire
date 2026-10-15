# RESUME.md — where this repo is and what happens next

_Updated 2026-10-15 (Plan v2 session; Phase 1 ended 2026-10-14). Owner decisions: free tools only · phases per session · four feed series · Kokoro
`am_michael` · disputed borders shown with controller/claimant plates · **v2 approved and production unlocked 2026-10-15 ("make videos")**._

## Now
**Phase 1 is complete and proven on a real runner (2026-10-14).** `selftest` #11 is green end to end on the private-repo
runner (2 vCPU / 7 GB): toolchain → Kokoro `am_michael` takes → whisper → voice gate → mastered mix → HyperFrames render →
upload master → QA pass (−14.6 LUFS, −1.8 dBTP, 9 Mbps, ASR match 0.96) → artifact `series/_template/out/final.mp4`
(50 MB, 43.6 s). The map-animator image pulls and its CLI is recorded
in `docs/MAPTILE.md`. Measured cost: **≈ 7.5 min of job time per 45-s episode** (render 2–2.5 min). No episode has been
produced — by instruction; Phase 2 starts only on the owner's "make videos".

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
Phase V3 — owner rejected the v2 look (2026-10-15): "robotic, basic, answer map visible, tiny question text, poor animation"
goal        : rebuild the visual format to the reference-channel standard (docs/V3_LOOK.md) — satellite basemap, lifted
              flag/colour highlights, big type, stickers, hook that hides the answer — then re-render the 10 pilot episodes
entry       : references and own frames actually watched (docs/img/reference_frames.png, v2_as_shipped_geo13.png);
              v3 comp approved? (docs/img/v3_direction.png) ; local HyperFrames+Chrome available (bash bootstrap.sh --browser)
steps       : V3.1 ✓ basemap → V3.2 ✓ lifted highlight → V3.3 ✓ v3 UI + stickers + flag-ball characters (docs/img/v3_3_contact_sheet.jpg)
              → V3.4 photo cut-outs (optional, later) → V3.5 ✓ template `_template_v3` + quizlint Q14/Q15 + selftest →
              V3.6 re-author 10 episodes with local contact sheets → V3.7 one runner render for owner look → batch
exit check  : owner approves the Geo #13 v3 render; 10/10 in Release pilot-v3-batch1; every episode has a reviewed sheet
rollback    : v2 engine paths stay (format quiz-v2); pilot-v2-batch1 Release is NOT to be posted
next        : V3.6 re-author the 10 pilots (start: geo ep13 = copy series/_template_v3 content over the episode; then ep10–12, 14, wild 07–09, sports 09–10); a local sheet per episode
```
Rule (new): nothing goes to Actions before a local contact sheet has been looked at. pilot-v2-batch1 (8/10 rendered) is shelved.
Last completed: **Phase 1.7 Actuals** (2026-10-14) — measured CI timings in `docs/OPERATING_MODEL.md §3/§6`, verified animator CLI +
`clips.py` width/flag rules in `docs/MAPTILE.md`, budget guard 12 min/episode, `render.yml` timeout 30 min.
Known, accepted `hyperframes check` warnings on quiz episodes: `lint/nested_structure_needs_subcomposition` (#stage_map → `_in`
wrapper, needed so fades never tween the clip element) and `layout/container_overflow` (#geo_main_cam when zoomed) — both benign.

## Next (in order)
0. **Plan v2 (2026-10-15)** — `docs/PLAN_V2.md` is the roadmap now: 2.1 scorecard → 2.2 v2 template/gates → 2.3 captions → 2.4 flag-fill/icons → 2.5 Wild → 2.6 Sports → 2.7 maptile cost → 2.8 v2 runner proof → 3.1 pilot batch (owner's go).
1. ~~Phase 1.5 Connect~~ — done 2026-10-14: private repo, PAT stored (expires 2027-01-12), `check` green.
2. ~~Phase 1.6 Runner proof~~ — done 2026-10-14 after 11 attempts / 12 one-commit fixes (1.6.1–1.6.12: whisper arrays, media pull,
   planlint/voice silence lines, voice number parser + script_words, end-card fade + clip wrapper, label centring, dead zones,
   ABR master, Q8 hand-offs, idle drift). `selftest` #11 success, artifact has `final.mp4`.
3. ~~Phase 1.7 Actuals~~ — done 2026-10-14 (see Current phase).
4. **Phase 2.x (only on the owner's "make videos")** — 2.1 pilot research (Geo Blitz #10) → 2.2 authoring + previews → 2.3 cloud
   render → 2.4 owner review; then 2.5+ one engine per phase: `callouts`/`counter` (Body & Brain), `strip`/`compare` (Sports Sprint),
   `compare` + GBIF range (Wild Files), raster globe, `geofacts.py`; first `maptile` clip measures the animator's runner cost.
5. Watch-list from the runner proof: the end card is the only ≥ 2.5-s frozen picture left (QA WARN) — give it a subtle motion
   element when the engine is next touched; `textqa` reading-time is tight on the s05 fact (4.25 s shown vs 4.38 s needed → WARN).

## Secrets / accounts
- GitHub PAT: fine-grained, this repo only (Contents/Actions/Workflows R/W), expires 2027-01-12. Stored only at `~/.cache/secrets/gh_token` (not snapshotted — the owner re-supplies it in a new sandbox).
- No other accounts needed: VersaTiles tiles + animator image are public; Kokoro/whisper models download from GitHub/HF anonymously; Wikidata is open.

## Decisions log
| date | decision | by |
|---|---|---|
| 2026-10-14 | New repo `quizwire` for all four feed topics (not a geo-only repo, not the history repo) | owner |
| 2026-10-15 | Format v2 "Guess it → See it" (reveal-first, 28–35 s, 3 options, 1.5-s beat, loop end), 2/day, series order Geo → Wild → Sports → Body — **approved**; owner said "make videos" (production unlocked, v2 only) | owner |
| 2026-10-14 | Narrator Kokoro `am_michael` | owner |
| 2026-10-14 | Sensitive borders included and labelled with controller + claimants (policy + registry + geolint P4) | owner |
| 2026-10-14 | Phase 1 = tools/system only; no episode production | owner |
| 2026-10-14 | Geo Blitz / Body & Brain / Sports Sprint / Wild Files active; Cosmic Quiz, Time Vault registered inactive | agent (from feed), to confirm |
| 2026-10-14 | Repo is **private** (GitHub Free: 2,000 Actions min/month); crons off, `check` main-only, `cloud.py` budget guard | owner |
| 2026-10-14 | Vector maps (d3-geo + Natural Earth) are the default stage; VersaTiles flyovers are cached hero clips; Blue Marble globe deferred | agent |

### V3.6e — DONE 2026-10-15 · variety system (owner: "how do we avoid template-like videos?")
- `docs/VARIETY.md`: fixed skeleton + 8 rotated surface axes (question, hook, opener, reveal, beats, cast, music, outro) with pools; brand constants never rotate.
- quizlint **Q16**: v3 episodes need `episode.json → variety`; FAIL when ≥ 4/8 axes equal the previous episode of the series, opener/reveal/outro or the hook's first two words repeat 3× in a row, or the emoji set equals the previous episode; WARN on question/hook repeats. Selftest negative `ep14-clone` → Q16.
- ep13 (`misconception · wide-drift · flag-lift · pin/route/scalebar/label`), ep14 (`fact-first · world-rotated · flash-cut · second-highlight/pin/label`, outro "TOO EASY?").

### V3.6d — DONE 2026-10-15 · branded outro replaces the "next video" tease (owner brief)
- `engine/quiz.py` `outro3()/outro_in()`: logo + wordmark + tagline, LIKE/SUBSCRIBE buttons clicked by an arrow cursor (white→yellow, yellow→green "✓ SUBSCRIBED", bursts, bell wiggle), social row (FB · IG · X · Threads) + thequizwire.com pill; dim layer; holds then loop frame at `end-1.0`.
- `reelkit/brand.py prep` (brand kit → build + media.json provenance: logo/cursor `own`, icons CC0); `brand/` allowed in repo_guard; stickers.py always fetches 👍🔔 for v3; `geo.clear` now also hides the scalebar.
- Episodes ep13/ep14/template: `quiz.outro`, no `tease`/`cta_line`; v08 rewritten as the ask (no numerals); beats `geo.clear@s08`, `cam_to@s08+0.2→end-0.3`, `cta_in until end-1.0`, `hook_in@end-1.0`. All gates green; frames viewed `/tmp/snapo/sheet2.jpg`, `/tmp/snapo2/sheet.jpg`.
- Local clean-up: removed `~/history`, `~/uploads` (CSVs already in docs/data), `~/geo-plan` (STYLE_ASSESSMENT moved to docs/); repo: dropped comps, v1 preview images, inactive series.

### V3.6c — DONE 2026-10-15 · 3-second think-time (owner: "too short to answer" → chose 3 s over 5 s)
- Measured Geo #13: options on screen 4.5 s total, silent beat only 1.5 s. Now `quiz.beat` = countdown `silence` = 3.0 s → ≈ 6 s with the options up.
- `engine/quiz.py` `beat3`: 200-px ring (y 1275) drains over `seconds`; digits 3·2·1 (130-px Lilita, ids `q1_d3..d1`) pop once per second; pills breathe per second; tease fades 0.25 s before the reveal. quizscore already ticks once per countdown second + riser.
- quizlint Q10 (v3): silence 2.5–3.5 s and `quiz.beat` equal; Q13 upper bound 44 s when `ESTIMATE=1` (estimates run ≈ 10 % long; real cap stays 40 s). Pills carry `data-layout-allow-caption-zone` (pill C dips 50 px into the band; HF check flagged the mid-exit at 9.55 s on ep14).
- ep13, ep14, `_template_v3`, set to 3.0; gates green for both (ESTIMATE totals 41.05 / 41.3 s → real ≈ 37 s). Frames viewed: `/tmp/snap13c/sheet.jpg` (3·2·1) and `/tmp/snap13d/sheet.jpg`.
- Sandbox was restored mid-phase: toolchain re-bootstrapped; **token missing → commit is local, push pending the owner's PAT**.

### V3.6b — DONE 2026-10-15 · Geo #14 v3 (world-scale template) + Geo #13 runner-review tweaks
- Geo #14 "most time zones" re-authored in v3: Pacific-centred rotated world (mercator rotate −150, Blue Marble bbox [−30,−66,330,85]), Russia fill beat, Europe flash-stage with France flag lift, Tahiti/Wallis pins, clock sticker. All gates green (textqa 19 units PASS 18 WARN 1).
- Engine: `mainBounds()` flag-lift rect (parts ≥ 20 % of the largest — France no longer stretched by Guiana); darker `.scrim-top` + 3-px hook stroke (loop-frame contrast 2.93 → PASS); `.v3 .geo.has-basemap` background deep navy beyond the raster; `ALLOW` attrs on hook/pill/fact children; basemap `MAX_W` 4864; quizlint Q14 skipped for ≥ 300° fits.
- Geo #13 after watching the runner render (`/home/user/review/geo13_v3_runner.mp4`): "South Island" label moved off the scalebar, scalebar → [60,1130], kiwi character → (205,800) off the Aoraki pin label. Template + comps synced; gates green.
- Lessons (keep): `sNN-x` anchors to the END of sNN — use `sNN.end-x`; rotated-world Mercator shows nothing beyond rel ±180 — keep cameras with half-width 540/(2.9·k) ≤ 180 − |rel centre|; Paris↔Tahiti are 209° apart in this rotation → one pin per hemisphere per camera.
- Next: V3.6c–j (geo ep10 Nile, ep11 Budapest, ep12 Antarctica; wild ep07–09; sports ep09–10), one episode per phase; then V3.7 batch render after the owner approves Geo #13.
