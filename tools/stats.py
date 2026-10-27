"""stats.py — what our published Shorts did in the last 24 h / 7 days, per channel, per video, per series, per publish hour
(owner 2026-10-27). The daily production reads this BEFORE choosing topics (what trends on our own channels) and BEFORE
scheduling (which hours perform per channel). ONE source of truth:

  Buffer Insights  Post.metrics through the Buffer GraphQL API, with the same two personal keys the dispatcher already
                   uses (BUFFER_API_KEY / BUFFER_API_KEY_2) — every channel (YouTube, Instagram, Facebook, Threads, X),
                   normalised names: views / impressions / reach / reactions / comments / shares / reposts / saves.
  fallback         YouTube only, when Buffer has no metrics for a post yet (new key without insights scope, or the
                   network has not reported): the public watch page's view counter. Nothing else, no other keys.

Snapshots are appended to dispatch/stats.json (3×/day from publish-sync + before every daily pick); the 24 h / 7 d /
first-24 h deltas come from those snapshots, so the numbers become exact after the first day of runs. Output:
dispatch/stats_summary.json (read by tools/slots.py and tools/signals.py) and dispatch/stats.md (human).

  python3 tools/stats.py snapshot        # fetch counters, append snapshots, write summary + markdown
  python3 tools/stats.py report          # recompute from stored snapshots (no network)
"""
import json, os, re, statistics, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reelkit"))
LEDGER = ROOT / "dispatch/ledger.json"; STORE = ROOT / "dispatch/stats.json"
SUMMARY = ROOT / "dispatch/stats_summary.json"; MD = ROOT / "dispatch/stats.md"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) thequizwire-stats/1.0"}
NOW = datetime.now(timezone.utc)
CFG = json.loads((ROOT / "config/publishing.json").read_text())
AUDIENCE_TZ = ZoneInfo(CFG.get("buffer", {}).get("scheduling", {}).get("audience_tz", "America/New_York"))
PLATFORMS = ("youtube", "instagram", "facebook", "threads", "twitter")
MIN_VIDEOS_FOR_HOURS = 8          # below this, hour-of-day stats are noise → keep researched defaults
SCORE_ORDER = ("views", "impressions", "reach", "reactions")   # the first metric a network reports becomes its "score"
Q_METRICS = ("query($input: PostsInput!, $after: String) { posts(first: 50, after: $after, input: $input) { edges { node { id channelId status "
             "externalLink sentAt dueAt metrics { type value } metricsUpdatedAt } } pageInfo { hasNextPage endCursor } } }")


def get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r: return r.read().decode("utf-8", "replace")


def yt_id(link):
    m = re.search(r"(?:shorts/|watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})", link or ""); return m.group(1) if m else None


def published_posts():
    """Every ledger post that went out, on every channel: Buffer post id (the key), platform, episode, series, sent time."""
    out = []
    for p in json.loads(LEDGER.read_text()).get("posts", []):
        if p.get("state") != "sent" or not p.get("post_id"): continue
        out.append({"post_id": p["post_id"], "platform": p.get("platform"), "video_id": yt_id(p.get("external_link")) if p.get("platform") == "youtube" else None,
                    "episode": p["episode"], "series": series_of(p["episode"]), "sent_at": p.get("sent_at") or p.get("due_at")})
    return out


def series_of(name):
    for ej in ROOT.glob(f"series/*/{name}/episode.json"): return ej.parent.parent.name
    return "?"


def fetch_buffer(posts):
    """{post_id: {metric: value}} from Buffer Insights for the sent posts of every configured channel (one paginated
    query per channel, personal keys only). Posts whose metrics Buffer cannot read yet come back without an entry."""
    import buffer as B
    c = B.cfg(); got, notes = {}, {}
    for (account, org), chans in B.groups(c, list(PLATFORMS)).items():
        if not os.environ.get(account) and not (Path.home() / f".cache/secrets/{account.lower()}").exists():
            for platform, _ in chans: notes[platform] = f"secret {account} not set here"
            continue
        cl = B.Client(c, account)
        for platform, cid in chans:
            inp = {"organizationId": org, "filter": {"channelIds": [cid], "status": ["sent"], "startDate": (NOW - timedelta(days=45)).isoformat(timespec="seconds")},
                   "sort": [{"field": "createdAt", "direction": "desc"}]}
            after, n, scope, seen, err1 = None, 0, None, 0, None
            for _ in range(4):
                st, _h, raw = cl._post({"query": Q_METRICS, "variables": {"input": inp, "after": after}})
                try: body = json.loads(raw)
                except Exception: body = {}
                for e in body.get("errors") or []:
                    code = ((e.get("extensions") or {}).get("code") or ""); err1 = err1 or f"{code} {e.get('message')}"[:120]
                    if "SCOPE" in code.upper() or "insight" in (e.get("message") or "").lower(): scope = e.get("message") or code
                page = ((body.get("data") or {}).get("posts") or {})
                for ed in page.get("edges") or []:
                    seen += 1; nd = ed["node"]; m = {x["type"]: x["value"] for x in (nd.get("metrics") or [])}
                    if m: got[nd["id"]] = {**m, "metrics_updated_at": nd.get("metricsUpdatedAt")}; n += 1
                if not page.get("pageInfo", {}).get("hasNextPage"): break
                after = page["pageInfo"]["endCursor"]
            notes[platform] = f"buffer insights · {n}/{seen} sent posts with metrics" + (f" · scope: {scope}" if scope else "") + (f" · http {st} {err1}" if (err1 or st != 200) else "")
    return got, notes


