# PLAN.md — the phased plan this repo executes

> Status (2026-10-14): **Phase 1 built in this repo** — see `RESUME.md` for what exists and `STATE.json` for the machine view.
> Decisions taken by the owner after the plan below was written (they override the plan's "D" table):
> **D1** new repo = this one (`quizwire`, 4 feed topics, not geography only) · **D2** Geo Blitz continues at #10; Body & Brain,
> Sports Sprint, Wild Files are the other three active series (Cosmic Quiz, Time Vault registered, inactive) · **D3** narrator = Kokoro
> `am_michael` · **D4** sensitive borders are SHOWN with controller/claimant plates (`docs/BORDER_POLICY.md`) · **D5** manual publishing.
> No videos are produced until the owner says so ("get the tools and make the system" first).

---

# Geography Shorts for **TheQuizWire** — full production plan (v1 · 2026‑10‑14)

> Written after cloning and reading `zainkhan122/history` (reelkit, engine, workflows, docs, both Paper Trail episodes), scraping the TheQuizWire channel, and cloning + reading all seven suggested tool repos. Everything marked **[tested]** was actually run from this sandbox today; everything else is read from the repos' own code/docs.

---

## 0 · TL;DR

| | |
|---|---|
| **What you have** | A production‑grade Shorts studio (`reelkit` + HyperFrames + GitHub Actions) with 9 quality gates, a clip cache, a media store in Releases, and a sandbox/CI operator model. It already renders **90 s Shorts in ~13 min** on the free 4‑vCPU runner. |
| **What's missing for geography** | A **map engine**. Your only map so far (ep02 Boston→Portland) is schematic: hand‑placed pixels, not projected coordinates. Geography content needs real projections, basemaps, routes, highlights, globes, flyovers — plus geography‑specific fact and provenance rules (projection honesty, border policy, ODbL/CC‑BY credits). |
| **What the channel data says** | TheQuizWire: **121 subs · 510 videos · 162,637 views** (≈320 views/video lifetime, ≈650 median on the last 19). The format is a quiz card over stock footage (4 options + 3‑s countdown). **Geography quizzes are the top performers** (coldest desert 943, largest peninsula 924 vs. 669 median). 510 uploads → 121 subs means the template converts almost nobody; it is also exactly the "template‑based" class YouTube's 2025/26 inauthentic‑content rules target (your own `docs/CONTENT_STRATEGY.md` §0). |
| **Recommendation** | Keep the brand and the quiz hook (question → guess → reveal), but make the **map the star**: a 45–60 s "Geo Blitz 2.0" where the reveal is a real animated map and 25–35 s of original, sourced explanation. Two render engines, both free and already proven headless: **(1) vector maps** (D3‑geo + Natural Earth, inside your existing HyperFrames build — no WebGL, no tiles, deterministic) for 80 % of scenes; **(2) cinematic satellite/terrain flyovers** (VersaTiles map‑animator, Docker, software WebGL) as cached hero clips, exactly the way Wan/archival clips flow today. |
| **Build it in 7 bounded phases** | Each phase = one sandbox session that ends with `tools/sync.sh`; everything heavy runs on Actions. Pilot episode delivered at the end of **Phase 3**; batch of 6 banked by **Phase 6**. |
| **Proof it works** | [tested] `poc_vector_frame.svg/.png`: a full 1080×1920 map frame (241 Natural Earth countries, 7 highlighted, projected pins + great‑circle route) generated in **0.37 s** on this 2‑vCPU sandbox with zero network. [tested] Wikidata SPARQL (facts), VersaTiles tile server (licences), the public `ghcr.io/versatiles-org/versatiles-map-animator` image (pullable anonymously, amd64) — all reachable. |

### Decisions I need from you (everything else is decided below)

| # | Decision | My recommendation |
|---|---|---|
| **D1** | New repo or same repo? | **New public repo `zainkhan122/geography`**, bootstrapped by copying `reelkit/ engine/ tools/ fonts/ .github/` from History (one‑time). Separate channel ⇒ separate Releases, STATE, RESUME, clip cache. Keep a `tools/upstream.sh` that diffs reelkit against History so fixes flow both ways. (Alternative: `series/geo-blitz/` inside History — zero duplication, but one studio for two channels muddles releases and state.) |
| **D2** | Series name/continuity | Keep **"Geo Blitz"** (playlist continuity, numbering continues at #10) but new look; sub‑formats carry their own tags (§2.1). Alternative: launch "Geo Files" as a new playlist. |
| **D3** | Narrator | **Kokoro‑82M on CI** (free, offline, identical voice for 500 episodes, already in `reelkit/tts_kokoro.py`). Arena TTS is better at emotion but voice IDs don't survive sessions (your RESUME notes this). Phase 1 renders 3 Kokoro candidates for you to pick. |
| **D4** | Border policy for sensitive regions (Kashmir, Taiwan, Crimea, Western Sahara, Arunachal) | Natural Earth **"de facto" set** + dashed "disputed/line of control" styling + neutral wording; logged once in `SERIES.md`; episodes touching these get a `caveat` claim. Needed before ep01 because every world map shows them. |
| **D5** | Publishing | Manual via YouTube Studio for the first 10 (POST_KIT.md gives you everything to paste). `publish.py` (YouTube Data API: private upload + scheduled publish) only when you say so — same rule as History. |

---

## 1 · What I analysed

### 1.1 The channel (scraped 2026‑10‑14)

- Handle `@thequizwire-com`, joined 2023‑12‑14, links to thequizwire.com, Instagram, Facebook, Threads, WhatsApp channel.
- **Cadence:** 4–5 Shorts/day across series: Geo Blitz (#9), Wild Files (#6), Sports Sprint (#8), Body & Brain (#3), Cosmic Quiz (#4), Time Vault (#4), plus "Trend:" one‑offs. Descriptions are identical boilerplate (“What was your first guess? … Learn daily with thequizwire.com … #GKshorts #usagk #1min”).
- **Format (from the `oar2` frame of Geo Blitz #8):** stock sunset‑road video → "TheQuizWire" header → yellow "Geo Blitz #8" plate → MEDIUM badge → question → 4 options → progress bar → countdown "3". Pure card template, no map, no motion that relates to the topic.
- **Numbers:** last 19 Shorts: median 669, max 975, mean 657. Geography: 943 / 924 / 669 / 421. Lifetime average ≈ 319/video.
- **Reading:** the audience signal (geography + space + body facts) is good; the *delivery* is the ceiling. Nothing in the format gives a reason to subscribe or to watch past the reveal. Your History repo already encodes the fix (research‑led, motion‑led, format rotation); this plan ports it to geography.

### 1.2 Your existing system — reuse map

Everything below is reused **unchanged** unless marked.

| Layer | File(s) | Status for geography |
|---|---|---|
| Operator model (sandbox = brain, Actions = muscle, Releases = media) | `AGENTS.md`, `RESUME.md`, `STATE.json`, `tools/sync.sh`, `tools/state.py`, `bootstrap.sh` | Reuse; rewrite the prose for the new repo |
| Episode pipeline (18 stages) | `reelkit/episode.sh` | Reuse; **add stages `tts` (Kokoro, CI) and `geo` (map data prep)** |
| Cloud render → Release | `.github/workflows/render.yml`, `reelkit/cloud.py`, `media.py`, `naming.py` | Reuse; **add a Docker step for map clips** |
| Hygiene CI | `check.yml`, `tools/repo_guard.py` | Reuse; add `geolint` |
| Composition engine | HyperFrames + GSAP, `engine/fx.py` (plates, root‑level videos, film inserts, leaks, flashes) | Reuse; **add `engine/geo.py`** (same Python→HTML/GSAP string style) |
| Clips & cache | `clips.py` (engines `wan`,`wan14`,`ltx25`,`url`), `clipcache.py`, `find.py` | Reuse; **add engines `maptile` and `globe`** |
| Voice | `voice.py` (plan, sample gate, words, check, shape), `tts_kokoro.py`, `trim_vo.py` | Reuse as is |
| Score | `synth.py` (seeded procedural music/SFX), per‑episode `score.py` | Reuse; new palette of cues (sonar ping, wind, compass click) |
| Gates | `factcheck.py`, `provenance.py`, `planlint.py`, `hfcheck.py`, `textqa.py`, `qa.py`, `decisions.jsonl` | Reuse; **extend**: provenance allow‑list += `ODbL`, `CC-BY-4.0-data`; planlint motion weights += `map` (0.75) & `maptile` (1.0); new `geolint.py` |
| Research protocol | `research.json` claims ledger, 2‑source rule, guardrails | Reuse; **add `geofacts.py`** (Wikidata + CIA Factbook → draft claims with references) |
| Fonts | Anton, Oswald, DM Serif, Special Elite, Noto Nastaliq | Reuse (new palette differentiates the brand) |

What does **not** transfer: the collage art direction (Paper Trail look), the Wan "paper diorama" prompt template (geography rarely needs AI video — the map *is* the motion), and the History‑specific niche docs.

### 1.3 Tool‑by‑tool verdicts

| Tool | Licence | What it really is (from the code) | Headless on CI? | Verdict for us |
|---|---|---|---|---|
| **iart‑ai/map‑animation‑skills** | MIT | **No code** — a 13 KB `SKILL.md` + two cookbooks (Earth Studio→After Effects; D3/Remotion vector maps) + 3 shell helpers (contact sheet, probe mp4). Its value is doctrine: one projection shared by basemap/pins/routes/labels; a single `beats[]` array drives camera, pins, routes, labels and duration; **12 fps stutter on the graphic layer only**; great‑circle routes via `geoInterpolate`; focus+context highlights; verify by rendering stills before encoding. | n/a | **Adopt the doctrine verbatim into `engine/geo.py`** (GSAP `steps()` ease gives the 12 fps stutter; `beats` becomes `geo.json`). Skip Earth Studio/AE (manual, browser, not scriptable) and Remotion (HyperFrames already fills that slot). |
| **open330/travelback** | MIT | Next.js 16 + React 19 + MapLibre GL 6 + WebCodecs (mediabunny). GPX/KML/Google‑Timeline parsers; 6 camera modes (`src/lib/camera.ts`: overview/flyover/orbit/ground‑follow/closeup/bird's‑eye with look‑ahead bearing, smoothstep); export is **browser‑side WebCodecs**. The 5 "map styles" shipped are background‑colour‑only (no tile sources: "local‑only"). | No (WebCodecs/UI) | **Borrow the math, not the app**: port the camera‑mode formulas and the GPX/KML parser into our keyframe generator for VersaTiles (Phase 4/7). |
| **gpx‑animator/gpx‑animator** | Apache‑2.0 | Java (Gradle, 81 classes); CLI + Swing GUI; top‑down track animation over raster XYZ tiles (`--tms-url-template`). | Yes (Java 21 is on ubuntu runners) | **Optional, low priority.** Its weak point is the basemap: OSM's public tile servers forbid this kind of bulk use and most free raster alternatives are CC‑BY‑SA. Our own D3 route draw‑on or a VersaTiles flyover covers the "journey" format better and licence‑clean. |
| **versatiles‑org/versatiles‑map‑animation** (actual name: *map‑animator*) | MIT | Far more than a prototype: SvelteKit editor + **headless renderer** (`render/render.mjs`: Playwright + chromium‑headless‑shell + SwiftShader software WebGL → PNG frames → ffmpeg). Seeks the map to each frame time and waits for settle (deterministic). JSON schema v1: keyframes (lng/lat/zoom/pitch/bearing/roll, hold, waypoint, arc/linear path, per‑stop ease), annotations (pin/arrow/circle/star/icon + label, fade in/out windows), styles `colorful` (24 themes) or `satellite`, **globe projection, 3D terrain, sky, sun, 9:16 aspect**, motion blur. Published Docker image `ghcr.io/versatiles-org/versatiles-map-animator:latest` **[tested: public, amd64]**. Tiles from `tiles.versatiles.org` **[tested reachable]**: OSM (ODbL), Sentinel‑2 mosaic (CC BY 4.0), NASA Blue Marble (PD), Copernicus DEM, Mapterhorn (CC BY 4.0). Speed (their numbers): ≈1.1 s draw + 0.34 s capture per 1920×1080 frame in software. | **Yes — this is its purpose** | **Adopt as the cinematic engine** (`clips.py` engine `maptile`). Budget: 1080×1920 ≈ same pixels as 1080p ⇒ ~1.5–3 s/frame on the runner ⇒ a 6 s hero clip at 30 fps ≈ 5–9 min, cached forever by content hash. Render at 15 fps and let the existing `clips.py prep` motion‑interpolate to 30 to halve it. Needs a tiny hash encoder (their `src/lib/url_state/*.ts`, MIT) because the image takes `--hash`, not JSON. |
| **aourednik/historical‑basemaps** | **GPL‑3.0** | 55 world GeoJSON snapshots (123,000 BC → 2010), 73 MB; fields NAME / SUBJECTO / PARTOF / **BORDERPRECISION** (1–3); `places.geojson`; `index.json` listing countries per year. Author says "work in progress… verify before academic use". | Data only | **Use only for history‑crossover episodes** ("how this border moved"), with on‑screen "approximate borders" + credit + a `decisions.jsonl` entry, because GPL is outside your provenance allow‑list. Natural Earth (PD) covers all modern geography. |
| **GeoHaberC/Story‑to‑Video** | none stated | Two Python files: OpenAI images + gTTS + ffmpeg slideshow. | n/a | **Nothing to adopt** — a paid‑API slideshow is the style the 2026 policy penalises and reelkit already exceeds it. |
| **gyoridavid/short‑video‑maker** | MIT | Kokoro‑js + whisper.cpp + Pexels stock + Remotion, Express/MCP server, needs 3–4 GB RAM. | Docker | **Nothing new vs reelkit** (you already run Kokoro + faster‑whisper + HyperFrames). Its stock‑footage output is the template look to avoid. Maybe copy its MCP/REST pattern much later. |
| **GEOlayers / After Effects** (mentioned in your brief) | commercial | — | No | Out of scope (paid, GUI). Our vector engine reproduces its editorial look. |

**Free tools I'm adding that weren't on your list** (all verified today or in your own docs):

| Tool | Licence | Role |
|---|---|---|
| `d3-geo`, `topojson-client`, `world-atlas` (npm) **[tested]** | ISC/BSD code; Natural Earth data **public domain** | Vector basemap + projections in the HyperFrames build (110m / 50m / 10m) |
| Natural Earth 10m cultural/physical (direct) | PD | Admin‑1 states, rivers, lakes, places, bathymetry, disputed areas, de‑facto variants |
| `mapshaper` (npm, MIT) | MIT | Clip/simplify/dissolve in CI so each scene ships ≤ 300 KB of paths |
| Wikidata SPARQL **[tested]** | CC0 | Structured facts with references (area, population + point‑in‑time, capital, highest point, coordinates, borders) |
| `factbook/factbook.json` (GitHub) | PD (CIA World Factbook) | Independent second source for country facts (auto‑diff vs Wikidata) |
| GeoNames | CC BY 4.0 | Place coordinates, alternate names, elevation |
| NASA Blue Marble NG / Black Marble 2016 / Visible Earth topo‑bathy | PD | Globe textures for the numpy `globe` engine; night‑lights hero shots |
| NASA GIBS / Worldview snapshots | PD (NASA) | Dated satellite imagery (storms, dust, ice) as credited inserts via existing `url` clips |
| GEBCO 2024 grid / NOAA ETOPO 2022 | free with attribution / PD | Ocean‑floor and relief shots |
| Köppen‑Geiger (Beck et al. 2018) | CC BY 4.0 | Climate‑zone episodes |
| GHSL / WorldPop | CC BY 4.0 | Population density surfaces |
| Overpass API (OSM) | ODbL | Micro‑features Natural Earth lacks (Baarle enclaves, Madha/Nahwa, tripoints) |
| Our World in Data / World Bank API | CC BY 4.0 | Data‑story overlays (already in your NICHE_RESEARCH) |
| Java 21, Docker, Node 22 | — | Already on `ubuntu-latest` runners |

### 1.4 Feasibility tests run in this session

1. **Vector frame [tested]** — `poc/geo_poc.mjs` → `poc_vector_frame.svg` (+ PNG preview): Mercator, 50m countries, 7 highlighted, 3 projected pins, great‑circle route, title plate on its own plate, credit strip in the safe zone. 0.37 s. (Title overflows in the PNG only because cairosvg lacks Anton; `textqa` would catch that in production.) Lesson: whole‑world 50m paths are 2.2 MB — production clips to the viewport and simplifies (mapshaper) ⇒ 50–300 KB per scene.
2. **Facts [tested]** — Wikidata SPARQL returned the six largest countries with area, population, capital in 0.9 s. Note Canada's population came back as a 2017 value: Wikidata is a *pointer* to sources, never the source — the 2‑source rule stays and `geofacts.py` must prefer the latest `point in time` qualifier and diff against the Factbook.
3. **Tiles & licences [tested]** — `tiles.versatiles.org/tiles/{osm,satellite,hillshade-vectors}/tiles.json` all answer; versatiles.org/sources lists every input and licence (OSM ODbL, Sentinel‑2 CC BY 4.0, Blue Marble PD, Copernicus DEM, Mapterhorn CC BY 4.0).
4. **Renderer image [tested]** — ghcr manifest for `versatiles-map-animator:latest` is public (linux/amd64 + arm64); `-gpu` variants exist (irrelevant on Actions).
5. **Sandbox limits (re‑confirmed)** — 2 vCPU, ~2 GB RAM, no ffmpeg, Node 20. All geodata processing, TTS, map‑clip rendering and video work stay in CI, as in History.

---

## 2 · The product

### 2.1 Format: "Geo Blitz 2.0" — a quiz that turns into a map story

**Promise:** one geography question, answered *on a real map*, with one fact you didn't know — in 45–60 s. (Shorts ≤ 60 s loop best; your Paper Trail runs 88 s because it's narrative; quizzes should be tighter.)

Skeleton (seconds are targets; `plan.py` derives real timings from the VO words):

| t | Beat | On screen | Engine |
|---|---|---|---|
| 0–3 | **Cold open on the map, not on a card.** Camera already moving. Question spoken. | Map zoom begins; question plate slides in (own plate, ≥ 4.5:1) | vector |
| 3–8 | Options A–D drop as pins/labels **in their real places** where possible (e.g. four peninsulas light up) | Options plate; difficulty badge; "Geo Blitz #10" bug | vector |
| 8–11 | Countdown 3‑2‑1 (ring sweep, ticks) — the classic TheQuizWire device, kept | Ring; map keeps drifting (never static) | vector |
| 11–14 | **Reveal:** wrong options dim, right one fills; label pops; one‑line answer | Highlight wipe + stat plate | vector |
| 14–45 | **The story (original research):** 3–4 scenes — scale bar, comparison, route, flyover, globe, archival photo insert | map sequence + 1 hero clip | vector + maptile/globe/url |
| 45–52 | **Kicker** (the fact people repeat) + CTA "What was your first guess? Tell me below" | Kicker plate | vector |
| 52–55 | End card repeats the question so the Short loops | End card | — |

**Four sub‑formats, rotated** (anti‑template rule from your strategy doc — `planlint` already checks cross‑episode fingerprints):
1. **Superlative** — "the largest / highest / only…" (Wikidata‑driven; easy, high demand).
2. **Why is it shaped like that?** — a border or coastline explained (Chile, Caprivi Strip, Gambia, Kaliningrad).
3. **Border oddity** — enclaves, tripoints, quadripoints, towns split by a line (needs OSM micro‑data).
4. **Scale shock** — true‑size comparisons on an **equal‑area** projection, distance stories (Point Nemo, "Africa fits 3 countries") — the format that makes viewers share.

### 2.2 Visual system (new brand, same quality rules)

- **Palette:** deep sea `#0F2A3A`, land `#1D3A4A` / dimmed `#17303D`, highlight sand `#E3A72F`, alert red `#C8102E`, cream type `#EFE6D2`, ink `#141414`. Night‑globe scenes go black/amber. (The PoC frame uses exactly this.)
- **Type:** Anton (headlines), Oswald (labels/options), DM Serif italic (kicker), Special Elite (data stamps / credits). Already in `fonts/`.
- **Map grammar (series rules, enforced by `geolint`):**
  - **Projection honesty:** any claim comparing *area* ("bigger than", "× the size") must sit on an equal‑area projection (Equal Earth / Lambert azimuthal). Mercator is allowed for regional/city scenes only. The projection name is printed in the credit strip.
  - **Distances** come from `d3.geoDistance` (great circle) and a scale bar appears whenever a km figure is on screen.
  - Labels never rotate with the map; labels counter‑scale during zooms; ≤ 3 labels on screen at once.
  - Routes are great‑circle arcs (densified), drawn on with `stroke-dashoffset`, with a travelling dot.
  - Highlights are focus + context (target lit, neighbours visible but dimmed) — never a country floating on black.
  - **12 fps stutter** on pins/labels/route draw (GSAP `ease:"steps(n)"`), camera stays smooth.
  - **Disputed borders** per D4; disputed features carry a dashed stroke and a one‑word tag.
- **Motion promise:** `episode.json` `min_motion` **0.70** with weights `maptile/globe/clip` 1.0, `map` (vector scene with an active camera move) 0.75, `graphic` 0.5, Ken Burns 0.
- **Readability:** unchanged owner rule — every text on its own plate/scrim; `textqa` ≥ 3:1 (target 4.5), dead zones top 230 / bottom 320 / right 120 px.

### 2.3 Audio

- Narrator: D3 (Kokoro, e.g. `am_michael:60,am_adam:40` or `af_heart`), produced in CI, gated by `voice.py` (pace per tone band, pauses, fidelity). Keep the question/answer energy curve: curious → tense (countdown) → bright (reveal) → warm (story) → punchy (kicker).
- Score: `synth.py` arrangement per episode — drifting pad for the map, ticking pulse under the countdown, a "ping" on the reveal, resolution under the kicker. SFX: pin thuds, paper slide, sonar ping, wind for terrain flyovers, projector clatter for archival inserts (exists).
- Loudness −14 LUFS, TP ≤ −1.5 dBTP (existing `qa.py`).

### 2.4 Pilot episode storyboard — **Geo Blitz #10 · "The loneliest point on Earth"** (format 4, Scale shock)

Why this one: it is *map‑native* (nothing to show but geography), uses the globe + great‑circle distances + a space twist, and every number is computable or NASA/NOAA‑sourced. (All figures below go into `research.json` with two sources **before** a word is recorded — the ledger decides, not this table.)

| # | VO (draft) | On screen | Engine / data |
|---|---|---|---|
| 1 | "Somewhere in this ocean is the farthest point from any land on Earth. Who are the nearest humans to it?" | Globe spin to the South Pacific; question plate | `globe` (Blue Marble, PD) → vector |
| 2 | "A — fishermen on Easter Island. B — scientists in Antarctica. C — astronauts. D — nobody within 1,000 km." | 4 option pins drop at the real places (Hanga Roa, Antarctic base, ISS icon, "nobody") | vector, 12 fps pin drops |
| 3 | countdown | ring + ticks over drifting ocean | vector |
| 4 | "Point Nemo. 48 degrees south, 123 west. The nearest land is **2,688 km** away in three directions." | Orthographic view; three great‑circle arcs to Ducie Island, Motu Nui, Maher Island with km labels; scale bar | vector, `geoDistance` |
| 5 | "That circle of empty water is bigger than… [true‑size comparison on Equal Earth]" | Equal Earth; circle of radius 2,688 km vs a country outline dragged in | vector, equal‑area |
| 6 | "When the ISS passes overhead, ~400 km up, its crew are the closest people. Answer: **C**." | Reveal: option C fills; ISS arc crosses the frame | vector |
| 7 | "Which is why space agencies aim dead satellites here — Mir came down in 2001." | Credited archival insert (NASA/ESA Mir imagery, PD/CC BY) in the film‑insert frame | existing `url` clip |
| 8 | "It's named after Captain Nemo — Verne's man who wanted no country at all." | Kicker plate; end card repeats the question | vector |

Motion estimate: globe (1.0) 6 s + vector camera scenes (0.75) ~35 s + archival (1.0) 4 s over 52 s ≈ 0.78 ≥ 0.70 promise. Zero GPU minutes needed.

---

## 3 · Architecture: how it plugs into reelkit

```
 Sandbox (2 GB)                                    GitHub Actions (4 vCPU / 16 GB)                 Releases
 ─────────────────                                 ───────────────────────────────                 ────────
 research.json  ←─ geofacts.py (Wikidata+Factbook) │ render.yml                                     media-<ep>
 voice.json, geo.json (beats), shots.json,         │  ci_setup.sh  (+ world-atlas, mapshaper, kokoro) cache-clips
 clips.json, build.py, score.py                    │  episode.sh:                                   geodata-v1
        │  tools/sync.sh (git push)                │   pull → tts(Kokoro) → trim → plan → voice     ep-<n>-vN (final)
        ▼                                          │   → score → geo(prep Natural Earth per scene)
 cloud.py render <ep> --tag … --wait  ─────────────►   → assets (+clips gen --cache-only: maptile via
        ▲                                          │      docker ghcr.io/versatiles…, globe via numpy)
        │ gate reports / mp4                       │   → build (engine/geo.py + fx.py → HyperFrames)
        └──────────────────────────────────────────┤   → facts → provenance → planlint → geolint
                                                   │   → check → textqa → render → encode → qa → publish
```

### 3.1 New files (all live in the new repo; names follow reelkit conventions)

| File | Purpose |
|---|---|
| `engine/geo.py` | Python → HTML/SVG/GSAP strings, like `fx.py`. API: `GeoScene(id, projection, center, scale|fit, w, h)`, `.basemap(level, layers)`, `.highlight(names, style)`, `.pin(lng, lat, label, t)`, `.route(coords, t0, t1, arc=True)`, `.camera_to(center, scale, t0, t1, ease)`, `.choropleth(data)`, `.scalebar(t)`, `.label(...)`, `.globe_spin(...)`. Emits the 12 fps `steps()` eases for graphics, smooth tweens for the camera. |
| `reelkit/geodata.py` | CI stage `geo`: downloads Natural Earth (via `world-atlas` + NE 10m zips) once, caches as release `geodata-v1`; per episode reads `geo.json`, clips to each scene's bbox with margin, simplifies with mapshaper, writes `hf/assets/geo/<scene>.json` (TopoJSON, ≤ 300 KB). Adds provenance rows (PD / ODbL / CC BY) to `media.json`. |
| `reelkit/geofacts.py` | `geofacts.py draft <ep> Q159 Q16 …` → SPARQL (with `prov:wasDerivedFrom` references and `point in time`) + `factbook.json` → draft `research.json` claims with two sources, caveats where sources differ > 2 %. Human (you/agent) edits, never auto‑accepted. |
| `reelkit/geolint.py` | Gate: every pin/route coordinate is within 25 km of its Wikidata/GeoNames coordinate; label text equals the data label; area‑comparison sentences ⇒ equal‑area projection; km figures ⇒ scale bar present; projection credited; disputed features styled per D4; antimeridian/pole sanity. |
| `reelkit/clips.py` (+) | Engine **`maptile`**: spec = VersaTiles animation JSON (keyframes/annotations/style/aspect 9:16) → hash via vendored MIT codec → `docker run ghcr.io/versatiles-org/versatiles-map-animator@sha256:… --hash … --width 1080 --height 1920 --fps 15 --quality high --output …`; cache key = sha256(spec + image digest + width/fps). Engine **`globe`**: numpy inverse‑orthographic reprojection of a PD texture (Blue/Black Marble), spin/zoom/pins/terminator → ffmpeg; cache key = spec. Both: **CI only**, like Wan/url today. |
| `reelkit/vendor/versatiles_codec/` | The 4 MIT files that encode animation JSON → URL hash (`src/lib/url_state/*.ts` compiled once to JS). |
| `reelkit/tts_kokoro.py` (+) | CI stage `tts`: generates `vo/*.wav` from `voice.json` with fixed voice blend + seed; uploads to `media-<ep>`; skipped when takes already exist. |
| `series/geo-blitz/SERIES.md` | Series bible: §2 rules, border policy (D4), fingerprint rotation, credits wording. |
| `series/geo-blitz/_template/` | Copy‑to‑start episode skeleton: `research.json`, `voice.json`, `geo.json`, `shots.json`, `clips.json`, `episode.json`, `plan.py`, `score.py`, `make_assets.py`, `build.py`, `POST_KIT.md`. |
| `docs/GEO_SOURCES.md` | The data/licence catalogue (§1.3 table) with URLs and credit strings. |

### 3.2 `geo.json` — the single source of truth for map scenes (the "beats" idea)

```json
{
  "version": 1,
  "data": {"countries": "ne_50m", "places": "wikidata", "rivers": "ne_10m"},
  "scenes": [
    {"id": "s04", "projection": "orthographic", "center": [-123.39, -48.88], "scale": 1.0,
     "layers": ["land", "graticule"], "camera": {"to": {"center": [-123.39, -48.88], "scale": 1.6}, "ease": "power2.inOut"},
     "pins": [{"q": "Q1052062", "label": "Point Nemo", "lng": -123.393, "lat": -48.876, "at": "nemo"}],
     "routes": [{"from": [-123.393, -48.876], "to": [-124.78, -24.67], "label_km": true, "at": "ducie"}],
     "scalebar": true, "stutter_fps": 12}
  ]
}
```
`plan.py` resolves `"at": "<word>"` to VO timings exactly as `C["portland"]` works today; `build.py` calls `GeoScene` per entry; `geolint` validates the file; `geodata.py` prepares the data. Change the JSON → new episode, no re‑keyframing.

### 3.3 Workflow changes (`render.yml`)

- `ci_setup.sh`: `npm i -g mapshaper`, `npm i world-atlas d3-geo topojson-client` into `~/.cache/node_modules`, Kokoro ONNX model into `~/.cache/huggingface` (cached by `actions/cache`), `docker pull ghcr.io/versatiles-org/versatiles-map-animator@sha256:<pinned>` only when `clips.json` has an uncached `maptile` clip.
- New env: `GEODATA_RELEASE=geodata-v1`, `KOKORO_VOICE`, `MAPTILE_FPS=15`.
- `timeout-minutes: 60` stays; a hero maptile clip (6 s @ 15 fps = 90 frames ≈ 3–5 min) plus the normal 13‑min render fits with margin. Clips are rendered once and cached (`cache-clips`), so re‑renders cost nothing.
- `check.yml`: + `geolint --offline` over every `geo.json`, + `clips.py lint` accepts the new engines.

### 3.4 Sandbox vs CI (RAM rules)

Sandbox: JSON/text only — `geofacts.py draft`, `geolint --offline` (coordinates from the cached Wikidata answers), `planlint`, `voice.py check --plan-only`, `episode.sh <ep> preflight` (build + layout only, with `--hf` assets stubbed for maps using 110m data). Never: Natural Earth 10m processing (70 MB shapefiles), Kokoro, Docker, numpy globe frames, ffmpeg.

---

## 4 · Phased plan (each phase = one bounded session, ends with `tools/sync.sh`)

Time estimates are agent wall‑clock including CI waits; "owner" steps are yours.

### Phase 0 — Analysis & plan ✅ (this session)
Deliverables: this document, `poc/geo_poc.mjs`, `poc_vector_frame.svg/.png`.

### Phase 1 — Repo bootstrap (≈ 1 h)
1. **Owner:** create public repo `zainkhan122/geography`, a fine‑grained PAT (contents + actions + releases), paste it into `~/.cache/secrets/gh_token`. Decide **D1–D5**.
2. Copy from History: `reelkit/ engine/ tools/ fonts/ bootstrap.sh .github/workflows/ .gitignore`; new `README.md`, `AGENTS.md` (geography operator model), `RESUME.md`, `STATE.json`, `series/geo-blitz/SERIES.md`, `docs/GEO_SOURCES.md`, `docs/CHANNEL_BASELINE.md` (the §1.1 numbers, for the scorecard).
3. Add `tools/upstream.sh` (diff reelkit vs History, prints a patch).
4. `check.yml` green on first push.
5. **Kokoro audition:** workflow `audition.yml` renders 3 voices × the ep10 sample line → release `audition-v1` → **owner picks** (D3).
**Acceptance:** `check.yml` passes; `cloud.py status` works against the new repo; audition release exists.

### Phase 2 — Vector map engine v1 (≈ 2–3 h, two sessions if needed)
1. `reelkit/geodata.py` (fetch, clip, simplify, provenance rows) + release `geodata-v1` built by a one‑off workflow `geodata.yml`.
2. `engine/geo.py` v1: Mercator/Equal Earth/orthographic(static), basemap, highlight, pins (12 fps drop), great‑circle routes with travelling dot, labels with counter‑scale, camera_to, scalebar, credit strip.
3. Smoke episode `series/geo-blitz/_smoke/` (no VO: 20 s, 4 scenes) → `cloud.py render _smoke --tag smoke-v1 --wait`.
4. Verify by **stills first** (`episode.sh _smoke snap` at scene times — same as the skill's verify loop), then the MP4: pins on the right coordinates, two adjacent frames identical on the graphic layer (stutter), camera smooth, no text in dead zones.
**Acceptance:** smoke render passes `check`, `textqa`, `qa`; render time per video‑second ≤ 1.5× Paper Trail's.

### Phase 3 — Pilot episode #10 end‑to‑end (≈ 3–4 h across 2 sessions)
1. Session A: `geofacts.py draft` + manual sources → `research.json` (≥ 2 sources per figure; NOAA/NASA/ESA primary); `voice.json` with climax + sample line; `geo.json`; `shots.json` (fingerprint recorded); `clips.json` (one `url` archival insert via `find.py`); `episode.json` promise 0.70; `POST_KIT.md`.
2. CI: `tts` stage produces takes → `voice.py words/check` in CI → report in the run summary; retakes by editing `voice.json` lines (seeded ⇒ reproducible).
3. Session B: `plan.py`, `score.py`, `make_assets.py`, `build.py` → `episode.sh preflight` → `cloud.py render … --tag ep10-nemo-v1 --wait`.
4. **Owner review** of the release (mp4 + every gate report), fixes, v2.
5. **Owner uploads** manually from POST_KIT (title, description with sources & credits, hashtags, pinned comment, "altered or synthetic" box not needed — no realistic AI media; AI voice disclosed in description).
**Acceptance:** all gates 0 FAIL; motion ≥ 0.70; −14 LUFS; published on TheQuizWire; `STATE.json` episode entry.

### Phase 4 — Cinematic engines (≈ 3 h)
1. `clips.py` engine `maptile`: vendored codec → hash; Docker step; cache; `prep` path (15→30 fps `minterpolate`, unsharp, grade `none|night`); credit strings auto‑filled ("© OpenStreetMap contributors (ODbL) · Sentinel‑2 cloudless CC BY 4.0 · Copernicus DEM · VersaTiles"); provenance allow‑list += ODbL (attribution‑only for produced works) and CC BY 4.0 data.
2. `clips.py` engine `globe`: numpy reprojection, textures cached from NASA (PD), pins + terminator + atmosphere, ≤ 8 s clips.
3. Keyframe helpers ported from travelback's `camera.ts` (`flyover`, `orbit`, `birdseye`) → generate VersaTiles JSON from a center/bbox so an episode asks for `{"mode":"orbit","target":[76.51,35.88],"zoom":11.5,"seconds":6}` instead of raw keyframes.
4. Episode #11 ("Why is Chile 4,300 km long?") uses one `maptile` terrain flyover + one `globe` + vector scenes.
**Acceptance:** maptile clip renders in CI in ≤ 10 min, cache hit on re‑render; `provenance` passes with the new licences; owner approves the look.

### Phase 5 — Geography gates & rotation (≈ 2 h)
1. `reelkit/geolint.py` (§3.1 rules) wired into `episode.sh` and `check.yml`.
2. `planlint`: motion weights for `map/maptile/globe`; fingerprint fields += `projection_set`, `map_opening` (globe / regional / street), `quiz_device` (pins‑as‑options / list / true‑size).
3. `factcheck`: unit‑aware number matching ("2,688 km" vs "two thousand six hundred and eighty‑eight kilometres"), tolerance table for rounded figures (±1 % declared per claim).
4. Border policy (D4) implemented as a style table in `engine/geo.py` + `SERIES.md`.
**Acceptance:** gates catch three planted errors (wrong pin, Mercator area claim, missing scale bar) in a sabotage test, as `clipcache` was tested in History.

### Phase 6 — Bank six, publish, measure (≈ 1 session per 2 episodes)
1. Produce #12–#15 rotating the four formats (backlog §7); matrix render up to 4 in parallel (`render.yml` already supports it).
2. `POST_KIT.md` template for TheQuizWire: title pattern "Question? 🗺️ | Geo Blitz #N", description = answer line + sources block (`out/sources.md`) + credits (`out/credits.md`) + thequizwire.com link + hashtags; pinned‑comment text; thumbnail = `COVER_AT` map frame.
3. Cadence: **1 Geo Blitz 2.0 per day at a fixed slot** replaces 1 of the 4–5 daily template quizzes (don't raise volume; replace). After 10 episodes compare the scorecard in `docs/CHANNEL_BASELINE.md`: viewed‑vs‑swiped ≥ 70 %, avg % viewed ≥ 85 %, subs/1k views ≥ 3, comment disputes = 0.
4. `publish.py` (YouTube Data API: private upload + `publishAt`) **only after D5**; note unaudited API projects keep uploads private — test one, else keep Studio.
**Acceptance:** 6 episodes in Releases, 10 published, scorecard filled.

### Phase 7 — Extensions (optional, after the scorecard)
- 16:9 long‑form "Geo Blitz Files Vol. 1" (8–12 min) from 4 episodes — the revenue format in your strategy doc; `engine/geo.py` is resolution‑agnostic.
- History crossover with `historical-basemaps` (GPL, decision‑gated; BORDERPRECISION drives border blur).
- "Journey" format from GPX/KML (travelback parser port) → VersaTiles flyover; gpx‑animator only if a licence‑clean raster basemap appears.
- Urdu/Hindi variants (Noto Nastaliq already in fonts; Arena/Gemini TTS for Urdu as your docs note Kokoro has none).

---

## 5 · Cadence, publishing, measurement (channel strategy)

- **Replace, don't add.** 510 templated Shorts have trained the algorithm on a weak signal; the fastest way to change the channel's "whole‑channel" judgement is to raise the median quality, not the count. Target: 1 map‑led Short/day; keep at most 1–2 of the old quizzes/day during transition, then retire them.
- **Series page hygiene:** rename the playlist to "Geo Blitz — on the map", new banner frame from the engine, channel description mentions "every answer shown on a real map, every fact sourced in the description".
- **Hook grammar** that the data supports: superlatives ("largest/coldest") and place‑names in the title + one map emoji; question in the first 2 seconds *spoken*, not just written.
- **Comments as research:** keep "What was your first guess?" — it is a free poll; `geofacts.py` can take next topics from a Community poll.
- **Policy posture:** original graphics, original narration, sourced facts, format rotation, credits on screen — the four things your CONTENT_STRATEGY lists as the monetisation defence. AI voice disclosed; no realistic synthetic imagery (maps and PD photos only) so the "altered content" box is normally not required.

---

## 6 · Risks & mitigations

| Risk | Mitigation |
|---|---|
| Software WebGL is slow on the runner (maptile clips) | Hero clips only (≤ 2 per episode, ≤ 8 s), 15 fps + `minterpolate`, pinned image digest, content‑hash cache; vector engine carries 80 % of scenes with no WebGL at all |
| `tiles.versatiles.org` is a free community server | Prewarm pass + cache (their renderer does it); small clip counts; credit them; if usage grows, self‑host a regional `.versatiles` extract in CI (documented option) |
| Licences outside the current allow‑list (ODbL, GPL data) | ODbL "produced work" needs attribution only → add with required credit string; GPL (historical‑basemaps) decision‑gated per episode |
| Wikidata staleness/vandalism | Reference‑bearing statements only, latest `point in time`, Factbook diff, 2‑source rule, caveats recorded |
| Mercator "lies" and border sensitivities (PK/IN audience) | `geolint` projection rule; D4 policy; neutral wording; dashed disputed lines; no political commentary |
| Large SVG payloads slow HyperFrames | Clip to bbox, simplify, 110m for world, 10m only when zoomed; no SVG filters on map layers (paper texture = static PNG) |
| Text in platform dead zones / low contrast | Existing `textqa` + `layout` preflight; map credits sit at y ≈ 1600 within the allowed band |
| HyperFrames quirks (videos in timed divs, double tweens) | Reuse `fx.py` patterns; map clips are root‑level `<video>` via `FX.footage()` |
| Sandbox timeouts | Phase boundaries above; all heavy work in CI; `cloud.py --wait` for long jobs; `RESUME.md` updated before every sync |
| Sandbox RAM (2 GB) | Nothing geo‑heavy runs locally; 110m stubs for preflight |

---

## 7 · Topic backlog (first 12, with engine and primary data)

| # | Hook (question) | Format | Engine(s) | Primary data |
|---|---|---|---|---|
| 10 | Who are the nearest humans to the loneliest point on Earth? | Scale shock | globe + vector + url | NOAA/NASA/ESA; Lukatela 1992 |
| 11 | Why is Chile 4,300 km long but 350 km wide? | Shape | maptile terrain + vector | NE 10m, Copernicus DEM, Wikidata |
| 12 | Which country has three capitals? | Superlative | vector | Wikidata, Factbook |
| 13 | The town where you change country by crossing a café (Baarle) | Border oddity | vector (OSM boundaries) + maptile street | Overpass (ODbL) |
| 14 | How many countries meet at one point here? (Kazungula) | Border oddity | maptile satellite + vector | NE rivers, Wikidata |
| 15 | Is Africa really that small? (true size) | Scale shock | vector equal‑area | NE, Wikidata areas |
| 16 | Why does Namibia have a finger? (Caprivi) | Shape | vector + historical (decision‑gated) | NE, historical‑basemaps |
| 17 | Which country is entirely inside another? (Lesotho / San Marino / Vatican) | Superlative | vector | NE, Wikidata |
| 18 | Where is it Monday and Sunday 3 km apart? (Diomede Islands) | Border oddity | globe + vector | NE, tz boundaries (ODbL) |
| 19 | Which desert is the coldest? (your top performer, redone on the map) | Superlative | globe night + vector | Köppen, Wikidata |
| 20 | Which river crosses the most countries? (Danube) | Superlative | vector route draw‑on | NE rivers, Wikidata |
| 21 | Why is Russia's clock wrong in Kaliningrad? | Shape | vector + maptile | NE, tz, Wikidata |

---

## 8 · Appendix

### 8.1 Licence matrix (for `provenance.py` allow‑list)
| Source | Licence | Credit string |
|---|---|---|
| Natural Earth / world‑atlas | Public domain | "Map data: Natural Earth" (optional but shown) |
| OpenStreetMap via VersaTiles | ODbL 1.0 (produced work → attribution) | "© OpenStreetMap contributors" |
| Sentinel‑2 cloudless mosaic (VersaTiles) | CC BY 4.0 | "Sentinel‑2 cloudless, Copernicus (CC BY 4.0)" |
| Copernicus GLO‑30 DEM / Mapterhorn | Copernicus licence / CC BY 4.0 | "Terrain: Copernicus DEM · Mapterhorn" |
| NASA Blue/Black Marble, SVS, GIBS | Public domain | "NASA" |
| Wikidata | CC0 | — (cite the referenced source instead) |
| CIA World Factbook | Public domain | "CIA World Factbook" |
| GeoNames, OWID, World Bank, GHSL, Köppen (Beck 2018) | CC BY 4.0 | per source |
| historical‑basemaps | GPL‑3.0 (decision‑gated) | "Historical borders: aourednik/historical‑basemaps (approximate)" |

### 8.2 Command cheat‑sheet (after Phase 2)
```bash
source bootstrap.sh
python3 reelkit/geofacts.py draft series/geo-blitz/ep10-nemo Q1052062      # draft claims with references
python3 reelkit/geolint.py series/geo-blitz/ep10-nemo --offline            # coordinates, labels, projection rules
bash reelkit/episode.sh series/geo-blitz/ep10-nemo preflight               # ~1 min, sandbox-safe
bash tools/sync.sh "ep10: geo.json + voice plan"
python3 reelkit/cloud.py render series/geo-blitz/ep10-nemo --tag ep10-nemo-v1 --wait
python3 reelkit/cloud.py why                                               # gate failures, if any
```

### 8.3 Files in this folder
- `GEO_PLAN.md` — this plan
- `poc/geo_poc.mjs` — the vector‑frame proof (Node 20, `d3-geo` + `topojson-client` + `world-atlas`)
- `poc_vector_frame.svg` / `.png` — the generated 1080×1920 frame
