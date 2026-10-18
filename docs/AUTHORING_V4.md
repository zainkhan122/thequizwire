# Authoring v4 — rules derived from the 2026-10-18 decode (`docs/DECODE_LESSONS_2026-10-18.md`)

Applies to every episode marked `status: ready` from now on. Gates: `quizlint` Q11 (warn), `postkit check`.

## Script (voice.json)
- **Sentence one = the premise.** No greeting, no channel name, no "today's question". Pattern: a claim with a number or a
  familiar anchor, then the question. *"A whole kingdom, and not a single river runs through it. Which country?"* ✓
- **72–88 spoken words** at Kokoro speed **1.2** (CI-measured: 93 words @1.15 ran 44 s with the beat and holds) (template default). Budget: hook 14–18 · options 5–7 ·
  reveal 12–16 · three story beats 18–22 each · tail ≤ 10. Every story beat names a place AND a number (years as digits).
- Consequence chaining: each story line changes something on the map (fill, pin, arrow, counter) — never two lines on the same picture.
- **Tail = punchline + ≤ 4-word CTA** ("Follow for tomorrow's map."). No "next video" tease (owner rule). The outro visual carries
  Subscribe/Like; the voice does not plead.
- Think-time stays 3.0 s (owner decision) but is **never silent**: ticks + music bed + camera creep (F3).

## Heading / description (episode.json `post`)
- `post.premise` — 45–60 chars, sentence case, keyword nouns first, no "quiz" word, e.g. *"The only country with zero rivers"*.
  postkit uses it as the YouTube title (+ emoji + 2 search hashtags) and as line 1 on IG/FB/X/Threads.
- `post.bait` — one comment-bait line that does **not** spoil the answer (*"Did you say Egypt or Saudi? 👇"*).
- `post.keywords` — 6–10 search phrases (country names, "map animation", topic nouns) → `yt_enrich` tags.
- Description = premise + question + the three options named (keyword article) → bait → facts → one subscribe line → sources → 3–5 tags.
  **No links anywhere** (0 % of winners link; thequizwire.com lives in the outro frame only).

## Voice/mix targets (checked by `reelkit/decode.py ours`)
- wpm 150–175 · integrated −14 LUFS **including** think-time (music bed never below −30 dBFS) · pitch range ≥ 15 st.
- Voice stays `am_michael` (owner) at speed 1.2; A/B of a brighter mix voice is pending owner's ear.

## Visual targets (F3, in progress)
- ≥ 12 motion events / 10 s (camera always moving; staggered pop-ins; flag-textured answer fill; one sticker/flag-ball reaction per beat).
- Frame 0 = full satellite stage with the series mascot already on the map; question types in word by word over it.
- On-screen text = one 1–3-word Anton label per beat; never the full sentence. `@thequizwire` watermark top-right on every frame.
- Cover = key frame (flag-filled answer + mascot reaction) + ≤ 3 giant yellow words.

## Enforcement — nothing ships without these (added 2026-10-18 on the owner's instruction)
| gate | where it runs | what it refuses |
|---|---|---|
| `quizlint` **Q11** (FAIL for every episode not already `status: published`) | `episode.sh` preflight, CI `render.yml`, `tools/daily_pick.py` | < 85 spoken words (v3 format) · CTA > 8 words · greeting hook · `kokoro_fallback.speed` < 1.15 · missing/short `post.premise` or the word "quiz" in it · missing `post.bait` or a bait that spoils the answer · < 6 `post.keywords` · any link in `post.description` |
| `postkit check` | CI render (post kit), `daily_pick.py` | title/description/hashtag rules per platform; ≤ 2 hashtags only at the end of the YouTube title |
| `qa.py` on the rendered master | CI render `qa` stage (after encode) | pace < 140 wpm while speaking (target 150–175) · loudness off −14 ±1 · motion < 6 events/10 s = FAIL (`V4_MOTION_MIN` raises the floor), < 10 = warning |
| `tools/daily_pick.py` | `daily.yml` 07:00 UTC | never picks a `ready` episode that fails quizlint or postkit — it prints `SKIP <ep>` with the failing lines |
| `tests/selftest.py` | before every commit, CI `selftest.yml` | the templates themselves must pass v4; an old-style copy (speed 1.0, no premise/bait) must be refused (`ep-v3-oldstyle`) |

The templates (`series/_template`, `_template_v2`, `_template_v3`) are already v4-compliant, so every new episode starts from a
passing example: `_template_v3` = 93 words, premise hook, 4-word follow, premise/bait/keywords filled, research anchors updated.

## F3 (2026-10-18) — motion / opener / cover, now in the engine and the gates
- **Hook lands word by word** (`engine/quiz.py hook3`): every word is a `.w` span popped in with a 60 ms stagger — automatic for all v3 episodes.
- **Opener**: `visuals.json` must put a character or sticker on the stage at `at: 0` (template: UN-flag "think" mascot, leaves when the pills land). Q11 refuses an empty map at frame 0.
- **Density**: Q11 refuses < 8 authored motion beats / 10 s and < 3 `geo.cam_to`; `qa.py` refuses a master under 6 measured events / 10 s.
- **Cover style `d` = KEY FRAME** (`reelkit/cover.py --style d`): the cleanest frame of the first story beat (answer lifted/flag-filled), ≤ 3 giant yellow words top-left (`post.cover.words`, else `answer_sub`), sticker top-right. Owner decision pending on making it the default (it shows the answer, unlike style b).
