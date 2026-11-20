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
- **Animate the thing itself (owner 2026-11-19).** When the narration names an object, a process or a result, the
  screen shows it moving — not a pin and a caption. Props live in `engine/props.py` (`rig` elements + `prop.*` devices,
  all glued to a lon/lat through every camera move): `sat` (station with the crew waving: `prop.orbit` + `prop.wave`),
  `fallsat` + `splash` (`prop.fall` — re-entries streak in and ring out), `person` (`prop.pop` rise, `prop.hop`,
  `prop.cross` when "nobody lives there"), `flag` (`prop.pop` rise + `prop.flutter`; `prop.orbit` to make it jump onto a
  claim), `tag` (a word/year/"?"/"NO", `prop.pop drop`). Rules of thumb: a flag rises on the country's name; a line
  draws with the camera riding it (`cam_path`); a number counts; a claim is a flag landing on the place; a refusal is a
  red NO or a red cross. Every beat gets ≥ 1 camera move with a real change of scale (push ≥ 1.3× or pull ≤ 0.75×),
  not only the drift. Ship-check: contact sheet — if two neighbouring frames look the same, the beat is dead.
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
- **Every short gets a CUSTOM-MADE cover — production rule, not a note (owner 2026-11-20: "not just a line").** No template
  frame-grabs. Per episode `<ep>/cover/spec.json` (written as a DRAFT stub by `tools/author_story.py`) is filled by the agent:
  `hero_prompt` → one bespoke 9:16 hero illustration (image generation, NO text in the art) saved as `cover/hero.jpg`;
  `head` (giant punchy headline, `*keyword*` in yellow), `badge` (tilted curiosity tag), optional `burst`/`marks` (starburst
  number, red ✕), `stickers` (Twemoji). `reelkit/cover_scroll.py <ep> --jpg <ep>/cover/cover.jpg` renders it; the owner sees a
  contact sheet and approves → `spec.approved = "<date> owner"`; `reelkit/mediahost.py cover <ep>` hosts hero + cover as
  `covers` release assets (repo carries no images) and writes `hero_url`/`cover_url`. Gates: `postkit.py check` FAILs without
  an approved cover; `cover.py --burn` (dispatch.sh) refuses to template; `yt_enrich` uses the approved JPG as the thumbnail.
  Cover rules: no place/answer spoiler, hero art carries no text, headline ≤ 4 lines, nothing important below y 1800.
- **Frame 0 IS the cover — production rule, not a note (owner 2026-11-19).** Instagram, Facebook, X and Threads show
  the first frame of a reel as its cover, so every published master opens on its cover card for 0.3 s (audio shifted to
  match). Enforced in three places: `reelkit/local_render.py` burns it into every full local render (what you review is
  what ships); `reelkit/dispatch.sh` burns it into the release master and then **refuses to post** if the burn fails or
  if `cover.py --verify` finds frame 0 ≠ the cover JPG; YouTube gets the same JPG as its custom thumbnail from
  `reelkit/yt_enrich.py` after Buffer publishes (frame 0 is irrelevant there — YouTube picks/uses the thumbnail).
  Manual uploads: use the release master as-is, never the plain render.

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

## v2 look (owner rejection 2026-11-19: "very few camera moves · too much text · basic animation · 360p maps")
Every new story episode follows these, enforced where a lint can:
1. **Basemap**: `geo.basemap: "s2"` — Sentinel-2 cloudless (EOX, 10 m/px, bright daylight; CC BY 4.0). Main raster z7 for a continent
   (`pad_deg` 8, `k_max` ≈ 4), `near` patches under every deep camera (`[{lonlat, k, pad}]`), far raster for the wide opener.
   Attribution is mandatory → top-level `screen_credit` (shown under the outro, copied into the post copy; provenance allows exactly that string).
2. **Camera**: continuous. Opener = `plunge` from a high-altitude wide view (k ≈ 0.4) down onto the subject while the neon border traces
   (`layers[].neon`). Every beat has a `cam_path` so the camera is never still; dives (k 3+) onto pins, tracking pans between them.
3. **Text**: ONE text element at a time (storylint S3): a kw caption OR a counter OR a card, never stacked. Pin labels ≤ 3 words.
4. **Animation**: each beat animates an object on the map — `plane` rig flown with `geo.travel`, true-scale `discs` (`geo.disc_in roll|drop|pop`),
   `geo.pin_ping` sonar rings after every pin, props with drop shadows (`prop.*`), neon routes (`cls: "neon"`, `"neon blue"`, `"neon dashed"`).
