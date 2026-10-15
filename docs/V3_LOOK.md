# V3 look — "satellite quiz" (owner review, 2026-10-15)

## Why
The first eight v2 renders (`pilot-v2-batch1`) were rejected by the owner: dull flat map, the answer country visible
before the reveal, 34-px question text in a strip, nothing moving, nothing to look at. Verified by watching the frames
(`docs/img/v2_as_shipped_geo13.png`) next to the reference channels (`docs/img/reference_frames.png`, pulled with
`tools/yt_storyboard.py`). The references share one recipe: bright satellite/relief basemap, the country lifted off the map
with a flag or saturated fill and a thick white outline, big display type, stickers/characters, a visible change every second.

## The v3 frame (see `docs/img/v3_direction.png`: left = shipped v2, middle = v3 hook, right = v3 reveal)
| Layer | v3 | Source / licence |
|---|---|---|
| Basemap | full-bleed NASA Blue Marble shaded-relief + bathymetry, Web-Mercator tiles stitched per scene (`reelkit/basemap.py`) | NASA GIBS — public domain, credit "NASA Blue Marble" |
| Hook camera | wide and **off the answer** (continent / hemisphere); the subject is never shown before the reveal | — |
| Highlight | country/region lifted: flag fill (`flag-icons`, MIT) or saturated colour, 9-px white outline, drop shadow, pop-in | flag-icons MIT; Natural Earth polygons |
| Question | Anton 104 px, 2–3 lines, centred, keyword in #FFD400, top third over a dark scrim | Anton OFL |
| Options | three 124-px pills with letter badge + **flag/icon circle** + 58-px label; correct pill turns green, others dim | flag-icons / Twemoji |
| Timer | 150-px ring with a 3-2-1 count; "GUESS BEFORE THE TIMER ENDS" | — |
| Reveal | camera flies in (1.2 s), flag wipes on, outline flashes, 150-px yellow answer name + "✓ B WAS RIGHT" | — |
| See-it beats | one 86-px caption (number in yellow) + one sticker/photo + one map action (pin, route, second highlight, counter) per beat | Twemoji CC-BY 4.0; Wikimedia PD/CC-BY cut-outs |
| Captions | word-by-word 86-px Anton for the story lines (from `words.json`) | — |
| Characters (optional) | own "flag-ball" SVG set (flag circle + 6 expressions) | own |
| Credit line | "NASA Blue Marble · Natural Earth · thequizwire" at y ≈ 1545 | — |

Safe zones, gates and budgets are unchanged (textqa dead zones, HF check, voice, facts, provenance, geolint); the
basemap is a Mercator raster, so size claims keep the equal-area vector scene (geolint P1) — the raster is only used for
Mercator/regional scenes.

## Rule added
**Nothing is dispatched to Actions before a local contact sheet of the episode has been looked at.** The sandbox now has
HyperFrames 0.8.137 + Chrome (`bash bootstrap.sh --browser`): `hyperframes snapshot --at …` and `hyperframes check` run here;
textqa runs here too. Actions minutes are for the final render only.

## Build plan (phases ≤ 15 min, commit per step)
| # | Phase | Output |
|---|---|---|
| V3.1 | basemap layer: `reelkit/basemap.py` in the `geo` stage (cache by bbox/zoom, ≤ 2 MB per scene), `engine/geo.py` `basemap:"bluemarble"` under the vector layers, antimeridian seam handled | raster under d3 Mercator, credit + provenance entry |
| V3.2 | lifted highlight: `flag` / `fill` highlight kinds (clipPath flag image, white outline, shadow, pop/wipe tweens) | `geo.highlight_in` variants |
| V3.3 | v3 UI: question/options/timer/reveal/caption components in `engine/quiz.py` + CSS; flag/icon circles in options | `format:"quiz-v3"` |
| V3.4 | sticker layer (Twemoji by codepoint, Wikimedia cut-outs with licence fields) + word-by-word captions | `sticker_in`, `captions.words` |
| V3.5 | template `series/_template_v3`, quizlint rules for v3 (no subject on screen before reveal, min type sizes), selftest | green offline + local snapshots |
| V3.6 | re-author the 10 pilot episodes' `visuals.json`/`geo.json` to v3 (scripts, voice, facts unchanged) with a local contact sheet each | 10 reviewed sheets |
| V3.7 | one runner render (Geo #13) → owner look → then the batch | Release `pilot-v3-batch1` |
