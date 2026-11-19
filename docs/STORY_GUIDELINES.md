# Geo Stories — guidelines (not templates)

Fifth feed topic (owner 2026-11-18): narrated map-story Shorts, no MCQ. Up to 60 s, all channels, cover = title only (owner 2026-11-19: naming the place on the cover gives the curiosity away).
Built inside the existing engine in three phases: **1** format + keyword captions + SFX + highlight styles ·
**2** camera grammar + map icons + zones/areas · **3** depth (parallax shadow under highlights, then terrain if stats
justify it). `docs/AUDIT_GEO_STORIES.md` has the reasoning. Everything below is a guideline with a reason; a story
that breaks one must say why in its brief.

## 1. What a Geo Story is
One geographic question, answered on the map, with one twist. The viewer should be able to retell it in a sentence.
Shape (timings are typical, not fixed):
- **Cold open (0–4 s)** — one line that creates the question. Title block on screen: PLACE kicker + headline.
  Camera already moving (never a static first frame).
- **Place (4–10 s)** — where it happens. Camera plunges from continent to subject; the subject lights up on its name.
- **Why (10–35 s)** — the mechanism in 2–4 beats, each with its own visual: a route drawn, a comparison, a counter,
  a zone map, a photo, a disputed-border plate when relevant.
- **Twist (35–50 s)** — the fact that reframes the opening line. Hard beat: flash, counter, or a second highlight.
- **Close (50–58 s)** — one sentence that answers the opening line, then the standard outro (Subscribe/Like, no tease).

Story shapes (variety axis `story_shape`; never two days in a row, never the previous episode of the series):
`line-that-shouldnt-exist` · `cant-see-from-the-ground` · `why-here-not-there` · `number-nobody-believes` ·
`before-after` · `the-detour` (a route that goes the long way and why) · `two-places-one-name` · `the-edge-case`
(an exclave, a tripoint, a time-zone oddity).

## 2. Narration
- 120–150 words for 50–60 s at Kokoro `am_michael` speed 1.3 (≈ 2.6–2.8 words/s). Hard range in precheck: 110–155.
- Present tense, concrete places, one idea per sentence, no "did you know", no "but wait", no "let me explain".
- The closing sentence answers the opening sentence with the same key noun.
- ≤ 3 spoken numerals; every number also appears on screen (card, counter, label) at the moment it is spoken.
- Disputed or political places: say *administers / claims / controls*, never *owns* (BORDER_POLICY.md); show the plate.
- Timely topics (from the news feed): only confirmed facts; projections and allegations are labelled as such or left out.

## 3. Picture rules
- **The highlight rule.** Whenever the narration names a place, it lights up on that word. Three styles:
  `tint` (subject area, translucent blue, white border), `solid` (the key place, opaque sand/orange), `glow`
  (one hero feature, fire glow). Earlier highlights stay while the next one builds; ≤ 2 highlight colours on screen
  except `zones`. Things without a border (a range, a strait, an archipelago) get an `area` polygon (phase 2).
- **Keyword captions.** A 2–5-word white phrase with one yellow `*keyword*`, placed in the caption band
  (y ≈ 1380), one per beat, on the stressed word, gone before the next. They carry the story when the viewer is muted.
  Word-timed captions (v2 engine) are NOT used on stories — the keyword caption is the caption.
- **Camera.** Span table: world 300–360° · continent 90–150° · large country 30–60° · small country 12–20° ·
  island group / metro 4–9° · city 0.4–1°. Deep zooms interpolate on a log scale (phase 2 engine change; until then
  split a 360→1 plunge into two moves). Held shots drift (lon/lat a little, span −10 % over the shot). No bare
  blue at the edges at any time (far bbox rule). Hard cuts only between acts; eased moves inside an act.
- **One visual event per idea change, ≥ 15 events / 10 s, nothing static > 2.5 s** (pacelint, unchanged).
- Cards for numbers and names; photos (PD/CC0) only when the thing itself is the story; stickers sparingly.
- Title block, captions and cards never enter the right action column or the bottom safe band (placelint dead zones).

## 4. Sound
- Bed: `bed:drone` (new, slow, low) or `bed:pulse`; keyed per episode as today.
- **Auto-SFX** from the beat timeline (reelkit/quizscore.py `sfx_cues`): big camera move → whoosh · highlight in →
  pop · pin / label in → click · route draw → swish · counter → riser · title / twist card → soft hit · flash → hit.
  Level −14 dB under the voice, ducked; one effect per beat (the first wins inside 0.35 s).

## 5. Cover
Style B frame, **title only** (owner 2026-11-19: no place kicker — naming the country gives the curiosity away): the headline (≤ 7 words, white, one yellow keyword), the
series tag "GEO STORIES · #n", brand footer. No options, no timer, no map that gives the twist away. The cover must
not reveal the twist (same hard rule as the quiz covers).

## 6. Copy
Title carries the search term verbatim + the place; descriptions promise the question, never the twist; a comment
question; per-Short hashtags with judgment; nothing about AI or sources. Spoilers list = the twist words.

## 7. Topics
Sources, in order: (1) the prompts the owner supplied — the GeoGlobeTales visual/story brief (hook → context → twist
→ payoff) and the "map-driven video" master prompt (idea card: working title · first line · question answered · key
map reveal); (2) `tools/signals.py` search/suggest signals; (3) **daily top world news** via `tools/feed.py news`
(GDELT / Wikipedia Current events, free) filtered to stories with a map at their centre (borders, routes, disasters,
infrastructure, elections by region) — confirmed facts only. Every story has `topic.md` (Signal · Why now · Idea card
· Twist · Rejected alternatives · Search term · Copy · Ship by) and `brief.md` (Hook fact · Show it · Beat order ·
Different from · Swipe test · Devices · Media & Pace) exactly like the quiz series.

## 8. Gates (phase 1)
quizlint skips `story-v1`; `storylint` (new) checks: shape + hook present, 110–155 words, every named place has a
highlight beat on its cue word, ≥ 1 keyword caption per story scene, ≤ 2 highlight colours per scene, cover has no
twist word, close answers the open (shared key noun), spoilers not in copy. Pacelint, geolint, textqa, layout,
claim ledger, two-publisher rule, border policy: unchanged and mandatory.
