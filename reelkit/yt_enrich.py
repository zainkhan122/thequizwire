#!/usr/bin/env python3
"""YouTube enrichment after Buffer has published a Short: file it into the series PLAYLIST and set backend TAGS.

Buffer's YouTube input carries title/description/category/privacy only — no playlist, no tags (API schema 2026-10-10).
This worker closes that gap with the YouTube Data API v3 and the owner's own OAuth grant (one-time device-code flow):

  python3 reelkit/yt_enrich.py auth               # one-time: prints a google.com/device URL + code; stores nothing — prints the refresh token to save as YT_REFRESH_TOKEN
  python3 reelkit/yt_enrich.py run [--dry-run]    # ledger: sent YouTube posts without yt_video_id → playlist + tags
  python3 reelkit/yt_enrich.py playlists          # list/create the series playlists (ids are written to config/publishing.json)

Secrets (GitHub Actions): YT_CLIENT_ID, YT_CLIENT_SECRET (an OAuth client of type "TVs and Limited Input devices" in the
owner's Google Cloud project with YouTube Data API v3 enabled), YT_REFRESH_TOKEN (from `auth`).
Scope: https://www.googleapis.com/auth/youtube (playlist + video metadata writes). Quota ≈ 110 units per video, 10,000/day.
Public copy is never changed: videos.update re-sends the existing title/description/category and only adds tags.
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config/publishing.json"
LEDGER = ROOT / "dispatch/ledger.json"
API = "https://www.googleapis.com/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube"
UA = "TheQuizWire-reelkit/1"


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http(method, url, data=None, headers=None, form=False):
    body = None
    if data is not None: body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    h = {"User-Agent": UA, **(headers or {})}
    if body is not None: h["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            t = resp.read(); return resp.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        t = e.read()
        try: return e.code, json.loads(t)
        except ValueError: return e.code, {"raw": t[:300].decode(errors="replace")}


def creds():
    cid, sec, rt = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and sec): sys.exit("yt_enrich: YT_CLIENT_ID / YT_CLIENT_SECRET missing")
    return cid, sec, rt


def access_token():
    cid, sec, rt = creds()
    if not rt: sys.exit("yt_enrich: YT_REFRESH_TOKEN missing — run `yt_enrich.py auth` once")
    st, d = http("POST", "https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "refresh_token": rt, "grant_type": "refresh_token"}, form=True)
    if st != 200 or "access_token" not in d: sys.exit(f"yt_enrich: token refresh failed ({st}): {d.get('error_description') or d}")
    return d["access_token"]


class YT:
    def __init__(self, dry=False):
        self.tok = access_token(); self.dry = dry; self.units = 0

    def call(self, method, path, params=None, data=None, cost=1):
        url = f"{API}/{path}?{urllib.parse.urlencode(params or {}, doseq=True)}"
        if self.dry and method != "GET":
            print(f"   DRY {method} {path} {json.dumps(data)[:160]}"); return {}
        for i in range(3):
            st, d = http(method, url, data, {"Authorization": f"Bearer {self.tok}"})
            self.units += cost
            if st in (200, 204): return d
            if st in (403, 429) and "quota" in json.dumps(d).lower(): sys.exit(f"yt_enrich: quota exhausted — {d.get('error', {}).get('message', '')}")
            if st >= 500 and i < 2: time.sleep(3 * (i + 1)); continue
            raise RuntimeError(f"{method} {path} → {st}: {json.dumps(d)[:300]}")
        raise RuntimeError("retries exhausted")

    def uploads_playlist(self):
        d = self.call("GET", "channels", {"part": "contentDetails", "mine": "true"})
        return d["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def recent_uploads(self, n=50):
        d = self.call("GET", "playlistItems", {"part": "snippet", "playlistId": self.uploads_playlist(), "maxResults": n})
        return [(i["snippet"]["resourceId"]["videoId"], i["snippet"]["title"], i["snippet"]["publishedAt"]) for i in d.get("items", [])]

    def my_playlists(self):
        out, tok = [], None
        while True:
            d = self.call("GET", "playlists", {"part": "snippet", "mine": "true", "maxResults": 50, **({"pageToken": tok} if tok else {})})
            out += [(p["id"], p["snippet"]["title"]) for p in d.get("items", [])]
            tok = d.get("nextPageToken")
            if not tok: return out

    def create_playlist(self, title, description):
        d = self.call("POST", "playlists", {"part": "snippet,status"}, {"snippet": {"title": title, "description": description}, "status": {"privacyStatus": "public"}}, cost=50)
        return d.get("id", "<dry>")

    def in_playlist(self, pid, vid):
        d = self.call("GET", "playlistItems", {"part": "id", "playlistId": pid, "videoId": vid, "maxResults": 1})
        return bool(d.get("items"))

    def add_to_playlist(self, pid, vid):
        self.call("POST", "playlistItems", {"part": "snippet"}, {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}, cost=50)

    def add_tags(self, vid, tags):
        d = self.call("GET", "videos", {"part": "snippet", "id": vid})
        if not d.get("items"): return False
        sn = d["items"][0]["snippet"]; have = [t.lower() for t in sn.get("tags", [])]
        new = [t for t in tags if t.lower() not in have]
        if not new: return False
        merged = (sn.get("tags") or []) + new
        while sum(len(t) + 2 for t in merged) > 480: merged.pop()                   # the tags field is capped at 500 chars
        body = {"id": vid, "snippet": {"title": sn["title"], "description": sn.get("description", ""), "categoryId": sn.get("categoryId", "27"), "tags": merged,
                                       **({"defaultLanguage": sn["defaultLanguage"]} if sn.get("defaultLanguage") else {})}}
        self.call("PUT", "videos", {"part": "snippet"}, body, cost=50); return True


def video_id_from(link):
    if not link: return None
    m = urllib.parse.urlparse(link)
    if "youtu.be" in m.netloc: return m.path.strip("/").split("/")[0] or None
    if "/shorts/" in m.path: return m.path.split("/shorts/")[1].split("/")[0]
    q = urllib.parse.parse_qs(m.query); return (q.get("v") or [None])[0]


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


def cmd_playlists(a):
    c = json.loads(CFG_PATH.read_text()); yt = YT(a.dry_run)
    have = {t: i for i, t in yt.my_playlists()}
    for slug, S in c["series"].items():
        title = S["playlist"]
        pid = S.get("playlist_id") or have.get(title)
        if not pid:
            pid = yt.create_playlist(title, f"{S['name']} — a new {S['topic']} every day from TheQuizWire. More at {c['channel']['site']}")
            print(f"   created playlist {title!r} → {pid}")
        else:
            print(f"   {title!r} → {pid}")
        if pid and not pid.startswith("<"): S["playlist_id"] = pid
    if not a.dry_run: CFG_PATH.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n")
    print(f"yt_enrich: playlists ok · {yt.units} quota units")


def cmd_run(a):
    c = json.loads(CFG_PATH.read_text()); L = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"posts": []}
    todo = [p for p in L["posts"] if p["platform"] == "youtube" and p.get("state") == "sent" and not p.get("enriched_at")]
    if not todo: print("yt_enrich: nothing to do"); return
    yt = YT(a.dry_run); uploads = None
    for p in todo:
        ep = p["episode"]; slug = next((s for s in c["series"] if (ROOT / "series" / s / ep).exists()), None)
        S = c["series"].get(slug) if slug else None
        if not S: print(f"   {ep}: series unknown — skip"); continue
        vid = p.get("yt_video_id") or video_id_from(p.get("external_link"))
        if not vid:
            uploads = uploads or yt.recent_uploads()
            title = p.get("title") or ""
            hit = [v for v, t, _ in uploads if t.strip() == title.strip()]
            vid = hit[0] if len(hit) == 1 else None
        if not vid: print(f"   {ep}: video id not found yet (no externalLink, no unique title match) — retry later"); continue
        pid = S.get("playlist_id")
        if not pid:
            have = {t: i for i, t in yt.my_playlists()}; pid = have.get(S["playlist"]) or yt.create_playlist(S["playlist"], f"{S['name']} — a new {S['topic']} every day from TheQuizWire.")
            if not pid.startswith("<"): S["playlist_id"] = pid
        added = False
        if not yt.in_playlist(pid, vid): yt.add_to_playlist(pid, vid); added = True
        kit = ROOT / "series" / slug / ep / "out/postkit.json"
        tags = (json.loads(kit.read_text())["youtube"].get("keywords") if kit.exists() else None) or S.get("keywords", [])
        tagged = yt.add_tags(vid, tags) if tags else False
        p.update({"yt_video_id": vid, "yt_playlist_id": pid, "enriched_at": now(), "playlist_added": added, "tags_added": tagged})
        print(f"   {ep}: video {vid} → playlist {pid} ({'added' if added else 'already in'}) · tags {'added' if tagged else 'unchanged'}")
    if not a.dry_run:
        LEDGER.write_text(json.dumps(L, indent=1, ensure_ascii=False) + "\n"); CFG_PATH.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n")
    print(f"yt_enrich: {len(todo)} candidate(s) · {yt.units} quota units")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("auth")
    for n in ("run", "playlists"): sp.add_parser(n).add_argument("--dry-run", action="store_true")
    a = ap.parse_args(); {"auth": cmd_auth, "run": cmd_run, "playlists": cmd_playlists}[a.cmd](a)


if __name__ == "__main__":
    main()
