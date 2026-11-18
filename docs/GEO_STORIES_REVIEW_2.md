# Geo Stories — review round 2 (owner's 5 points on *The navy with no sea*)

Rendered **locally in the sandbox** (new `reelkit/local_render.py`: headless Chromium drives the same GSAP timeline frame by frame,
imageio-ffmpeg encodes, ≈ 3–7 min per episode). CI run `geo-stories-review-9` dispatched only as confirmation.

| # | Owner note | What was actually wrong | Fix |
|---|---|---|---|
| 1 | Border needs to be animated | Country fills just faded in. Worse: every "draw-on" (routes too) **popped** instead of drawing — the SVG paths used `pathLength="1"` and GSAP rounds the px dash-offset to whole numbers, so 1→0 jumped in one frame. | `pathLength="1000"` (engine/geo-runtime.js + geo.py). Each highlighted layer now gets an `edge_<layer>` outline that a yellow pen traces over 1.5 s, the fill follows 0.7 s later, the pen fades. Bolivia at 0.6 s, Chile at 10.7 s. |
| 2 | Ships rise where they are | Only a flag sticker, which popped/spun in. | New `sticker_in(frm="rise")`: grows from its own baseline, in place (flag at 19.4 s). Plus a ship that **rises out of Lake Titicaca** via `geo.rise` on the lake polygon (32.3 s), pulses on "Andes", leaves before the counter. |
| 3 | Kinetic text / TTS overlap | Captions said different words from the narration at the same moment ("400 km of coast" while VO said "a long desert coast"; "Día del Mar" while VO said "Day of the Sea"; "Lake Titicaca" on cue *andes*; "1879 · War of the Pacific" on *north*). Captions also stayed up through the whole scene. | Every caption now echoes the words being spoken, timed 0.05–0.15 s **before** its cue word, with an explicit `until` so it leaves before the next idea. The 400 km fact moved to a card after the caption is gone. Same pass on st02/st03 (e.g. st03 "2,688 km" caption duplicated the counter → "farthest from any land"; "spacecraft cemetery" was never spoken → "dead spacecraft fall here"). |
| 4 | Too few camera moves | 1 glide + 2 drifts per beat (≈ 10 moves). | Authored `cam_path` per beat (push on each cue) + a default second push on the last cue for any beat without one → **25 camera moves** in st01, 20+ in st02/st03. |
| 5 | SFX are noise | The story cues used the quiz whoosh/tick/riser: filtered white-noise sweeps (spectral flatness 0.18–0.47, centroid 3–11 kHz) at −11 dB under VO, and the music bed sat only 4.5 dB under the voice. | New tonal palette in `reelkit/synth.py` (`s_pop`, `s_click`, `s_air`, `s_draw`, `s_riser`, `s_hit`, `s_bloop`): sine-based, short, reverb tail, flatness ≈ 0.000, centroids 400–700 Hz; placed only on real events (border trace, pins, route draws, counter, camera moves ≥ 1.25× zoom), 0.45 s minimum spacing. Bed −65 %, deeper duck → **VO 15.4 dB over music**, 11.7 dB over SFX. |

Local outputs (1080×1920, 30 fps, mastered −14 LUFS):
- `review/st01/local/The-navy-with-no-sea-local.mp4` (49.0 s) + `contact16.jpg`
- `review/st02/local/The-land-nobody-wants-local.mp4` (47.6 s) + `contact16.jpg`
- `review/st03/local/The-place-where-the-nearest-people-are-in-space-local.mp4` (49.8 s) + `contact16.jpg`

Known, not yet touched (st02): the compare chart covers the Halayib/Bir Tawil plates for ~5 s; the close line brushes the Halayib plate. Say if you want those moved before the next round.
