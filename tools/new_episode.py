#!/usr/bin/env python3
"""
tools/new_episode.py — scaffold an episode folder from series/_template_v2 (default, Plan v2) or series/_template (--v1).

  python3 tools/new_episode.py geo-blitz "Which is the longest river in Africa?" \
      --options "Nile" "Congo" "Niger" "Zambezi" --correct 0 --difficulty EASY --slug longest-river-africa
  python3 tools/new_episode.py body-brain "How many bones does an adult human have?" --options 206 212 198 220 --correct 0

What it does
  • picks the number: series.json `next_number` (bumps it in place so the feed numbering never collides)
  • creates series/<series>/ep<NN>-<slug>/ with every template file, then rewrites
      episode.json  id/series/number/title/difficulty/quiz/post (hashtags from channel + series)
      voice.json    the 7-scene skeleton with the question + option read-out already filled; story lines left as TODO
      research.json empty ledger with the schema + the channel guardrails kept; `topic` set
      geo.json      kept for geo-blitz (scene skeleton), removed for other series unless --map
      visuals.json  stage swapped to the series' default engine (geo map / plate placeholder)
      media.json    empty `files`
      POST_KIT.md   title/description skeleton
  • prints the TODO list the author (or agent) must complete before `reelkit/episode.sh <ep> plan … provenance` goes green.

It never touches an existing folder (refuses), never writes outside series/, never posts anything.
"""
import argparse, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "series/_template"
TPL2 = ROOT / "series/_template_v2"      # Plan v2 "Guess it → See it"
TPL3 = ROOT / "series/_template_v3"      # v3 satellite quiz (default since 2026-10-15, docs/V3_LOOK.md)
SERIES = ROOT / "series/series.json"
LETTERS = "ABCD"


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return "-".join(s.split("-")[:5])


