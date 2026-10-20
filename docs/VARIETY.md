# VARIETY — how the system avoids "template-like" videos (owner question, 2026-10-15)

A quiz channel *needs* a fixed skeleton — question → think → reveal → see it → outro is the brand, the same way every
Jeopardy round looks like Jeopardy. What makes videos feel machine-made is when the **surface** repeats too: the same
sentence stems, the same camera move, the same reveal, the same sticker, the same music, in the same order, every day.
So the rule is: **fixed skeleton, rotated surface, enforced by a gate** — not left to memory or mood.

## 1. The eight rotation axes (every episode declares its choice in `episode.json → variety`)

| axis | pool (✓ = engine supports today · ◌ = planned phase) | how it changes the video |
|---|---|---|
| `question` | `which-country` ✓ · `where-is` ✓ (pin/place answer) · `how-many` ✓ (numeric pills) · `bigger-or-smaller` ◌ (two-option face-off) · `true-or-false` ◌ · `odd-one-out` ◌ · `name-the-capital` ✓ · `which-flag` ✓ (flag pills, no names) · `which-animal` ✓ (Wild Files) · `which-record` ◌ (fastest/farthest/oldest) · `who-was-first` ◌ (Sports) · `which-body-part` ◌ (Body & Brain) | different pill content and phrasing |
| `hook` (voice stem) | `question-first` ✓ · `fact-first` ✓ ("Only one country spans 12 time zones. Which?") · `challenge` ✓ ("90 % get this wrong") · `story` ✓ ("In 1877…") · `misconception` ✓ ("Everyone says Switzerland…") · `character-asks` ◌ (flag-ball speaks the line) | the first 2 s sound different |
| `opener` (visual) | `wide-drift` ✓ · `world-rotated` ✓ (Pacific/Atlantic-centred) · `globe-spin` ✓ (orthographic, ep12) · `mystery-zoom-out` ◌ (k 3 close-up → pulls out) · `night-lights` ◌ (GIBS Black Marble) · `split-candidates` ◌ (two regions side by side) | the map you see before the options |
| `reveal` | `flag-lift` ✓ · `fill-pulse` ✓ · `flash-cut` ✓ (fx.flash to a zoomed scene) · `border-draw` ✓ (route_draw around the outline) · `stamp` ◌ · `card-flip` ◌ (character flips the answer) | the moment of payoff |
| `beats` (see-it set, ≥ 2 kinds) | `pin` ✓ · `route` ✓ · `counter` ✓ · `scalebar` ✓ · `label` ✓ · `second-highlight` ✓ · `photo-cutout` ✓ · `true-size-overlay` ◌ · `timeline-strip` ◌ · `before-after` ◌ | the three facts never *look* the same |
| `cast` | `flagball:<face>` ✓ (think/wow/happy/sad/angry/cool) · `emoji-set:<theme>` ✓ · `none` ✓ · `photo-cutout` ✓ | who is on screen |
| `music` | `seed` per episode ✓ (key + motif) · `bed:pad` ✓ · `bed:pluck` ◌ · `bed:marimba` ◌ · `bed:lofi` ◌ | the sound bed |
| `outro` | `headline` pool: DID YOU GET IT? · TOO EASY? · 1 FOR 1? · CHALLENGE A FRIEND · DAILY MAP QUIZ ✓ · click order `like-first` ✓ / `sub-first` ◌ | the last 5 s |

Plus two things that are *not* axes but matter more than all of them:
- **Script craft.** `docs/STYLE_VOICE.md` (next phase) keeps pools of reveal phrasings ("It's X" / "X — and here's why" /
  "Correct: X" / "Yes — X, because…") and bans the same two opening words in consecutive episodes of a series.
- **Specific, surprising facts** with real numbers. Sameness is felt hardest when the content is generic; a "23 km of
  ice" or "Paris 07:00 = Tahiti 20:00" beat is remembered as that video, not as "the template".

## 2. The gate — quizlint **Q16 variety** (shipped V3.6e)
For an episode N of a series, quizlint loads episodes N−1 and N−2 of the same series and FAILS when
- the `variety` block is missing on a v3 episode, or an axis value is not in the pool;
- **≥ 4 of the 8 axes equal episode N−1** (the fingerprint is "too close");
- `opener`, `reveal` or `outro.headline` equal **both** N−1 and N−2 (three in a row);
- the hook line starts with the same two words as N−1 **and** N−2 (e.g. "Which country…" ×3);
- the sticker/emoji set is identical to N−1.
WARN when `question` or `hook` repeats N−1. The feed order across series (Geo → Wild → Sports → Body) adds natural
contrast on top; `tools/feed.py` (planned) prints the last ten published fingerprints so the author picks the farthest one.

## 3. What this does *not* do
It does not randomise. Each choice is authored (so it fits the fact) and reviewed on frames; the gate only refuses
repetition. Brand constants never rotate: Lilita/Anton type, yellow keyword, green = correct, Michael's voice,
the satellite look, the 3-s countdown, the branded outro.

## 4. Roll-out
- V3.6e ✓ axes + Q16 on ep13/ep14/template (pools in `reelkit/quizlint.py VARIETY`).
- While re-authoring the remaining 8 pilots: each picks a distinct fingerprint (table kept in `docs/SCORECARD.md`).
- V3.8+: ◌ items above, one per phase, each landing with a pilot that uses it (night-lights with Wild #7, true-size overlay
  with Geo #10 Nile, globe-spin already in Geo #12, counter in Sports #10).


### Reveal mechanics (engine)
`banner_in` takes `style`: `pop` (default) · `stamp` (slams down, twist — pair with `fx.flash`) · `flip` (card turns up — use for `card-flip`) · `slide`. The map action still carries the reveal kind: `flag-lift`/`fill-pulse` = `highlight_in`, `border-draw` = `route_draw` of the outline, `flash-cut` = `fx.flash` + stage switch, `stamp`/`card-flip` = banner style when the answer is not a place.


## 2026-10-20 — pools are executable
Openers and reveals listed in `reelkit/quizlint.py` are only those `tools/author_v4.py` actually choreographs; shapelint Q21 fails an episode whose declared opener/reveal is not visible on the timeline. See `docs/EDITOR_FLOW.md`.
