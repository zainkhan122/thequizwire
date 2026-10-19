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
        nm = re.sub(r"\s*\([^)]*\)", "", nm).strip(" ,·")                      # drop parentheticals: "(MoEFCC / NTCA–WII)", "(via docs/…)"
        if re.search(r"(?i)natural earth|nasa|gibs|blue marble|world-atlas|tz database|iana|thequizwire|docs/|registry", nm): continue   # base data / internal
        if nm and nm.lower() not in {x.lower() for x in names}: names.append(nm)
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
# 2026-10-19 (owner): NO templates. Every channel's text is WRITTEN per episode by the author, in episode.json#post.copy:
#   {"youtube_title": str, "youtube": str, "instagram": str, "facebook": str, "x": str, "threads": str, "spoilers": [str,...]}
# Hashtags are written inline by the author (last line of each text). postkit only: appends the sources line (YouTube),
# the AI-narration disclosure (Facebook), extracts the hashtags, and LINTS: spoiler gate, template-repeat gate, platform limits.
DEMONYMS = {"netherlands": ["dutch", "holland", "hollander", "amsterdam"], "brazil": ["brazilian", "brasil", "seleção", "selecao", "pelé", "pele"],
            "indonesia": ["indonesian", "komodo island", "flores", "rinca"], "botswana": ["batswana", "motswana", "okavango", "chobe", "gaborone"],
            "russia": ["russian", "siberia", "siberian", "baikal", "irkutsk"], "greece": ["greek", "athens", "athenian", "marathon to athens"],
            "canada": ["canadian", "ottawa"], "usa": ["american", "americans", "united states"], "united states": ["american", "americans"],
            "germany": ["german"], "italy": ["italian"], "france": ["french"], "india": ["indian"], "australia": ["australian"],
            "kenya": ["kenyan"], "south africa": ["south african"], "tanzania": ["tanzanian"], "philippines": ["filipino"], "united kingdom": ["british", "london"]}
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]+|\d[\d.,]*")


def spoiler_terms(E, V, post):
    """Everything that identifies the answer: the option itself, its demonyms/places, authored extras, numbers on the fact cards."""
    ans = answer_text(E); terms = set()
    for w in re.findall(r"[A-Za-z]{3,}", ans): terms.add(w.lower())
    terms.add(ans.lower())
    terms |= set(DEMONYMS.get(ans.lower(), []))
    terms |= {str(t).lower() for t in post.get("copy", {}).get("spoilers", [])}
    nums = set()
    for el in V.get("elements", []):
        if el.get("type") != "fact": continue
        for n in re.findall(r"\d[\d.,]*", (el.get("kicker") or "") + " " + (el.get("text") or "")):
            n = n.strip(".,")
            if len(n) >= 2 and n not in {"10", "20", "30", "50", "100"}: nums.add(n)
    return terms, nums


def find_spoilers(text, terms, nums, allowed, options=(), answer=""):
    """Return the spoiler hits in `text`, ignoring words that already appear in the question. Naming the answer is allowed
    ONLY when every option is named in the same text (that is listing the choices, not revealing the pick); demonyms,
    places and fact-card numbers are never allowed."""
    low = text.lower(); hits = []
    lists_all = bool(options) and all(o.lower() in low for o in options)
    ans_words = {answer.lower()} | {w.lower() for w in re.findall(r"[A-Za-z]{3,}", answer)}
    for t in sorted(terms, key=len, reverse=True):
        if t in allowed: continue
        if lists_all and t in ans_words: continue
        if re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", low) or re.search(r"#\w*" + re.escape(t.replace(" ", "")), low): hits.append(t)
    for n in nums:
        if re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", low): hits.append(n)
    return sorted(set(hits))


def sentences(text):
    out = []
    for line in text.split("\n"):
        line = re.sub(r"#\w+", "", line)
        for s_ in re.split(r"(?<=[.!?…])\s+", line):
            n = re.sub(r"[^a-z0-9 ]", "", s_.lower()).strip()
            if len(n) >= 25: out.append(n)
    return out


def other_episode_sentences(ep):
    """Sentences used by every OTHER episode's authored copy (the template-repeat gate)."""
    seen = {}
    for e in (ROOT / "series").glob("*/*/episode.json"):
        if e.parent.resolve() == Path(ep).resolve(): continue
        try: c = json.loads(e.read_text()).get("post", {}).get("copy", {})
        except Exception: continue
        for k, v in c.items():
            if isinstance(v, str):
                for s_ in sentences(v): seen.setdefault(s_, e.parent.name)
    return seen


def tags_in(text): return [h for h in re.findall(r"#\w+", text)]


