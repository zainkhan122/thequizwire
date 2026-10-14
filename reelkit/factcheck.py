#!/usr/bin/env python3
"""Fact gate: every factual thing the episode SAYS or SHOWS must trace to the claims ledger.

    python3 reelkit/factcheck.py <episode_dir> [--hf <hf_dir>] [--report out/factcheck.json]
                                 [--online] [--archive]

Inputs
  <ep>/research.json   sources, claims (each with VO/screen anchors), myths, guardrails, landscape
  <ep>/timeline.json   aligned VO words (what is actually spoken)
  <hf>/index.html      built composition (what is actually on screen); optional

FAIL (exit 1)
  - ledger (evidence tiers):
      core    load-bearing story claim      ≥ 2 independent publishers, ≥ 1 primary/scholarly
      record  uncontested public record     ≥ 2 publishers, ≥ 1 fact-checked reference or stronger
      detail  colour (place names, labels)  ≥ 2 publishers
      framing characterisation              ≥ 1
    quotes need a quote_origin (first publication of the words), which counts as primary for that quote;
    unknown source ids, or sources missing url/type/date/publisher, also FAIL
  - drift: a claim's VO/screen anchor no longer appears in the episode (script changed, ledger didn't)
  - coverage: a narrated sentence carrying a checkable token (number, date, year, name, quote)
    that no claim anchor covers
  - coverage: an on-screen text unit that is neither spoken, claimed nor exempt
  - guardrail: a forbidden phrase in VO, on screen or in POST_KIT.md
  - research brief: < 5 sources, < 3 landscape entries, or an empty our_gap
WARN
  - claims with caveats (shown so the writer sees them each run)
  - with --online: dead or blocked links (sites often 403 bots, so this never FAILs)
--archive  writes Wayback snapshot URLs back into research.json (sources[*].archived)
"""
import html as html_mod  # noqa (alias kept for map_units)
import argparse, html, json, re, sys, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

UNIT = set("tag cap stamp node strip kicker quote bigserif hr filmlabel filmcredit credit ename efollow "
           "clabel fivelabel bug waitbox counter startglow eklogo qby num title "
           "tu".split())          # tu = generic text unit: any new on-screen text element in a build must carry a unit class
SPOKEN_UNITS = {"cap"}                       # captions mirror the VO; checked via the VO path
TYPES = {"primary", "scholarly", "reference", "press"}
STRONG = {"primary", "scholarly"}
WEIGHTS = {"core", "record", "detail", "framing"}   # see policy in docstring
NUMWORDS = set(("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand "
                "million billion first third fourth fifth sixth seventh eighth ninth tenth dozen").split())
MONTHS = set("january february march april may june july august september october november december".split())
STOP_CAPS = set("i a the and but so then it he she they we when one for".split())


def norm(s: str) -> str:
    s = html.unescape(s).replace("\xa0", " ").lower()
    s = s.replace("’", "'").replace("‘", "'").replace("—", " ").replace("–", "-")
    s = re.sub(r"(?<=\w)-(?=\w)", " ", s)            # twenty-three -> twenty three
    s = re.sub(r"[^\w'\s:.·/]", " ", s)              # keep : . · / (times, dates, labels)
    s = re.sub(r"(?<!\d)[.:·/]|[.:·/](?!\d)", " ", s)  # ...but only inside numbers
    return re.sub(r"\s+", " ", s).strip()


