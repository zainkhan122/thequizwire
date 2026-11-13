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
| Kokoro crashed in CI (`int32` vs `float`) on every episode | NOT onnxruntime: upstream re-exported `kokoro-v1.0.int8.onnx` on 2026-08-18 (`input_ids` + float `speed`); our cache held the old file until the cache key changed on 11-11, and kokoro-onnx ≤ 0.4.9 feeds that export an int32 speed. onnxruntime 1.22.1 additionally lacks the ConvInteger kernel | `render.yml`/`selftest.yml` use `setup-python 3.12`; `ci_setup.sh` pins numpy 2.2.6 / kokoro-onnx 0.6.1 (reads the graph's input dtypes) / onnxruntime 1.31.1, proven in the sandbox against the 2026-08-18 model files, and refuses 3.14; bumps only with a proving render |
| Three backlog episodes re-asked published questions (heart transplant = #05, first modern Olympics = #11, France time zones = #14/#24) | the author checked variety (stems, devices, outros) against recent episodes but nothing compared the TOPIC with the catalogue | `reelkit/dupelint.py` (Q25) runs in the quizlint stage of every preflight/CI render: same slug stem, same answer + ≥ 50 % shared question words, or ≥ 80 % shared question words against every episode in series/ → FAIL. Pre-existing pair #14/#24 left alone (#24 is already scheduled) |
| Two 85-word episodes rendered at 40.7–41.8 s (Q13 FAIL) although plan.py estimated ~35 s | big numerals (267,000 / 17,000 / 3,640) cost ~1.5 s each in Kokoro; the word budget hides that | budget in seconds: V2 numeral warning is real — with ≥ 5 large numerals keep the script ≤ 78 words and trust the CI timeline, not the word count |
| Antarctica episode failed QA motion (28 % of frame-time moving) with the usual cam drifts | ice and dark ocean have no texture, so the motion probe sees nothing | over low-texture basemaps (poles, open ocean) drift ≥ 3° and k ≥ ×1.1 per hold, aim the frame at a coastline |

| 2026-11-13 | ep29/ep30 round 2 | Pace gate (≥140 wpm while speaking) fails when a script is mostly numerals and pauses: 3,640 / 2,850 / 17,000 read slowly and every comma is a pause, so words/min collapses even though total time is fine. Keep ≤3 big numerals per script and fill the rest with short, flowing words; put the other figures on tags/charts. | pace + total time are two budgets; a numeral-heavy script loses both. |
| 2026-11-13 | ep30 round 2 | Whisper heard “Keto”/“Kefmandu” → intelligibility FAIL. When the options are cities with non-English names, ask the question as which-country and keep the city names on screen only. Quito/Kathmandu added to names_bad.json. | proper nouns Kokoro mangles stay visual. |
