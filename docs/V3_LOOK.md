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
| Timer | **3-s think-time after the options are read** (owner decision 2026-10-15): 200-px ring at y 1275 drains while 130-px digits 3·2·1 pop (tick per digit, riser); "GUESS BEFORE THE TIMER ENDS" at 1512 fades 0.25 s before the reveal. `quiz.beat` = countdown `silence` = 3.0 (quizlint Q10 2.5–3.5) | — |
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
| V3.1 ✓ `5e808b4` | basemap layer: `reelkit/basemap.py` in the `geo` stage (cache by bbox/zoom, ≤ 2 MB per scene), `engine/geo.py` `basemap:"bluemarble"` under the vector layers, antimeridian seam handled | raster under d3 Mercator, credit + provenance entry |
| V3.2 ✓ `6e02d59` | lifted highlight: `flag` / `fill` highlight kinds (clipPath flag image, white outline, shadow, pop/wipe tweens) | `geo.highlight_in` variants |
| V3.3 ✓ | v3 UI: question/options/timer/reveal/caption components in `engine/quiz.py` + CSS; flag/icon circles in options; stickers + flag-ball characters landed here too | `format:"quiz-v3"` · `docs/img/v3_3_contact_sheet.jpg` |
| V3.4 | Wikimedia photo cut-outs (licence fields) + word-by-word caption timing polish; sticker/character verbs already exist | `plate` cut-outs, `captions.words` |
| V3.5 ✓ | template `series/_template_v3` (= Geo #13 in v3), quizlint Q14 (no camera on the answer bbox before the reveal unless k ≤ 0.5) / Q15 (full-bleed stage, banner_in), `BASEMAP_OFFLINE=1` placeholder tiles for selftest, `tools/new_episode.py` scaffolds v3 by default | selftest green; full local chain on the example: HF check 0 errors, textqa 0 FAIL |
| V3.6 | re-author the 10 pilot episodes' `visuals.json`/`geo.json` to v3 (scripts, voice, facts unchanged) with a local contact sheet each | 10 reviewed sheets |
| V3.7 | one runner render (Geo #13) → owner look → then the batch | Release `pilot-v3-batch1` |

## v3 authoring schema (what V3.3 shipped — `series/_template_v3/` (= Geo #13) is the worked example)
**episode.json** `"format": "quiz-v3"`; `quiz.option_meta: [{"flag":"ch"},{"flag":"nz"},{"emoji":"1f3c6"}]` (icon circle per pill, optional);
`quiz.banner` (big yellow answer, default = correct option; ≤ 11 chars 150 px · ≤ 16 → 118 px · else 92 px) · `quiz.banner_sub` (default "✓ B was right").
Copy limits (quizlint Q4, v3): question ≤ 72 chars (100 px Lilita, auto 86/74), option ≤ 18, fact kicker ≤ 16 + text, kicker+text ≤ 46 (two 84-px Anton lines).

**geo.json** scene: `"projection":"mercator"`, `"basemap": {"layer":"bluemarble","k_max":2.0,"far":{"bbox":[100,-60,200,10],"k_min":0.3}}` — `far` = coarse wide raster so the
hook camera can sit at k ≈ 0.3 **off the answer** (Australia for the NZ question). Highlight layer `"lift":"flag","flag":"nz"` (flag stretched into the shape; `"flag_fit":"cover"` to crop instead)
or `"lift":"fill","color":"#C8102E"`. No `scalebar` on basemap scenes. **Map text safe zone y 700–1180** (hook/banner above, caption band below) at every visible camera.

**visuals.json** stage `box [0,0,1080,1920]`, `anchor [540,900]` (full-bleed; the camera centres targets at y 900).
Elements: `fact {kicker,text}` (84-px caption at y 1250, kicker yellow) · `sticker {emoji:"1f3d4", x, y, size, rot}` (Twemoji, CC-BY 4.0, fetched by `reelkit/stickers.py` in the geo stage;
or `src` for a cut-out + `credit`) · `character {flag:"nz", face: think|wow|happy|sad|angry|cool, x, y, size, rot}` (flag-ball SVG, own).
Verbs (v2 verbs keep their names): `hook_in/out` → pop; `chips_in/out` → pills; `beat` → 3-s timer ring with 3·2·1 digits + "GUESS BEFORE THE TIMER ENDS"; `reveal` → correct pill green; new: `banner_in/out`,
`sticker_in/out {id}`, `character_in/out {id}`. Word captions (Anton 56 px, y 1500) auto-hide while a fact/CTA is on screen. Scrim-top dims to 35 % after `banner_out`, back to full at the loop `hook_in`.
Flags for pills/characters/lifts are collected by `geodata.py prep` from geo.json + visuals.json + episode.json (`flag` keys ≤ 6 chars).

## Outro (V3.6d, owner brief 2026-10-15) — no "next video" tease
The last scene (`s08`, cta role, ≈ 5–7 s) is a branded end card that *demonstrates* the ask instead of announcing tomorrow's question:
1. map text clears (`geo.clear` at `s08`), the satellite dims (radial, 0.55–0.86) and the camera drifts back to the hook framing;
2. the channel logo (white disc, yellow ring) pops with a spin, **TheQuizWire** wordmark (Lilita 104) and "ONE MAP QUESTION A DAY" follow;
3. "DID YOU GET IT?" + two buttons: **LIKE** (white) and **SUBSCRIBE** (yellow). An arrow cursor glides in, clicks LIKE (→ yellow, thumb bounce,
   burst ring), glides to SUBSCRIBE and clicks (→ green **✓ SUBSCRIBED**, bell wiggle, burst), then leaves;
4. social row pops one by one — Facebook · Instagram · X · Threads (Simple Icons, CC0, brand-coloured discs) — and the **thequizwire.com** pill;
5. everything holds (logo float, subscribe breathing) until `end-1.0`, then the hook frame returns for the loop.
VO for v08 is the ask itself ("Got it right? Hit like, and subscribe for a new map question every day." — avoid numerals: factcheck counts them).
Authoring: `quiz.outro {headline, tagline, url}` (defaults shown above); beats `cta_in` at `s08` until `end-1.0`, `credit_in` until `end-0.2`,
`hook_in` at `end-1.0`; `geo.clear` at `s08` (dur 0.25) and the return `cam_to` at `s08+0.2`→`end-0.3` with the hook camera (Q12).
Assets: `brand/` (logo.png = channel avatar, owner's mark; cursor.svg own; 4 Simple Icons CC0) are copied by `reelkit/brand.py prep` and
registered in media.json; the like/bell stickers are Twemoji 1f44d/1f514 (always fetched for v3). Engine: `engine/quiz.py` `outro3()` / `outro_in()`.
