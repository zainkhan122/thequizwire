# Can thequizwire make "map-animation Shorts" like these? — capability assessment (2026-10-15)

Reference set supplied by the owner:

| Source | What it is | Size (fetched) |
|---|---|---|
| facebook.com/share/1HQDf5qYYs → **Geo Explains** | "Simple but informative map animation shorts" | 551K followers |
| facebook.com/share/1LxqYcEQWB → **Geo guy** (Karachi) | "Geopolitics videos daily" | 152K |
| facebook.com/share/1daBeFmbLR → **Geo GK** | "best world map-related facts" | 30.8K |
| facebook.com/share/1CHNXsFjrR → **Geography** | map Shorts | 544K |
| youtube.com/@geomapunveiled25 | fact listicles on satellite map + 9–14-min long-form | 46.5K subs, 9.6M views |
| youtube.com/@gyanotrick | "What if X…" scenarios, flag-filled countries + emoji-ball characters, AI voice | 20.7K subs, 21.7M views (recent avg ≈ 700K/video) |
| youtube.com/@histoboi | alternate-history / empire-expansion map animations, countryballs | 8.9K subs, 6.3M views |
| youtube.com/@huhindustry | 3D satellite flyovers (Bing/Earthstar imagery), Urdu voice, Pakistan infra + military | ≥100K subs (Silver button) |

Facebook videos themselves are behind the login wall (HTTP 400/403 to crawlers); page metadata and the
YouTube equivalents (RSS + thumbnails of the top Shorts) were used instead.

## The common recipe (what every one of these videos is built from)

1. Basemap: satellite/terrain (GeoMap, Histoboi, HUH) or flat light map (Gyano).
2. One country/region shape **filled with its flag or a flat colour + glow outline**.
3. Camera: zoom/pan (2D) or 3D flyover (HUH).
4. Overlays: flags, emoji/countryball characters, icons (wheat, trains, missiles), dashed route lines, cut-out photos.
5. Big bold captions, often word-by-word, centred.
6. AI voice (English / Hindi / Urdu) + trending music; 30–60 s; "What if / Why / N countries that…" hook.

## What the system already has vs. needs

| Capability | Status in `thequizwire` (489b18f) |
|---|---|
| Country shapes, highlights, borders, disputed plates, pins, labels, routes, scale bar, camera moves (d3-geo, vector) | ✅ built, runner-proven |
| Satellite / terrain / globe / 3D-buildings flyovers, 9:16, markers (VersaTiles map-animator, `engine:"maptile"`) | ✅ wired + CLI verified; ❗ not yet exercised on a real episode (Phase-2 backlog) |
| Word-level timing of the voice-over (`words.json`, faster-whisper) | ✅ exists (used for sync) — word-by-word caption *renderer* ❌ |
| Flag-filled country shapes + glow outline | ❌ small addition (SVG clipPath + flag SVGs; flag-icons is MIT) |
| Icon / sticker / arrow / cut-out layer | ❌ small addition (OpenMoji CC BY-SA 4.0 or Twemoji CC-BY 4.0; photos only PD/CC from Wikimedia) |
| Emoji-ball / countryball characters with expressions | ❌ needs an own SVG character set (6–8 expressions) + a `character` layer |
| Satellite raster under the vector overlays (GeoMap look) | ❌ VersaTiles satellite tiles as a Mercator background plate (CC BY 4.0 Sentinel-2, 10 m/px) |
| "Explainer / what-if" beat template (no question/options) | ❌ new series template + relaxed quizlint/planlint path |
| Historical borders + expanding-empire animation (Histoboi) | ❌ data (public-domain historical GeoJSON, licence to check) + timed polygon-reveal feature |
| English VO (Kokoro `am_michael`) | ✅ |
| Hindi VO (Kokoro `hf_alpha` / `hm_omega`) | ✅ available, untested in pipeline |
| Urdu VO | ❌ Kokoro has none; free options are weak (MMS-TTS is CC-BY-NC, edge-tts is unofficial) |
| Trending music | ❌ by design — procedural score only |
| Military / one-sided dispute framing | ❌ by design — `docs/BORDER_POLICY.md` neutrality; fiction needs an explicit "hypothetical" label |

## Verdict per channel

- **Geo Explains / Geo GK / Geography / GeoMap Unveiled Shorts** (map fact + highlight + captions): **YES** after 3–4 small Phase-2 additions (explainer template, word captions, flag-fill, icon layer, optional satellite plate).
- **HUH Industry** (3D flyovers): **YES for the visuals in English** (maptile clips are exactly this; Sentinel-2 is coarser than Bing aerial at bridge-level zoom, so frame at region/city scale or use OSM 3D buildings); **NO for Urdu VO today**; military framing out of policy, infrastructure/geography framing fine.
- **Gyano Trick** (what-if with characters): **PARTIAL** — visuals doable with an own character set; content is fiction and often provocative — needs a "hypothetical" mode and editorial limits.
- **Histoboi** (alternate history / all territories ever controlled): **LATER** — 2–3 phases of engine + data work plus contested-history fact-check load.

## Estimated Phase-2 work (phases ≤ 15 min each, per `docs/PHASE_PROTOCOL.md`)

| # | Item | Phases |
|---|---|---|
| 2.1 | First real maptile clip on the runner; measure Actions cost; pin image digest | 1 |
| 2.2 | Explainer beat template (hook → 3–5 map beats → payoff → end card) + lint path | 2 |
| 2.3 | Word-by-word captions from `words.json` | 1 |
| 2.4 | Flag-fill + glow highlight layer | 1 |
| 2.5 | Icon/sticker/arrow layer + provenance rules | 1–2 |
| 2.6 | Satellite raster plate under vector scenes | 1–2 |
| 2.7 | Character set + `character` layer (optional) | 1–2 |
| 2.8 | Hindi VO path test (optional); Urdu = open problem | 1 |
| 2.9 | Historical borders + timed reveal (optional, later) | 2–3 |

Cost reference: ≈ 7.5 Actions-min per 45-s episode (runner proof); maptile clips add Docker/Chrome time (to be measured in 2.1).
