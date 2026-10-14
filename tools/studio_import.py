#!/usr/bin/env python3
"""studio_import.py — turn a YouTube Studio export into docs/SCORECARD.md (PLAN_V2 §4 gates).

Usage:
  python3 tools/studio_import.py docs/data/studio_2026-09-16_10-13 [--batch v2] [--out docs/SCORECARD.md] [--append]

Expects <prefix>_table.csv (per-video table, first data row = Total) and optionally <prefix>_totals.csv (daily subs)
and <prefix>_chart.csv. Columns used: Video title, Video publish time, Duration, Subscribers, Stayed to watch (%),
Average view duration, Views, Likes. Everything else is ignored, so extra Studio columns are harmless.

Format classes (title/duration heuristics for the v1 era; v2 episodes are matched by question text against
series/*/<episode>/episode.json so the batch gates are computed on exactly the videos this repo produced):
  5Q      "5 … – Quiz" cards, ≥ 55 s           1Q16    single-question cards ≤ 20 s
  1-3Q    1–3-question cards 30–50 s           v2      episodes produced by this repo (Plan v2)
  other   anything else
"""
import argparse, csv, datetime as dt, json, pathlib, statistics as st, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATES = {"stayed": 70.0, "pct_viewed": 65.0, "views_max": 5000, "views_median": 2000, "subs_per_1k": 2.0, "like_rate": 8.0}


def num(x):
    try:
        return float(str(x).replace(",", "").replace("%", ""))
    except Exception:
        return None


def secs(s):
    try:
        p = [int(x) for x in str(s).split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]
    except Exception:
        return None


