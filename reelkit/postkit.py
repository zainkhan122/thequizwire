#!/usr/bin/env python3
"""Per-channel post copy (SEO) for one rendered episode — the text Buffer sends to YouTube, Instagram and Facebook.

  python3 reelkit/postkit.py build <episode_dir> [--out out/postkit.json]   # write the kit (+ prints a preview)
  python3 reelkit/postkit.py check <episode_dir>                            # lint only (exit 1 on FAIL)
  python3 reelkit/postkit.py show  <episode_dir>                            # print the kit as it would be sent

Source of truth: episode.json (`title` = the question, `quiz`, `post`), visuals.json facts (the three see-it facts),
research.json sources, and config/publishing.json (series hashtags/keywords/category). No model in the loop: the copy
is deterministic, so a re-run yields byte-identical text and the lint below is the whole review.

Platform rules encoded here (2026 guidance, see docs/DISTRIBUTION.md §4 for the references):
  YouTube  title ≤ 100 chars (aim 50–80, question first, keyword inside the first 50), no hashtags in the title;
           description: hook + keyword in the first 100 chars, 3–5 hashtags at the END (YouTube shows up to three above
           the title; > 15 hashtags → all ignored); category per series; Shorts are auto-detected by aspect/length.
  Instagram caption ≤ 2,200 chars, the first ~125 chars are the visible hook; keywords in plain words (IG search reads
           captions), 3–5 hashtags at the end; links are not clickable → sources go to the first comment.
  Facebook Reel description short; the question + a comment prompt; 1–3 hashtags; disclosure line for AI narration.
Per-episode overrides live in episode.json#post: title, description (used as the YouTube body), hashtags (extra, any
platform), tags (episode-specific hashtag words), youtube_is_ai_generated. Platforms: youtube · instagram · facebook · twitter (X) · threads.
"""
import argparse, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config/publishing.json").read_text())
BANNED = re.compile(r"\b(next video|tomorrow'?s? (video|quiz)|see you tomorrow|coming tomorrow)\b", re.I)
HASHTAG = re.compile(r"^#[A-Za-z0-9_]{2,40}$")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\u23F0-\u23FF]")


# ---------------------------------------------------------------- inputs
def load(ep):
    ep = Path(ep)
    E = json.loads((ep / "episode.json").read_text())
    V = json.loads((ep / "visuals.json").read_text()) if (ep / "visuals.json").exists() else {}
    R = json.loads((ep / "research.json").read_text()) if (ep / "research.json").exists() else {}
    return E, V, R


def facts(V):
    """The three see-it facts as readable bullets: 'WORPLE ROAD 1877 | 22 men, one event, 200 watched' → 'Worple Road 1877 — 22 men, one event, 200 watched'."""
    out = []
    for el in V.get("elements", []):
        if el.get("type") != "fact": continue
        k, t = (el.get("kicker") or "").strip(), (el.get("text") or "").strip()
        k = re.sub(r"\s+", " ", k)
        kick = k.title() if k.isupper() else k
        kick = re.sub(r"\b(Mm|Km|Kg|Bc|Ad|Usa|Uk|Nz|Us)\b", lambda m: m.group(0).upper(), kick)
        out.append(f"{kick} — {t}" if kick and t else (kick or t))
    return out[:3]


def source_names(R, n=4):
    """Short, human source names for the credits line: wimbledon.com, Wikipedia, The Guardian …"""
    names = []
    src = R.get("sources", [])
    rows = list(src.values()) if isinstance(src, dict) else src           # research.json keeps sources as {key: {...}}; older files used a list
    rows = sorted(rows, key=lambda s: 0 if isinstance(s, dict) and s.get("type") in ("primary", "scholarly") else 1)
    for s in rows:
        if not isinstance(s, dict): continue
        nm = (s.get("publisher") or s.get("name") or s.get("title") or "").strip()
        if not nm:
            m = re.search(r"https?://(?:www\.)?([^/]+)", s.get("url", "")); nm = m.group(1) if m else ""
        nm = re.sub(r"^(en\.)?wikipedia\.org$", "Wikipedia", nm)
        if nm and nm not in names: names.append(nm)
    return names[:n]


def answer_text(E):
    q = E.get("quiz", {})
    opts, c = q.get("options", []), q.get("correct")
    return opts[c] if isinstance(c, int) and 0 <= c < len(opts) else (q.get("answer_line") or "")


