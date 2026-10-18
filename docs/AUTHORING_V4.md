# Authoring v4 — rules derived from the 2026-10-18 decode (`docs/DECODE_LESSONS_2026-10-18.md`)

Applies to every episode marked `status: ready` from now on. Gates: `quizlint` Q11 (warn), `postkit check`.

## Script (voice.json)
- **Sentence one = the premise.** No greeting, no channel name, no "today's question". Pattern: a claim with a number or a
  familiar anchor, then the question. *"A whole kingdom, and not a single river runs through it. Which country?"* ✓
- **90–110 spoken words in 30–36 s** at Kokoro speed **1.15** (template default). Budget: hook 14–18 · options 5–7 ·
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
- Voice stays `am_michael` (owner) at speed 1.15; A/B of a brighter mix voice is pending owner's ear.

## Visual targets (F3, in progress)
- ≥ 12 motion events / 10 s (camera always moving; staggered pop-ins; flag-textured answer fill; one sticker/flag-ball reaction per beat).
- Frame 0 = full satellite stage with the series mascot already on the map; question types in word by word over it.
- On-screen text = one 1–3-word Anton label per beat; never the full sentence. `@thequizwire` watermark top-right on every frame.
- Cover = key frame (flag-filled answer + mascot reaction) + ≤ 3 giant yellow words.
