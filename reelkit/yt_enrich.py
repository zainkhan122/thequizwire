#!/usr/bin/env python3
"""YouTube enrichment after Buffer has published a Short: COVER as the custom thumbnail, the Short into its SERIES playlist
and the channel-wide playlist, backend TAGS. YouTube Data API v3 with the owner's own OAuth grant (docs/YT_API_PLAN.md).

Buffer's YouTube input carries title/description/category/privacy only — no thumbnail, no playlist, no tags (API schema
2026-10-10). This worker closes the gap. Shorts are ordinary videos to the API (no Shorts endpoint, no flag).

  python3 reelkit/yt_enrich.py auth                  # one-time device-code flow; prints the refresh token to save as YT_REFRESH_TOKEN
  python3 reelkit/yt_enrich.py whoami                # channel title, subscriber/video counts, playlist count, quota used today (1 unit)
  python3 reelkit/yt_enrich.py playlists [--dry-run] # ensure the series playlists + the channel playlist exist (ids → config/publishing.json)
  python3 reelkit/yt_enrich.py run [--dry-run]       # ledger: every sent YouTube post → thumbnail → playlists → tags (each step idempotent)
  python3 reelkit/yt_enrich.py thumb <episode> [--force]   # (re)set one Short's thumbnail, e.g. after a cover redesign

Secrets (GitHub Actions): YT_CLIENT_ID, YT_CLIENT_SECRET (OAuth client of type "TVs and Limited Input devices" in a Google Cloud
project with YouTube Data API v3 enabled and the consent screen PUBLISHED — in "Testing" refresh tokens die after 7 days),
YT_REFRESH_TOKEN (from `auth`). One scope, https://www.googleapis.com/auth/youtube, covers all three writes.
Optional GH_TOKEN: lets the cover fall back to the GitHub release asset for Shorts published before covers were hosted.

Quota (official: 10,000 units/day shared): thumbnails.set 50 · playlistItems.insert 50 · videos.update 50 · every list 1.
≈ 153 units per new Short (thumb 50 + 2 playlist checks 2 + 2 inserts 100 + tags read 1 → 50). Guarded by
config/publishing.json#youtube_api.daily_units_cap and dispatch/yt_quota.json; the run stops cleanly at the cap and resumes next time.
Thumbnails are additionally capped per run (uploadRateLimitExceeded is a documented 429) and only attempted ≥ min_age_minutes
after Buffer reports `sent` (the upload is still processing for a few minutes).

Without secrets, `run --dry-run` prints the plan offline (used by selftest). Public copy is never changed: videos.update re-sends the
existing title/description/category and only adds tags.
"""
import argparse, json, os, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config/publishing.json"
LEDGER = ROOT / "dispatch/ledger.json"
QUOTA = ROOT / "dispatch/yt_quota.json"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube"
UA = "TheQuizWire-reelkit/2"
DEFAULTS = {"daily_units_cap": 6000, "thumbnails_per_run": 12, "min_age_minutes": 10, "max_cover_bytes": 2_000_000,
            "channel_playlist": "TheQuizWire · Daily Map Quiz", "channel_playlist_id": None, "thumbnails": True}


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def today(): return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class Budget(Exception): pass          # daily cap reached — stop cleanly, resume next run
class RateLimited(Exception): pass     # 429 uploadRateLimitExceeded — stop thumbnails for this run only
class Forbidden(Exception): pass       # 403 on thumbnails — channel cannot set custom thumbnails (phone verification)


def http(method, url, data=None, headers=None, form=False, raw=None):
    """Returns (status, json|{}). `raw` = (bytes, content_type) for media uploads."""
    body = None; h = {"User-Agent": UA, **(headers or {})}
    if raw is not None: body, h["Content-Type"] = raw[0], raw[1]
    elif data is not None:
        body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            t = resp.read(); return resp.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        t = e.read()
        try: return e.code, json.loads(t)
        except ValueError: return e.code, {"raw": t[:300].decode(errors="replace")}


def fetch(url, limit=60_000_000):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(r, timeout=120) as resp: return resp.status, resp.read(limit + 1)
    except urllib.error.HTTPError as e: return e.code, b""
    except (urllib.error.URLError, TimeoutError): return 0, b""


