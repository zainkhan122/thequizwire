# series/_template_v3 — the v3 "satellite quiz" fixture (docs/V3_LOOK.md)

Geo Blitz #13 (Southern Alps) re-authored in the v3 look: NASA Blue Marble under a Mercator scene, hook camera **off the answer**
(Australia, k 0.34 over the coarse `far` raster), Lilita One 100-px question, three flag pills, timer ring, flag-lifted New Zealand,
yellow answer banner, flag-ball character, Twemoji stickers, 84-px Anton fact captions, tease + subscribe, loop to the hook.

`tools/new_episode.py` copies this folder (default format since 2026-10-15). `tests/selftest.py` composes it offline
(`BASEMAP_OFFLINE=1` swaps the tiles for flat placeholders; the real tiles are fetched in the `geo` stage on the runner).

Authoring checklist (every v3 episode):
1. `episode.json` — `format: quiz-v3`, `option_meta` flags/emoji, `banner` ≤ 16 chars, question ≤ 72 chars with a `keyword`.
2. `geo.json` — `projection: mercator`, `basemap {layer, k_max, far{bbox,k_min}}`, highlight `lift: flag|fill`, labels inside y 700–1180
   at every camera they are visible at, no `scalebar`.
3. `visuals.json` — stage `box [0,0,1080,1920]`, `anchor [540,900]`; hook cams outside the fit bbox or k ≤ 0.5 (quizlint Q14);
   `banner_in` ≈ reveal+1.3, `banner_out` ≤ first story beat; one sticker/character per see-it beat; facts kicker ≤ 16, kicker+text ≤ 46.
4. Local sheet BEFORE any dispatch: `ESTIMATE=1 bash reelkit/episode.sh <ep> geo build static check layout textqa`, then
   `hyperframes snapshot --at <times> -o /tmp/snap` and look at the frames.
