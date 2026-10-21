# Template audit — where the system still thinks like a machine (2026-10-21)

Owner's brief: *"Guidelines instead of templates. Use your mind per Short. Topic selection, video making and copy are all still
template-driven."* This is an honest walk through the whole pipeline, stage by stage: what is templated, why it hurts, and what
replaces it. No code was changed for this document.

## 0. The one-sentence diagnosis
Every stage has a **human decision point that was replaced by a fixed list or a fixed order**. Lists (pools) were my way of
making variety *checkable*; but a pool of 4 openers is still a template with 4 faces. The fix is not bigger pools — it is to
move the decision to a written **brief per Short** (already exists for the explanation) and let the gates check **quality
criteria**, not membership in a list.

## 1. Topic selection — TEMPLATED (worst offender)
| What happens now | Why it is a template | Guideline-based replacement |
|---|---|---|
| Episodes come from `tools/specs/*.json` that I invented ("most / longest / deepest / first" superlatives), then `daily_pick.py` picks by a date-seeded random. | Every question has the same grammar: *Which country has the MOST X?* Reach dies because the algorithm (and viewers) see the same video with a different noun. The picker knows nothing about what performed, what is trending, or what the channel feed audience asked for. | **Topic brief before any spec**: each Short starts from a *reason to exist* — a search/trend signal (Google Trends, YouTube search suggest, a news hook, a comment on our channel, a seasonal moment), a target emotion (surprise / "I would have got that wrong" / pride), and a **question shape chosen for that reason** (true-or-false, odd-one-out, guess-the-number-range, "which is bigger", before/after, spot-the-country-from-the-shape). Daily pick becomes: *read the signals, write 1–3 topic briefs, author those*. The random count stays (cadence), the random **choice** goes. Gate: Q22 rejects a question whose stem matches the last 5 published (stem fingerprint), and a brief without a stated signal. |

## 2. Question + script — HALF TEMPLATED
- Fixed: hook = question verbatim (owner rule), options A/B/C, 3 s think, reveal, 74–92 words, ≤ 40 s, Kokoro speed 1.3. These are **constraints**, fine.
- Templated: the *explanation text* is still written to fit the device beats ("counter → compare → card"), so sentences come out as data read-outs ("1,642 metres deep, 20 % of the world's fresh water"). Winners (decode report) narrate a **claim → tension → payoff**, with one number max per sentence and a sentence that talks to the viewer.
- Replacement: the brief's *Hook fact* becomes a one-line **story spine** (what the viewer will feel they learnt), the script is written first, devices chosen afterwards to *serve* the sentences. Gate: Q23 — no more than one numeral per sentence; at least one second-person sentence; no sentence starting with the answer's name twice in a row.

## 3. Opening / reveal — TEMPLATED (pools of 4)
`OPENERS_REVEALS` = {wide-drift, mystery-zoom-out, split-candidates, night-lights} × {flag-lift, route-draw, …}. Q16 only forbids three-in-a-row. The owner sees "the same four openings" and is right.
- Replacement: the opener is **described in the brief in words** ("start inside the stadium photo, pull back until Athens appears") and `author_v4` composes it from primitives (camera path, layer order, what is hidden, what enters). Named presets stay only as *examples* in `docs/BRIEF.md`, never as an allow-list. Gate becomes: *is the answer hidden before the reveal (Q14)*, *does something move in the first second*, *is the opener's camera path different from the last 5 episodes' paths* (compare the actual k/lonlat curve, not a name).

## 4. Explanation (M1) — PARTLY FIXED, still list-shaped
Briefs exist and devices are chosen per episode — but the device vocabulary is 14 named verbs, and the shape gate only checks that the fingerprint is unique. Honest view: this made the episodes *different from each other*, not *better*. Missing: real media (photos/footage of the thing, not only a map), a reason for each cut, and pacing tied to the voice (motion events 27/10 s in winners vs ours ~8–10).
- Replacement: (a) **media first** — every brief must name 1–3 real assets (Wikimedia Commons CC photo/video, NASA, public-domain footage) and the engine gets a `media` stage (Ken-Burns photo, masked cut-out, short clip) as a first-class scene type; (b) cuts follow the script — a beat per clause, not per device; (c) `shapelint` checks *motion density per 10 s ≥ 15*, *no static span > 2.5 s*, *at least one non-map visual*, instead of "device set unique".

## 5. Outro — FIXED TEMPLATE (by owner rule)
Subscribe/Like outro with logo and socials is intentionally the same. Keep. But the **spoken** ending varies: no spoken CTA (decode finding), end on the payoff sentence.

## 6. Copy / SEO — TEMPLATED (by the 2026-10-19 rule, now rejected)
Current: exact question / comment CTA / like CTA / N hashtags from `config/publishing.json` per series. The CTAs come from a tiny per-episode field and the hashtags from a **static per-series pool** — that is the "poor hashtags" the owner saw.
- Replacement — **guidelines, written per Short by me at authoring time**, gated for spoilers and length only:
  - Title: the question *or* a curiosity rewrite that keeps the keyword people actually search (check YouTube search suggest for the topic while authoring; write the term the brief recorded).
  - Description: 1–2 lines that tell the viewer **why this matters to them** (the "what will I take away" line) — not the answer, not a fact dump; a comment question that is specific to this Short ("Which option fooled you — B looked right to me"), platform CTA only where it helps (YouTube yes, X no).
  - Hashtags: 2–3 **topic** tags researched per Short (the subject, the place/sport/organ, the format) + 1 brand tag; no series-wide pool. Different per platform because audiences differ (IG: discovery tags; X: 1 conversational tag; Threads: often none).
  - Gate: spoiler check, limits, and a **novelty check** against the last 10 descriptions (no reused sentence, no identical tag set).

## 7. Covers — TEMPLATED (style B everywhere)
Owner chose B, so the layout is fixed; but the *image* under it is always the map. Replacement: cover brief line in each episode brief — the strongest frame or a real photo cut-out, with the question's emotional word big; style B stays as the frame, not the content.

## 8. Scheduling — RULE-BASED (fine)
Best-time slots per channel are evidence-based; keep. Add a fallback cron (today's 07:00 UTC did not fire).

## 9. Who decides what (the "whole system")
| Stage | Decides | Checks |
|---|---|---|
| Topic & question shape | **Agent, from signals (topic brief)** | Q22 novelty + signal present |
| Script | Agent, story spine first | voice/fact gates + Q23 prose |
| Look (opener, reveal, explanation, media, cover) | Agent, written brief → composed, not picked | Q14 hide, motion density, no-static, non-map visual, camera-path novelty |
| Copy per platform | Agent, per Short | spoiler, limits, novelty |
| Render / dispatch / schedule | GitHub Actions | existing CI gates |

## 10. Order of work (phased)
1. **P1 Topic briefs + Q22** (replace `daily_pick` random choice with signal-driven briefs; keep random count).
2. **P2 Media stage** in the engine (photo/clip with licence capture) + brief requires real assets.
3. **P3 Composed openers** (words → camera path), retire the opener/reveal allow-lists; motion-density/no-static gates replace shape-uniqueness.
4. **P4 Copy guidelines** (per-Short title/description/tags written at authoring time; publishing.json pools deleted) + novelty gate.
5. **P5 Re-author the 2 remaining backlog episodes and the next 6 under the new rules; ship one for review before bulk.**