def cfg():
    c = json.loads(CFG_PATH.read_text()); c.setdefault("youtube_api", {})
    for k, v in DEFAULTS.items(): c["youtube_api"].setdefault(k, v)
    return c


def creds(required=True):
    cid, sec, rt = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), os.environ.get("YT_REFRESH_TOKEN")
    if required and not (cid and sec): sys.exit("yt_enrich: YT_CLIENT_ID / YT_CLIENT_SECRET missing")
    return cid, sec, rt


def access_token():
    cid, sec, rt = creds()
    if not rt: sys.exit("yt_enrich: YT_REFRESH_TOKEN missing — run `yt_enrich.py auth` once")
    st, d = http("POST", "https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "refresh_token": rt, "grant_type": "refresh_token"}, form=True)
    if st != 200 or "access_token" not in d:
        why = d.get("error_description") or d.get("error") or d
        if d.get("error") == "invalid_grant":
            print("::error::YouTube refresh token rejected (invalid_grant): revoked, or the OAuth consent screen is still in 'Testing' (tokens expire after 7 days). "
                  "Publish the consent screen, then re-run `YT_CLIENT_ID=… YT_CLIENT_SECRET=… python3 reelkit/yt_enrich.py auth` and update YT_REFRESH_TOKEN. docs/YT_API_PLAN.md Phase A.")
        sys.exit(f"yt_enrich: token refresh failed ({st}): {why}")
    return d["access_token"]


# ---------------------------------------------------------------- quota ledger
def quota_load():
    q = json.loads(QUOTA.read_text()) if QUOTA.exists() else {}
    return q if q.get("date") == today() else {"date": today(), "units": 0, "runs": 0}


def quota_save(q, extra=None):
    q.update(extra or {}); QUOTA.write_text(json.dumps(q, indent=1) + "\n")


# ---------------------------------------------------------------- API client
class YT:
    def __init__(self, dry=False, offline=False, cap=None):
        self.dry, self.offline, self.units = dry, offline, 0
        self.q = quota_load(); self.cap = cap if cap is not None else DEFAULTS["daily_units_cap"]
        self.tok = None if offline else access_token()

    def spent(self): return self.q["units"] + self.units

    def _charge(self, cost):
        if self.spent() + cost > self.cap: raise Budget(f"daily cap {self.cap} units: {self.spent()} used today")
        self.units += cost

    def call(self, method, path, params=None, data=None, cost=1, raw=None, base=API):
        url = f"{base}/{path}?{urllib.parse.urlencode(params or {}, doseq=True)}"
        if self.offline or (self.dry and method != "GET"):
            print(f"   DRY {method} {path} {('<%d bytes>' % len(raw[0])) if raw else json.dumps(data)[:120]}"); return {}
        self._charge(cost)
        for i in range(3):
            st, d = http(method, url, data, {"Authorization": f"Bearer {self.tok}"}, raw=raw)
            if st in (200, 204): return d
            reason = ((d.get("error") or {}).get("errors") or [{}])[0].get("reason", "")
            msg = json.dumps(d).lower()
            if st in (403, 429) and ("quotaexceeded" in msg or "dailylimitexceeded" in msg): raise Budget(f"API says quota exceeded ({reason})")
            if st == 429 and reason == "uploadRateLimitExceeded": raise RateLimited("thumbnails: uploadRateLimitExceeded")
            if st == 403 and path.startswith("thumbnails"): raise Forbidden(f"thumbnails: {reason or 'forbidden'} — channel may lack custom-thumbnail permission (phone verification)")
            if st >= 500 and i < 2: time.sleep(3 * (i + 1)); continue
            raise RuntimeError(f"{method} {path} → {st}: {json.dumps(d)[:300]}")
        raise RuntimeError("retries exhausted")

    # reads (1 unit)
    def whoami(self):
        d = self.call("GET", "channels", {"part": "snippet,statistics,contentDetails", "mine": "true"})
        return (d.get("items") or [{}])[0]

    def uploads_playlist(self):
        return self.whoami().get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

    def recent_uploads(self, n=50):
        up = self.uploads_playlist()
        if not up: return []
        d = self.call("GET", "playlistItems", {"part": "snippet", "playlistId": up, "maxResults": n})
        return [(i["snippet"]["resourceId"]["videoId"], i["snippet"]["title"], i["snippet"]["publishedAt"]) for i in d.get("items", [])]

    def my_playlists(self):
        out, tok = [], None
        while True:
            d = self.call("GET", "playlists", {"part": "snippet", "mine": "true", "maxResults": 50, **({"pageToken": tok} if tok else {})})
            out += [(p["id"], p["snippet"]["title"]) for p in d.get("items", [])]
            tok = d.get("nextPageToken")
            if not tok: return out

    def in_playlist(self, pid, vid):
        d = self.call("GET", "playlistItems", {"part": "id", "playlistId": pid, "videoId": vid, "maxResults": 1})
        items = d.get("items") or []
        return items[0]["id"] if items else None

    def video(self, vid):
        d = self.call("GET", "videos", {"part": "snippet,status", "id": vid})
        return (d.get("items") or [None])[0]

    # writes (50 units)
    def create_playlist(self, title, description):
        d = self.call("POST", "playlists", {"part": "snippet,status"}, {"snippet": {"title": title, "description": description}, "status": {"privacyStatus": "public"}}, cost=50)
        return d.get("id", "<dry>")

    def add_to_playlist(self, pid, vid):
        d = self.call("POST", "playlistItems", {"part": "snippet"}, {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}, cost=50)
        return d.get("id", "<dry>")

    def set_thumbnail(self, vid, jpg: bytes):
        d = self.call("POST", "thumbnails/set", {"videoId": vid, "uploadType": "media"}, cost=50, raw=(jpg, "image/jpeg"), base=UPLOAD)
        return ((d.get("items") or [{}])[0].get("high") or {}).get("url") or ("<dry>" if self.dry or self.offline else "")

    def add_tags(self, vid, tags, sn=None):
        sn = sn or (self.video(vid) or {}).get("snippet")
        if not sn: return False
        have = [t.lower() for t in sn.get("tags", [])]
        new = [t for t in tags if t.lower() not in have]
        if not new: return False
        merged = (sn.get("tags") or []) + new
        while sum(len(t) + 2 for t in merged) > 480: merged.pop()                   # the tags field is capped at 500 chars
        body = {"id": vid, "snippet": {"title": sn["title"], "description": sn.get("description", ""), "categoryId": sn.get("categoryId", "27"), "tags": merged,
                                       **({"defaultLanguage": sn["defaultLanguage"]} if sn.get("defaultLanguage") else {})}}
        self.call("PUT", "videos", {"part": "snippet"}, body, cost=50); return True


# ---------------------------------------------------------------- helpers
def video_id_from(link):
    if not link: return None
    m = urllib.parse.urlparse(link)
    if "youtu.be" in m.netloc: return m.path.strip("/").split("/")[0] or None
    if "/shorts/" in m.path: return m.path.split("/shorts/")[1].split("/")[0]
    q = urllib.parse.parse_qs(m.query); return (q.get("v") or [None])[0]


def series_of(c, ep):
    return next((s for s in c["series"] if (ROOT / "series" / s / ep).exists()), None)


def is_jpeg(b): return len(b) > 4 and b[:3] == b"\xff\xd8\xff"


def cover_bytes(row, ep_dir, limit, log=print):
    """Cover JPG for a ledger row: hosted sidecar (media_url .mp4 → _cover.jpg) → GitHub release asset → regenerate from the hosted MP4."""
    stem = Path(urllib.parse.urlparse(row.get("media_url") or "").path).stem
    if row.get("media_url"):
        url = row["media_url"][:-4] + "_cover.jpg" if row["media_url"].endswith(".mp4") else None
        if url:
            st, b = fetch(url, limit)
            if st == 200 and is_jpeg(b) and len(b) <= limit: return b, "hosted"
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok and stem:
        repo = os.environ.get("GITHUB_REPOSITORY", "zainkhan122/thequizwire")
        for page in (1, 2, 3):
            st, d = http("GET", f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}", headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
            if st != 200 or not d: break
            for rel in d:
                for a in rel.get("assets", []):
                    if a["name"] == f"{stem}_cover.jpg":
                        st2, b = fetch(a["browser_download_url"], limit)
                        if st2 == 200 and is_jpeg(b) and len(b) <= limit: return b, f"release {rel['tag_name']}"
    if row.get("media_url") and ep_dir and (ep_dir / "episode.json").exists():
        st, mp4 = fetch(row["media_url"])
        if st == 200 and mp4:
            with tempfile.TemporaryDirectory() as td:
                v = Path(td) / "final.mp4"; v.write_bytes(mp4); j = Path(td) / "cover.jpg"
                r = subprocess.run([sys.executable, str(ROOT / "reelkit/cover.py"), str(ep_dir), "--video", str(v), "--jpg", str(j), "--out", str(Path(td) / "cover.png")], capture_output=True, text=True)
                if r.returncode == 0 and j.exists():
                    b = j.read_bytes()
                    if is_jpeg(b) and len(b) <= limit: return b, "regenerated"
                log(f"      cover regen failed: {(r.stderr or r.stdout).strip()[-160:]}")
    return None, "none"


def ensure_playlist(yt, c, title, description, holder, key, cache):
    pid = holder.get(key)
    if pid and not str(pid).startswith("<"): return pid
    if cache.get("_have") is None: cache["_have"] = {t: i for i, t in yt.my_playlists()}
    pid = cache["_have"].get(title) or yt.create_playlist(title, description)
    cache["_have"][title] = pid                                                   # one create per title per run, even in dry mode
    if pid and not str(pid).startswith("<"): holder[key] = pid
    return pid


def resolve_video_id(yt, p, uploads_cache):
    vid = p.get("yt_video_id") or video_id_from(p.get("external_link"))
    if vid: return vid
    if uploads_cache.get("_u") is None: uploads_cache["_u"] = yt.recent_uploads()
    title = (p.get("title") or "").strip()
    hit = [v for v, t, _ in uploads_cache["_u"] if t.strip() == title] if title else []
    return hit[0] if len(hit) == 1 else None


def age_minutes(p):
    t = p.get("sent_at") or p.get("due_at")
    if not t: return 0
    try: return (datetime.now(timezone.utc) - datetime.fromisoformat(t.replace("Z", "+00:00"))).total_seconds() / 60
    except ValueError: return 0


def steps_for(p, A):
    """Which of thumb/series/channel/tags a row still needs. Legacy rows (v1 `enriched_at`) already have series playlist + tags."""
    if p.get("enriched_at") and not p.get("yt_series_item"):
        p["yt_series_item"] = "legacy"; p["yt_tags_at"] = p["enriched_at"]
    s = []
    if A["thumbnails"] and not p.get("yt_thumbnail_at") and not p.get("yt_thumbnail_error"): s.append("thumb")
    if not p.get("yt_series_item"): s.append("series")
    if not p.get("yt_channel_item"): s.append("channel")
    if not p.get("yt_tags_at"): s.append("tags")
    return s


EST = {"thumb": 50, "series": 51, "channel": 51, "tags": 51}


# ---------------------------------------------------------------- commands
def cmd_auth(a):
    cid, sec, _ = creds()
    st, d = http("POST", "https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": SCOPE}, form=True)
    if st != 200: sys.exit(f"device code failed ({st}): {d}")
    print(f"\n1. Open {d['verification_url']}\n2. Enter code: {d['user_code']}\n3. Sign in with the TheQuizWire channel's Google account and allow YouTube access.\n(waiting up to {d['expires_in'] // 60} min)")
    t0 = time.time(); iv = int(d.get("interval", 5))
    while time.time() - t0 < int(d["expires_in"]):
        time.sleep(iv)
        st, r = http("POST", "https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "device_code": d["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, form=True)
        if st == 200 and r.get("refresh_token"):
            print("\nAuthorised. Save this as the GitHub secret YT_REFRESH_TOKEN (shown once, not stored here):\n" + r["refresh_token"] + "\n"); return
        if r.get("error") == "slow_down": iv += 5
        elif r.get("error") not in ("authorization_pending", None): sys.exit(f"auth failed: {r}")
    sys.exit("auth timed out")


