# Creative brief — written BEFORE the spec, committed as `series/<series>/<ep>/brief.md`

Owner rule (2026-10-19): every short's explanation is thought out on its own, like a human maker would. The brief is the
thinking; `reelkit/shapelint.py` (quizlint Q19/Q20) refuses an episode without one, and refuses an explanation whose shape
copies another episode of the series or is "three identical fact cards".

```markdown
# <question>

## Hook fact
The single most surprising thing, one line. If this doesn't make you say "wait, what?", find another fact.

## Show it
How the hook fact is SHOWN, not said (counter rolling, comparison blocks, route tracing, wrong flags falling away,
a globe spin, a camera flyover, a mascot reaction). Name the device and what the viewer sees.

## Beat order
Beat 1 → beat 2 → beat 3 (2–5 beats). Why this order: escalation, contrast, payoff. Each beat = one idea.

## Media
The real thing. Name the Commons file(s) (`python3 reelkit/photos.py find "..."` lists CC0/PD/CC BY candidates), what the
viewer sees in it, where it enters (rises out of the country · slides in · pops) and WHY this image beats a sticker here —
or one sentence on why this Short is stronger with no photo. CC BY-SA / NC / ND files are refused by provenance.

## Different from
One sentence: how this explanation differs in SHAPE from the last episodes of this series (not just in topic).

## Swipe test
8 s: what is moving, why they stay.  15 s: …  22 s: …  (use the real timeline after preflight)

## Devices
List the devices used (card, sticker, counter, bars, compare, pin, label, route, erase, spin, flash, character).
```
Devices available today: `engine/charts.py` counter / bars / compare / callouts / strip, `engine/geo.py` cam_to / spin /
route_draw / highlight_in / highlight_out / pulse / pin / label / disputed / fade, `engine/quiz.py` fact cards, stickers,
flag-ball characters with faces, `engine/fx.py` flash. In a spec, a story beat is
`{"vo": {...}, "cam": [...], "card"?: {...}, "sticker"?: {...}, "elements"?: [chart elements], "devices"?: [engine beats with "at": "@+1.2"]}`.

## M2 devices (2026-10-20)
- **travel** — a sticker/character rides along a route while it draws: element `{"id":"runner","type":"sticker","emoji":"1f3c3",...}` + beat `{"at":"@@cue","do":"geo.travel","until":"@.end","args":{"rid":"course","layer":"line","sid":"runner"}}` (pair with `geo.route_draw` on the same span).
- **split** — then-vs-now stacked panels (THEN top, NOW bottom, left column): element `{"id":"tn","type":"split","left":{"kicker":"169 cm","text":"born 1896"},"right":{"kicker":"182.5 cm","text":"born 1996"},"label_left":"THEN","label_right":"NOW"}` + `{"at":"@+0.3","do":"chart.split_in","id":"tn"}` + `hide`.
- **erase** — a plate with one word wipes away to reveal the map underneath: element `{"id":"myth","type":"erase","text":"BACTERIA?"}` + `{"at":"@+0.2","do":"chart.erase_run","id":"myth","until":"@+1.4","args":{"direction":"left"}}`.

## P2 devices (2026-10-21)
- **photo** — `"photo": {"id":"ph1","commons":"File:X.jpg","caption":"…","x":60,"y":430,"w":620,"h":430,"from":"up|left|right|pop","at":0.5}` on a story beat; fetched + licensed at build time by `reelkit/photos.py`, credit burned into the frame, slow push inside the frame.
- **rise** — `"from":"rise","fid":"NLD"` makes the photo (or any element via `geo.rise` args fid/eid) pop up OUT of the country's shape like a pop-up book. Owner's suggestion 2026-10-21.

## P3 — pace is measured, not promised (2026-10-21)
The quiz part (question · options with flags/symbols · timer · reveal) is fixed. The explanation is gated by `reelkit/pacelint.py` (Q23)
on the resolved timeline: ≥ 15 visual events / 10 s, no span > 2.5 s without motion, at least one real visual (photo, chart, route,
rise, split…), and every sentence with ≥ 2 moves. The gate prints the dead timestamps — fix that sentence with a move that
belongs to it (a cue-timed `devices` line: `"at": "@@word"`), never with filler.
