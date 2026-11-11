# Lessons → gates
Every render failure gets a row here AND a gate in the pipeline (precheck / placelint / author / workflow). A lesson that is only written down is not a lesson.

## 2026-11-11 — backlog batch (insulin, Silverstone, swift, Geo #27)
| What failed | Why | Now enforced by |
|---|---|---|
| Hook pace 8.53 syl/s (urgent band ≤ 7.4) | 18-syllable hook of short words at Kokoro speed 1.10 | `precheck V6`: hook > 15 syllables FAIL, > 14 WARN |
| Whisper heard "F1, first" for "F1's FIRST" | possessive on a digit token | `precheck V7`: `\d+'s` / `ABBR's` in any line FAIL |
| Flag-ball covered the answer tag (insulin, Silverstone) | default character positions vs a tag near the subject | `placelint L4`: character box ∩ tag box at s04/s05 cams FAIL; character bottom ≥ 1190 FAIL |
| Readability 1.3:1 at the reveal instant (Geo #27) | `flash-cut` fx.flash whitens the frame under text | `flash-cut` removed from `author_v4` reveals (with reason) |
| 4 runners failed at `cd` | bare ids passed to `render.yml` | plan job resolves ids / fails fast; `tools/ship.sh` always sends paths |
| A FAIL got pushed + dispatched | `;` chain in the shell | `tools/ship.sh`: preflight for every episode must be 0 before commit/push/dispatch |
| 10 m map data 1.6 MB | India's coastline inside the far bbox | existing P5 cap (kept); note: Indian-Ocean-wide views stay 50 m |
