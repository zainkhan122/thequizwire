# Sports Sprint (`sports-sprint`)

Records, rules and venues: bar races for records, procedural pitch diagrams for rules, a map when the venue is the story.

Numbering: feed #8 → next #9 (`series/series.json` is the counter; `tools/new_episode.py sports-sprint …` bumps it).

## Format rules
- Stage: `bars` (record race) · `compare` · `strip` (timeline of firsts) · `geo` (venue)
- Numbers from governing bodies' record pages (reference tier) + Wikidata (CC0); never scrape their graphics
- Nationality/venue questions in disputed regions follow docs/BORDER_POLICY.md like Geo Blitz
- Engine status: `bars` exists; `compare`/`strip` are Phase-2

## Sources
See `docs/DATA_SOURCES.md` (Sports Sprint section). Every fact → `research.json` claim; every file → `media.json`.

## Episodes
- `ep09-basketball-invented-springfield` — In which US state was BASKETBALL invented? → **Massachusetts** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
- `ep10-grand-slam-on-grass-wimbledon` — Which Grand Slam is still played on GRASS? → **Wimbledon** (v2, Phase 3.1 pilot, green offline; media in the `pilot-v2-batch1` Release once run #3 passes)