class Units(HTMLParser):
    """Collect visible text per top-most UNIT element (same unit model as textqa)."""
    VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.units, self.skip, self.bare = [], [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            if tag == "br" and any(u is not None for _, _, u, _ in self.stack):
                self._append(" ")
            return
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        inside = any(u is not None for _, _, u, _ in self.stack)
        uid = None
        if not inside and (cls & UNIT):
            uid = len(self.units)
            self.units.append({"cls": " ".join(sorted(cls & UNIT)), "id": a.get("id", ""), "text": "", "fc": a.get("data-fc", "")})
        if tag in ("script", "style") or a.get("data-fc") == "skip":     # option letter badges, decorative glyphs
            self.skip += 1
        self.stack.append((tag, cls, uid, a.get("data-fc") == "skip"))

    def handle_endtag(self, tag):
        while self.stack:
            t, _, _, sk = self.stack.pop()
            if t in ("script", "style") or sk:
                self.skip -= 1
            if t == tag:
                break

    def _append(self, s):
        for _, _, u, _ in reversed(self.stack):
            if u is not None:
                self.units[u]["text"] += s
                return

    def handle_data(self, d):
        if self.skip:
            return
        if d.strip() and not any(u is not None for _, _, u, _ in self.stack) and not any(t in ("head", "title") for t, _, _, _ in self.stack):
            # visible text outside every unit would escape the ledger check — reported as a FAIL by run()
            key = " ".join(c for _, cls, _, _ in self.stack[-2:] for c in sorted(cls))
            if self.bare and self.bare[-1][0] == key: self.bare[-1][1] += d
            else: self.bare.append([key, d])
        self._append(d)


def bare_text(index_html: Path):
    """Visible text that sits in no text unit (give its element class `tu`)."""
    p = Units(); p.feed(index_html.read_text(encoding="utf-8"))
    return [f".{k.replace(' ', '.')} :: {re.sub(r'\s+', ' ', t).strip()[:70]}" for k, t in p.bare]


def map_units(html_text: str):
    """Text the map runtime (engine/geo-runtime.js) renders at run time from the inline scene spec
    (<script type="application/json" id="geo_<sid>_spec">): pin labels, place labels and the disputed-border policy
    plates (name / Administered by … / Claimed by …). Static HTML never contains them, so the ledger scan reads the spec."""
    out = []
    for m in re.finditer(r'<script type="application/json" id="(geo_[^"]+_spec)">(.*?)</script>', html_text, re.S):
        try: spec = json.loads(m.group(2))
        except json.JSONDecodeError: continue
        sid = m.group(1)[:-5]
        for pin in spec.get("pins", []):
            if pin.get("label"): out.append({"cls": "pinlabel", "id": f"{sid}_pin_{pin.get('id', '')}", "text": pin["label"], "fc": pin.get("fc", "")})
        for lab in spec.get("labels", []):
            raw = lab.get("html") or lab.get("text") or ""
            for part in re.split(r"<br\s*/?>|</b>|<i>|</i>", raw):
                t = html_mod.unescape(re.sub(r"<[^>]+>", "", part)).strip()
                if t: out.append({"cls": "geo-label " + (lab.get("cls") or ""), "id": f"{sid}_lbl_{lab.get('id', '')}", "text": t, "fc": lab.get("fc", "")})
    return out


def screen_units(index_html: Path):
    p = Units()
    text = index_html.read_text(encoding="utf-8")
    p.feed(text)
    out, seen = [], set()
    for u in p.units + map_units(text):
        t = re.sub(r"\s+", " ", u["text"].replace("\xa0", " ")).strip()
        if not t or (u["cls"], t) in seen:
            continue
        seen.add((u["cls"], t))
        out.append({**u, "text": t})
    return out


def vo_sentences(timeline: dict):
    words = timeline["words"]
    sents, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.?!][\"”']?$", w["w"]):
            sents.append(cur); cur = []
    if cur:
        sents.append(cur)
    out = []
    for ws in sents:
        raw = " ".join(w["w"] for w in ws)
        out.append({"t": round(ws[0]["s"], 2), "raw": raw, "norm": norm(raw), "first": ws[0]["w"]})
    return out


