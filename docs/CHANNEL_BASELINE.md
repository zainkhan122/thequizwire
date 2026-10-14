# CHANNEL_BASELINE.md — TheQuizWire as found on 2026-10-14 (before any QuizWire-system upload)

Measured from the public channel pages and RSS (no API key). Re-measure monthly with the same method and append a row.

| captured | subscribers | videos | lifetime views | views/video | median views, last 19 Shorts | max |
|---|---|---|---|---|---|---|
| 2026-10-14 | 121 | 510 | 162,637 | ≈ 319 | 669 | 975 |

- Handle `@thequizwire-com` (channel id `UCrg5L4o5vTs4Rt_VeVdHpzQ`), joined 2023-12-14; links: thequizwire.com, Instagram, Facebook, Threads, WhatsApp.
- Cadence: 4–5 Shorts per day, all ~1 min quiz cards; series numbering at capture: Geo Blitz #9, Sports Sprint #8, Wild Files #6,
  Cosmic Quiz #4, Time Vault #4, Body & Brain #3, plus "Trend:" one-offs.
- Format (Geo Blitz #8 frame): stock b-roll → red "TheQuizWire" wordmark → yellow series pill → dark glass card → difficulty badge →
  question → 4 option rows → progress bar → cyan countdown. No map, no topic-related motion, boilerplate description.
- Best performers were geography (coldest desert 943, largest peninsula 924) — the audience signal this repo is built on.
- Description boilerplate: "What was your first guess? Do share in the comments below. / Learn daily with thequizwire.com Quizzes and MCQs"
  + `#GKshorts #usagk #thequizwire #1min #shorts` (kept in `series/series.json` so POST_KIT stays on-brand).

## What success looks like after Phase 2–3 (targets, not promises)
- Median views of the first 10 QuizWire-system Shorts > 2× the 669 baseline; ≥ 1 of 10 above 5,000.
- Subscriber conversion: ≥ 1 new subscriber per 300 views (baseline ≈ 1 per 1,344).
- Zero copyright / reused-content flags (provenance gate) and zero border complaints that the policy plates don't already answer.

## Method
`fetch https://www.youtube.com/feeds/videos.xml?channel_id=UCrg5L4o5vTs4Rt_VeVdHpzQ` (latest 15 uploads with view counts in
`media:statistics`), `/about` for totals. yt-dlp cannot run from the sandbox (bot check) — metadata only.
