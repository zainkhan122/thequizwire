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
```json
{"id": "hero_fly", "engine": "maptile", "scene": "s04", "seconds": 6, "fps": 15,
 "args": ["--style", "colorful", "--from", "73.05,33.69,9", "--to", "73.05,33.69,12", "--duration", "6"],
 "note": "args are passed verbatim to the animator; width/height/fps/output are appended by clips.py"}
```
- `reelkit/clips.py lint` requires `args`, `scene`, `seconds ≤ 8` (plan §1.3: a flyover is a hero beat, not wallpaper).
- `clips.py gen` runs only on CI (`GITHUB_ACTIONS=1`) or with `MAPTILE_LOCAL=1`; locally it prints "deferred to CI".
- Cache key = the full call spec (image, args, size, fps, seconds) → a clip is rendered once, then restored from the `cache-clips`
  release like every other clip (`reelkit/clipcache.py`).
- Provenance is written automatically: kind `clip`, licence `ODbL-1.0`, provider/source/credit/`screen_credit` filled; the HF
  composition shows the credit line in the caption-safe credit slot (compose.py `credits`).

## First-run checklist (do this once, on CI)
1. Actions → `selftest` → Run. Open the "Map animator image pulls" step; copy the `--help` text into this file under *CLI (verified)*.
2. If flag names differ (`--output`, `--width`, `--height`, `--fps` are the only ones clips.py adds), adjust `gen_maptile` in
   `reelkit/clips.py` — one place.
3. Declare a 4-second test clip in `series/_template/clips.json`, run `python3 reelkit/cloud.py render series/_template --wait`
   (or the selftest workflow with `MAPTILE_LOCAL` unset) and review `~/.cache/build/_template/snaps` + `clips/hero_fly.mp4`.
4. Record the verified image digest (`docker inspect --format '{{index .RepoDigests 0}}'`) in `clips.json` as `docker_image`
   so renders stay reproducible when `:latest` moves.

## CLI (verified)
_not yet — fill in from the first CI run_

## Limits
- Portrait 1080×1920 at 15 fps keeps a 6 s flyover under ~90 s of runner time; 30 fps doubles it.
- Tile server etiquette: one clip per scene, cache everything; no bulk pre-rendering.
- Disputed borders: the OSM style draws de-facto lines. A maptile clip over a registry region still needs the `geo.json`
  `disputed` plates on top (geolint P4 applies to the scene, not the engine) — the Geo stage can overlay the animator clip.