def risky_tokens(raw: str):
    """Checkable tokens in a narrated sentence: numbers, number words, months, years, mid-sentence names, quotes."""
    toks = []
    words = raw.split()
    for i, w in enumerate(words):
        n = norm(w)
        if not n:
            continue
        bare = re.sub(r"'s$", "", n)
        if re.search(r"\d", n) or bare in NUMWORDS or bare in MONTHS:
            toks.append(n)
        elif i > 0 and w[:1].isupper() and not re.search(r"[.?!]$", words[i - 1]) and bare not in STOP_CAPS:
            toks.append(n)                          # proper noun mid-sentence
    if re.search(r"[\"“”]", raw) or re.search(r"\bhe said\b|\bshe said\b|\bsaid\b", raw, re.I):
        toks.append("<quote>")
    return toks


def wayback(url: str):
    q = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    with urllib.request.urlopen(urllib.request.Request(q, headers={"User-Agent": "quizwire-factcheck"}), timeout=20) as r:
        snap = json.load(r).get("archived_snapshots", {}).get("closest") or {}
    return snap.get("url") if snap.get("available") else None


def link_status(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (quizwire factcheck)"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # DNS, TLS, timeout
        return f"error: {type(e).__name__}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("--hf", help="built HyperFrames dir (default ~/.cache/build/<ep>/hf)")
    ap.add_argument("--report")
    ap.add_argument("--online", action="store_true", help="check every source URL responds")
    ap.add_argument("--archive", action="store_true", help="look up Wayback snapshots and write them into research.json")
    ap.add_argument("--sources-md", help="write a paste-ready 'Sources' block for the video description")
    a = ap.parse_args()
    ep = Path(a.ep).resolve()
    rpath = ep / "research.json"
    if not rpath.exists():
        sys.exit(f"factcheck: {rpath} missing — every episode needs a claims ledger (see docs/OPENMONTAGE_LESSONS.md §D)")
    R = json.loads(rpath.read_text())
    T = json.loads((ep / "timeline.json").read_text())
    hf = Path(a.hf) if a.hf else Path.home() / ".cache/build" / ep.name / "hf"
    fails, warns = [], []
    F = lambda kind, msg, **k: fails.append({"kind": kind, "msg": msg, **k})
    W = lambda kind, msg, **k: warns.append({"kind": kind, "msg": msg, **k})

    # ---------- ledger integrity ----------
    S = R.get("sources", {})
    for sid, s in S.items():
        miss = [k for k in ("url", "type", "date", "publisher") if not s.get(k)]
        if miss:
            F("source", f"{sid}: missing {', '.join(miss)}")
        if s.get("type") not in TYPES:
            F("source", f"{sid}: type '{s.get('type')}' not in {sorted(TYPES)}")
    claims = R.get("claims", [])
    ids = [c["id"] for c in claims]
    for d in {i for i in ids if ids.count(i) > 1}:
        F("ledger", f"duplicate claim id {d}")
    for c in claims:
        src = c.get("sources", [])
        unknown = [x for x in src if x not in S]
        if unknown:
            F("ledger", f"{c['id']}: unknown source id(s) {unknown}")
        w = c.get("weight")
        if w not in WEIGHTS:
            F("ledger", f"{c['id']}: weight '{w}' not in {sorted(WEIGHTS)}")
            continue
        pubs = {S[x]["publisher"] for x in src if x in S}
        need = 1 if w == "framing" else 2
        if len(pubs) < need:
            F("ledger", f"{c['id']}: {len(pubs)} independent publisher(s), need {need}", claim=c["text"])
        types = {S.get(x, {}).get("type") for x in src}
        if c.get("type") == "quote":
            o = c.get("quote_origin")
            if not o or o not in src:
                F("ledger", f"{c['id']}: quote needs a quote_origin (first publication of the words) listed in its sources")
            else:
                types.add("primary")                    # the first publication IS the primary evidence of a quote
        if w == "core" and not types & STRONG:
            F("ledger", f"{c['id']}: core claim has no primary/scholarly source", claim=c["text"])
        if w == "record" and not types & (STRONG | {"reference"}):
            F("ledger", f"{c['id']}: public-record claim needs a fact-checked reference or stronger", claim=c["text"])
        if c.get("caveat"):
            W("caveat", f"{c['id']}: {c['caveat']}")

    # ---------- research brief completeness ----------
    if len(S) < 5:
        F("brief", f"only {len(S)} sources (need ≥ 5)")
    land = R.get("landscape", {})
    if len(land.get("existing", [])) < 3:
        F("brief", "landscape needs ≥ 3 existing pieces (url, angle, misses)")
    if not str(land.get("our_gap", "")).strip():
        F("brief", "landscape.our_gap is empty — what does this episode add?")

    # ---------- VO coverage + drift ----------
    # Anchors are matched against the WHOLE narration with global offsets, so an anchor may straddle sentences.
    sents = vo_sentences(T)
    vo_all, offs = "", []
    for s in sents:
        offs.append(len(vo_all) + (1 if vo_all else 0))
        vo_all = (vo_all + " " + s["norm"]) if vo_all else s["norm"]
    spans = []                                         # (start, end, claim_id) in vo_all
    for c in claims:
        for an in c.get("vo", []):
            n = norm(an)
            hits = [(m.start(), m.end(), c["id"]) for m in re.finditer(r"(?<!\w)" + re.escape(n) + r"(?!\w)", vo_all)] if n else []
            if hits:
                spans += hits
            else:
                F("drift", f"{c['id']}: VO anchor not found in narration: '{an}'")
    vo_rows = []
    vo_exempt = [re.compile(x, re.I) for x in R.get("vo_exempt", [])]
    for s, o in zip(sents, offs):
        if any(rx.search(s["raw"]) for rx in vo_exempt):
            vo_rows.append({"t": s["t"], "text": s["raw"], "status": "exempt", "claims": [], "checkable": []}); continue
        e = o + len(s["norm"])
        mine = [(a0, b0, cid) for a0, b0, cid in spans if a0 < e and b0 > o]
        toks = risky_tokens(s["raw"])
        bad = []
        for t in toks:
            if t == "<quote>":
                ok = any(cid for *_, cid in mine if any(c.get("type") == "quote" and c["id"] == cid for c in claims))
            else:
                occ = [o + m.start() for m in re.finditer(r"(?<!\w)" + re.escape(t) + r"(?!\w)", s["norm"])]
                ok = bool(occ) and all(any(a0 <= p0 and p0 + len(t) <= b0 for a0, b0, _ in mine) for p0 in occ)
            if not ok:
                bad.append(t)
        row = {"t": s["t"], "text": s["raw"], "claims": sorted({cid for *_, cid in mine}), "checkable": toks}
        if bad:
            row["uncovered"] = bad
            F("coverage", f"VO t={s['t']}s: uncovered {bad} in “{s['raw']}”")
        vo_rows.append(row)

    # ---------- screen coverage + drift ----------
    screen_rows = []
    exempt = [re.compile(x) for x in R.get("screen_exempt", [])]
    if (hf / "index.html").exists():
        units = screen_units(hf / "index.html")
        for b in bare_text(hf / "index.html"):
            F("unit", f"on-screen text outside any text unit (add class `tu`): {b}")
        scr_norms = [(norm(u["text"]), u) for u in units]
        anchors_scr = []
        for c in claims:
            for an in c.get("screen", []):
                n = norm(an)
                if n and any(n == un or n in un for un, _ in scr_norms):
                    anchors_scr.append((n, c["id"]))
                else:
                    F("drift", f"{c['id']}: screen anchor not on screen: '{an}'")
        for un, u in scr_norms:
            if not un:
                continue
            row = {"text": u["text"], "cls": u["cls"], "id": u["id"]}
            if u.get("fc") == "distractor":                 # quiz wrong answers: not claims (engine/quiz.py marks them)
                row["status"] = "distractor"
            elif u["cls"] in SPOKEN_UNITS or (len(un) > 3 and un in vo_all):
                row["status"] = "spoken"
            elif any(rx.search(u["text"]) for rx in exempt):
                row["status"] = "exempt"
            else:
                hit = [cid for n, cid in anchors_scr if n == un or n in un]
                if hit:
                    row["status"], row["claims"] = "claimed", sorted(set(hit))
                else:
                    row["status"] = "UNACCOUNTED"
                    F("coverage", f"screen text not in ledger: “{u['text']}” (.{u['cls']}#{u['id']})")
            screen_rows.append(row)
    else:
        W("screen", f"{hf}/index.html not built — on-screen text not checked (run the build stage first)")

    # ---------- guardrails ----------
    texts = {"vo": vo_all, "screen": " | ".join(norm(r["text"]) for r in screen_rows)}
    pk = ep / "POST_KIT.md"
    if pk.exists():
        texts["post_kit"] = norm(pk.read_text())
    for g in R.get("guardrails", []):
        pat = g["never"].replace("-", "[ -]?")        # text is normalised (hyphens -> spaces); match either form
        rx = re.compile(r"\b(?:" + pat + r")\b", re.I)
        for where, t in texts.items():
            m = rx.search(t)
            if m:
                F("guardrail", f"'{m.group(0)}' in {where} — {g['why']}")

    # ---------- optional network checks ----------
    links = {}
    if a.online or a.archive:
        for sid, s in S.items():
            st = link_status(s["url"])
            links[sid] = st
            if st != 200:
                W("link", f"{sid}: {s['url']} → {st}" + (f" (archived: {s['archived']})" if s.get("archived") else ""))
            if a.archive and not s.get("archived"):
                try:
                    snap = wayback(s["url"])
                    if snap:
                        s["archived"] = snap
                except Exception as e:
                    W("archive", f"{sid}: wayback lookup failed ({type(e).__name__})")
        if a.archive:
            rpath.write_text(json.dumps(R, ensure_ascii=False, indent=1) + "\n")

    # ---------- report ----------
    n_claimed = sum(1 for r in screen_rows if r.get("status") == "claimed")
    summary = {"claims": len(claims), "sources": len(S),
               "strong_sources": sum(1 for s in S.values() if s.get("type") in STRONG),
               "vo_sentences": len(vo_rows), "vo_checkable": sum(1 for r in vo_rows if r["checkable"]),
               "screen_units": len(screen_rows), "screen_claimed": n_claimed,
               "fail": len(fails), "warn": len(warns)}
    rep = {"summary": summary, "fails": fails, "warns": warns, "vo": vo_rows, "screen": screen_rows, "links": links}
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    if a.sources_md:
        used = []
        for c in claims:
            for x in c.get("sources", []):
                if x in S and x not in used:
                    used.append(x)
        rank = {"primary": 0, "scholarly": 1, "press": 2, "reference": 3}
        used.sort(key=lambda x: (rank.get(S[x]["type"], 9), S[x]["date"]))
        lines = ["Sources (primary first):"]
        for x in used:
            s_ = S[x]
            lines.append(f"• {s_['publisher']}, “{s_['title']}” ({s_['date'][:4]}) {s_['url']}")
        myths = R.get("myths", [])
        if myths:
            lines += ["", "Common myth, corrected:"] + [f"• “{m['myth']}” → {m['reality']}" for m in myths]
        Path(a.sources_md).parent.mkdir(parents=True, exist_ok=True)
        Path(a.sources_md).write_text("\n".join(lines) + "\n")
    for f in fails:
        print(f"  FAIL  [{f['kind']}] {f['msg']}")
    for w in warns:
        print(f"  WARN  [{w['kind']}] {w['msg']}")
    print(f"claims {summary['claims']} · sources {summary['sources']} ({summary['strong_sources']} primary/scholarly) · "
          f"VO sentences {summary['vo_sentences']} ({summary['vo_checkable']} checkable) · "
          f"screen units {summary['screen_units']} ({n_claimed} claimed)  →  FAIL {len(fails)}  WARN {len(warns)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
