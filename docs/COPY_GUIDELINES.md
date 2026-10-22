# Copy guidelines — written per Short, per platform (P4, 2026-10-21)

Owner: *"SEO-optimised descriptions and hashtags for each channel… guidelines, not templates… human-made content for humans."*
The 2026-10-19 fixed structure (question / comment CTA / like CTA / pool tags) is retired for new episodes. From now on the editor
writes the copy for each platform while authoring, records the reasoning in `topic.md → ## Copy`, and `reelkit/postkit.py` lints
it (spoilers, limits, bot phrases, links, novelty, search term, topic tags). Already-scheduled posts are never touched.

## What stays non-negotiable (hard gates)
- **Never reveal the answer** — no option name, demonym, place, person or number that identifies it (spoiler gate).
- No links anywhere; no sources line; no "AI narration" line (credits are burned into the video).
- No bot phrases ("in this video", "don't forget to", "smash that like", emoji walls). No greeting.
- Nothing copied from another episode: not a sentence, not a tag set.
- The **search term** from topic.md appears in the YouTube title or the first line of the description.

## How to write it (think, then type)
**YouTube** — title ≤ 100: lead with the words people type (the search term), then the hook of *this* question; the question
itself is fine when it already contains the term. Description first line = why this is worth 35 seconds *to the viewer*
(what they will be able to say at dinner), second line = a comment question that only makes sense for this Short, third =
an ask that fits the mood (sometimes none). 3–5 tags at the end: 2–3 subject tags (#marathon, #olympics1896), 1 format tag
(#geographyquiz / #sportsquiz), #shorts.

**Instagram** — caption speaks to the person watching with the sound off: open with the question or a one-line tease, a
line that invites a comment (a guess, an opinion, a tag-a-friend that is earned), 3–5 discovery tags for *this* subject.

**Facebook** — shortest, warmest, conversational; older audience; a question that invites a story ("have you run one?"),
1–3 tags.

**X** — ≤ 280 weighted chars, one punchy line + the question; 1–2 tags max, often one.

**Threads** — conversational, no hashtag soup: exactly one topic tag (only the first becomes a Threads topic).

## topic.md → ## Copy (required, lint reads it)
Three to six lines: the search term you built the title around, why the comment question fits this Short, which tags are the
subject's own and where they came from (suggest list / Commons category / the sport's own vocabulary), what you deliberately left out.

## Spec format (`post.copy` in the episode spec)
```json
"copy": {
  "spoilers": ["greek", "athens"],
  "youtube":   {"title": "…", "description": "…", "tags": ["#…", "#shorts"]},
  "instagram": {"caption": "…", "tags": ["#…"]},
  "facebook":  {"text": "…", "tags": ["#…"]},
  "twitter":   {"text": "…", "tags": ["#…"]},
  "threads":   {"text": "…", "tags": ["#…"]}
}
```