def load(p): return json.loads(Path(p).read_text())
def dump(p, d): Path(p).write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("series", help="series slug from series/series.json (geo-blitz, body-brain, sports-sprint, wild-files, …)")
    ap.add_argument("question")
    ap.add_argument("--options", nargs="+", required=True, metavar="OPT", help="3 options (v2, default) or 4 with --v1")
    ap.add_argument("--v1", action="store_true", help="scaffold the old 4-option card format from series/_template")
    ap.add_argument("--v2", action="store_true", help="scaffold the flat v2 look (series/_template_v2) instead of v3")
    ap.add_argument("--keyword", help="v2: the word(s) of the question to colour in the hook (default: the capitalised word of the title)")
    ap.add_argument("--tease", default="Tomorrow: TODO the next question in this series.", help="v2: the 'Tomorrow:' line (must be true)")
    ap.add_argument("--correct", type=int, required=True, help="0-based index of the right option")
    ap.add_argument("--difficulty", default="MEDIUM", choices=["EASY", "MEDIUM", "HARD"])
    ap.add_argument("--slug", help="folder suffix (default: from the question)")
    ap.add_argument("--number", type=int, help="override the series counter")
    ap.add_argument("--hook", default="misconception", choices=["misconception", "superlative", "scale", "stakes", "trend"])
    ap.add_argument("--map", action="store_true", help="keep the map stage for a non-geo series (venue / range / origin story)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    S = load(SERIES); ser = next((s for s in S["series"] if s["slug"] == a.series), None)
    if not ser: sys.exit(f"new_episode: unknown series {a.series!r} — register it in series/series.json first")
    if not ser.get("active"): print(f"  ! {ser['name']} is registered but inactive (series.json active=false) — scaffolding anyway")
    v2 = not a.v1; n_opt = 4 if a.v1 else 3
    if len(a.options) != n_opt: sys.exit(f"new_episode: {'--v1 needs 4 options' if a.v1 else 'v2 needs exactly 3 options (use --v1 for the 4-option card)'}")
    if not 0 <= a.correct < n_opt: sys.exit(f"new_episode: --correct must be 0..{n_opt - 1}")
    num = a.number or ser["next_number"]
    slug = a.slug or slugify(a.question)
    ep = ROOT / "series" / a.series / f"ep{num:02d}-{slug}"
    if ep.exists(): sys.exit(f"new_episode: {ep.relative_to(ROOT)} exists — refusing to overwrite")
    print(f"== {ser['name']} #{num} → {ep.relative_to(ROOT)}")
    if a.dry: return

    shutil.copytree((TPL2 if a.v2 else TPL3) if v2 else TPL, ep, ignore=shutil.ignore_patterns("out", "__pycache__", "vo", "words.json", "README.md"))
    eid = ep.name
    use_map = a.series == "geo-blitz" or a.map

    # episode.json
    E = load(ep / "episode.json")
    q = a.question.strip(); opts = [o.strip() for o in a.options]
    E.update({"id": eid, "series": a.series, "number": num, "title": q, "difficulty": a.difficulty, "seed": 1000 + num, "hook_type": a.hook})
    if v2:
        kw = a.keyword or next((w for w in q.replace("?", "").split() if w.isupper() and len(w) > 2), None)
        E["format"] = "quiz-v2" if a.v2 else "quiz-v3"
        E["quiz"] = {"question": q, "keyword": kw, "options": opts, "correct": a.correct, "beat": 1.5, **({} if a.v2 else {"option_meta": [{} for _ in opts], "banner": opts[a.correct][:16]}),
                     "answer_line": opts[a.correct], "answer_sub": "TODO — one sourced number or place (≤ 40 chars)",
                     "tease": a.tease, "cta_line": "One map question a day · Subscribe" if use_map else "One question a day · Subscribe"}
    else:
        E["quiz"] = {"question": q, "options": opts, "correct": a.correct, "countdown": S["defaults"]["countdown_seconds"],
                     "answer_line": opts[a.correct], "answer_sub": "TODO — one sourced number or place (≤ 60 chars)"}
    E["credits"] = ["Natural Earth"] if use_map else []
    E["post"] = {"title": f"{q} {ser['name']} #{num}" if not v2 else q,
                 "description": (f"{q} Guess first — then see it.\n\nWhat was your first guess?\n\n{ser['name']} #{num}" if v2 else f"{q} Answer in 3… 2… 1.\n\n{S['channel']['description_tail']}"),
                 "hashtags": (["#GKshorts", "#thequizwire", "#shorts"] if v2 else S["channel"]["hashtags"]) + [f"#{a.series.replace('-', '')}"]}
    dump(ep / "episode.json", E)

    # voice.json — question + read-out filled, story TODO
    V = load(ep / "voice.json")
    def first_word(t): return re.sub(r"[^a-z0-9'-]", "", t.split()[0].lower())
    ans_word = first_word(opts[a.correct])
    if v2:
        read = f"{opts[0]}, {opts[1]}, or {opts[2]}?"
        for l in V["lines"]:
            if l["id"] == "v01": l["text"] = q; l["cues"] = {"which": first_word(q)}
            elif l["id"] == "v02": l["text"] = read; l["cues"] = {"a": first_word(opts[0]), "b": first_word(opts[1]), "c": first_word(opts[2])}
            elif l["id"] == "v04": l["text"] = f"It's {opts[a.correct]}… TODO one sourced number."; l["cues"] = {"answer": ans_word, "number": "todo"}
            elif l["id"] == "v05": l["text"] = "TODO see-it beat one (one claim, shown on the visual)."; l["cues"] = {"seven": "todo", "saudi": "see-it"}
            elif l["id"] == "v06": l["text"] = "TODO see-it beat two."; l["cues"] = {"bigger": "todo"}
            elif l["id"] == "v07": l["text"] = "TODO payoff — the number people repeat."; l["cues"] = {"three": "todo"}
            elif l["id"] == "v08": l["text"] = f"{re.sub(r'^Tomorrow:', 'Tomorrow,', a.tease)} Subscribe, and guess it first."; l["cues"] = {"subscribe": "subscribe"}   # Kokoro skips the colon pause; the screen keeps 'Tomorrow:'
    else:
        read = f"{LETTERS[0]}, {opts[0]}. {LETTERS[1]}, {opts[1]}. {LETTERS[2]}, {opts[2]}. Or {LETTERS[3]}, {opts[3]}."
        for l in V["lines"]:
            if l["id"] == "v01": l["text"] = f"TODO hook sentence. {q}"; l["cues"] = {"which": first_word(q)}
            elif l["id"] == "v02": l["text"] = read
            elif l["id"] == "v04": l["text"] = f"It's {LETTERS[a.correct]}… {opts[a.correct]}. TODO one sourced detail."; l["cues"] = {"answer": ans_word, "number": "todo"}
            elif l["id"] == "v05": l["text"] = "TODO story sentence, every fact becomes a research.json claim."; l["cues"] = {"seven": "todo", "saudi": "story"}
            elif l["id"] == "v06": l["text"] = "TODO second story sentence, the one that makes the answer stick."; l["cues"] = {"bigger": "second"}
    V["episode"] = eid; V["title"] = q
    dump(ep / "voice.json", V)

    # research.json — schema + channel guardrails, ledger emptied
    R = load(ep / "research.json")
    R.update({"episode": eid, "topic": q, "researched": "TODO (YYYY-MM-DD)", "sources": {}, "claims": [], "myths": [],
              "policy_note": "Every spoken or shown fact → a claim with ≥ 2 independent publishers; core claims need a primary/scholarly source."})
    R["screen_exempt"] = [x for x in R["screen_exempt"] if not re.search(r"Peninsula|Riyadh|Sea\$", x)]
    R["screen_exempt"][0] = "^" + ser["name"].upper().replace("&", "&")
    R["vo_exempt"] = (["^" + re.escape(read.lower()).replace("\\ ", " ") + "$", "^tomorrow[,:]? ", "^subscribe, and guess it first"] if v2
                      else ["^(a|b|c|or d), .*\\.$", "^what was your first guess", "^tell me in the comments"])
    if v2: R["screen_exempt"] = [x for x in R["screen_exempt"] if "Tomorrow" not in x] + ["^Tomorrow:"]
    R["landscape"] = {"our_gap": "TODO — what the feed's version of this question misses", "existing": []}
    dump(ep / "research.json", R)

    # geo.json / visuals.json
    if use_map:
        G = load(ep / "geo.json"); G["episode"] = eid
        for sid, sc in G["scenes"].items():
            sc["projection_reason"] = "TODO — why this projection is honest for this claim (geolint P1)"
            sc["pins"] = []; sc["labels"] = []; sc["disputed"] = []
        dump(ep / "geo.json", G)
        Vz = load(ep / "visuals.json")      # keep the camera moves; drop beats that point at the template's pins/labels/highlights
        Vz["beats"] = [b for b in Vz["beats"] if b.get("do") not in ("geo.pin_in", "geo.label_in", "geo.disputed_in", "geo.highlight_in")]
        dump(ep / "visuals.json", Vz)
    else:
        (ep / "geo.json").unlink()
        Vz = load(ep / "visuals.json")
        Vz["stage"] = [{"id": "stage_main", "type": "plate", "image": "assets/plate_main.jpg", "scene": "main", "from": "start", "to": "end",
                        "box": [0, 0, 1080, 1180], "z": 10, "_todo": f"{ser['name']} default engines: {', '.join(ser['engines'])} — replace this plate stage"}]
        Vz["beats"] = [b for b in Vz["beats"] if not str(b.get("do", "")).startswith("geo.")]
        dump(ep / "visuals.json", Vz)
    Vz = load(ep / "visuals.json")          # answer card follows the quiz; story facts become TODOs (factcheck keeps them honest)
    for el in Vz.get("elements", []):
        if el.get("type") == "answer": el["text"] = E["quiz"]["answer_line"]; el["sub"] = E["quiz"]["answer_sub"]
        elif el.get("type") == "fact": el["kicker"] = "TODO KICKER"; el["text"] = "TODO short plate, traced to a claim." if v2 else "TODO fact under 140 chars, traced to a research.json claim."
    dump(ep / "visuals.json", Vz)
    dump(ep / "media.json", {"files": {}})
    (ep / "POST_KIT.md").write_text(f"# {ser['name']} #{num} — {q}\n\n**Title:** {E['post']['title']}\n\n**Description:**\n{E['post']['description']}\n\n"
                                    f"{' '.join(E['post']['hashtags'])}\n\n**Credits:** {', '.join(E['credits']) or 'TODO'}\n\n**Voice:** AI (Kokoro am_michael) — disclosed in the description.\n")

    ser["next_number"] = num + 1
    SERIES.write_text(json.dumps(S, indent=2, ensure_ascii=False) + "\n")
    print(f"""created {eid}  (series.json next_number → {num + 1})
TODO before the gates go green:
  1. research.json — ≥ 5 sources, one claim per fact (answer = core: needs a primary/scholarly source)
  2. voice.json    — replace every TODO; keep the beat/countdown line silent; cue words for beats; v2: 26–36 s total
  3. visuals.json  — beats for the story scenes (fact_in with `until`); stage must move (Q5/Q6)
  {'4. geo.json      — fit/bbox, pins with Wikidata qid, scalebar for distance claims, disputed entries for any registry region (geolint P4)' if use_map else '4. stage         — pick an engine from series.json and replace the plate placeholder'}
  5. bash reelkit/episode.sh {ep.relative_to(ROOT)} plan geo build static quizlint geolint facts provenance""")


if __name__ == "__main__":
    main()
