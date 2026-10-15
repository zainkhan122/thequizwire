# DATA_SOURCES.md — where every number, shape and pixel is allowed to come from

Rule: a fact enters a video only through `research.json` (≥ 2 independent publishers; core answers need a primary or scholarly
source). A visual enters only through `media.json` with a licence on the allow-list (`reelkit/provenance.py`: PD, PD-USGov, CC0,
CC BY 3.0/4.0, OFL, Apache-2.0, ISC, MIT, BSD-3, ODbL (attribution-only use), Copernicus, own/own-ai/own-tts). Share-alike (except
ODbL maps), NC, ND, "fair use" and unknown are refused. Everything below is free of charge and scriptable.

## Geo Blitz (`geo-blitz`) — maps
| data | what for | licence / credit | how |
|---|---|---|---|
| Natural Earth 1:110m / 1:50m / 1:10m via world-atlas 2.0.2 (TopoJSON) | land, countries, borders | public domain; credit "Natural Earth" (geolint P6) | `reelkit/geodata.py fetch`; ids = 3-char zero-padded ISO numeric (`"586"` Pakistan); Bahrain only at 50m/10m |
| Natural Earth 10m admin-0 disputed areas + disputed boundary lines | dashed disputed polygons/lines, policy plates | public domain | `geodata.py disputed <name>` → `geo.json.disputed[].ne_name` |
| Wikidata (SPARQL, P625 coordinates, P2046 area, P2044 elevation, P1082 population) | pin coordinates, numbers | CC0 | `geolint --online` checks every pin `qid` within 25 km |
| CIA World Factbook (`factbook.json` mirror) | areas, highest points, disputes text | PD-USGov | cite as `primary` in research.json |
| GeoNames | place names, populations | CC BY 4.0 | credit in POST_KIT if quoted |
| VersaTiles (OSM vector, Sentinel-2 mosaic, Blue Marble, Copernicus DEM hillshade) | cinematic flyovers via `maptile` clips | ODbL / CC BY 4.0 / Copernicus → "© OpenStreetMap contributors · VersaTiles · Contains modified Copernicus Sentinel data" | `clips.json` engine `maptile` (CI docker; docs/MAPTILE.md) |
| NASA GIBS / Blue Marble NG | raster globe (Phase 2) | public domain, credit NASA | deferred |
| USGS PP 1395 (Snyder) | projection honesty wording | PD-USGov | framing claims |

Projection policy (geolint P1): size comparisons → equal-area (`equalEarth`, `conicEqualArea`, `azimuthalEqualArea`); distance
claims → scale bar at the claim's latitude (P2); never Mercator for a size claim; `projection_reason` required per scene.

## Body & Brain (`body-brain`) — anatomy, physiology, neuroscience
| data | licence | notes |
|---|---|---|
| Gray's Anatomy 1918 plates (Bartleby / Wikimedia Commons) | public domain | plates for call-outs; name the plate number in media.json |
| NIH / NLM (MedlinePlus, NCBI Bookshelf, StatPearls summaries), NIH NINDS brain basics | PD-USGov / CC BY (StatPearls CC BY-NC-ND is REFUSED as a visual, fine as a *source*) | primary tier for numbers |
| WHO fact sheets, CDC | © WHO (quote facts, don't reuse graphics) / PD-USGov | reference/primary |
| Open textbooks: OpenStax Anatomy & Physiology 2e | CC BY 4.0 | figures reusable with credit |
| Allen Brain Atlas, Human Protein Atlas | CC BY 4.0 (check per asset) | imagery |
Engines: `callouts` (lines + plates over a PD plate), `counter` (counted number), `bars`.

## Sports Sprint (`sports-sprint`) — records, rules, venues
| data | licence | notes |
|---|---|---|
| World Athletics, FIFA, IOC/Olympics.com, ICC, FIBA record pages | © — cite as reference, never scrape graphics | numbers only |
| Wikidata sports properties (P1346 winner, P1132 participants, P2048 height, P1350 games played) | CC0 | bar races |
| Olympedia | CC BY-SA text (do NOT quote verbatim; use numbers → own charts) | reference |
| Procedural pitch/court/track diagrams (`engine/charts.py`) | own | rule explainers |
| Venue maps → Geo engine (Natural Earth + Wikidata P625) | PD / CC0 | "where is it" questions |
Engines: `bars`, `compare`, `strip` (timeline), `geo`.

## Wild Files (`wild-files`) — animals
| data | licence | notes |
|---|---|---|
| GBIF occurrence downloads (DOI per download) | CC0 / CC BY 4.0 per dataset — the download DOI is the citation | range maps (hex-binned, not raw points) |
| IUCN Red List status text | © IUCN — cite status, no map reuse | reference |
| Encyclopedia of Life, Animal Diversity Web (U. Michigan) | CC BY / CC BY-NC-SA (text as *source* only) | numbers |
| Wikimedia Commons CC0/CC BY photos (species) | per file; `screen_credit` mandatory | stills with Ken Burns |
| Scale silhouettes: PhyloPic (CC0 subset only) | CC0 | `compare` engine |
Engines: `compare`, `bars`, `geo` (range).


## Voice, music, fonts, code
- Voice: Kokoro-82M `am_michael` (Apache-2.0 model; takes are `own-tts`; AI voice is disclosed in every description).
- Music/SFX: procedural (`reelkit/synth.py` via `reelkit/quizscore.py`) — no library tracks, nothing to clear.
- Fonts: Anton, Oswald (OFL-1.1, `fonts/LICENSES.md`).
- Code shipped in the video: GSAP (Standard "No Charge"), d3-geo / d3-array / topojson-client (ISC), `engine/*` (own) — `engine/vendor/LICENSES.md`.