def pubdate(s):
    for f in ("%b %d, %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s.strip(), f).date()
        except Exception:
            pass
    return None


def repo_questions():
    """question text → (series, episode) for every episode folder with an episode.json."""
    out = {}
    for ep in (ROOT / "series").glob("*/*/episode.json"):
        try:
            q = json.loads(ep.read_text(encoding="utf-8")).get("question", "")
        except Exception:
            continue
        if q:
            out[norm(q)] = (ep.parent.parent.name, ep.parent.name)
    return out


def norm(t):
    t = "".join(ch for ch in t.lower() if ch.isalnum() or ch == " ")
    return " ".join(t.split())


def classify(r, questions):
    key = norm(r["title"])
    for q, (series, ep) in questions.items():
        if q and (q in key or key in q):
            r["series"], r["episode"] = series, ep
            return "v2"
    t = r["title"].strip()
    if t.startswith("5 ") and (r["dur"] or 0) >= 55:
        return "5Q"
    if (r["dur"] or 0) <= 20:
        return "1Q16"
    if 30 <= (r["dur"] or 0) <= 50:
        return "1-3Q"
    return "other"


def load(prefix):
    table = pathlib.Path(f"{prefix}_table.csv")
    if not table.exists():
        sys.exit(f"missing {table}")
    rows = list(csv.DictReader(open(table, encoding="utf-8-sig")))
    total = rows[0] if rows and rows[0].get("Content") == "Total" else {}
    vids = []
    questions = repo_questions()
    for r in rows[1:] if total else rows:
        v = {
            "id": r.get("Content", ""), "title": r.get("Video title", ""), "pub": pubdate(r.get("Video publish time", "")),
            "dur": num(r.get("Duration")), "subs": int(num(r.get("Subscribers")) or 0), "stayed": num(r.get("Stayed to watch (%)")),
            "avd": secs(r.get("Average view duration")), "views": int(num(r.get("Views")) or 0), "likes": int(num(r.get("Likes")) or 0),
        }
        v["pct"] = 100 * v["avd"] / v["dur"] if (v["avd"] is not None and v["dur"]) else None
        v["fmt"] = classify(v, questions)
        vids.append(v)
    daily = []
    totals = pathlib.Path(f"{prefix}_totals.csv")
    if totals.exists():
        for r in csv.DictReader(open(totals, encoding="utf-8-sig")):
            d = pubdate(r.get("Date", "")) or None
            if d:
                daily.append((d, int(num(r.get("Subscribers")) or 0)))
    return total, vids, daily


def med(v):
    v = [x for x in v if x is not None]
    return st.median(v) if v else None


def f(x, d=0, suf=""):
    return "—" if x is None else f"{x:,.{d}f}{suf}"


def group_table(groups, title):
    out = [f"### {title}", "", "| group | n | views median | views max | stayed % | AVD s | % viewed | likes/views | subs | subs / 1k |", "|---|---|---|---|---|---|---|---|---|---|"]
    for name, rs in groups:
        if not rs:
            continue
        views = sum(r["views"] for r in rs)
        out.append(
            f"| {name} | {len(rs)} | {f(med([r['views'] for r in rs]))} | {f(max(r['views'] for r in rs))} | {f(med([r['stayed'] for r in rs]), 1)} | "
            f"{f(med([r['avd'] for r in rs]))} | {f(med([r['pct'] for r in rs]))} | {f(100 * sum(r['likes'] for r in rs) / views if views else None, 1, ' %')} | "
            f"{sum(r['subs'] for r in rs)} | {f(1000 * sum(r['subs'] for r in rs) / views if views else None, 2)} |")
    return "\n".join(out) + "\n"


def gates_table(rs):
    if not rs:
        return "_No v2 episodes in this export yet (titles are matched against series/*/*/episode.json)._\n"
    views = sum(r["views"] for r in rs)
    m = {
        "stayed to watch (median)": (med([r["stayed"] for r in rs]), GATES["stayed"], "%", "hook — rewrite the 0–2 s beat"),
        "AVD / duration (median)": (med([r["pct"] for r in rs]), GATES["pct_viewed"], "%", "middle — cut a beat, payoff earlier"),
        "best video views": (max(r["views"] for r in rs), GATES["views_max"], "", "distribution — Variant B / named entities"),
        "median views": (med([r["views"] for r in rs]), GATES["views_median"], "", "distribution — Variant B / named entities"),
        "subs / 1k views": (1000 * sum(r["subs"] for r in rs) / views if views else None, GATES["subs_per_1k"], "", "end — CTA line / tease"),
        "likes / views": (100 * sum(r["likes"] for r in rs) / views if views else None, GATES["like_rate"], "%", "keep"),
    }
    out = ["| gate | value | target | result | if missed |", "|---|---|---|---|---|"]
    for k, (val, tgt, suf, fix) in m.items():
        ok = val is not None and val >= tgt
        out.append(f"| {k} | {f(val, 1 if suf else 0, suf)} | ≥ {f(tgt, 0, suf)} | {'✅' if ok else '❌'} | {fix} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix")
    ap.add_argument("--out", default=str(ROOT / "docs" / "SCORECARD.md"))
    ap.add_argument("--append", action="store_true", help="append a dated section instead of rewriting the file")
    ap.add_argument("--since", help="only videos published on/after YYYY-MM-DD for the format table (default: 2026-09-06)", default="2026-09-06")
    ap.add_argument("--min-views", type=int, default=100)
    a = ap.parse_args()
    total, vids, daily = load(a.prefix)
    since = dt.date.fromisoformat(a.since)
    recent = [v for v in vids if v["pub"] and v["pub"] >= since and v["views"] >= a.min_views]
    v2 = [v for v in vids if v["fmt"] == "v2"]
    window = pathlib.Path(a.prefix).name.replace("studio_", "")
    md = [f"## Studio export `{window}` — imported {dt.date.today().isoformat()}", ""]
    if total:
        md += [f"Totals: **{f(num(total.get('Views')))} views** · {f(num(total.get('Likes')))} likes · **{total.get('Subscribers')} subscribers** · "
               f"stayed to watch **{total.get('Stayed to watch (%)')} %** · AVD {total.get('Average view duration')} · "
               f"thumbnail impressions {f(num(total.get('Thumbnail impressions')))}", ""]
    if daily:
        md += [f"Daily subscribers: {sum(s for _, s in daily)} over {len(daily)} days (max {max(s for _, s in daily)}/day, "
               f"{sum(1 for _, s in daily if s == 0)} zero days)", ""]
    md.append("### Plan v2 gates (v2 episodes only)\n")
    md.append(gates_table(v2))
    fmts = ["v2", "5Q", "1-3Q", "1Q16", "other"]
    md.append(group_table([(k, [r for r in recent if r["fmt"] == k]) for k in fmts], f"By format (published ≥ {since}, views ≥ {a.min_views})"))
    if v2:
        series = sorted({r.get("series") for r in v2})
        md.append(group_table([(s, [r for r in v2 if r.get("series") == s]) for s in series], "v2 by series"))
        md.append("### v2 episodes\n\n| published | series/episode | views | stayed % | AVD | % viewed | likes | subs | title |\n|---|---|---|---|---|---|---|---|---|")
        for r in sorted(v2, key=lambda r: (r["pub"] or dt.date.min), reverse=True):
            md.append(f"| {r['pub']} | {r.get('series')}/{r.get('episode')} | {r['views']:,} | {f(r['stayed'], 1)} | {f(r['avd'])} s | {f(r['pct'])} | {r['likes']} | {r['subs']} | {r['title'][:60]} |")
        md.append("")
    stayed = sorted(r["stayed"] for r in recent if r["stayed"] is not None)
    if stayed:
        q = lambda p: stayed[int(p * (len(stayed) - 1))]
        md += [f"Stayed-to-watch distribution (n = {len(stayed)}): p10 {q(.1):.1f} · p25 {q(.25):.1f} · median {st.median(stayed):.1f} · p75 {q(.75):.1f} · p90 {q(.9):.1f} · max {stayed[-1]:.1f}", ""]
    md.append("### Top 8 by stayed % · bottom 5\n\n| stayed % | AVD/dur | views | subs | title |\n|---|---|---|---|---|")
    rs = [r for r in recent if r["stayed"] is not None]
    for r in sorted(rs, key=lambda r: -r["stayed"])[:8] + [None] + sorted(rs, key=lambda r: r["stayed"])[:5]:
        md.append("| … | | | | |" if r is None else f"| {r['stayed']:.1f} | {f(r['avd'])}/{f(r['dur'])} s | {r['views']:,} | {r['subs']} | {r['title'][:60]} |")
    md.append("")
    text = "\n".join(md)
    head = ("# SCORECARD.md — what the channel's own analytics say about each batch\n\n"
            "Generated by `tools/studio_import.py <docs/data/studio_PREFIX>` from the owner's YouTube Studio export "
            "(Content → Advanced mode → export). Gates come from `docs/PLAN_V2.md` §4 and are evaluated on the episodes this repo "
            "produced (matched by question text). Re-run after every batch; keep older sections (use `--append`).\n\n")
    out = pathlib.Path(a.out)
    if a.append and out.exists():
        out.write_text(out.read_text(encoding="utf-8").rstrip() + "\n\n---\n\n" + text, encoding="utf-8")
    else:
        out.write_text(head + text, encoding="utf-8")
    print(text)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
