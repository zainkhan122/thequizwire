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
- `ep10-nile-basin-countries` — How many countries share the NILE basin? → **11** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
- `ep11-budapest-buda-pest` — Which capital is split into BUDA and PEST? → **Budapest** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
- `ep12-coldest-desert-antarctica` — Which is the COLDEST desert on Earth? → **Antarctica** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
- `ep13-southern-alps-new-zealand` — In which country are the SOUTHERN ALPS? → **New Zealand** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
- `ep14-most-time-zones-france` — Which country has the MOST time zones? → **France** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
