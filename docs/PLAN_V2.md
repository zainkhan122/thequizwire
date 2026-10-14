# PLAN_V2.md — Final plan: the format pivot "Guess it → See it" (2026-10-15)

_Supersedes `docs/PLAN.md` §2.1 (structure), §5 (cadence) and the Phase-2 roadmap rows in `docs/PHASE_PROTOCOL.md` §7.
Everything else in PLAN.md (tools, engines, gates, operating model, border policy) stands. Owner rules unchanged:
free tools only, phases, four feed series, Kokoro `am_michael`, disputed borders labelled, **no videos until "make videos"**._

## 0 · TL;DR

1. The channel is not failing on topics; it is failing at the **swipe decision**. YouTube Studio (Sep 16 – Oct 13):
   **57.6 % "stayed to watch"** (≈ 42 % swipe away at once), average view duration 24 s, 72 subscribers from 113,104 views
   (0.64 per 1,000). Every Short is seeded to ≈ 1,000–1,300 viewers and never expands; 156 videos, max 2,035 views.
2. The Oct 5 switch to 11–16-s single-question cards made it **worse** (stayed 50 %, 0.45 subs/1k) — proof that the opening
   frame (stock b-roll → wordmark → series pill → card) is what people swipe on, not the length.
3. The fix is a **reveal-first** Short: the question is asked *on the visual* in the first 2 s, options take ≤ 2 s, the
   countdown becomes a 1.5-s beat, and 60–70 % of the runtime **shows** the answer on a map/visual with a payoff fact,
   ending on a loop frame and a one-line reason to subscribe. 28–35 s, one question.
4. Series order by evidence: **Geo Blitz** (maps = the engine), **Wild Files** (animal videos have the best stayed %,
   67–73 %), **Sports Sprint** (highest views/likes, worst stayed % — needs the visual most), **Body & Brain** last.
   Cosmic Quiz / Time Vault stay parked. Cadence **2 per day**, not 4.
5. Phase 2 = eight ≤ 15-min phases of system work (scorecard importer, v2 template + gates, word-timed captions,
   flag-fill/icons, two series visuals, first maptile clip, v2 runner proof). Phase 3 = a 10-video pilot batch,
   only on the owner's go, scored after 7 days against hard gates (stayed ≥ 70 %, AVD ≥ 65 %, ≥ 1 video > 5,000 views).

## 1 · Evidence

### 1.1 Public data — 239 Shorts, Aug 16 → Oct 14 (`docs/data/channel_shorts_60d_2026-10-15.csv`)

| window | n | median views | max | in the 900–1,400 band |
|---|---|---|---|---|
| Aug 16–30, first 15 days of "5 Questions – Quiz" | 58 | 1 | 34 | 0 % (not distributed) |
| Sep 6 – Oct 13, all formats | 156 | 1,074 | 2,035 | **71 %** |
| ├ 5-question cards 60–77 s | 120 | 1,092 | 2,035 | 72 % |
| ├ 1-question cards 11–16 s (from Oct 5) | 20 | 1,007 | 1,724 | 60 % |
| └ 1–3-question cards 35–48 s (from Oct 6) | 16 | 1,072 | 1,259 | 69 % |

≈ 100 % of the channel's lifetime views (162,637) arrived in these 60 days; 2024 uploads median 5 views.

### 1.2 YouTube Studio export — Sep 16 → Oct 13 (`docs/data/studio_2026-09-16_10-13_*.csv`)

Totals: 113,104 views · 13,559 likes (12.0 %) · 72 subscribers · stayed to watch 57.6 % · AVD 0:24 · thumbnail
impressions 17,461 (≈ all traffic is the Shorts feed; titles/thumbnails barely matter for views).

| format (published ≥ Sep 6, views ≥ 100) | n | views med | **stayed %** med | AVD med | % of duration | likes/view | subs | subs / 1k views |
|---|---|---|---|---|---|---|---|---|
| 5-question cards 60–77 s | 74 | 1,134 | **60.5** | 27 s | 40 % | 12.0 % | 55 | 0.70 |
| 1–3-question cards 35–48 s | 16 | 1,074 | 56.4 | 18 s | 44 % | 13.4 % | 8 | 0.53 |
| 1-question cards 11–16 s | 19 | 1,009 | **50.4** | 11 s | 73 % | 10.8 % | 8 | 0.45 |