def build(ep):
    E, V, R = load(ep)
    slug = E.get("series", "")
    S = CFG["series"].get(slug) or {"name": slug.title(), "emoji": "❓", "topic": "quiz", "youtube_category": "24", "playlist": slug, "hashtags": {}, "keywords": []}
    post = E.get("post", {}); copy = post.get("copy") or {}
    question = E["title"].strip(); q_clean = EMOJI.sub("", question).strip()
    ans = answer_text(E); srcs = source_names(R)
    _terms, _ = spoiler_terms(E, V, post)
    srcs = [x for x in srcs if not any(re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", x.lower()) for t in _terms)]
    missing = [k for k in ("youtube_title", "youtube", "instagram", "facebook", "x", "threads") if not str(copy.get(k, "")).strip()]
    g = lambda k: str(copy.get(k, "")).strip()

    # ---- YouTube: authored title + body; sources belong here (the only channel where a long description is read by search)
    yt_title = g("youtube_title")
    yt_body = g("youtube")
    yt_tags = tags_in(yt_body)
    body_wo = re.sub(r"(\s*#\w+)+\s*$", "", yt_body).rstrip()
    yt_lines = [body_wo]
    if srcs: yt_lines += ["", "Sources: " + " · ".join(srcs) + ". Map: Natural Earth, NASA Blue Marble. Narration: synthetic voice (Kokoro)."]
    yt_lines += ["", " ".join(yt_tags)]
    yt_desc = "\n".join(yt_lines).strip()
    yt = {"title": yt_title, "description": yt_desc, "hashtags": yt_tags, "categoryId": str(S["youtube_category"]),
          "madeForKids": CFG["youtube"]["made_for_kids"], "notifySubscribers": CFG["youtube"]["notify_subscribers"],
          "privacy": CFG["youtube"]["privacy"], "license": CFG["youtube"]["license"], "embeddable": CFG["youtube"]["embeddable"],
          "isAiGenerated": bool(post.get("youtube_is_ai_generated", CFG["disclosure"]["youtube_is_ai_generated"])),
          "keywords": list(dict.fromkeys(S.get("keywords", []) + [k.lower() for k in post.get("keywords", [])]))[:12],   # keywords are metadata, not visible; the answer stays out anyway
          "playlist": S["playlist"]}

    # ---- Instagram: authored caption as written (hook in the first 125 chars is the author's job; lint warns)
    ig_caption = g("instagram")
    ig = {"caption": ig_caption, "firstComment": "", "hashtags": tags_in(ig_caption), "shouldShareToFeed": True,
          "isAiGenerated": bool(CFG["disclosure"]["instagram_is_ai_generated"]), "thumbnailOffsetMs": 0}

    # ---- Facebook: authored text + the one line Meta asks for (synthetic narration)
    fb_body = g("facebook"); fb_tags = tags_in(fb_body)
    fb_wo = re.sub(r"(\s*#\w+)+\s*$", "", fb_body).rstrip()
    fb_text = "\n".join([fb_wo, CFG["disclosure"]["facebook_caption_line"], " ".join(fb_tags)]).strip()
    fb = {"text": fb_text, "firstComment": "", "hashtags": fb_tags}

    # ---- X and Threads: as written
    x_text = g("x"); th_text = g("threads")
    x = {"text": x_text, "hashtags": tags_in(x_text), "isAiGenerated": bool(CFG["disclosure"].get("twitter_is_ai_generated", True))}
    th = {"text": th_text, "hashtags": tags_in(th_text)}

    kit = {"episode": Path(ep).name, "series": slug, "question": question, "answer": ans, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "youtube": yt, "instagram": ig, "facebook": fb, "twitter": x, "threads": th}
    kit["checks"] = check(kit)
    F = kit["checks"]["fail"]
    if missing: F.insert(0, f"post.copy missing authored text for: {', '.join(missing)} (owner 2026-10-19: no templates — write each channel by hand)")
    # ---- spoiler gate (hard): the answer, its demonyms/places, authored extras and the fact-card numbers may not appear anywhere
    terms, nums = spoiler_terms(E, V, post)
    allowed = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", q_clean)}
    for name, text in (("YT title", yt_title), ("YT", yt_desc), ("IG", ig_caption), ("FB", fb_text), ("X", x_text), ("Threads", th_text)):
        hits = find_spoilers(text, terms, nums, allowed, E.get("quiz", {}).get("options", []), ans)
        if hits: F.append(f"SPOILER {name}: {hits} — the copy gives the answer away")
    # ---- template gate (hard): no sentence reused from another episode; no two channels opening with the same line
    seen = other_episode_sentences(ep)
    for k in ("youtube", "instagram", "facebook", "x", "threads"):
        for s_ in sentences(g(k)):
            if s_ in seen: F.append(f"TEMPLATE {k}: '{s_[:60]}…' also used in {seen[s_]} — write it fresh")
    firsts = {k: re.sub(r"[^a-z0-9 ]", "", g(k).split("\n")[0].lower()).strip() for k in ("youtube", "instagram", "facebook", "x", "threads")}
    for a_ in firsts:
        for b_ in firsts:
            if a_ < b_ and firsts[a_] and firsts[a_] == firsts[b_]: F.append(f"TEMPLATE: {a_} and {b_} open with the same line — each channel gets its own opening")
    for k in ("youtube", "instagram", "facebook", "x", "threads"):
        if re.search(r"(?i)\b(guess in \d|watch the reveal|which did you pick|three quick facts|answer \+|you get \d)", g(k)): F.append(f"TEMPLATE {k}: stock quiz phrase — say it like a person")
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
    if len(th["hashtags"]) > 1: F.append(f"Threads hashtags {len(th['hashtags'])} (want 0–1 — only the first becomes a topic tag)")
    t = yt["title"]
    if len(t) > 100: F.append(f"YT title {len(t)} chars > 100")
    elif len(t) > 85: W.append(f"YT title {len(t)} chars (aim ≤ 80 so feeds show it whole)")
    if len(t) < 30: W.append("YT title < 30 chars (looks low-effort)")
    body, *tail = re.split(r"\s+(?=#)", t, maxsplit=1)
    if "#" in body or len(re.findall(r"#\w+", t)) > 2: F.append("YT title: at most 2 hashtags, only at the END (decode 2026-10-18: winners carry 2–3 search tags in Shorts titles)")
    if len(EMOJI.findall(t)) > 2: W.append("YT title has > 2 emoji")
    first = yt["description"].split("\n")[0]
    if len(first) > 120: W.append(f"YT description first line {len(first)} chars (the first ~100 are the search snippet)")
    if len(yt["description"]) > 5000: F.append("YT description > 5000 chars")
    if not 2 <= len(yt["hashtags"]) <= 5: F.append(f"YT hashtags {len(yt['hashtags'])} (want 2–5)")
    if not yt["description"].rstrip().endswith(" ".join(yt["hashtags"])): F.append("YT hashtags must be the last line of the description")
    if len(ig["caption"]) > 2200: F.append("IG caption > 2200 chars")
    hook = ig["caption"].split("\n")[0]
    if len(hook) > 125: W.append(f"IG hook line {len(hook)} chars (> 125 gets cut behind 'more')")
    if not 3 <= len(ig["hashtags"]) <= 5: F.append(f"IG hashtags {len(ig['hashtags'])} (want 3–5)")
    if ig["caption"] and len(ig["caption"].split("\n")[0]) > 125: F.append("IG: the opening line must fit in 125 chars (what shows before 'more')")
    if re.search(r"https?://|www\.", ig["caption"]): W.append("IG caption has a URL (not clickable; sources belong in the first comment)")
    if len(fb["text"]) > 1000: W.append("FB text > 1000 chars")
    if not 1 <= len(fb["hashtags"]) <= 3: F.append(f"FB hashtags {len(fb['hashtags'])} (want 1–3)")
    if len(fb["text"]) > 400: W.append(f"FB text {len(fb['text'])} chars (reel descriptions read best under ~300)")
    if x_len(x["text"]) > 280: F.append(f"X text {x_len(x['text'])} weighted chars > 280")
    elif x_len(x["text"]) > 260: W.append(f"X text {x_len(x['text'])} weighted chars (aim ≤ 260)")
    if not 1 <= len(x["hashtags"]) <= 2: F.append(f"X hashtags {len(x['hashtags'])} (want 1–2)")
    for name, text in (("YT", yt["title"] + "\n" + yt["description"]), ("IG", ig["caption"]), ("FB", fb["text"]), ("X", x["text"]), ("Threads", th["text"])):
        if BANNED.search(text): F.append(f"{name}: tease of a next/tomorrow video (owner rule: no announcements)")
        for h in re.findall(r"#\S+", text):
            if not HASHTAG.match(h): F.append(f"{name}: malformed hashtag {h!r}")
    if not kit.get("answer"): F.append("no answer text (quiz.options/correct missing)")
    if yt["title"] and not re.search(r"\?", yt["title"]) and not re.search(r"\b(which|where|who|what|how|why)\b", yt["title"], re.I): W.append("YT title is not a question (quiz titles that ask outperform statements for us)")
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
