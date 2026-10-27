#!/usr/bin/env python3
"""stats.py — what our published Shorts did in the last 24 h / 7 days, per video, per series, per publish hour (owner 2026-10-27).

The daily production reads this BEFORE choosing topics (what is trending on our own channels) and BEFORE scheduling
(which hours actually perform per channel). Free sources only:

  youtube   YouTube Data API v3 `videos.list(statistics)` when YT_API_KEY is set (free quota, 1 unit/call) — views, likes, comments.
            Fallback without a key: the public watch page ("N views") — views only.
  others    Instagram / Facebook / Threads / X expose no public counters. They are filled in when the owner adds
            IG_ACCESS_TOKEN (+ IG_USER_ID) / FB_PAGE_TOKEN (+ FB_PAGE_ID) / THREADS_ACCESS_TOKEN; until then those
            channels keep the researched default slots (config/publishing.json) and the report says so.

Every run appends one snapshot per video to dispatch/stats.json; deltas are computed between snapshots, so 24 h / 7 d
numbers become exact after the first day of runs (publish-sync runs 3×/day).

  python3 tools/stats.py snapshot        # fetch counters, append snapshots, write dispatch/stats_summary.json + dispatch/stats.md
  python3 tools/stats.py report          # recompute the summary/markdown from stored snapshots (no network)
"""
import json, os, re, statistics, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "dispatch/ledger.json"; STORE = ROOT / "dispatch/stats.json"
SUMMARY = ROOT / "dispatch/stats_summary.json"; MD = ROOT / "dispatch/stats.md"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) thequizwire-stats/1.0"}
NOW = datetime.now(timezone.utc)
AUDIENCE_TZ = ZoneInfo(json.loads((ROOT / "config/publishing.json").read_text()).get("buffer", {}).get("scheduling", {}).get("audience_tz", "America/New_York"))
MIN_VIDEOS_FOR_HOURS = 8          # below this, hour-of-day stats are noise → keep researched defaults


def get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r: return r.read().decode("utf-8", "replace")


def yt_id(link):
    m = re.search(r"(?:shorts/|watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})", link or ""); return m.group(1) if m else None


def published_videos():
    """YouTube posts in the ledger that went out: video id, episode, series, sent time."""
    out = []
    for p in json.loads(LEDGER.read_text()).get("posts", []):
        if p.get("platform") != "youtube" or p.get("state") != "sent": continue
        vid = yt_id(p.get("external_link"))
        if not vid: continue
        out.append({"video_id": vid, "episode": p["episode"], "series": series_of(p["episode"]), "sent_at": p.get("sent_at") or p.get("due_at")})
    return out


def series_of(name):
    for ej in ROOT.glob(f"series/*/{name}/episode.json"): return ej.parent.parent.name
    return "?"


def fetch_youtube(ids):
    key = os.environ.get("YT_API_KEY")
    stats = {}
    if key:
        for i in range(0, len(ids), 50):
            q = urllib.parse.urlencode({"part": "statistics", "id": ",".join(ids[i:i + 50]), "key": key})
            try:
                for it in json.loads(get("https://www.googleapis.com/youtube/v3/videos?" + q)).get("items", []):
                    s = it["statistics"]; stats[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)) if "likeCount" in s else None, "comments": int(s.get("commentCount", 0)) if "commentCount" in s else None}
            except Exception as ex: print(f"stats: YouTube API failed ({ex}) — falling back to public pages", file=sys.stderr)
    for vid in ids:
        if vid in stats: continue
        try:
            html = get(f"https://www.youtube.com/watch?v={vid}")
            m = re.search(r'"videoViewCountRenderer":\{"viewCount":\{"simpleText":"([\d,\.]+)', html) or re.search(r'"viewCount":"(\d+)"', html)
            if m: stats[vid] = {"views": int(re.sub(r"[^\d]", "", m.group(1)) or 0), "likes": None, "comments": None}
        except Exception as ex: print(f"stats: {vid}: {ex}", file=sys.stderr)
    return stats


def load_store():
    return json.loads(STORE.read_text()) if STORE.exists() else {"version": 1, "snapshots": []}


def value_at(snaps, when):
    """Views at the snapshot closest to `when` (within ±6 h), else None."""
    best = None
    for s in snaps:
        t = datetime.fromisoformat(s["t"]); d = abs((t - when).total_seconds())
        if d <= 6 * 3600 and (best is None or d < best[0]): best = (d, s["views"])
    return best[1] if best else None


