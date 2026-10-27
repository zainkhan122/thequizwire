#!/usr/bin/env python3
"""signals.py — the raw material for a topic decision (P1 of docs/TEMPLATE_AUDIT_2026-10-21.md).

It does NOT choose topics. It gathers what people are searching, reading and about to celebrate, plus what we already
published, and writes one reading sheet. The agent reads the sheet and writes `topic.md` per episode (docs/TOPIC_GUIDELINES.md),
recording the reasoning. Free sources only, no keys:

  youtube suggest   https://suggestqueries.google.com/...ds=yt      what people type into YouTube after a seed term
  google trends     https://trends.google.com/trending/rss?geo=XX    today's trending searches (US, GB, IN, PK)
  wikipedia top     wikimedia pageviews top/en.wikipedia              what people read yesterday (we strip the noise)
  calendar          config/calendar.json                              awareness days / anniversaries in the next 21 days
  our channel       dispatch/ledger.json + series/*/episode.json      stems and subjects already used (novelty)

Usage: python3 tools/signals.py [--seeds "deepest lake,olympics"] [--days 21] [--out review/signals.md]
"""
import argparse, datetime as dt, json, re, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "thequizwire-signals/1.0 (editorial research)"}
SEEDS = ["geography quiz", "guess the country", "deepest lake", "longest border", "world cup record", "olympics first",
         "human body facts", "brain facts", "animal facts", "tallest people", "which country has the most"]
NOISE = re.compile(r"^(Main_Page|Special:|Wikipedia:|Portal:|Deaths_in|.*_\(film\)|.*_\(TV_series\)|.*_season_\d|File:)")

def get(url, timeout=12):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r: return r.read().decode("utf-8", "replace")
    except Exception as ex: return f"__ERR__ {ex}"

def yt_suggest(seed):
    raw = get("https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=" + urllib.parse.quote(seed))
    if raw.startswith("__ERR__"): return []
    try: return json.loads(raw)[1][:10]
    except Exception: return []

def trends(geo):
    raw = get(f"https://trends.google.com/trending/rss?geo={geo}")
    if raw.startswith("__ERR__"): return []
    items = re.findall(r"<item>(.*?)</item>", raw, re.S); out = []
    for it in items[:20]:
        t = re.search(r"<title>(.*?)</title>", it, re.S); tr = re.search(r"<ht:approx_traffic>(.*?)</ht:approx_traffic>", it)
        if t: out.append((t.group(1).strip(), tr.group(1) if tr else ""))
    return out

def wiki_top(day):
    raw = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{day:%Y/%m/%d}")
    if raw.startswith("__ERR__"): return []
    try: arts = json.loads(raw)["items"][0]["articles"]
    except Exception: return []
    return [(a["article"].replace("_", " "), a["views"]) for a in arts if not NOISE.match(a["article"])][:40]

def calendar(days):
    p = ROOT / "config/calendar.json"
    if not p.exists(): return []
    today = dt.date.today(); out = []
    for e in json.loads(p.read_text()):
        m, d = map(int, e["date"].split("-")); when = dt.date(today.year, m, d)
        if when < today: when = dt.date(today.year + 1, m, d)
        if (when - today).days <= days: out.append((when.isoformat(), e["name"], e.get("series", ""), e.get("angle", "")))
    return sorted(out)

def ours():
    used = []
    for ej in sorted(ROOT.glob("series/*/ep*/episode.json")):
        if "_template" in str(ej): continue
        E = json.loads(ej.read_text())
        if E.get("status") in ("ready", "sent", "scheduled") or E.get("published"):
            used.append((ej.parent.parent.name, (E.get("quiz") or {}).get("question") or E.get("question", ""), E.get("status", "")))
    ledger = json.loads((ROOT / "dispatch/ledger.json").read_text()).get("posts", [])
    live = {p["episode"] for p in ledger if p.get("state") in ("scheduled", "sent")}
    return used, live

def stem(q):
    """Question-shape fingerprint: first two words + the capitalised superlative, lower-cased ('which country most', 'where first')."""
    w = re.findall(r"[A-Za-z']+", q); caps = [x.lower() for x in w if x.isupper() and len(x) > 2]
    return " ".join([*(x.lower() for x in w[:2]), *caps[:1]])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", default=""); ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--out", default="review/signals.md"); a = ap.parse_args()
    seeds = [s.strip() for s in a.seeds.split(",") if s.strip()] or SEEDS
    today = dt.date.today(); L = [f"# Signals — {today}", "", "Reading sheet only. The decision and its reasons go into `topic.md` (docs/TOPIC_GUIDELINES.md).", ""]
    L += ["## Calendar (next %d days)" % a.days] + [f"- {d} · **{n}** · {s} · {ang}" for d, n, s, ang in calendar(a.days)] + [""]
    L += ["## YouTube search suggestions (what people type)"]
    for s in seeds: L.append(f"- `{s}` → " + " · ".join(yt_suggest(s)))
    L.append("")
    for geo in ("US", "GB", "IN", "PK"):
        L += [f"## Google Trends {geo} (today)"] + [f"- {t} ({tr})" for t, tr in trends(geo)[:12]] + [""]
    L += ["## Wikipedia most-read (yesterday, noise removed)"] + [f"- {t} · {v:,}" for t, v in wiki_top(today - dt.timedelta(days=1))[:30]] + [""]
    used, live = ours()
    S = ROOT / "dispatch/stats_summary.json"
    if S.exists():
        st = json.loads(S.read_text())
        L += ["## Our channel — last 24 h / 7 d (dispatch/stats.md; what OUR viewers are rewarding)"]
        for r in st.get("top_24h", [])[:5]: L.append(f"- {r['episode']} ({r['series']}): +{r['views_24h']} in 24 h · {r['views']} total")
        for k, v in sorted(st.get("series", {}).items(), key=lambda kv: -(kv[1].get("views_7d") or 0)):
            L.append(f"- series {k}: {v['videos']} videos · {v['views_7d']} views in 7 d · median 24 h {v['median_24h']}")
        L.append("")
    L += ["## Already ours (do not repeat the stem or the subject)"]
    for s, q, st in used: L.append(f"- {s} · {q} · `{stem(q)}` · {st}")
    out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True); out.write_text("\n".join(L) + "\n")
    print(f"signals → {out.relative_to(ROOT)} ({len(L)} lines)")

if __name__ == "__main__":
    main()