Stayed-to-watch distribution: p10 48.6 · p25 52.9 · median 58.4 · p75 62.0 · p90 65.4 · max 72.9.
Inside the plateau, stayed % does not predict views (every bucket ≈ 930–1,150 median) — nothing clears the expansion bar.

Topic signal (same export): the best stayed % are animal/nature cards — "Animal Facts That Surprise Adults" 72.9,
"Amazing Animal Skills" 72.2, "Myths About Animals Busted" 67.8 (1,566 views), "Famous Islands" 70.2, "Water" 68.9.
The worst are sports — World Cup 39.3, FIFA 48.0, basketball origin 46.4 (yet 1,725 views, 166 likes), yellow card 47.5.
Two "Trend" one-offs without the house title style (raindrop shape 18.6 %, LA winds 24.7 %) are the channel's worst openers.
Loop evidence exists: "drives on the LEFT" 16 s → AVD 21 s (131 %), "GOLF" 15 s → 107 %. A 2024 "Chelsea" question still
earns 271 views at 83 % stayed / 15 % CTR from search — named entities have search value.

### 1.3 Diagnosis

| failure point | number | meaning |
|---|---|---|
| the first 2 seconds | stayed 57.6 % overall, 50 % on the 16-s cards | the opening (stock clip + wordmark + pill + text card) loses 4 in 10 before the question lands |
| the middle | AVD 40–44 % of duration on 35–77-s cards | the countdown is dead time; a text reveal is no payoff; viewers leave between questions |
| the end | 0.64 subs / 1,000 views | nothing asks for, or earns, the subscription; no series promise, no tomorrow |
| topic | animals 67–73 % stayed, sports 39–48 % | topics modulate retention by ± 10 points; format moves it by 20–30 |

## 2 · The format: "Guess it → See it" (v2)

One question · 28–35 s · 1080×1920 · narration `am_michael` · procedural score · captions word-timed.

| t (s) | beat | on screen | voice | rule |
|---|---|---|---|---|
| 0.0–2.0 | **hook** | the subject is already moving: map zooming to the region, flag filling, animal silhouette scaling — no logo, no pill, no card | the question, ≤ 9 words, starts at 0.0 | first frame must contain the subject and the first caption word |
| 2.0–4.0 | **options** | 3 options (not 4) as compact chips over the visual; series pill appears small, top-left | "A, B or C?" | chips ≤ 2.0 s; no full-screen card |
| 4.0–5.5 | **beat** | 1.5-s pulse on the chips (tick ×3), visual keeps moving | silence | replaces the 3-s countdown (Q-gate below) |
| 5.5–7.5 | **reveal** | correct chip locks, the visual *answers*: highlight/flag-fill/count/scale bar/route — never text alone | "It's … B — Russia." | the reveal must change the map/visual state |
| 7.5–24 | **see it** ×3 | three visual beats, one claim each: e.g. neighbours light up one by one with a counter; scale comparison; disputed-border plate when the registry says so | 2–3 short sentences per beat | one claim per beat, every claim in `research.json`; captions ≤ 4 words per line |
| 24–29 | **payoff + tomorrow** | the "wow" number big; then "Tomorrow: …" tease | the single fact people repeat | the payoff is the last claim of the script |
| 29–31 | **loop + CTA** | end state cross-fades into the first frame; one caption line "One map question a day → subscribe" | "Guess tomorrow's before I reveal it." | end card ≤ 1.5 s, the last frame matches t = 0 |

Per-series visual payoff (what the "see it" beats are made of):

