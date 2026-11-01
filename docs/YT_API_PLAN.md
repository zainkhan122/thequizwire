# YouTube Data API v3 — covers as thumbnails + Shorts into playlists

Status 2026-11-01: Phases B, C, E BUILT (`2dc35c4`, `9b38c35`, +guard rails). Phase A (owner OAuth) OPEN → then Phase D (first live run + backfill). Builds on `reelkit/yt_enrich.py`, which already does
playlists + tags and is wired into `publish-sync.yml` but idle until the `YT_*` secrets exist.

## 0. What the official docs say (checked 2026-11-01, pages "last updated 2026-10-15")

| Item | Official value | Source |
|---|---|---|
| Thumbnail endpoint | `POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=…` (media upload; **note the `/upload/` host path**) | developers.google.com/youtube/v3/docs/thumbnails/set |
| Thumbnail body | raw image bytes, `image/jpeg` / `image/png` / `application/octet-stream`; max **50 MB** (API) — YouTube Studio's own rule is 2 MB, so we stay under 2 MB | same |
| Thumbnail scopes | any of `youtube`, `youtube.upload`, `youtube.force-ssl`, `youtubepartner` | same |
| Thumbnail errors | `400 invalidImage`, `403 forbidden` (channel not allowed custom thumbnails = **phone-unverified channel**), `404 videoNotFound`, **`429 uploadRateLimitExceeded`** ("too many thumbnails recently — retry later") | same |
| Playlist add | `POST https://www.googleapis.com/youtube/v3/playlistItems?part=snippet` body `snippet.playlistId` + `snippet.resourceId{kind:"youtube#video",videoId}`; optional `snippet.position` (only if playlist ordering is Manual, else `400 manualSortRequired`) | developers.google.com/youtube/v3/docs/playlistItems/insert |
| Playlist errors | `403 playlistContainsMaximumNumberOfVideos` (5,000), `403 playlistItemsNotAccessible`, `400 videoAlreadyInAnotherSeriesPlaylist`, `400 playlistOperationUnsupported` (the Uploads playlist), `404 playlistNotFound/videoNotFound` | same |
| Quota | default **10,000 units/day** shared bucket; `thumbnails.set` 50, `playlistItems.insert` 50, `playlists.insert` 50, `videos.update` 50, every `*.list` 1. Since mid-2026 `videos.insert` and `search.list` have their own 100/day buckets (not used here) | developers.google.com/youtube/v3/getting-started#quota; determine-quota-cost |
| Shorts | no Shorts flag or endpoint: a Short is a ≤ 3 min vertical video; every call above applies unchanged | docs + owner note |
| Where a custom thumbnail shows | channel page, search, subscriptions feed, embeds, playlists. **Not** in the swipe feed (plays the video) | owner note; YouTube Help |

Our cover (`<stem>_cover.jpg`, 1080×1920 JPG from `reelkit/cover.py`) is accepted as is; YouTube centre-crops it to 16:9
where it needs a wide thumbnail and uses the vertical in the Shorts shelf.

## 1. Design decisions (with reasons)

1. **One worker, one scope.** Extend `yt_enrich.py` instead of a new tool: it already owns OAuth, the ledger join
   (Buffer `externalLink` → video id), playlists and tags. Scope stays `https://www.googleapis.com/auth/youtube` — it covers
   thumbnails, playlists and videos.update, so the owner authorises once.
2. **Per-video steps are independent and idempotent.** Ledger row gains `yt_thumbnail_at`, `yt_playlist_item_id`,
   `yt_tags_at`. A rerun only does the steps that are missing; the playlist step first checks `playlistItems.list
   (videoId, playlistId)` (1 unit) so a lost response never duplicates an item.
3. **Order per video:** thumbnail → playlist → tags. The thumbnail is the user-visible win and the most rate-limited call,
   so it goes first while budget is fresh; tags last (least visible).
