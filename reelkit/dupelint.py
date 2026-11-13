#!/usr/bin/env python3
"""reelkit/dupelint.py — Q25 topic-duplicate gate (2026-11-13).

Why: three backlog episodes (heart transplant, first modern Olympics, France time zones) were authored on topics that had
already been PUBLISHED or scheduled under another number. Nothing in the pipeline compared a new episode with the catalogue.
A repeated answer is a repeated Short: the audience sees the same reveal twice and the channel looks automated.

Rule: the episode FAILS when any OTHER episode in series/ (any series, any status) has
  • the same answer (answer_line / correct option, normalised), AND the two questions share ≥ 50 % of their content words, OR
  • a question with ≥ 80 % shared content words (same ask, different wording), OR
  • the same slug stem after the epNN- prefix.
Usage: python3 reelkit/dupelint.py <episode_dir>   (exit 1 on FAIL) · called from episode.sh quizlint stage.
"""
import glob, json, os, re, sys

STOP = {"the", "a", "an", "of", "in", "on", "is", "was", "does", "do", "did", "which", "what", "where", "who", "how", "many",
        "most", "first", "country", "has", "have", "use", "uses", "its", "to", "by", "with", "and", "or", "world", "world's",
        "earth", "animal", "human", "ever", "than", "more", "that", "this", "there", "are", "for", "from", "into"}

def words(q):
    return {w for w in re.findall(r"[a-z0-9']+", (q or "").lower()) if w not in STOP and len(w) > 2}

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def load(d):
    try: e = json.load(open(os.path.join(d, "episode.json")))
    except Exception: return None
    q = e.get("quiz") or {}
    opts = q.get("options") or []
    ans = q.get("answer_line") or (opts[q["correct"]] if isinstance(q.get("correct"), int) and q["correct"] < len(opts) else "")
    return {"dir": d, "slug": os.path.basename(d), "stem": re.sub(r"^ep\d+-", "", os.path.basename(d)),
            "question": q.get("question") or e.get("title") or "", "answer": norm(ans), "status": e.get("status")}

def main():
    ep = sys.argv[1].rstrip("/")
    me = load(ep)
    if not me: sys.exit(f"dupelint: {ep}/episode.json unreadable")
    mw = words(me["question"]); fails = []
    for d in sorted(glob.glob("series/*/ep*")):
        if os.path.abspath(d) == os.path.abspath(ep): continue
        o = load(d)
        if not o: continue
        ow = words(o["question"]); shared = len(mw & ow) / max(1, min(len(mw), len(ow)))
        if o["stem"] == me["stem"]:
            fails.append(f"same slug stem as {o['slug']} ({o['status']})")
        elif me["answer"] and me["answer"] == o["answer"] and shared >= 0.5:
            fails.append(f"same answer “{me['answer']}” and {shared:.0%} shared question words as {o['slug']} ({o['status']}): “{o['question']}”")
        elif shared >= 0.8 and len(mw) >= 2:
            fails.append(f"question repeats {o['slug']} ({o['status']}) — {shared:.0%} shared words: “{o['question']}”")
    for f in fails: print(f"  FAIL  Q25 duplicate topic: {f}")
    print(f"dupelint: {me['slug']} → {'FAIL ' + str(len(fails)) if fails else 'OK'} (catalogue {len(glob.glob('series/*/ep*'))} episodes)")
    sys.exit(1 if fails else 0)

if __name__ == "__main__": main()
