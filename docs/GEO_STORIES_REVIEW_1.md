# Geo Stories — first three episodes for owner review (2026-11-18)

Status of all three: `draft` (the `daily` workflow only consumes `ready`, so nothing is scheduled until you say so).
Rendered end-to-end by CI (Kokoro VO, every gate green: storylint, geolint, facts, provenance, hyperframes check, textqa, QA).

| # | Episode | Shape · opener | Length | Release (mp4 + jpg + gate reports) |
|---|---|---|---|---|
| 1 | The navy with **no sea** — Bolivia | the-edge-case · plunge | 49 s | `geo-stories-review-7` |
| 2 | The land **nobody wants** — Bir Tawil | why-here-not-there · wide-drift | 48 s | `geo-stories-review-4` |
| 3 | Nearest humans **in space** — Point Nemo | number-nobody-believes · mystery-zoom-out | 50 s | `geo-stories-review-5` |

Pending in the repo (not yet in the releases above): fact cards moved up to y=1010 so they never sit on a keyword caption
(seen once in #1, "ICJ 2018" card over "Día del Mar"). Next render picks it up.

## What was built (phase 1, all in our own code)
- Format `story-v1`: `engine/story.py` (title block place+headline, keyword captions with dark plate, close line), wired in `engine/compose.py`.
- Authoring: `tools/author_story.py` (spec → episode/voice/research/geo/visuals), specs in `tools/specs/story/`.
  Auto "cue breath" (every spoken cue gets a visual answer), slow camera drift after each glide, one climax, energy arc.
- Gates: `reelkit/storylint.py` (S1–S9, see docs/STORY_GUIDELINES.md §8); quizlint delegates; topiclint has story sections; pacelint knows the story verbs.
- Sound: `bed:drone` under the pad; auto-SFX from the visuals beats (whoosh on big camera moves, pops on highlights, clicks on pins/labels, swish on route draws, riser on counters, hit on title/close) — all procedural, all −14 LUFS mastered in CI.
- Cover: `reelkit/cover.py` style `story` = title + place (no sticker, no options).
- Series: `geo-stories` registered (colour #5FB6F2, key A2); publishing entry has `playlist_id: null` → create the playlist in Studio and paste the id; no playlist is ever created by title.
- Fixes along the way: Natural Earth 10m files use upper-case property keys (geodata name match), outro stickers + brand assets for story-v1, Bir Tawil plate wording in the border registry (as_of 2026-11).

## Decisions wanted
1. Approve / reject each episode (or notes per beat).
2. Playlist id for "Geo Stories".
3. Phase 2 go-ahead: camera grammar (push-in, rotate-zoom, log-scale span), map-anchored icons, zone highlight sets, `tools/feed.py news` for daily-news topics.