def tag_word(s):
    """'US Open' → 'USOpen', 'Galápagos penguin' → 'GalapagosPenguin' (ASCII, CamelCase, ≤ 30)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    parts = re.findall(r"[A-Za-z0-9]+", t)
    w = "".join(p if p.isupper() else p[:1].upper() + p[1:] for p in parts)
    return w[:30]


def hashtags_for(E, S, platform, limit):
    """Series set + brand + episode-specific tags; de-duplicated case-insensitively; capped per platform."""
    post = E.get("post", {})
    extra = [("#" + tag_word(t)) if not str(t).startswith("#") else str(t) for t in post.get("tags", [])]
    if not extra:
        extra = ["#" + tag_word(answer_text(E))] if answer_text(E) else []
    legacy = [h for h in post.get("hashtags", []) if h.lower() not in {"#shorts", "#gkshorts", "#usagk", "#1min", "#thequizwire"} and not h.lower().startswith("#" + E.get("series", "").replace("-", ""))]
    base = {"youtube": ["#Shorts"], "instagram": [], "facebook": [], "twitter": [], "threads": []}[platform]
    pool = base + S["hashtags"].get(platform, []) + extra + legacy + [CFG["channel"]["brand_hashtag"]]
    seen, out = set(), []
    for h in pool:
        if HASHTAG.match(h) and h.lower() not in seen:
            seen.add(h.lower()); out.append(h)
    if limit == 1: return out[:1]                        # single-tag networks (Threads): the series topic tag, not the brand
    if len(out) > limit:                                 # keep #Shorts/series/episode tags, drop legacy first, brand last
        keep = [h for h in out if h != CFG["channel"]["brand_hashtag"]][: limit - 1] + [CFG["channel"]["brand_hashtag"]]
        out = keep[:limit]
    return out


# ---------------------------------------------------------------- copy
def build(ep):
    E, V, R = load(ep)
    slug = E.get("series", "")
    S = CFG["series"].get(slug) or {"name": slug.title(), "emoji": "❓", "topic": "quiz", "youtube_category": "24", "playlist": slug, "hashtags": {}, "keywords": []}
    post = E.get("post", {})
    question = E["title"].strip()
    emoji = EMOJI.search(post.get("title", "")) or EMOJI.search(question)
    emoji = emoji.group(0) if emoji else S["emoji"]
    q_clean = EMOJI.sub("", question).strip()
    ans = answer_text(E)
    bullets = facts(V)
    srcs = source_names(R)
    site, handle, brand = CFG["channel"]["site"], CFG["channel"]["instagram_handle"], CFG["channel"]["name"]
    beat = E.get("quiz", {}).get("beat", 3)
    secs = f"{int(beat)} seconds" if float(beat) == int(beat) else f"{beat} seconds"
    topic = S["topic"]

    # ---- YouTube
    yt_title = post.get("youtube_title") or f"{q_clean} {emoji} | {topic.title()}"
    if len(yt_title) > 100: yt_title = f"{q_clean} {emoji}"
    if len(yt_title) > 100: yt_title = q_clean[:97].rstrip() + "…"
    tease = (post.get("description") or "").split("\n")[0].strip()
    tease = "" if tease.lower().startswith(q_clean.lower()[:30]) and len(tease) < len(q_clean) + 10 else tease
    yt_tags = hashtags_for(E, S, "youtube", 5)
    yt_lines = [f"{q_clean} You get {secs} to guess — then the map reveals it. {emoji}"]
    if tease and not tease.lower().startswith(q_clean.lower()):
        yt_lines.append(tease)
    elif tease:
        rest = tease[len(q_clean):].strip(" .—-")
        if rest: yt_lines.append(rest[:1].upper() + rest[1:])
    if bullets:
        yt_lines += ["", f"✅ In this {topic} Short:"] + [f"• {b}" for b in bullets]
    yt_lines += ["", "What was your first guess? Tell us in the comments 👇",
                 f"🔔 Subscribe for a new {topic} every day · more quizzes at {site}"]
    if srcs: yt_lines += ["", "📚 Sources: " + " · ".join(srcs)]
    yt_lines += ["🗺️ Map data: Natural Earth (public domain) · imagery NASA Blue Marble · Voice: AI narration (Kokoro)",
                 "", " ".join(yt_tags)]
    yt_desc = "\n".join(yt_lines)
    yt = {"title": yt_title, "description": yt_desc, "hashtags": yt_tags, "categoryId": str(S["youtube_category"]),
          "madeForKids": CFG["youtube"]["made_for_kids"], "notifySubscribers": CFG["youtube"]["notify_subscribers"],
          "privacy": CFG["youtube"]["privacy"], "license": CFG["youtube"]["license"], "embeddable": CFG["youtube"]["embeddable"],
          "isAiGenerated": bool(post.get("youtube_is_ai_generated", CFG["disclosure"]["youtube_is_ai_generated"])),
          "keywords": list(dict.fromkeys(S.get("keywords", []) + [ans.lower()] + [k.lower() for k in post.get("keywords", [])]))[:12],
          "playlist": S["playlist"]}

    # ---- Instagram (reel)
    ig_tags = hashtags_for(E, S, "instagram", 5)
    hook = f"{q_clean} {emoji} You get {secs}… ⏱️"
    ig_lines = [hook, "", f"✅ The answer and three quick facts are in the reel — a daily {topic} from {brand}."]
    ig_lines += [f"• {b}" for b in bullets[:2]]
    ig_lines += ["", "💬 What was your first guess? Comment before the reveal!", f"Follow {handle} for a new {topic} every day.", "", " ".join(ig_tags)]
    ig_caption = "\n".join(ig_lines)
    ig_first = "📚 Sources: " + (" · ".join(srcs) if srcs else "see the video credits") + f"\n🗺️ Map data: Natural Earth · NASA Blue Marble · 🎙️ AI narration (Kokoro)\nMore quizzes: {site}"
    ig = {"caption": ig_caption, "firstComment": ig_first, "hashtags": ig_tags, "shouldShareToFeed": True,
          "isAiGenerated": bool(CFG["disclosure"]["instagram_is_ai_generated"]), "thumbnailOffsetMs": 2000}

    # ---- Facebook (reel)
    fb_tags = hashtags_for(E, S, "facebook", 3)
    fb_lines = [f"{q_clean} {emoji} Guess in {secs} — then watch the reveal!",
                "✅ Answer + three quick facts inside. What was your first guess? 👇",
                f"Daily {topic} · {site}", CFG["disclosure"]["facebook_caption_line"], "", " ".join(fb_tags)]
    fb = {"text": "\n".join(fb_lines), "firstComment": ig_first, "hashtags": fb_tags}

    # ---- X (Twitter): one post, video attached; 280-char budget (X counts most emoji as 2); 1–2 hashtags; sources stay in the video credits
    x_tags = hashtags_for(E, S, "twitter", 2)
    x_text = "\n".join([f"{q_clean} {emoji}", "", f"Guess in {secs}, then watch the reveal. What was your first guess? 👇", "", " ".join(x_tags)])
    if x_len(x_text) > 270:
        x_text = "\n".join([f"{q_clean} {emoji}", "", "What was your first guess? 👇", " ".join(x_tags)])
    x = {"text": x_text, "hashtags": x_tags, "isAiGenerated": bool(CFG["disclosure"].get("twitter_is_ai_generated", True))}

    # ---- Threads: ≤ 500 chars, conversational; Threads turns only the FIRST hashtag into a topic tag, so exactly one
    th_tags = hashtags_for(E, S, "threads", 1)
    th_text = "\n".join([f"{q_clean} {emoji}", "", f"You get {secs}. Then the map reveals it, with three facts you can repeat at dinner.", "",
                         "What was your first guess? 👇", "", " ".join(th_tags)])
    th = {"text": th_text, "hashtags": th_tags}

    kit = {"episode": Path(ep).name, "series": slug, "question": question, "answer": ans, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "youtube": yt, "instagram": ig, "facebook": fb, "twitter": x, "threads": th}
    kit["checks"] = check(kit)
    return kit


def x_len(text):
    """X's weighted length: URLs count 23, most emoji/CJK count 2, everything else 1 (close enough for a lint)."""
    t = re.sub(r"https?://\S+|www\.\S+", "x" * 23, text)
    return sum(2 if ord(ch) > 0x1100 else 1 for ch in t)