def fetch_youtube_pages(posts):
    """Fallback for YouTube posts Buffer has no metrics for: the public watch page's view counter (views only)."""
    out = {}
    for p in posts:
        try:
            html = get(f"https://www.youtube.com/watch?v={p['video_id']}")
            m = re.search(r'"videoViewCountRenderer":\{"viewCount":\{"simpleText":"([\d,\.]+)', html) or re.search(r'"viewCount":"(\d+)"', html)
            if m: out[p["post_id"]] = {"views": int(re.sub(r"[^\d]", "", m.group(1)) or 0)}
        except Exception as ex: print(f"stats: {p['video_id']}: {ex}", file=sys.stderr)
    return out


def score_of(m):
    for k in SCORE_ORDER:
        if m.get(k) is not None: return int(m[k]), k
    return 0, None


def load_store():
    return json.loads(STORE.read_text()) if STORE.exists() else {"version": 1, "snapshots": []}


def value_at(snaps, when):
    """Views at the snapshot closest to `when` (within ±6 h), else None."""
    best = None
    for s in snaps:
        t = datetime.fromisoformat(s["t"]); d = abs((t - when).total_seconds())
        if d <= 6 * 3600 and (best is None or d < best[0]): best = (d, s["score"])
    return best[1] if best else None


def summarise(store, posts, notes=None):
    by_pid = {}
    for sn in store["snapshots"]: by_pid.setdefault(sn["post_id"], []).append(sn)
    rows = []
    for p in posts:
        snaps = sorted(by_pid.get(p["post_id"], []), key=lambda x: x["t"])
        if not snaps: continue
        last = snaps[-1]; now_v = last["score"]; sent = datetime.fromisoformat(p["sent_at"].replace("Z", "+00:00"))
        age_h = (NOW - sent).total_seconds() / 3600
        v24 = value_at(snaps, NOW - timedelta(hours=24)); v7 = value_at(snaps, NOW - timedelta(days=7))
        first24 = None                                                        # score gained in the first 24 h (slot quality)
        if age_h >= 24:
            a = value_at(snaps, sent + timedelta(hours=24)); b = value_at(snaps, sent)
            first24 = (a - (b or 0)) if a is not None else (now_v if age_h <= 36 else None)
        rows.append({**p, "score": now_v, "metric": last.get("metric"), "source": last.get("source"),
                     "reactions": last.get("reactions"), "comments": last.get("comments"), "shares": last.get("shares"), "saves": last.get("saves"),
                     "age_h": round(age_h, 1), "d24": (now_v - v24) if v24 is not None else (now_v if age_h <= 24 else None),
                     "d7": (now_v - v7) if v7 is not None else (now_v if age_h <= 24 * 7 else None),
                     "first24": first24, "sent_hour_local": sent.astimezone(AUDIENCE_TZ).hour, "sent_weekday": sent.astimezone(AUDIENCE_TZ).strftime("%a")})
    channels = {}
    for ch in PLATFORMS:
        R = [r for r in rows if r["platform"] == ch]
        hours = {}
        for r in R:
            if r["first24"] is not None: hours.setdefault(r["sent_hour_local"], []).append(r["first24"])
        n_hours = sum(len(v) for v in hours.values())
        hour_table = {h: {"n": len(v), "median_first24": statistics.median(v)} for h, v in sorted(hours.items())}
        best_hours = None
        if n_hours >= MIN_VIDEOS_FOR_HOURS:
            ranked = sorted(hour_table.items(), key=lambda kv: (-kv[1]["median_first24"], -kv[1]["n"]))
            best_hours = [f"{h:02d}:00" for h, _ in ranked[:2]]
        # per series on this channel (7 d) — what trends for us, per channel
        series = {}
        for r in R:
            s_ = series.setdefault(r["series"], {"posts": 0, "d7": 0, "score": 0, "d24s": []}); s_["posts"] += 1; s_["score"] += r["score"]
            if r["d7"] is not None: s_["d7"] += r["d7"]
            if r["d24"] is not None: s_["d24s"].append(r["d24"])
        for s_ in series.values(): s_["median_24h"] = statistics.median(s_["d24s"]) if s_["d24s"] else None; s_.pop("d24s")
        top = sorted(R, key=lambda r: (-(r["d24"] if r["d24"] is not None else -1), -r["score"]))[:5]
        srcs = sorted({r["source"] for r in R if r.get("source")})
        channels[ch] = {"posts": len(R), "source": "+".join(srcs) or None, "note": (notes or {}).get(ch), "metric": next((r["metric"] for r in R if r["metric"]), None),
                        "best_hours": best_hours, "hour_table": hour_table, "videos_with_first24": n_hours, "series": series,
                        "top_24h": [{k: r[k] for k in ("episode", "series", "d24", "score", "metric")} for r in top]}
    # cross-channel per series (what to make more of): sum of 7-day score deltas across channels, YouTube weighted 1, others 1
    series_all = {}
    for r in rows:
        s_ = series_all.setdefault(r["series"], {"posts": 0, "d7": 0, "score": 0}); s_["posts"] += 1; s_["score"] += r["score"]; s_["d7"] += r["d7"] or 0
    return {"generated_at": NOW.isoformat(timespec="seconds"), "audience_tz": str(AUDIENCE_TZ), "posts": len(rows), "channels": channels,
            "series": series_all, "top_24h": channels["youtube"]["top_24h"], "rows": rows}