4. **Quota budget guard.** `config/publishing.json#youtube_api.daily_units_cap = 6000` (60 % of 10,000, leaves room for
   publish-sync's other reads and for manual Studio work). The worker keeps `dispatch/yt_quota.json` `{date, units}` and
   stops cleanly with a `::notice` when the cap is reached; the next run continues. Cost per new video ≈ 50 + 1 + 50 + 50
   = ~151 units → 2–3 Shorts/day ≈ 450 units; the 30-video backfill ≈ 4,500 units.
5. **Thumbnail rate limit.** `429 uploadRateLimitExceeded` → stop thumbnails for this run (not the whole run), leave rows
   un-stamped, continue with playlists/tags. Backfill is capped at `thumbnails_per_run = 12` to stay clear of it; with
   publish-sync 3×/day the backfill completes in one day.
6. **Only sent + processed videos.** Rows must be `state: sent` with an `external_link` and `sent_at` ≥ 10 min ago
   (Buffer's upload is still processing for a few minutes; `thumbnails.set` on a processing video can 404/403).
7. **Never touch public copy.** `videos.update` re-sends the existing snippet (title/description/categoryId) + tags only,
   as today. No privacy, no madeForKids changes.
8. **Cover source.** Prefer the GitHub release asset `<tag>/<stem>_cover.jpg` (already uploaded by `dispatch.sh`); fall
   back to regenerating from the episode with `cover.py --jpg` (deterministic). Assert < 2 MB and JPEG before upload.
9. **Playlists.** Per-series playlists as already configured (`series.*.playlist`, ids written back to
   `config/publishing.json`) **plus** one channel-wide "TheQuizWire · Daily Map Quiz" playlist so the channel page has a
   single binge list. Two inserts per video (+50 units). Position not set (default ordering).
10. **OAuth consent in "Production", not "Testing".** In Testing status Google expires refresh tokens after 7 days; moving
    the consent screen to Production (unverified is fine for the owner's own channel; shows a warning once during the grant)
    makes the refresh token durable. This is the #1 cause of "it worked for a week then died".

## 2. Phases (each ≤ 15 min agent work; one commit each)

### Phase A — owner one-time setup (≈ 15 min, cannot be automated)
1. Google Cloud → new project `thequizwire-yt` → enable **YouTube Data API v3**.
2. OAuth consent screen: External → fill name/support email → **Publish app** (Production).
3. Credentials → OAuth client → type **TVs and Limited Input devices** → copy client id/secret.
4. On a machine with the repo: `YT_CLIENT_ID=… YT_CLIENT_SECRET=… python3 reelkit/yt_enrich.py auth` → open the printed
   google.com/device URL, sign in as the **TheQuizWire channel's Google account**, paste the refresh token it prints.
5. GitHub → repo secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. YouTube Studio → Settings → Channel → Feature eligibility: confirm **phone verified** (required for custom thumbnails).
Done-check: `python3 reelkit/yt_enrich.py whoami` prints the channel title + playlist count (Phase B adds this command).

### Phase B — worker: thumbnails + budget + whoami (agent) — DONE
- `yt_enrich.py`: add `set_thumbnail(video_id, jpg_bytes)` using the `/upload/` endpoint with `uploadType=media`,
  `Content-Type: image/jpeg`; `whoami` (channels.list mine, 1 unit); quota file + cap; `thumbnails_per_run`; the 10-minute
  processing guard; per-step ledger stamps; `playlistItems.list` pre-check; channel-wide playlist.
- `cover_bytes(row)`: release asset download via `GH_TOKEN` → fallback `cover.py --jpg`.
- Unit tests with a fake HTTP layer (`tests/test_yt_enrich.py`): 429 path, cap path, idempotent rerun, oversize cover.
- Dry run against the ledger: `python3 reelkit/yt_enrich.py run --dry-run` prints the plan and unit estimate.

### Phase C — workflow + config (agent) — DONE (covers are now hosted as `<media_url>_cover.jpg` sidecars for every new Short)
- `publish-sync.yml`: pass `GH_TOKEN` to the step (release asset download); keep the "secrets missing → notice" early exit.
- `config/publishing.json#youtube_api`: `{daily_units_cap: 6000, thumbnails_per_run: 12, min_age_minutes: 10,
  channel_playlist: "TheQuizWire · Daily Map Quiz"}`.
- `docs/DISTRIBUTION.md §6` and `docs/OPERATING_MODEL.md` updated (agent vs Actions: Actions runs it 3×/day; agent only reads the notices).

### Phase D — first live run + backfill (agent, after Phase A)
- `workflow_dispatch publish-sync` → read the step log: `whoami`, units used, per-video lines.
- Backfill the ~30 already-live Shorts over the day's three runs (≤ 12 thumbnails each); verify 3 random videos in Studio.
- Add to `dispatch/stats.md` a one-line "YT API: n thumbnails, n playlist items, units today".

### Phase E — guard rails (agent) — DONE (selftest runs the unit tests + offline dry-run; publish-sync runs `whoami` first; stats.md carries a YouTube API line)
- `reelkit/selftest.yml` case: `yt_enrich.py run --dry-run` on the committed ledger must exit 0 without secrets.
- Alert path: if `whoami` fails with `invalid_grant` (revoked/expired token) → `::error` with the Phase A step-4 command, so
  the daily summary surfaces it instead of silently skipping.

## 3. Run-book (after go-live)

| Situation | Action |
|---|---|
| New Short published by Buffer | nothing — next publish-sync (01:23/09:23/17:23Z) sets the cover, files it into 2 playlists, adds tags |
| `429 uploadRateLimitExceeded` in the log | nothing — the rows stay un-stamped and the next run retries |
| `403 forbidden` on thumbnails for every video | channel not phone-verified → Studio → verify, no code change |
| `invalid_grant` | token revoked or consent screen left in Testing → redo Phase A step 4 (and step 2 if Testing) |
| Quota cap notice daily | raise `daily_units_cap` (max sensible 9,000) or request more quota via the YouTube API Services audit form |
| Cover redesign for an old Short | `python3 reelkit/yt_enrich.py thumb <episode> --force` (Phase B adds `--force` = ignore the stamp) |

## 4. Explicitly out of scope
Uploading via the API (Buffer uploads; `videos.insert` is a separate 100/day bucket and would change the whole pipeline);
comments/pinned comments (`commentThreads.insert`, 50 units — maybe later as "first comment with the question");
Analytics API (stats come from Buffer today; YouTube Analytics API is a different scope/grant and a separate plan).
