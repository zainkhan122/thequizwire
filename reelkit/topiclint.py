"""topiclint.py — Q22: the topic decision must be written and reasoned (docs/TOPIC_GUIDELINES.md).

  python3 reelkit/topiclint.py <episode_dir>     # exit 1 on FAIL
Checks: topic.md exists; every section present and substantive; Signal names a source; the question stem is not among the last
five live/ready episodes of the channel; the question shape differs from the previous two episodes of the same series; Ship by is a date.
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ["Signal", "Why this, why now", "Viewer takeaway", "Question shape", "Options and why they fool", "Search term", "Rejected alternatives", "Ship by", "Copy"]
MIN = {"Signal": 30, "Why this, why now": 60, "Viewer takeaway": 30, "Question shape": 40, "Options and why they fool": 80, "Search term": 5, "Rejected alternatives": 40, "Ship by": 10, "Copy": 80}
SOURCE = re.compile(r"https?://|calendar:|comment:|suggest:|trends?:|wikipedia:|news:", re.I)

def stem(q):
    w = re.findall(r"[A-Za-z']+", q); caps = [x.lower() for x in w if x.isupper() and len(x) > 2]
    return " ".join([*(x.lower() for x in w[:2]), *caps[:1]])

def sections(md):
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r"##\s+(.*)", line)
        if m: cur = m.group(1).strip(); out[cur] = ""
        elif cur: out[cur] += line + "\n"
    return {k: v.strip() for k, v in out.items()}

def question_of(E): return (E.get("quiz") or {}).get("question") or E.get("question", "")

def recent(ep_dir):
    """Other episodes that are live or ready, newest first by number within the whole channel (ledger due_at when known)."""
    ledger = json.loads((ROOT / "dispatch/ledger.json").read_text()).get("posts", []) if (ROOT / "dispatch/ledger.json").exists() else []
    due = {}
    for p in ledger:
        if p.get("state") in ("scheduled", "sent"): due[p["episode"]] = max(due.get(p["episode"], ""), p.get("due_at", ""))
    rows = []
    for ej in ROOT.glob("series/*/ep*/episode.json"):
        if "_template" in str(ej) or ej.parent.resolve() == Path(ep_dir).resolve(): continue
        E = json.loads(ej.read_text()); name = ej.parent.name
        if name in due or E.get("status") == "ready":
            tp = ej.parent / "topic.md"; shape = sections(tp.read_text()).get("Question shape", "").split("—")[0].strip().lower() if tp.exists() else ""
            rows.append((due.get(name, "0000") + f"{int(E.get('number', 0)):04d}", ej.parent.parent.name, question_of(E), shape))
    return sorted(rows, reverse=True)

def run(ep_dir):
    F, W = [], []; ep = Path(ep_dir); E = json.loads((ep / "episode.json").read_text()); tp = ep / "topic.md"
    if not tp.exists(): return [f"Q22: {tp.name} missing — write the topic decision first (docs/TOPIC_GUIDELINES.md)"], W
    S = sections(tp.read_text())
    for k in SECTIONS:
        if k not in S: F.append(f"Q22: topic.md section '## {k}' missing")
        elif len(S[k]) < MIN[k]: F.append(f"Q22: topic.md '{k}' is too thin ({len(S[k])} chars) — write the actual reasoning")
    if S.get("Signal") and not SOURCE.search(S["Signal"]): F.append("Q22: Signal must name a source (URL, suggest:, trends:, wikipedia:, calendar:, comment:, news:)")
    if S.get("Ship by") and not re.search(r"\d{4}-\d{2}-\d{2}", S["Ship by"]): F.append("Q22: Ship by needs a YYYY-MM-DD date")
    if S.get("Rejected alternatives") and S["Rejected alternatives"].count("\n- ") + S["Rejected alternatives"].startswith("- ") < 1: F.append("Q22: list at least one rejected alternative")
    q = question_of(E); my = stem(q); R = recent(ep_dir)
    for _, s, oq, _ in R[:5]:
        if stem(oq) == my: F.append(f"Q22: question stem '{my}' repeats a recent episode ('{oq}') — choose another question shape")
    my_shape = S.get("Question shape", "").split("—")[0].strip().lower()
    same = [r for r in R if r[1] == E.get("series")][:2]
    if my_shape and len(same) == 2 and all(r[3] == my_shape for r in same): F.append(f"Q22: '{my_shape}' is the shape of the last two {E.get('series')} episodes — vary it")
    if S.get("Search term") and not re.search(r'"[^"]{4,}"', S["Search term"]): W.append("Q22: put the search term in quotes exactly as typed")
    return F, W

if __name__ == "__main__":
    F, W = run(sys.argv[1])
    for x in F: print("  FAIL ", x)
    for x in W: print("  WARN ", x)
    print(f"topiclint: {Path(sys.argv[1]).name} → FAIL {len(F)} WARN {len(W)}"); sys.exit(1 if F else 0)