def cmd_whoami(a):
    c = cfg(); A = c["youtube_api"]; yt = YT(cap=A["daily_units_cap"])
    ch = yt.whoami(); sn, stt = ch.get("snippet", {}), ch.get("statistics", {})
    pls = yt.my_playlists()
    print(f"channel: {sn.get('title')} ({ch.get('id')}) · {stt.get('subscriberCount')} subs · {stt.get('videoCount')} videos · {len(pls)} playlists")
    for pid, t in pls: print(f"   {pid}  {t}")
    print(f"quota today: {yt.spent()} / {A['daily_units_cap']} units (this call {yt.units})")
    quota_save(yt.q, {"units": yt.spent()})


def cmd_playlists(a):
    c = cfg(); A = c["youtube_api"]; yt = YT(a.dry_run, cap=A["daily_units_cap"]); cache = {}
    for slug, S in c["series"].items():
        pid = ensure_playlist(yt, c, S["playlist"], f"{S['name']} — a new {S['topic']} every day from TheQuizWire. More at {c['channel']['site']}", S, "playlist_id", cache)
        print(f"   {S['playlist']!r} → {pid}")
    pid = ensure_playlist(yt, c, A["channel_playlist"], f"Every TheQuizWire Short in one list — guess before the map reveals it. {c['channel']['site']}", A, "channel_playlist_id", cache)
    print(f"   {A['channel_playlist']!r} → {pid}")
    if not a.dry_run:
        CFG_PATH.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n"); quota_save(yt.q, {"units": yt.spent()})
    print(f"yt_enrich: playlists ok · {yt.units} quota units")


