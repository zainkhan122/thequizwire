# Editor flow (how every Short is made since 2026-10-20)

No episode is produced from a template. The pipeline forces the order a human editor works in, and CI refuses anything that skips a step.

1. **Brief first** — `series/<series>/<ep>/brief.md` (template: `docs/BRIEF.md`). Hook fact, how we SHOW it, beat order, what makes it different from the previous episode in the series, a swipe test at three timestamps, the devices. Gate **Q19**.
2. **Story, not slots** — the spec (`tools/specs/<ep>.json`) carries `story: [...]`, 2–5 beats. Each beat picks its own devices: counter, bars, compare blocks, route trace, pin hop, map label, flash, mascot face, sticker, card, camera move. `tools/author_v4.py` only turns that into the engine files; it adds nothing of its own except the fixed brand frame (question → options → 3-s beat → reveal → outro).
3. **The look is executed, not labelled** — `variety.opener` and `variety.reveal` change the choreography (`wide-drift`, `mystery-zoom-out`, `split-candidates`, `night-lights`; `fill-pulse`, `flag-lift`, `colour-lift`, `flash-cut`, `route-draw`, `feature-fill`). Gate **Q21** checks the declared look is on the timeline. Pools in `reelkit/quizlint.py` list only what renders.
4. **Anti-sameness** — gate **Q20** fingerprints the device set per story scene; identical shapes within a series, cards-only explanations, or card+sticker-every-beat all FAIL. Q16 still rotates opener/reveal/outro across consecutive episodes.
5. **Preflight locally** (`reelkit/episode.sh <ep> preflight`), **render in CI** (`render.yml`, dispatch=false), then **watch it**: extract frames (opening 0–2 s, each story beat, outro) and fix what looks wrong — overlaps, labels colliding, counters hidden behind characters, bare map edges. Only then `status: ready`.
6. `daily.yml` picks 1–3 ready episodes per day and schedules them; covers come from the release for the YouTube thumbnail.

Fixed by owner decision and therefore identical in every Short: question verbatim as the hook, three option pills with flags, 3-second think time, Kokoro `am_michael`, the TheQuizWire outro (Like / Subscribe, socials, thequizwire.com), no "next video" tease.
