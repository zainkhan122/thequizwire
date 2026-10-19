# Distribution — rendered reel → Buffer queue → YouTube · Instagram · Facebook · X

Owner ask (2026-10-16): successful renders go to Buffer as **queued** posts; Buffer publishes them in the time slots
already set per channel. Each channel gets its own SEO copy. YouTube Shorts land in their series playlist.

## 1. How it fits the pipeline

```
render.yml (GitHub Actions)                dispatch.yml / render.yml(dispatch=true)                 publish-sync.yml (3×/day)
episode.sh → gates → final.mp4 ─▶ Release ─▶ postkit (SEO copy + lint) ─▶ mediahost (public URL) ─▶ Buffer createPost ─▶ ledger ─▶ Buffer states → ledger
                                                                                                          (addToQueue)         └▶ YouTube playlist + tags (Data API)
                                                                                                                               └▶ prune media sent ≥ 14 d ago
```

| Step | Tool | What it does | Fails closed when |
|---|---|---|---|
| copy | `reelkit/postkit.py build <ep>` | per-channel title/description/caption/hashtags from `episode.json`, the three see-it facts and the research sources; lint (§4) | any lint FAIL |
| host | `reelkit/mediahost.py push <ep> [<ep>…]` | `git push`es every `out/final.mp4` to the public media repo in ONE commit (blob-less sparse clone; the Contents API rejects our 45 MB files), path `media/<sha256:12>/<Stem>.mp4`; `dispatch.sh` then waits once for the Pages deploy and checks every URL serves `video/mp4` | URL not live within 15 min (is Pages enabled?) |
| queue | `reelkit/buffer.py dispatch <ep> --media-url … --live` | one `createPost` per enabled channel, `mode: addToQueue`, `schedulingType: automatic`; records `dispatch/ledger.json` | postkit FAIL · media probe FAIL · queue cap · daily limit · ambiguous response |
| sync | `reelkit/buffer.py status --refresh`, `reelkit/yt_enrich.py run`, `mediahost.py prune --apply` | post states, YouTube playlist/tags, retention | secret missing → stage skipped with a notice |

Entry points: `bash reelkit/dispatch.sh --tag <release> [--live] <ep…>` (what the workflows run) · Actions → **dispatch**
(manual; `live=false` is a complete dry run) · Actions → **render** with `dispatch=true` (queue right after a successful render).
Episodes whose MP4 is not in the release are skipped — a failed render never reaches Buffer.

## 2. Why these choices

* **Queue, not custom times.** `addToQueue` hands the slot choice to Buffer's per-channel schedule (the owner's settings);
  the system never invents a time, so cadence is changed in Buffer, not in code. `buffer.py queue` shows depth; the
  dispatcher defers an episode when a channel already holds ≥ `queue_limit_per_channel` (14) posts or Buffer reports
  `isAtLimit` for the day.
* **Public media repo.** Buffer has no upload endpoint; the asset URL must be public, direct, HTTPS and *stable until the
  post goes out* (Buffer fetches at publish time — a redirecting or expiring URL fails silently later). This repo is
  private (Release assets need a token; Pages is not available for private repos on Free), so media lives in
  `zainkhan122/thequizwire-media` (public, generated files only). Paths are content-addressed: a re-render gets a new URL,
  a queued URL is never overwritten; `robots.txt` disallows `/media/`; prune removes files 2 days after every post using
  them was sent.
* **Idempotent and honest.** `dispatch/ledger.json` (episode × channel → Buffer post id, state, due time) is the duplicate
  guard; before any write the dispatcher also scans the channel's posts for the same media URL and adopts a match. A
  timeout/5xx *after* `createPost` is recorded as `ambiguous` and stops the run — the next run reconciles first. Both
  workflows share one concurrency group so the ledger is never written by two jobs at once. "Scheduled" ≠ "sent": the sync
  job updates states and the `externalLink` (the public URL) once Buffer has published.
* **No model in the copy loop.** Copy is deterministic from the episode files, so the lint is the whole review and a
  re-run is byte-identical. Per-episode overrides live in `episode.json#post` (`title`, `description`, `tags`, `keywords`,
  `youtube_is_ai_generated`).
* **Disclosure.** Narration is a synthetic voice. Instagram gets Buffer's native `isAiGenerated: true`; Facebook (no native
  field in the API) gets a caption line "🎙️ AI narration"; YouTube's altered-content flag stays `false` (it targets
  realistic depictions of people/events, not narrated animated maps) and the description credits "AI narration (Kokoro)".
  Toggle in `config/publishing.json#disclosure`.

## 3. One-time setup (owner, ≈ 10 minutes)

1. **Buffer API key** — Buffer → Settings → API → create a key → GitHub → thequizwire → Settings → Secrets and variables →
   Actions → `BUFFER_API_KEY`. Do not paste it in chat; the workflow never prints it.
