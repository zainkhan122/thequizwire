# Decode lessons — 2026-10-18 (what the high-traffic map channels actually do, and what we change)

Source of numbers: `docs/DECODE_2026-10-18.md` (+ `docs/data/decode-2026-10-18.json`), produced by `reelkit/decode.py`
on the latest 12 Shorts of **@gyanotrick** (20.7K subs, median 463K views), **@histoboi** (median 104K),
**@huhindustry** (median 88K), **@geomapunveiled25** (median 8K) — top-3 + bottom-1 per channel, 16 videos
downloaded, transcribed (Hindi/Urdu → English via Whisper translate), prosody-measured, frame-sheeted and covers saved —
against our own 10 released v3 pilots run through the *same* measurements.
Contact sheets I looked at: `~/review/decode_<channel>_sheets.jpg`, covers `~/review/decode_gyanotrick_covers.jpg`.

## 1. The scoreboard (medians)

| | winners (top tier, n=12) | losers (bottom, n=4) | **TheQuizWire (n=10)** |
|---|---|---|---|
| length | 38 s (map-story channels 22–31 s; explainer 45–75 s) | 49 s | 36 s |
| spoken words / pace | 113 words · **173 wpm** | 121 · 173 | 70 · **116 wpm** |
| pitch range (semitones, mixed audio) | **16.4 st** | 18.2 | **13.2 st** |
| pitch median | 160 Hz | 150 Hz | **92 Hz** (am_michael is very low) |
| integrated loudness | **−13.8 LUFS** (GyanoTrick −12.7, Histoboi −8.7!) | −14.9 | **−17.6 LUFS** |
| motion events / 10 s | **27** (continuous zoom + pops) | 20 | **1.2** |
| spoken CTA | 17 % | 50 % | 100 % |
| heading is a question | 33 % | 25 % | 100 % |
| description has a link | 0 % | 0 % | 0 % |
| hashtags in description | 3–4 | 5–6 | 3–5 ✓ |
| likes ‰ views | 11 | 7.5 | — |

Three things separate us from the winners by a mile and they are all *production*, not topics:
**pace (116 → 170 wpm), motion (1 → 20+ events/10 s), loudness/energy (−17.6 → −14, flat low voice → livelier voice).**

## 2. What each component looks like at the winners

### Script (listen/read: GyanoTrick hi, huhindustry ur, Geomap en, Histoboi = music only)
- **Sentence one is the whole premise, as a question or claim with a number**: *"What happens if Gandhi came back for 12 hours?"*,
  *"This crater was hidden for 390 million years."*, *"If you look at Google Maps of Saudi Arabia you will see …"*, *"10 countries with facts
  that sound impossible."* No greeting, no "welcome", no channel name. The bottom video of GyanoTrick is the one that opens *"Hi guys …"*.
