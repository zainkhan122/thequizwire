# Audit — adding narrated Geography story Shorts (non-MCQ) to TheQuizWire

Date 2026-11-18 · scope: what the pipeline already has, what is missing for "fully animated, multiple camera moves,
aesthetic, professional" map-story Shorts, and whether the three supplied inputs (p1/p2 prompts, the Kaz Map
Animation skill + its master prompt) can be used. No code was changed for this audit.

## 1. What we already have (≈ 80 % of the production chain)

| Layer | Status | Notes |
|---|---|---|
| Basemap | ✓ real imagery | NASA GIBS Blue Marble shaded-relief + bathymetry, Web-Mercator tiles stitched per scene (zoom ≤ 8 ≈ 611 m/px), Black Marble night layer; public domain. This is the "bright satellite" look p1/p2 ask for, without licence risk. |
| Camera | ✓ | `geo.cam_set / cam_to` with eased moves and per-scene holds; `geo.spin` (globe), wide-drift / mystery-zoom-out openers. Multi-move sequences already exist (ep30 La Paz: 6 moves). |
| Map devices | ✓ | highlight in/out/pulse, pins + labels, `route_draw`, `travel` (moving marker), `rise` (3-D extrusion), disputed-border plates with holder text, scalebar, fade. |
| Data graphics | ✓ | bars, compare, split, counter, erase, callouts, strip — on-map or card. |
| Casting | ✓ | flag-ball characters, emoji stickers, photo cut-outs (PD/CC0 only), fact cards. |
| Voice | ✓ | Kokoro `am_michael`, word-level timestamps → every device lands on a cue word. |
| Audio | ◐ | generative music beds (pad/pulse/tense/warm, seeded per episode); **no SFX layer**. |
| Typography/brand | ✓ | Lilita One + Anton, series tag, outro with logo/CTA. |
| QA gates | ✓ | placelint (dead zones), pacelint (≥ 15 events / 10 s, static > 2.5 s = FAIL), geolint (projection size claims), shapelint, topiclint, textqa (contrast), claim ledger (every screen text sourced), spoiler gate, Q20/Q24 variety & show-the-real-thing. |
| Publishing | ✓ | Buffer scheduling by per-channel best times, covers → YouTube thumbnails, playlists, tags, stats loop. |

Everything above is reusable as-is for a story format; the renderer does not care whether the script is a question.

## 2. What is missing for the target look (the real gap)

Ranked by visual impact per unit of work.