# ---------------------------------------------------------------- lint
def check(kit):
    F, W = [], []
    yt, ig, fb, x = kit["youtube"], kit["instagram"], kit["facebook"], kit.get("twitter") or {"text": "", "hashtags": ["#x"]}
    th = kit.get("threads") or {"text": "", "hashtags": ["#x"]}
    if len(th["text"]) > 500: F.append(f"Threads text {len(th['text'])} chars > 500")
    if len(th["hashtags"]) != 1: F.append(f"Threads hashtags {len(th['hashtags'])} (want exactly 1 — only the first becomes a topic tag)")
    t = yt["title"]
    if len(t) > 100: F.append(f"YT title {len(t)} chars > 100")
    elif len(t) > 85: W.append(f"YT title {len(t)} chars (aim ≤ 80 so feeds show it whole)")
    if len(t) < 30: W.append("YT title < 30 chars (looks low-effort)")
    if "#" in t: F.append("YT title contains a hashtag (keep the title clean; hashtags go at the end of the description)")
    if len(EMOJI.findall(t)) > 2: W.append("YT title has > 2 emoji")
    first = yt["description"].split("\n")[0]
    if len(first) > 120: W.append(f"YT description first line {len(first)} chars (the first ~100 are the search snippet)")
    if len(yt["description"]) > 5000: F.append("YT description > 5000 chars")
    if not 3 <= len(yt["hashtags"]) <= 5: F.append(f"YT hashtags {len(yt['hashtags'])} (want 3–5)")
    if not yt["description"].rstrip().endswith(" ".join(yt["hashtags"])): F.append("YT hashtags must be the last line of the description")
    if len(ig["caption"]) > 2200: F.append("IG caption > 2200 chars")
    hook = ig["caption"].split("\n")[0]
    if len(hook) > 125: W.append(f"IG hook line {len(hook)} chars (> 125 gets cut behind 'more')")
    if not 3 <= len(ig["hashtags"]) <= 5: F.append(f"IG hashtags {len(ig['hashtags'])} (want 3–5)")
    if re.search(r"https?://|www\.", ig["caption"]): W.append("IG caption has a URL (not clickable; sources belong in the first comment)")
    if len(fb["text"]) > 1000: W.append("FB text > 1000 chars")
    if not 1 <= len(fb["hashtags"]) <= 3: F.append(f"FB hashtags {len(fb['hashtags'])} (want 1–3)")
    if x_len(x["text"]) > 280: F.append(f"X text {x_len(x['text'])} weighted chars > 280")
    elif x_len(x["text"]) > 260: W.append(f"X text {x_len(x['text'])} weighted chars (aim ≤ 260)")
    if not 1 <= len(x["hashtags"]) <= 2: F.append(f"X hashtags {len(x['hashtags'])} (want 1–2)")
    for name, text in (("YT", yt["title"] + "\n" + yt["description"]), ("IG", ig["caption"]), ("FB", fb["text"]), ("X", x["text"]), ("Threads", th["text"])):
        if BANNED.search(text): F.append(f"{name}: tease of a next/tomorrow video (owner rule: no announcements)")
        for h in re.findall(r"#\S+", text):
            if not HASHTAG.match(h): F.append(f"{name}: malformed hashtag {h!r}")
    if not kit.get("answer"): F.append("no answer text (quiz.options/correct missing)")
    return {"fail": F, "warn": W}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "check", "show"]); ap.add_argument("episode"); ap.add_argument("--out")
    a = ap.parse_args()
    kit = build(a.episode)
    c = kit["checks"]
    if a.cmd in ("build", "show"):
        for p in ("youtube", "instagram", "facebook", "twitter", "threads"):
            body = kit[p].get("title", "") and f"TITLE: {kit[p]['title']}\n" or ""
            body += kit[p].get("description") or kit[p].get("caption") or kit[p].get("text")
            print(f"── {p.upper()} " + "─" * 60); print(body)
            if kit[p].get("firstComment"): print(f"↳ first comment: {kit[p]['firstComment']}")
        print("─" * 72)
    if a.cmd == "build":
        out = Path(a.out) if a.out else Path(a.episode) / "out" / "postkit.json"
        out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(kit, indent=1, ensure_ascii=False) + "\n")
        print(f"postkit: wrote {out}")
    for w in c["warn"]: print(f"  WARN  {w}")
    for f in c["fail"]: print(f"  FAIL  {f}")
    print(f"postkit: {kit['episode']} · YT {len(kit['youtube']['title'])}-char title · IG {len(kit['instagram']['caption'])} chars · FB {len(kit['facebook']['text'])} chars · X {x_len(kit['twitter']['text'])} → FAIL {len(c['fail'])} WARN {len(c['warn'])}")
    sys.exit(1 if c["fail"] else 0)


if __name__ == "__main__":
    main()
