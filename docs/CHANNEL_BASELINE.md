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

## 60-day audit (captured 2026-10-15, 239 Shorts published 2026-08-16 → 2026-10-14; data: `docs/data/channel_shorts_60d_2026-10-15.csv`)

Method: Shorts tab + innertube continuation for the video list (432 ids), one watch-page fetch per video for exact views,
likes, duration and publish date. Subscribers 122, lifetime views 162,637 — **≈ 100 % of lifetime views came in these 60 days**
(2024 uploads: median 5 views; Feb 2026: median 1).

| window | n | median views | p90 | max | in 900–1,400 band | >1,500 | <200 | median like-rate |
|---|---|---|---|---|---|---|---|---|
| Aug 16–30 (first 15 days of "5 Questions – Quiz") | 58 | 1 | 7 | 34 | 0 | 0 | 58 | — |
| Sep 6–Oct 13 "plateau" (all formats) | 156 | 1,074 | 1,266 | 2,035 | 71 % | 4 | 8 | 11.0 % |
| ├ 5-question cards, 60–77 s | 120 | 1,092 | 1,272 | 2,035 | 72 % | 3 | 7 | 10.9 % |
| ├ 1-question cards, 11–16 s (from Oct 5) | 20 | 1,007 | 1,348 | 1,724 | 60 % | 1 | 1 | 9.4 % |
| └ 1–3-question cards, 35–48 s (from Oct 6) | 16 | 1,072 | 1,202 | 1,259 | 69 % | 0 | 0 | 14.0 % |

Readings:
- Views are flat at ≈ 1,000–1,300 per Short regardless of topic, length or question count — the signature of Shorts-feed
  seed distribution that never expands. The Oct 5 format change (1 Q, 11–16 s) did not move it. Topic is not the limiter;
  the card-and-timer format (dead time, text-only reveal, no visual payoff, no reason to subscribe) is the hypothesis to test.
- Subscriber conversion ≤ 1 per 1,300 views. Like-rate is high (≈ 11 %), so the few who finish do engage.
- Slight topic tilt inside the plateau: Sports Sprint median 1,190 (n = 8), animals/nature and geography superlatives hold the
  top-15 (Big Cats 2,035; basketball origin 1,724; natural wonders 1,612; "borders the MOST countries" 1,374). Body & Brain and
  Time Vault sit lowest (median 681 / 619 over 60 days).
- Title openers: "Which…" median 1,058 (n = 16), "What…" 952 vs "5 Questions About… – Quiz" 702 (n = 200).
- Owner-side numbers to confirm in YouTube Studio (not public): Shorts "viewed vs swiped away", average percentage viewed,
  and where the retention curve drops (expected: at the countdown).

Targets above are restated against this audit: break the plateau (≥ 1 of the first 10 system Shorts > 5,000 views) and lift
the median above 2,000 (≈ 2× the 1,074 plateau median).

## What success looks like after Phase 2–3 (targets, not promises)
- Median views of the first 10 QuizWire-system Shorts > 2× the 669 baseline; ≥ 1 of 10 above 5,000.
- Subscriber conversion: ≥ 1 new subscriber per 300 views (baseline ≈ 1 per 1,344).
- Zero copyright / reused-content flags (provenance gate) and zero border complaints that the policy plates don't already answer.

## Method
`fetch https://www.youtube.com/feeds/videos.xml?channel_id=UCrg5L4o5vTs4Rt_VeVdHpzQ` (latest 15 uploads with view counts in
`media:statistics`), `/about` for totals. yt-dlp cannot run from the sandbox (bot check) — metadata only.