def cmd_thumb(a):
    c = cfg(); A = c["youtube_api"]; L = json.loads(LEDGER.read_text()); ep = Path(a.episode).name
    rows = [p for p in L["posts"] if p["platform"] == "youtube" and p["episode"] == ep and p.get("state") == "sent"]
    if not rows: sys.exit(f"yt_enrich: no sent YouTube post for {ep}")
    p = rows[-1]; yt = YT(a.dry_run, cap=A["daily_units_cap"])
    vid = resolve_video_id(yt, p, {})
    if not vid: sys.exit("yt_enrich: video id unknown")
    if p.get("yt_thumbnail_at") and not a.force: sys.exit(f"yt_enrich: thumbnail already set {p['yt_thumbnail_at']} — use --force")
    slug = series_of(c, ep); b, src = cover_bytes(p, ROOT / "series" / slug / ep if slug else None, A["max_cover_bytes"])
    if not b: sys.exit("yt_enrich: no cover available")
    url = yt.set_thumbnail(vid, b)
    p.update({"yt_video_id": vid, "yt_thumbnail_at": now(), "yt_thumbnail_src": src}); p.pop("yt_thumbnail_error", None)
    if not a.dry_run: LEDGER.write_text(json.dumps(L, indent=1, ensure_ascii=False) + "\n"); quota_save(yt.q, {"units": yt.spent()})
    print(f"   {ep}: thumbnail set from {src} ({len(b) // 1024} KB) → {url}\nyt_enrich: {yt.units} quota units")