- **Then a chain of consequences, one per sentence, each naming a country** ("India moves to Australia's spot → Pakistan and China now border
  Australia → Australia builds …"). 5–10 sentences, every sentence has a new map action. Numbers everywhere (years, km, $, hours).
- **No spoken CTA in 10 of 12 winners.** The CTA lives in the description ("Subscribe!!!!") or not at all. Winners end on the punchline
  ("…and the 12 hours are over."). Losers waste the last 5 s asking.
- Explainer winners (Geomap) end on a **comment bait question in the description**, not in the audio: *"Genius or a massive waste of money? Tell me in the comments."*

### TTS / voice
- Fast, mid-pitched, energetic male narration: 160–240 wpm, median 150–160 Hz, 16 st range. GyanoTrick's voice is an Indian-English/Hindi
  TTS at **236 wpm** on its 4M video. Geomap uses an American TTS at 175 wpm with music ducked under.
- Mix is **hot**: −12.7 to −14 LUFS with a music bed that *fills the silences*. Our 3 s think-time is 3 s of near-silence → pulls our
  integrated loudness to −17.6 and reads as "dead air" in a feed.

### Cover / first frame
- **First frame (0.5 s) is already the stage**: GyanoTrick opens *every* video on the same satellite South-Asia view with a big blue
  thinking-emoji character (brand consistency = recognisable in the feed), then the country shape fills with a flag within 1 s.
- Maxres thumbnail = a key frame from the middle (flag-filled shape + characters + explosion) with **2–3 words of giant yellow text**
  ("12 HOUR", "6X", "24 HOUR") — never the full title, never a quiz layout. Geomap/Histoboi: the hero map with the country/empire filled.
- No faces, no photos of presenters; photo cut-outs of famous people (Gandhi, MBS, Gaddafi) are the "face" that stops the thumb.

### Media / motion (the biggest gap)
- The camera **never stops**: slow zoom/pan the whole time, country shapes fill with flags (texture-filled polygons, not flat colours),
  flag-ball characters with expressions pop on the map, emoji stickers (💪🔥💰✈️), explosions/arrows for "attacks/moves", photo cut-outs.
  27 motion events/10 s vs our 1.2.
- **On-screen text**: GyanoTrick none at all (audio + visuals carry it); Histoboi and huhindustry use ONE short all-caps label per beat
  ("MONGOL EMPIRE", "PAKISTAN SSG", "$ 500K", "9288 km"); Geomap shows a single keyword caption per beat ("crater", "70 BILLION"). Nobody uses
  full-sentence captions. Labels are 1–3 words, white/yellow, bottom third or beside the object.
- Watermark/handle on every frame (small, top-right or centre) — reposts carry the brand.
- Satellite basemap everywhere (Esri/Microsoft imagery, Google-Earth look) — our V3 satellite look is correct.

### Heading (title)
- 45–60 chars, sentence case, **no channel name, no "quiz"**, keyword nouns first. Patterns that win: *What If X … for N Hours? 😱*,
  *Countries Now Vs Then*, *All Territories Ever Controlled by Each Country*, *Google Maps Just Exposed a 390 Million Year Old Mystery*,
  *Green Circles in Saudi Arabia Map*. Histoboi/huhindustry put 2–3 hashtags **inside the title** (#geography #maps #history) — on Shorts
  the title *is* the visible text in the feed, hashtags there are search hooks.
- Only 1 in 3 winning headings is a question; the winners are **premise statements** that imply a question.

### Description
- GyanoTrick: a 600–900-char keyword **mini-article** (every country named, "map animation", "what if", "geography") + a disclaimer line +
  ~5 hashtags; ~20 tags. Geomap: 1–2 sentences of real facts + a comment-bait question + 7–11 hashtags. Histoboi/huhindustry: one line or
  empty — **description is optional for the algorithm; the package (first 2 s + title) is not.**
- **No links anywhere in any winner** (0 %). Links in the first lines are a swipe/leave signal; keep thequizwire.com in the outro frame only.

### How they work the algorithm (matches `platform-algorithms-2026-10-18.md`)
- YouTube Shorts: swipe decision in 1–2 s → premise in sentence one + stage already moving at frame 0; completion/loop → end on the
  punchline, no outro; catalogue consistency → same opener character, same basemap, serial titles ("What If …", "Now vs Then").
- Comments ‰ is **higher on losers** (0.9 vs 0.2) — comments do not rescue a weak retention; likes ‰ tracks winners (11 vs 7.5).
- Cross-posting: all four re-post the same file to FB/IG unchanged (watermark on frame); nothing platform-specific in the video.

## 3. What we change (pipeline, in order of expected impact)

| # | change | where | status |
|---|---|---|---|
| 1 | **Pace 116 → 150–170 wpm**: Kokoro `speed` 1.0 → **1.18**; scripts 70 → **90–110 words** in the same 30–36 s (one more fact beat, shorter think-time 3.0 → **2.0 s** with a ticking SFX + camera creep so it is not dead air) | `reelkit/voice.py` speed, `docs/AUTHORING.md` word budget, `plan.py` think-time | to do (F2) |
| 2 | **Continuous motion**: slow Ken-Burns on every scene (zoom 1.00 → 1.06 over the beat), option-chip pop-ins staggered, flag-filled reveal polygon (texture fill, not flat), one emoji sticker / flag-ball reaction per beat; target **≥ 12 motion events / 10 s** measured by `decode.py ours` | `reelkit/scenes/*`, `qa.py` new gate `motion_per_10s ≥ 10` | to do (F3) |
| 3 | **Loudness/energy**: music bed −22 dB under VO and **never silent**; master −14 LUFS integrated *including* think-time; voice: keep `am_michael` (owner's choice) but raise pitch range with Kokoro mixed voice `am_michael×0.7 + am_adam×0.3` **or** `af_heart` test — A/B on the next 2 episodes; `voice_study`-style check: median ≥ 110 Hz, range ≥ 15 st | `reelkit/mix.py`, `voice.py` | to do (F2) |
| 4 | **Opening 0–2 s**: frame 0 = the full-stage satellite view with the series mascot (flag-ball with ❓) already on the map and the camera moving; question appears word-by-word over it. No logo card, no "TheQuizWire" sting before the question. | scenes `q_open`, `cover.py` first-frame burn | to do (F3) |
| 5 | **Spoken CTA → removed from the voice**; keep the 2 s animated outro visual (approved) but VO ends on the punchline fact. CTA + comment-bait go to description line 2. | `plan.py` CTA piece, `postkit.py` | to do (F2) |
| 6 | **Headings**: premise-statement option alongside the question, 45–60 chars, keyword nouns first, no "quiz" word in YouTube title (keep "Geography quiz" only in the playlist); emoji at end allowed; 2 hashtags inside the YouTube title for Shorts search | `postkit.py` title builder, `series.json` | to do (F2) |
| 7 | **Description**: line 1 = premise + the countries named; line 2 = comment-bait question; 3–5 hashtags last; **no link**; 15–20 tags via `yt_enrich` | `postkit.py`, `yt_enrich.py` | to do (F2) |
| 8 | **Covers**: key frame (flag-filled answer shape + mascot reaction) + ≤ 3 giant yellow words, not the question text layout | `cover.py` | to do (F3) |
| 9 | **Watermark** `@thequizwire` small top-right on all frames | HyperFrames layer | to do (F3) |
| 10 | On-screen text = one 1–3-word label per beat, Anton caps, never the full sentence | scenes | to do (F3) |

Guardrails kept: honest maps (equal-area/scale bar, disputed plates with controller labels), 3 options → reveal, no "next video" tease,
Lilita/Anton fonts, V3 satellite look, approved outro visual (now silent under the last fact).

## 4. How to re-run / extend
```
python3 reelkit/decode.py channels @gyanotrick @histoboi @huhindustry @geomapunveiled25 --latest 12 --top 3 --bottom 1   # ≈ 2 min/channel
python3 reelkit/decode.py ours series/*/ep*                                                                              # needs <ep>/out/final.mp4
python3 reelkit/decode.py report                                                                                          # docs/DECODE_<date>.md
```
Raw video/audio/frames stay in `~/.cache/decode/<date>/` (never committed). Add quiz-format peers to the list when found —
none are recorded yet; the four above are the owner's reference set from `docs/STYLE_ASSESSMENT.md`.