2. **Media repo** — create the public repo `thequizwire-media` (empty, public, "Add a README" ticked). Then a fine-grained
   PAT (GitHub → Settings → Developer settings → Fine-grained tokens): repository access = only `thequizwire-media`,
   permissions **Contents: Read and write** (+ **Pages: Read and write** if you want the job to switch Pages on itself), expiry ≤ 1 year → secret `MEDIA_TOKEN`.
   (`mediahost.py setup`, run by the workflow, adds `.nojekyll`/`index.html`/`robots.txt` and enables Pages on `main`; without the Pages
   permission it prints a warning and you enable Pages once by hand: media repo → Settings → Pages → *Deploy from a branch* → `main` / `(root)` → Save.)
3. **Discover channels** — Actions → dispatch → Run workflow with any episode, `live=false`. The preflight step runs
   `buffer.py channels`, prints every connected channel (service · id · name · slots/week) and commits the YouTube,
   Instagram and Facebook ids into `config/publishing.json`. If a service has two channels, set `buffer_id` by hand.
4. **YouTube playlists (optional, §6)** — Google Cloud project → enable *YouTube Data API v3* → OAuth client of type
   *TVs and Limited Input devices* → secrets `YT_CLIENT_ID`, `YT_CLIENT_SECRET`; then `python3 reelkit/yt_enrich.py auth`
   (prints a google.com/device code to approve with the channel's Google account) → secret `YT_REFRESH_TOKEN`.

Go-live: run **dispatch** with `live=true` for the approved pilots (`tag: pilot-v3-all`). From then on, render with
`dispatch=true`, or keep dispatch as a separate, deliberate click — both are supported.

## 4. SEO policy per channel (encoded in `postkit.py`; 2026 guidance)

| | YouTube Shorts | Instagram Reels | Facebook Reels |
|---|---|---|---|
| Title | the question (keyword in CAPS as the channel's house style) + emoji + ` \| <topic> quiz`; ≤ 100 chars (aim 50–80), **no hashtags in the title** | — | — |
| First line | question + "You get 3 seconds to guess — then the map reveals it." (≤ 120 chars: the search snippet) | question + "You get 3 seconds… ⏱️" (≤ 125 chars: visible before *more*) | question + "Guess in 3 seconds — then watch the reveal!" |
| Body | tease line from `post.description`, "✅ In this <topic> Short:" + the three facts, comment prompt (channel's "What was your first guess?"), subscribe line + site, sources, map-data/voice credits | "✅ The answer and three quick facts are in the reel", two facts, comment prompt, follow line | "✅ Answer + three quick facts inside", comment prompt, site, AI-narration line |
| Hashtags | 3–5, **last line of the description** (`#Shorts` + 2 series + 1 episode + brand) | 3–5 at the end of the caption (series + `#QuizReels` + episode + brand) | 1–3 |
| Links/sources | in the description | first comment (links are not clickable in captions) | first comment |
| Metadata | `categoryId` per series (Geo/Body 27 Education, Sports 17, Wild 15), `madeForKids false`, `notifySubscribers true`, `privacy public`, `embeddable`, `license youtube` | `type reel`, `shouldShareToFeed true`, `isAiGenerated true`, cover frame `thumbnailOffset 2000 ms` | `type reel` |
| Lint | title ≤ 100 (warn > 85, < 30), no `#` in title, ≤ 2 emoji, first line ≤ 120, 3–5 tags as the last line, ≤ 5000 chars | caption ≤ 2200, hook ≤ 125, 3–5 tags, URL warning | ≤ 1000 chars, 1–3 tags |
| Always | no "next video / tomorrow" tease (owner rule); hashtags `#[A-Za-z0-9_]{2,40}`; an answer must exist | | |

Sources behind the rules: YouTube Help (hashtags: > 15 → all ignored; up to three shown above the title; Shorts are
detected by aspect/length, not by `#Shorts`), YouTube Data API category list (as mirrored in Buffer's schema),
Instagram's 2025–26 guidance toward few relevant hashtags and keyword-rich captions (a 5-hashtag cap is being tested),
Buffer API docs (Hosting Media; createPost examples; YouTube/Instagram/Facebook metadata inputs — schema snapshot
2026-10-10). Hashtag sets and keywords per series are in `config/publishing.json#series`.

## 5. Operating rules

* Dispatch only what passed every gate **and** the owner's review for a new look; pilots go live by an explicit `live=true` run.
* Never edit a queued post's copy here — edit in Buffer; the ledger entry stays (re-dispatch is a no-op for that channel).
* To re-queue after a re-render: mark the old ledger rows `"state": "abandoned"` (and delete the Buffer post if it is still
  scheduled), then dispatch again — the new render has a new media URL.
* Monthly budget: dispatch ≈ 2 min, sync ≈ 1 min × 3/day ≈ 90 min/month on the private-repo Actions allowance.
* Media repo budget 900 MB (`media.max_site_bytes`); a 10 Mbps master is ~45 MB per 40 s, kept until every channel's post is sent + 2 days → ≤ 14 queued per channel × 45 MB ≈ 630 MB. GitHub Pages bandwidth: 3 fetches × 60 videos × 45 MB ≈ 8 GB/month of the 100 GB soft limit.

## 6. YouTube playlists and tags (gap in Buffer)

Buffer's `YoutubePostMetadataInput` has `title, categoryId, privacy, madeForKids, notifySubscribers, embeddable, license,
isAiGenerated` — **no playlist and no tags**. `reelkit/yt_enrich.py run` (in publish-sync) takes every ledger row that is
`sent` on YouTube, resolves the video id from Buffer's `externalLink` (fallback: unique exact-title match among the last
50 uploads), creates the series playlist on first use (titles in `config/publishing.json#series.*.playlist`; ids are
written back), inserts the video, and adds backend tags (`postkit.youtube.keywords`) without touching title,
description or privacy. ≈ 110 quota units per video of the 10,000/day default. Until the OAuth secrets exist the step is
skipped with a notice and nothing else is affected.

## 7. Files

`config/publishing.json` (ids, caps, disclosure, series SEO sets) · `reelkit/postkit.py` · `reelkit/buffer.py` ·
`reelkit/mediahost.py` · `reelkit/yt_enrich.py` · `reelkit/dispatch.sh` · `.github/workflows/dispatch.yml` ·
`.github/workflows/publish-sync.yml` · `render.yml` (`dispatch` input) · `dispatch/ledger.json` (generated, committed).

## X (Twitter)

The Buffer organisation also has X `@thequizwire`. `postkit.py` builds an X variant (question + CTA, ≤ 260 weighted chars, 1–2 hashtags:
series + brand) and `buffer.py` queues it with the same MP4 (`metadata.twitter.isAiGenerated true`; X's video limit is 140 s / 512 MB, a
35 s Short is fine). Channel key is `twitter` (Buffer's service name); disable with `buffer.channels.twitter.enabled=false` or leave it
out of `--channels`.

## Two Buffer logins, Free-plan limits (learned on the first live dispatch, 2026-10-16)

* **Channels live in two Buffer logins** (Buffer Free = 3 channels per login): `support@thequizwire.com` → YouTube *TheQuizWire* + Threads;
  `psychwisdomdaily@gmail.com` → Instagram, Facebook, X. One API key per login: secrets `BUFFER_API_KEY` and `BUFFER_API_KEY_2`
  (`config/publishing.json` → `buffer.accounts`). `buffer.py channels` discovers through every key present and records the
  owning account per channel; queue/dispatch/status always use the owning key (a key never queries another login's channels).
* **First comment is a paid feature** (`InvalidInputError: First comment requires a paid plan`) → `buffer.first_comment=false`:
  the sources/credits line goes into the Instagram/Facebook caption (before the hashtags). Flip to `true` after upgrading.
* **Rate limit**: ~10 createPost + scans within minutes on one key → HTTP 429 with `Retry-After` of 4–6 min. The client sleeps
  through waits ≤ 8 min; `buffer.py dispatch` takes all episodes in ONE process (one post scan + limits query per account) and
  the duplicate scan is bounded to `buffer.dedupe_window_days` (14) so logins with years of history stay cheap.
* **Cadence is Buffer's posting schedule, not ours** (`addToQueue`): with 7–8 slots/day per channel the 10 pilots went out over
  two days. Thin the slots in Buffer (Settings → Posting schedule); queued posts re-flow automatically.
* **GitHub side**: the Contents API rejects ~45 MB files (422) → media is `git push`ed from a blob-less sparse clone, all episodes
  in one commit (one Pages deploy); a `MEDIA_TOKEN` without the Pages permission cannot switch Pages on → enable once by hand.

## Best-time scheduling (2026-10-17)
`config/publishing.json → buffer.scheduling` (`mode: best_times`) replaces plain queueing: each post is created with
`mode: customScheduled` + `dueAt` = the next free slot from the per-platform `times` table in `audience_tz`
(default America/New_York — the channel's hashtags target the US; change it once YouTube/IG analytics show the real
audience). Slots already holding a scheduled/sent post (Buffer scan + ledger) are skipped, and a `min_gap_hours`
spacing is kept per channel. `mode: queue` restores Buffer's own posting-plan slots.

## Cover (2026-10-17)
`dispatch.sh` renders `reelkit/cover.py` per episode (hook headline, series tint, sticker side rotate per episode;
authors can pin them in `episode.json → post.cover`), burns it in as the first 0.3 s of `out/final.mp4` (so frame 0 —
the auto-cover on IG/FB/X/Threads, `thumbnailOffset 0`) and attaches `<stem>_cover.jpg` to the release for the YouTube
thumbnail (manual upload until the `YT_*` secrets exist; then `yt_enrich.py thumbnails.set`).


## Rule (owner 2026-10-19): one cover per Short, set on YouTube
YouTube picks a random frame for Shorts unless a thumbnail is set, and a random frame of a map quiz rarely makes sense.
Every episode therefore ships its own style-B cover (`reelkit/cover.py`, `<stem>_cover.jpg` on the release and burned in as frame 0),
and the cover MUST be set as the YouTube thumbnail: automatically via `tools/yt_enrich.py thumbnails.set` once the `YT_*` secrets exist,
until then by hand in YouTube Studio from the cover zip the agent delivers with each batch. `dispatch.sh` fails an episode without a cover.
Never alter or re-create posts that are already scheduled or sent; copy/cover rules apply to future videos only.
