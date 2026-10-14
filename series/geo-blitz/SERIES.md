# Geo Blitz (`geo-blitz`)

One geography question answered on a real, honest map.

Numbering: feed #9 → next #10 (`series/series.json` is the counter; `tools/new_episode.py geo-blitz …` bumps it).

## Format rules
- Map stage 0–1180 px: `geo` scene (d3-geo, Natural Earth) or a `maptile` flyover clip (VersaTiles, CI only)
- Size claim → equal-area projection + `projection_reason`; distance claim → scale bar at the claim's latitude
- Any registry region on screen or in the script → dashed disputed polygons + 'Administered by / Claimed by' plates (docs/BORDER_POLICY.md)
- Pins carry a Wikidata `qid`; `geolint --online` verifies them within 25 km in CI
- Credits: 'Map data: Natural Earth' always; OSM/VersaTiles/Copernicus line whenever a maptile clip is used

## Sources
See `docs/DATA_SOURCES.md` (Geo Blitz section). Every fact → `research.json` claim; every file → `media.json`.

## Episodes
_none yet — Phase 2 starts here_