| series | engine (exists) | v2 addition | first topics (from the channel's own winners) |
|---|---|---|---|
| **Geo Blitz** | `geo` highlights/pins/labels/routes/disputed plates/camera; `maptile` flyovers | flag-fill + glow, counter, icon layer | borders-the-most countries (14 neighbours lit one by one); largest peninsula; coldest desert; drives-on-the-left map; Buda + Pest |
| **Wild Files** | `geo` (range maps), `charts` bars | silhouette scale compare (`compare`), counter, GBIF range | slowest mammal; sleeps with one eye open; starfish arms; toucan; big cats |
| **Sports Sprint** | `geo` (venues/origins), `charts` | `strip` timeline/compare | where basketball was invented (Springfield on the map); grass Grand Slam; Olympic birthplace; Chelsea-type named entities |
| **Body & Brain** | `charts` | `callouts` on PD plates, counter | goosebumps, tastes, nails — only after the three above prove the format |

Keep from v1: the series pill (small, late), the question-as-title with the KEYWORD in caps + one emoji, the "What was your
first guess?" comment hook, `#GKshorts #thequizwire #shorts` tail. Drop: " – Quiz" suffix, the 3-s countdown, the
full-screen card, stock b-roll openers, the 4th option, multi-question Shorts.

New gates (Phase 2.2): **Q9** first caption + subject motion by t ≤ 0.3 s and no logo/pill/card before 2.0 s; **Q10**
countdown/beat ≤ 1.5 s; **Q11** the reveal beat changes the visual state (a layer or camera tween exists in the reveal
window); **Q12** last frame matches the first within a tolerance (loop); **Q13** total 26–36 s, exactly one question.

Variant B (held for batch 2 if stayed % does not move): same visual, no options — pure "Why/Which … ?" explainer with
the answer at 4 s. Everything downstream is identical, so the A/B costs nothing extra to build.

## 3 · Content strategy

- **Cadence:** 2 Shorts/day (14/week). Volume did not help at 4/day; the Actions budget (≈ 7.5 min per episode) makes
  60/month ≈ 450 min + checks ≈ 650 of 2,000 minutes.
- **Weekly mix:** 6 Geo Blitz · 4 Wild Files · 3 Sports Sprint · 1 Body & Brain. Re-weight monthly from the scorecard.
- **Topic rules:** superlatives and comparisons (most/largest/coldest/slowest), "which country/animal/planet" with a named
  answer, origins ("invented in"), anything that can be *shown* changing on a map or scale. Named entities with search value
  (clubs, cities, animals) get priority. Avoid questions whose answer is a date or an abstract term unless the visual carries it.
- **Title:** the question itself, KEYWORD in caps, one emoji; ≤ 60 characters. **Description:** question → "What was your first
  guess?" → one source line → series tag `Geo Blitz #10` → hashtags. **Pinned comment:** the question + "answer at 0:06 👀".
- **Channel surface:** one playlist per series; a weekly community poll (the next question); posting at the two best hours
  from Studio "When your viewers are on YouTube"; the "Tomorrow: …" tease must be true (the next upload in that series).
- **Policy stays:** disputed regions get the controller/claimant plate; no military framing; no fiction without a
  "hypothetical" label; procedural music only; PD/CC assets only.

## 4 · KPIs and decision rules (per batch of 10, read 7 days after the last upload, from the Studio export)

| metric | plateau today | **gate** | if missed → |
|---|---|---|---|
| stayed to watch (median) | 58 % | ≥ 70 % | hook problem: rewrite the 0–2 s beat (subject earlier, question shorter), re-test 5 videos |
| AVD / duration (median) | 40–44 % | ≥ 65 % | middle problem: cut a beat, move the payoff earlier, tighten captions |
| views | median 1,074, max 2,035 | ≥ 1 of 10 > 5,000 and median ≥ 2,000 | distribution problem: swap to Variant B and named-entity topics |
| subscribers / 1k views | 0.64 | ≥ 2.0 | end problem: change the CTA line / tease, add the series promise earlier |
| likes / views | 12 % | ≥ 8 % (keep) | — |

`tools/studio_import.py` (Phase 2.1) ingests the three Studio CSVs (`Table data`, `Chart data`, `Totals`) and writes
`docs/SCORECARD.md` with these tables per format/series, so each batch is judged the same way with one command.

## 5 · Phases (each ≤ 15 min sandbox wall time, ≤ 3 min per tool call, commit per step, phase card in `RESUME.md`)

| phase | goal | agent does | Actions does | verify by | exit |
|---|---|---|---|---|---|
| **2.1 Scorecard** | `tools/studio_import.py` + `docs/SCORECARD.md` from the Oct export | write importer, run on `docs/data/studio_*` | — | `python3 tools/studio_import.py docs/data/studio_2026-09-16_10-13` prints the §1.2 table | SCORECARD committed |
| **2.2 Format v2 template** | `series/_template_v2/` with the §2 timeline; `series.json` structure v2; quizlint Q9–Q13 | edit `engine/quiz.py` (chips, 1.5-s beat, reveal hook), `compose.py` beats, `quizlint.py`, `tools/new_episode.py --v2` | `check` | `tests/selftest.py --quick` + negatives for Q9–Q13 | preflight green on `_template_v2` |
| **2.3 Word-timed captions** | caption band driven by `words.json` (≤ 4 words/line, keyword emphasis) | `engine/compose.py` captions mode, textqa dead-zone rules | `check` | `hfstatic.mjs` + textqa fixture | captions in `_template_v2` |
| **2.4 Flag-fill, glow, icons** | `highlight` layer `fill:"flag"` + glow; `icons` layer (OpenMoji CC BY-SA 4.0); counter | `engine/geo.py`, `geo-runtime.js`, provenance kinds, `docs/DATA_SOURCES.md` | `check` | `tests/test_geo_runtime.mjs` + `geopreview.mjs` PNG in `docs/img/` | preview shows a flag-filled country with glow + 2 icons |
| **2.5 Wild Files visual** | `compare` silhouettes-to-scale + counter; optional GBIF range layer | `engine/charts.py`/`geo.py`, fixture episode | `check` | preflight on fixture | fixture passes all offline gates |
| **2.6 Sports Sprint visual** | `strip` (timeline/venue strip) + venue pin on map | `engine/charts.py`, fixture | `check` | preflight on fixture | same |
| **2.7 First maptile clip** | one 6-s satellite flyover rendered on the runner; cost measured; image digest pinned | author clip spec in a fixture | `render` (clip only) | `cloud.py why` + `clipcache` hit | cost recorded in `docs/MAPTILE.md` |
| **2.8 v2 runner proof** | `selftest.yml` renders `_template_v2`; frames reviewed | dispatch, poll ≤ 60 s calls, pull artifact, contact sheet | `selftest` (≈ 9 min) | `docs/img/runner_proof_v2.jpg` | QA pass, Q9–Q13 green on the runner |
| **3.1 Pilot batch A** (owner's "make videos") | 10 episodes: 5 Geo, 3 Wild, 2 Sports — research → authoring → previews → `cloud.py render` | 1 episode per phase (research + authoring), renders dispatched in pairs | `render` ≈ 10 min each | Release per episode with POST_KIT | owner uploads 2/day for 5 days |
| **3.2 Score** | 7 days after the last upload | `studio_import.py` on the new export | — | `docs/SCORECARD.md` batch table | gates in §4 decided |
| **3.3 Iterate** | fix the failed gate per §4 rules; Variant B if distribution failed | 5-episode re-test | `render` | scorecard | gates met → Phase 4 |
| **4.x Scale** | sustained 2/day; monthly mix re-weight; Body & Brain enters; maptile flyovers where they add retention | batches of 6 per session | `render` | monthly SCORECARD row | — |

Actions budget per month at scale: 60 renders × 7.5 min + ≈ 30 `check` runs × 2 min + 2 selftests ≈ 530–650 min of 2,000
(`cloud.py render` guard: 12 min per episode + 60 reserve; no crons).

## 6 · Risks

| risk | mitigation |
|---|---|
| stayed % does not move with v2 | Variant B (no options) is pre-built; the 0–2-s beat is parameterised so a re-test is authoring, not engineering |
| the map-explainer look is generic (hundreds of channels) | the quiz hook + honest-map identity (scale bars, equal-area, border plates) is the differentiator; keep it visible |
| maptile clips cost too many minutes | measure in 2.7 before any batch uses them; cache clips; vector maps are the default |
| owner upload discipline (2/day, two time slots) | POST_KIT carries the slot; batches are released in pairs with dates |
| policy pressure toward provocative "what-if" content | out of scope by rule; hypothetical content only with a label, never on disputed regions |

## 7 · Needed from the owner

1. Approve the v2 format (§2) and the weekly mix (§3) — or name the changes.
2. The explicit **"make videos"** for Phase 3.1 (nothing renders before it).
3. A fresh Studio export (the same three CSVs, 28-day window) after each batch, dropped into `docs/data/`.
4. The two best posting hours from Studio → "When your viewers are on YouTube".
