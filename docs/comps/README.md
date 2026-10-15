# Design comps (static, Chrome-rendered — not engine output)

`v3_satellite_comp.html` (A) and `v3_gyano_comp.html` (B) are the two candidate looks shown to the owner on 2026-10-15
(`docs/img/v3_vs_gyano.png`). They need local assets that are not committed (media rule): run in `~/.cache/comp/`
- fonts: `fonts/Anton-Regular.ttf`, `fonts/Oswald.ttf`, Lilita One (OFL, google/fonts `ofl/lilitaone`)
- vendor: `engine/vendor/d3-array.min.js d3-geo.min.js topojson-client.min.js`
- flags: flag-icons `flags/4x3/{nz,ch,cl}.svg` (MIT); stickers: Twemoji `1f3d4.svg 1f914.svg` (CC-BY 4.0)
- basemaps: A = `python3 reelkit/basemap.py 160,-52,180,-30 1080 nz.jpg` and `-30,-40,180,75 1080 world_asia.jpg` (NASA GIBS, PD);
  B = Natural Earth II 50m raster `NE2_50M_SR_W.zip` (PD) cropped at 30 px/° (NZ crop upscaled ×2), saturation ×1.45
- `nz_topo.json` = world-atlas 50m filtered to id 554
Render: Playwright Chromium, `--allow-file-access-from-files`, viewport 1080×1920, `?mode=hook|reveal`.