def write_md(S):
    L = [f"# Channel stats — {S['generated_at'][:16]}Z (audience tz {S['audience_tz']}) · source: Buffer Insights (YouTube page fallback)", ""]
    L += ["## Per series, all channels (7-day movement — what is trending for us)"]
    for k, v in sorted(S["series"].items(), key=lambda kv: -kv[1]["d7"]): L.append(f"- {k}: {v['posts']} posts · +{v['d7']} in 7 d · {v['score']} total")
    for ch in PLATFORMS:
        C = S["channels"][ch]
        L += ["", f"## {ch} — {C['posts']} posts · metric {C['metric'] or '—'} · {C['note'] or C['source'] or 'no data'}"]
        if not C["posts"]: continue
        L.append("last 24 h:")
        for r in C["top_24h"]: L.append(f"- {r['episode']} ({r['series']}): +{r['d24'] if r['d24'] is not None else '?'} · {r['score']} total")
        L.append("series (7 d): " + " · ".join(f"{k} +{v['d7']} ({v['posts']})" for k, v in sorted(C["series"].items(), key=lambda kv: -kv[1]["d7"])))
        L.append("hours (first-24 h by publish hour): " + (" · ".join(f"{int(h):02d}:00 n={v['n']} med {v['median_first24']}" for h, v in C["hour_table"].items()) or "none yet"))
        L.append(f"→ slots: {C['best_hours'] or f'not enough first-24 h data ({C['videos_with_first24']}/{MIN_VIDEOS_FOR_HOURS}) — researched defaults in use'}")
    L += ["", "## Every post", "", "| episode | channel | sent (local) | metric | total | 24 h | 7 d | first 24 h | reactions | comments |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(S["rows"], key=lambda r: (r["sent_at"], r["platform"]), reverse=True):
        L.append(f"| {r['episode']} | {r['platform']} | {r['sent_weekday']} {r['sent_hour_local']:02d}:00 | {r['metric']} | {r['score']} | {r['d24']} | {r['d7']} | {r['first24']} | {r['reactions']} | {r['comments']} |")
    MD.write_text("\n".join(L) + "\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    posts = published_posts(); store = load_store(); notes = {}
    if store.get("version", 1) < 2: store = {"version": 2, "snapshots": [  # v1 snapshots were YouTube page views keyed by video id
        {"t": sn["t"], "post_id": next((p["post_id"] for p in posts if p.get("video_id") == sn["video_id"]), sn["video_id"]), "platform": "youtube",
         "score": sn["views"], "metric": "views", "source": "youtube-page"} for sn in store["snapshots"]]}
    if cmd == "snapshot":
        got, notes = fetch_buffer(posts); t = NOW.isoformat(timespec="seconds"); n_b = 0
        for p in posts:
            m = got.get(p["post_id"])
            if not m: continue
            sc, metric = score_of(m); n_b += 1
            store["snapshots"].append({"t": t, "post_id": p["post_id"], "platform": p["platform"], "score": sc, "metric": metric, "source": "buffer",
                                       **{k: m.get(k) for k in ("views", "impressions", "reach", "reactions", "comments", "shares", "reposts", "saves") if m.get(k) is not None}})
        missing_yt = [p for p in posts if p["platform"] == "youtube" and p["video_id"] and p["post_id"] not in got]
        pages = fetch_youtube_pages(missing_yt)
        for p in missing_yt:
            if p["post_id"] in pages: store["snapshots"].append({"t": t, "post_id": p["post_id"], "platform": "youtube", "score": pages[p["post_id"]]["views"], "metric": "views", "source": "youtube-page"})
        STORE.write_text(json.dumps(store, indent=0) + "\n")
        print(f"stats: {n_b} posts from Buffer Insights, {len(pages)}/{len(missing_yt)} YouTube page fallbacks, of {len(posts)} sent posts", file=sys.stderr)
        for ch, note in notes.items(): print(f"stats: {ch}: {note}", file=sys.stderr)
    S = summarise(store, posts, notes); SUMMARY.write_text(json.dumps(S, indent=1) + "\n"); write_md(S)
    print(f"stats: {S['posts']} posts · YouTube top 24 h: " + ", ".join(f"{r['episode']} +{r['d24']}" for r in S["top_24h"][:3]), file=sys.stderr)


if __name__ == "__main__": main()