1. **A story-format authoring path (biggest gap, small code).** Today `author_v4` assumes hook → 3 options → 3 s
   think → reveal → 4 explanation beats → CTA. A story Short needs: cold-open line (0–3 s) → place established
   (3–8 s) → mechanism/why (8–25 s) → twist (25–35 s) → closing line + CTA. Needs a `format:"story"` spec with
   its own gates: no option/timer scenes, no answer-spoiler logic, 100–130 words for 40–50 s, caption band for
   keyword captions, and a new variety axis (story shapes: "the line that shouldn't exist", "the thing you can't
   see from the ground", "why here and not there", "the number nobody believes", "before/after").
2. **Keyword captions (small).** Short white phrases at ~72 % height with one yellow keyword, 2–4 words, one per
   beat — the strongest single signal in the reference channels; we only have fact cards + the hook block.
3. **SFX layer (small).** 8 synthesised cues (whoosh on big zoom, swish on path, pop on pin/highlight, riser on
   counter, impact on title, ding, click, flip) mixed at −12 dB under VO, auto-cued from the device timeline.
   Kaz's `make_sfx.py` shows this can be generated procedurally (no licence). Without SFX the "cinematic" feel
   is missing even with perfect motion.
4. **Camera grammar for stories (medium).** Add: slow push-in on held shots (span −10 % over 3 s), rotate-while-
   zoom (`rot` on the mercator stage), hard-cut vs eased move as an authored choice, and a **log-scale span
   interpolation** so 360° → 1° zooms look constant-speed (Kaz does this; ours eases linearly on scale — visible on
   very deep zooms).
5. **Terrain depth (medium-large, optional).** A real 3-D tilted terrain (p1/p2's "3D topography") needs a
   DEM + hillshade/tilt renderer — not in our 2-D SVG/raster stage. Honest options: (a) keep 2-D Blue Marble with
   shaded relief (already has relief baked in) and add a subtle parallax drop-shadow under highlighted
   countries — 90 % of the perceived depth for 5 % of the work; (b) CesiumJS/MapLibre-GL 3-D terrain in headless
   Chromium — possible on free tools (MapLibre + AWS Terrain Tiles/Terrarium are free; imagery still must be PD),
   but a second renderer, GPU-less CI rendering at ~2–4 fps, and a new QA surface. Recommend (a) first.
6. **Highlight styles (small).** Kaz's rule "every named place lights up on its beat" with three styles — subject
   tint (translucent blue, white borders), key place solid orange, hero glow — plus `zones` (multi-colour
   categories with pill labels) and free `area` polygons for things with no border (mountain ranges, straits,
   island chains). We have one highlight style + pulse; zones/area are the missing explainer tools.
7. **Icons with drop shadow on the map (small).** Plane/ship/pin/X/warning as flat SVG with soft shadow,
   moving along `travel` — we have emoji stickers (screen-space) but no map-anchored icon set.
8. **Script discipline for narration (process, not code).** Documentary pace 2.6–2.8 words/s, present tense,
   concrete places, one idea per sentence, the closing line answers the opening line, no "did you know".
   Needs a `docs/STORY_GUIDELINES.md` with the same "guidelines not templates" rule and a per-episode brief.
9. **Fact rigour for stories (process).** Stories make more claims per Short (8–12 vs 4–5). The claim ledger,
   two-independent-publisher rule and spoiler gate already exist; the story gate must require ≥ 2 sources per
   claim and a "disputed-wording" check for borders/politics (our `border_registry.json` already does the
   holder text).
10. **Music.** Story beds need a darker, slower palette (drone, low pulse) than the quiz beds; two new seeds.

Effort estimate (phased, agent + Actions, same free stack): phase 1 (format + captions + SFX + highlight styles)
≈ 3 author/CI rounds; phase 2 (camera grammar + icons + area/zones) ≈ 2 rounds; phase 3 (terrain depth
option a) ≈ 1 round. Nothing requires a paid tool or new secrets.

## 3. The supplied inputs — can they be used?

### p1.txt / p2.txt (identical "GeoGlobeTales" prompt)
- **What it is:** a prompt for AI image→video generators (Veo/Kling/Runway style): one image prompt for scene 1,
  then "upload the last frame" chaining for scenes 2–4 at exactly 8 s each.
- **Fit:** the *visual spec* is useful and matches what we can render deterministically: bright daylight
  satellite look, glowing neon borders/paths (red/blue/yellow), minimal icons with drop shadows, kinetic
  zoom-in from continent to target, isometric pans, documentary VO with whooshes/scans/radar beeps.
- **Not usable as a workflow:** generative video is not free, not deterministic, fabricates coastlines/borders
  (a hard no for disputed-border content and for the claim ledger), has no word-level sync, and the 4 × 8 s
  rigid structure contradicts our pacing gates. The 8-second blocks exist only because the generator's clip
  length is 8 s.
- **Take from it:** the shot grammar (hook/context/twist/payoff), the colour language for neon overlays, the SFX
  vocabulary, and the "no hard cuts within a scene" rule → becomes a story-shape entry and a camera/overlay
  style in our own engine. Do not take: the 8 s grid, "dark shocking facts" framing (keep neutral, sourced).

### "Map Animation master prompt.pdf"
- **What it is:** a 3-step chat workflow (pick niche → pitch ideas → write a 130–150-word VO script with shot
  cues and sources after the script).
- **Fit:** directly compatible with our topic/brief files. Its best rules — "verify timely or disputed claims
  before writing", "distinguish confirmed facts / projections / allegations", "put sources after the script so
  narration stays clean" — are already our hard rules (claim ledger, no credits in video).
- **Take from it:** the Step-2 idea card (working title · first line · the question it answers · the key map
  reveal) as the mandatory header of a story brief; the 130–150 words / 60 s calibration (we would target
  110–130 words for 45–50 s Shorts).

### Kaz Map Animation skill (zip)
- **What it is:** a complete, well-designed SVG map renderer (Playwright + ffmpeg) with Natural Earth borders,
  admin-1 provinces for 9 countries, highlight styles (tint/solid/glow/zones/area), paths, rulers, meridians,
  time tags, blueprint and cross-section cutaways, georeferencing of user screenshots (thin-plate spline +
  auto-align), auto-SFX kit, Whisper timing. Architecturally very close to ours (scene JSON → headless Chromium
  → MP4).
- **Licence — decisive:** `rights/OWNERSHIP_AND_RIGHTS.txt` is **proprietary, all rights reserved** to a named
  third party; "no one else may copy, modify, redistribute… without prior written permission". Our repo is
  public. **We cannot vendor or copy its code, presets or designs.** Its *basemap* is also not satellite imagery:
  it is a procedurally drawn flat globe (ocean gradient + land fill + grain), i.e. less photoreal than our Blue
  Marble stage, and it has no disputed-border handling.
- **What we can legitimately use:** the ideas, not the code — (1) the highlight rule and the three-style colour
  system, (2) zones with pill labels, (3) free-polygon `area` highlights, (4) log-scale span interpolation,
  (5) the auto-SFX cue mapping (device → sound), (6) the QC checklist ("every named place highlighted on its
  beat", "≤ 2 highlight colours per shot except zones", "every claim has a visual; every visual is said"),
  (7) the span table for framings (world 300–360°, continent 90–150°, country 12–20°, city 0.4–1°). Each of
  these is a generic technique we would implement in our own engine, in our own code, recorded with its reason
  in LESSONS/VARIETY as usual.
- Natural Earth + world-atlas data it bundles are PD/ISC — we already use the same sources.

## 4. Recommendation

1. Build the story format inside the existing engine (phase 1 above). Do not adopt generative video and do not
   copy the Kaz code. The quality bar — multiple eased camera moves, real satellite relief, highlights on cue
   words, SFX, keyword captions, disputed borders labelled — is reachable with what we own.
2. Run it as a fifth feed topic ("Geo Stories") with its own variety axis, brief, and gates, scheduled by the
   same stats loop; first 3 episodes as backlog for review before any scheduling.
3. Terrain tilt only after phase 1 ships and the first stats come back; option (a) first.

Open decisions for the owner: series name and cover style for stories (no options/timer on the cover; a title
line + place), target length (45–50 s vs 60 s), and whether stories also go to X/Threads or YouTube/IG/FB only.
