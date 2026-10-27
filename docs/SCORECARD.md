# SCORECARD.md — what the channel's own analytics say about each batch

> **Frozen baseline (YouTube Studio export, Sept–Oct 2026).** Not updated by the pipeline. Live numbers for every channel come from Buffer Insights via `tools/stats.py` → `dispatch/stats.md` (the only stats source of truth since 2026-10-27).


Generated (once) by the retired `tools/studio_import.py <docs/data/studio_PREFIX>` from the owner's YouTube Studio export (Content → Advanced mode → export). Gates come from `docs/PLAN_V2.md` §4 and are evaluated on the episodes this repo produced (matched by question text). Re-run after every batch; keep older sections (use `--append`).

## Studio export `2026-09-16_10-13` — imported 2026-10-14

Totals: **113,104 views** · 13,559 likes · **72 subscribers** · stayed to watch **57.59 %** · AVD 0:00:24 · thumbnail impressions 17,461

Daily subscribers: 72 over 28 days (max 6/day, 3 zero days)

### Plan v2 gates (v2 episodes only)

_No v2 episodes in this export yet (titles are matched against series/*/*/episode.json)._

### By format (published ≥ 2026-09-06, views ≥ 100)

| group | n | views median | views max | stayed % | AVD s | % viewed | likes/views | subs | subs / 1k |
|---|---|---|---|---|---|---|---|---|---|
| 5Q | 74 | 1,134 | 2,035 | 60.5 | 27 | 40 | 12.0 % | 55 | 0.70 |
| 1-3Q | 16 | 1,074 | 1,259 | 56.4 | 18 | 44 | 13.4 % | 8 | 0.53 |
| 1Q16 | 19 | 1,009 | 1,725 | 50.4 | 11 | 73 | 10.8 % | 8 | 0.45 |

Stayed-to-watch distribution (n = 109): p10 48.6 · p25 52.9 · median 58.4 · p75 62.0 · p90 64.5 · max 72.9

### Top 8 by stayed % · bottom 5

| stayed % | AVD/dur | views | subs | title |
|---|---|---|---|---|
| 72.9 | 34/63 s | 1,009 | 1 | 5 Animal Facts That Surprise Adults - Quiz |
| 72.2 | 29/63 s | 853 | 0 | 5 Amazing Animal Skills - Quiz |
| 70.2 | 27/67 s | 706 | 0 | 5 Famous Islands of the World - Quiz |
| 68.9 | 35/66 s | 801 | 0 | 5 Things You Didn't Know About Water - Quiz |
| 68.0 | 29/67 s | 403 | 0 | 5 Discoveries Made by Accident - Quiz |
| 67.8 | 32/70 s | 1,566 | 0 | 5 Myths About Animals Busted - Quiz |
| 67.1 | 30/73 s | 988 | 1 | 5 More Facts About Planet Earth - Quiz |
| 67.0 | 18/42 s | 620 | 1 | Which Roman leader was killed in 44 BC? 🗡️ |
| … | | | | |
| 18.6 | 14/19 s | 372 | 0 | What is the actual shape of a large falling raindrop? |
| 24.7 | 33/19 s | 691 | 0 | Which dry, hot winds often affect Los Angeles? |
| 39.3 | 27/69 s | 936 | 0 | 5 Questions About the 2026 World Cup - Quiz |
| 45.8 | 18/63 s | 1,132 | 0 | 5 Kitchen Inventions That Changed Cooking - Quiz |
| 46.1 | 19/17 s | 371 | 0 | When was the GREAT FIRE of London? 🔥 |