def cmd_run(a):
    c = cfg(); A = c["youtube_api"]; L = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"posts": []}
    cid, sec, rt = creds(required=False); offline = a.dry_run and not (cid and sec and rt)
    if offline: print("yt_enrich: no YT_* secrets — offline plan only")
    rows = [p for p in L["posts"] if p["platform"] == "youtube" and p.get("state") == "sent"]
    todo = [(p, steps_for(p, A)) for p in rows]; todo = [(p, s) for p, s in todo if s]
    if not todo: print("yt_enrich: nothing to do"); return
    est = sum(EST[s] for _, ss in todo for s in ss)
    print(f"yt_enrich: {len(todo)} video(s) with work · estimate {est} units · cap {A['daily_units_cap']}/day · thumbnails ≤ {A['thumbnails_per_run']}/run")
    yt = YT(a.dry_run, offline=offline, cap=A["daily_units_cap"]); cache = {}; done = {"thumb": 0, "series": 0, "channel": 0, "tags": 0}
    thumbs_open, stopped = True, None
    try:
        for p, steps in todo:
            ep = p["episode"]; slug = series_of(c, ep); S = c["series"].get(slug) if slug else None
            if not S: print(f"   {ep}: series unknown — skip"); continue
            vid = resolve_video_id(yt, p, cache)
            if not vid: print(f"   {ep}: video id not found yet (no externalLink, no unique title match) — retry later"); continue
            p["yt_video_id"] = vid; out = []
            if "thumb" in steps:
                if age_minutes(p) < A["min_age_minutes"] and not offline: out.append("thumb: too fresh, next run")
                elif not thumbs_open or done["thumb"] >= A["thumbnails_per_run"]: out.append("thumb: deferred (per-run cap)")
                else:
                    b, src = cover_bytes(p, ROOT / "series" / slug / ep, A["max_cover_bytes"]) if not offline else (b"\xff\xd8\xff", "offline")
                    if not b: out.append("thumb: NO COVER (hosted/release/regen all failed)")
                    else:
                        try:
                            yt.set_thumbnail(vid, b); p.update({"yt_thumbnail_at": now(), "yt_thumbnail_src": src}); done["thumb"] += 1; out.append(f"thumb set ({src})")
                        except RateLimited as e: thumbs_open = False; out.append(f"thumb: {e} — rest next run")
                        except Forbidden as e: p["yt_thumbnail_error"] = str(e)[:200]; print(f"::warning::{ep}: {e}"); out.append("thumb: forbidden (see warning)")
            if "series" in steps:
                pid = ensure_playlist(yt, c, S["playlist"], f"{S['name']} — a new {S['topic']} every day from TheQuizWire.", S, "playlist_id", cache)
                item = yt.in_playlist(pid, vid) or yt.add_to_playlist(pid, vid); p.update({"yt_playlist_id": pid, "yt_series_item": item}); done["series"] += 1; out.append("series playlist")
            if "channel" in steps:
                pid = ensure_playlist(yt, c, A["channel_playlist"], f"Every TheQuizWire Short in one list — guess before the map reveals it. {c['channel']['site']}", A, "channel_playlist_id", cache)
                item = yt.in_playlist(pid, vid) or yt.add_to_playlist(pid, vid); p.update({"yt_channel_item": item}); done["channel"] += 1; out.append("channel playlist")
            if "tags" in steps:
                kit = ROOT / "series" / slug / ep / "out/postkit.json"
                tags = (json.loads(kit.read_text())["youtube"].get("keywords") if kit.exists() else None) or S.get("keywords", [])
                tagged = yt.add_tags(vid, tags) if tags else False
                p["yt_tags_at"] = now(); done["tags"] += 1; out.append("tags added" if tagged else "tags unchanged")
            print(f"   {ep} ({vid}): " + " · ".join(out))
    except Budget as e:
        stopped = str(e); print(f"::notice::yt_enrich stopped at the quota cap — {e}; remaining work resumes next run")
    finally:
        if not a.dry_run:
            LEDGER.write_text(json.dumps(L, indent=1, ensure_ascii=False) + "\n"); CFG_PATH.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n")
            quota_save(yt.q, {"units": yt.spent(), "runs": yt.q.get("runs", 0) + 1, "last_run": now()})
    left = sum(1 for p, _ in todo if steps_for(p, A))
    print(f"yt_enrich: thumbnails {done['thumb']} · series items {done['series']} · channel items {done['channel']} · tags {done['tags']} · {yt.units} units this run, {yt.spent()} today · {left} video(s) still pending" + (f" · stopped: {stopped}" if stopped else ""))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("auth"); sp.add_parser("whoami")
    for n in ("run", "playlists"): sp.add_parser(n).add_argument("--dry-run", action="store_true")
    t = sp.add_parser("thumb"); t.add_argument("episode"); t.add_argument("--force", action="store_true"); t.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(); {"auth": cmd_auth, "whoami": cmd_whoami, "run": cmd_run, "playlists": cmd_playlists, "thumb": cmd_thumb}[a.cmd](a)


if __name__ == "__main__":
    main()
