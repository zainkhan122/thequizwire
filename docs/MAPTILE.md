# MAPTILE.md — cinematic basemap flyovers with the VersaTiles map animator (`clips.json` engine `maptile`)

Status (Phase 1, 2026-10-14): **wired, not yet exercised.** The sandbox has no docker; the first `selftest` workflow run on GitHub
Actions pulls the image and prints its `--help` — read that output, then fix the `args` convention below if the CLI differs.
Nothing in an episode depends on this until a `maptile` clip is declared.

## What it is
`ghcr.io/versatiles-org/versatiles-map-animator:latest` (MIT, linux/amd64) renders a camera path over VersaTiles' public tile
server (`https://tiles.versatiles.org`, no key) to an mp4. Data: OpenStreetMap (ODbL), Sentinel-2 cloudless mosaic (CC BY 4.0),
NASA Blue Marble (PD), Copernicus GLO-30 hillshade (Copernicus licence). Required credit, enforced by `geolint` P6 whenever a
maptile clip ships: **© OpenStreetMap contributors · VersaTiles · Contains modified Copernicus Sentinel data**.

## Declaring a clip
The trajectory is authored in the web editor (<https://versatiles.org/versatiles-map-animator/>): drop keyframes
(lng, lat, zoom, pitch, bearing, roll; stops/waypoints, holds, ease-in/out), pick style `colorful`/`satellite`, a theme
(`natural-dark` suits the house palette), projection `mercator`/`globe`, terrain/sky, markers, and **aspect ratio `9:16`**.
*Share by URL* encodes the whole animation into the URL hash (`V2` codec); *Export video…* shows the docker command.
Paste the payload into `clips.json`:
```json
{"id": "hero_fly", "engine": "maptile", "scene": "s04", "seconds": 6,
 "args": ["--hash", "<URL-hash payload from Share by URL>", "--quality", "high", "--motion-blur", "2"],
 "note": "args = trajectory + taste flags; clips.py manages --width (1280) --fps (30) --output and adds --preset medium"}
```
- `reelkit/clips.py lint` requires `args` with `--hash` or `--url`, `scene`, `seconds ≤ 8` (plan §1.3: a flyover is a hero
  beat, not wallpaper) and rejects managed flags (`--output --width --height --fps --format`) inside `args`.
- Width: the renderer accepts only 640 / 1280 / 1920 / 3840; a requested 1080 is snapped up to **1280** and the height
  follows the animation's aspect ratio (9:16 → 1280×2276). compose.py scales the clip to the 1080-px stage.
- `clips.py gen` runs only on CI (`GITHUB_ACTIONS=1`) or with `MAPTILE_LOCAL=1`; locally it prints "deferred to CI".
- Cache key = the full call spec (image, args, width, fps, seconds) → a clip is rendered once, then restored from the
  `cache-clips` release like every other clip (`reelkit/clipcache.py`).
- Provenance is written automatically: kind `clip`, licence `ODbL-1.0`, provider/source/credit/`screen_credit` filled; the HF
  composition shows the credit line in the caption-safe credit slot (compose.py `credits`).
- Export/import JSON (schema v1) is for archival: keep the exported `.json` next to `clips.json` as `clips/<id>.animation.json`
  so the trajectory stays readable even though the renderer only takes the hash/URL.

## CLI (verified on the private-repo runner, selftest #11, 2026-10-14)
`ghcr.io/versatiles-org/versatiles-map-animator:latest` pulls anonymously (linux/amd64) and prints:
```
Usage: render.mjs [options]
  --hash <code>          URL-hash payload from the editor (alternative to --url)
  --url <full-url>       full /view URL (the renderer extracts #kf=...)
  --site-root <dir>      static-files root to serve (default: /app/site or ./build)
  --site-url <url>       skip the built-in static server and use this base URL instead
  --width <n>            video width — one of 640, 1280, 1920, 3840 (default 1280)
  --height <n>           video height (default: from the animation's aspect ratio)
  --fps <n>              frame rate (default 30)
  --format <name>        mp4 (default) | prores (.mov) | ffv1 (.mkv) | animation (.mov)
  --quality <level>      mp4: high (CRF 15), standard (CRF 18), small (CRF 24); default standard
  --crf <n>              mp4: exact x264 CRF instead of --quality
  --preset <name>        mp4: x264 preset (default "slow")        ← clips.py adds `medium` unless set (2-vCPU runner)
  --frame-timeout <ms>   per-frame settle timeout (default 30000)
  --motion-blur <n>      N sub-frames per output frame, averaged (1 = off, 4–8 typical; render time scales N×)
  --shutter-angle <deg>  for motion blur (default 180)
  --gpu                  GPU drawing (needs --gpus/--device on docker; no effect on GitHub runners)
  --no-prewarm           skip the initial trajectory walk that pre-fills the tile cache
  --output <path>        output file (required); extension must match the format
  --progress-json        progress as JSON lines on stdout
  -v, --verbose          ffmpeg output and page console messages
```
There is **no JSON-file input**: the trajectory travels as the hash/URL. Render time per clip is not yet measured on the
2-vCPU runner (Phase 2 measures the first real clip; expect minutes, not seconds — prewarm + per-frame settle).

## First-run checklist (remaining, Phase 2)
1. Author a 4–6 s portrait flyover in the editor, *Share by URL*, paste `--hash` into `series/<ep>/clips.json`.
2. `python3 reelkit/clips.py lint <ep>` locally; then `cloud.py render <ep> --wait` (or the selftest workflow with a test
   clip in `series/_template/clips.json`) and review the snaps + `clips/<id>.mp4`; note the stage time in OPERATING_MODEL §3.
3. Pin the image: record `docker inspect --format '{{index .RepoDigests 0}}'` in `clips.json` as `docker_image` so renders
   stay reproducible when `:latest` moves.

## Limits
- One clip per scene, ≤ 8 s; cache everything; no bulk pre-rendering (tile-server etiquette).
- Motion blur multiplies render time (N×); on 2 vCPU keep it at 1–2.
- Disputed borders: the OSM style draws de-facto lines. A maptile clip over a registry region still needs the `geo.json`
  `disputed` plates on top (geolint P4 applies to the scene, not the engine) — the Geo stage can overlay the animator clip.
