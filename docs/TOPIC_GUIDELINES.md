# Topic guidelines — how a Short earns the right to exist (P1, 2026-10-21)

Owner: *"Each step from topic selection to scheduling must involve a reason / thought process. Guidelines, not templates."*
This file is the guideline. The thought process for one Short is written in `series/<series>/<ep>/topic.md` **before** the
creative brief and the spec. `reelkit/quizlint.py` Q22 refuses an episode whose topic.md is missing, thin, or whose question
repeats a recent stem. `tools/daily_pick.py` schedules by the *Ship by* date in topic.md, not by chance.

## The questions a human editor answers (and the file records)

1. **Signal — why would anyone look for this right now?** One concrete source: a YouTube search suggestion, a trend, a
   Wikipedia most-read page, a date on `config/calendar.json`, a comment on our channel, a news item. Paste the term/URL.
   `tools/signals.py` builds the reading sheet (`review/signals.md`); the editor picks from it or brings their own.
2. **Why this, why now** — the sentence that would convince a sceptical producer. If it is "because it is a fact", stop.
3. **Viewer takeaway** — what the viewer will *feel* they learnt or can repeat to a friend. Written as the viewer would say it.
4. **Question shape** — chosen for the fact, not from habit. Shapes we know work: *which-of-three*, *true-or-false*,
   *odd-one-out*, *guess-the-range* ("more or less than 100?"), *which is bigger*, *before-or-after*, *name-the-shape*,
   *what-happens-if*. Not more than two Shorts in a row in a series with the same shape; never the same stem as the last
   five published (stem = first two words + superlative — "which country most" is dead for a month once used).
5. **Options and why they fool** — each wrong option must be the answer a reasonable person would give. Write the reason.
6. **Search term** — the exact phrase people type (from the suggest list). It drives the title and the tags later (P4).
7. **Rejected alternatives** — at least one other topic considered and why it lost. This is what stops auto-pilot.
8. **Ship by** — the date after which the signal is cold (calendar day, trend week). Daily pick honours it.

## What stays automatic
Count per day (1–3, date-seeded), best-time slots per platform, the CI gates. Everything that is a *choice* is written down.

## topic.md skeleton
```markdown
# <question as it will be asked>

## Signal
<source + term/URL + date seen>

## Why this, why now
…

## Viewer takeaway
"…" (in the viewer's words)

## Question shape
<shape> — why this shape fits this fact

## Options and why they fool
A … · B … · C …

## Search term
"…"

## Rejected alternatives
- … because …

## Ship by
YYYY-MM-DD
```