def summarise(store, videos):
    by_vid = {}
    for s in store["snapshots"]: by_vid.setdefault(s["video_id"], []).append(s)
    rows = []
    for v in videos:
        snaps = sorted(by_vid.get(v["video_id"], []), key=lambda s: s["t"])
        if not snaps: continue
        now_v = snaps[-1]["views"]; sent = datetime.fromisoformat(v["sent_at"].replace("Z", "+00:00"))
        age_h = (NOW - sent).total_seconds() / 3600
        v24 = value_at(snaps, NOW - timedelta(hours=24)); v7 = value_at(snaps, NOW - timedelta(days=7))
        first24 = None                                                        # views in the first 24 h after publish (slot quality)
        if age_h >= 24:
            a = value_at(snaps, sent + timedelta(hours=24)); b = value_at(snaps, sent)
            first24 = (a - (b or 0)) if a is not None else (now_v if age_h <= 36 else None)
        rows.append({**v, "views": now_v, "likes": snaps[-1].get("likes"), "comments": snaps[-1].get("comments"),
                     "age_h": round(age_h, 1), "views_24h": (now_v - v24) if v24 is not None else (now_v if age_h <= 24 else None),
                     "views_7d": (now_v - v7) if v7 is not None else (now_v if age_h <= 24 * 7 else None),
                     "first24": first24, "sent_hour_local": sent.astimezone(AUDIENCE_TZ).hour, "sent_weekday": sent.astimezone(AUDIENCE_TZ).strftime("%a")})
    # per series: median 24 h views and total 7 d — what is trending on OUR channel
    series = {}
    for r in rows:
        s = series.setdefault(r["series"], {"videos": 0, "views_24h": [], "views_7d": 0, "views": 0})
        s["videos"] += 1; s["views"] += r["views"]
        if r["views_24h"] is not None: s["views_24h"].append(r["views_24h"])
        if r["views_7d"] is not None: s["views_7d"] += r["views_7d"]
    for s in series.values(): s["median_24h"] = statistics.median(s["views_24h"]) if s["views_24h"] else None; s.pop("views_24h")
    # per publish hour (audience tz): median first-24 h views → best hours when we have enough videos
    hours = {}
    for r in rows:
        if r["first24"] is not None: hours.setdefault(r["sent_hour_local"], []).append(r["first24"])
    n_hours = sum(len(v) for v in hours.values())
    hour_table = {h: {"n": len(v), "median_first24": statistics.median(v)} for h, v in sorted(hours.items())}
    best_hours = None
    if n_hours >= MIN_VIDEOS_FOR_HOURS:
        ranked = sorted(hour_table.items(), key=lambda kv: (-kv[1]["median_first24"], -kv[1]["n"]))
        best_hours = [f"{h:02d}:00" for h, _ in ranked[:2]]
    top = sorted(rows, key=lambda r: (-(r["views_24h"] if r["views_24h"] is not None else -1), -r["views"]))[:5]
    return {"generated_at": NOW.isoformat(timespec="seconds"), "audience_tz": str(AUDIENCE_TZ), "videos": len(rows),
            "channels": {"youtube": {"source": "api" if os.environ.get("YT_API_KEY") else "public-page", "best_hours": best_hours, "hour_table": hour_table, "videos_with_first24": n_hours},
                         "instagram": {"source": None, "needs": "IG_ACCESS_TOKEN + IG_USER_ID"}, "facebook": {"source": None, "needs": "FB_PAGE_TOKEN + FB_PAGE_ID"},
                         "threads": {"source": None, "needs": "THREADS_ACCESS_TOKEN"}, "twitter": {"source": None, "needs": "X API (paid) — not planned"}},
            "series": series, "top_24h": [{k: r[k] for k in ("episode", "series", "views_24h", "views")} for r in top], "rows": rows}


def write_md(S):
    L = [f"# Channel stats — {S['generated_at'][:16]}Z (audience tz {S['audience_tz']})", "",
         f"YouTube: {S['videos']} published Shorts tracked · source {S['channels']['youtube']['source']} · "
         f"{S['channels']['youtube']['videos_with_first24']} with first-24 h data (hour learning starts at {MIN_VIDEOS_FOR_HOURS}).", "",
         "## What moved in the last 24 h (our channel — this is what is trending for us)"]
    for r in S["top_24h"]: L.append(f"- {r['episode']} ({r['series']}): +{r['views_24h'] if r['views_24h'] is not None else '?'} in 24 h · {r['views']} total")
    L += ["", "## Per series (7 days)"]
    for k, v in sorted(S["series"].items(), key=lambda kv: -(kv[1]["views_7d"] or 0)):
        L.append(f"- {k}: {v['videos']} videos · {v['views_7d']} views in 7 d · median 24 h {v['median_24h']}")
    L += ["", "## Best publish hours (first-24 h views by hour published, audience tz)"]
    yt = S["channels"]["youtube"]
    for h, v in yt["hour_table"].items(): L.append(f"- {int(h):02d}:00 — n={v['n']} · median first-24 h {v['median_first24']}")
    L.append(f"- → YouTube slots: {yt['best_hours'] or 'not enough data yet — researched defaults in use'}")
    for c in ("instagram", "facebook", "threads", "twitter"):
        L.append(f"- {c}: no counters without {S['channels'][c]['needs']} — researched defaults in use")
    L += ["", "## Every video", "", "| episode | series | sent (local) | views | 24 h | 7 d | first 24 h |", "|---|---|---|---|---|---|---|"]
    for r in sorted(S["rows"], key=lambda r: r["sent_at"], reverse=True):
        L.append(f"| {r['episode']} | {r['series']} | {r['sent_weekday']} {r['sent_hour_local']:02d}:00 | {r['views']} | {r['views_24h']} | {r['views_7d']} | {r['first24']} |")
    MD.write_text("\n".join(L) + "\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    videos = published_videos(); store = load_store()
    if cmd == "snapshot":
        got = fetch_youtube([v["video_id"] for v in videos]); t = NOW.isoformat(timespec="seconds")
        for v in videos:
            if v["video_id"] in got: store["snapshots"].append({"t": t, "video_id": v["video_id"], **got[v["video_id"]]})
        STORE.write_text(json.dumps(store, indent=0) + "\n")
        print(f"stats: {len(got)}/{len(videos)} YouTube videos snapshotted", file=sys.stderr)
    S = summarise(store, videos); SUMMARY.write_text(json.dumps(S, indent=1) + "\n"); write_md(S)
    print(f"stats: {S['videos']} videos · top 24 h: " + ", ".join(f"{r['episode']} +{r['views_24h']}" for r in S["top_24h"][:3]), file=sys.stderr)


if __name__ == "__main__": main()
