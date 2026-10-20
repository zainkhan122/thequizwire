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
- **split** — then-vs-now panels: element `{"id":"tn","type":"split","left":{"kicker":"169 cm","text":"born 1896"},"right":{"kicker":"182.5 cm","text":"born 1996"},"label_left":"THEN","label_right":"NOW"}` + `{"at":"@+0.3","do":"chart.split_in","id":"tn"}` + `hide`.
- **erase** — a plate with one word wipes away to reveal the map underneath: element `{"id":"myth","type":"erase","text":"BACTERIA?"}` + `{"at":"@+0.2","do":"chart.erase_run","id":"myth","until":"@+1.4","args":{"direction":"left"}}`.
