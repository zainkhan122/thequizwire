#!/usr/bin/env python3
"""reelkit/quizlint.py — QuizWire format gate (the quiz equivalent of planlint for story docs).

    python3 reelkit/quizlint.py <ep> [--hf <hf_dir>] [--release] [--report out/quizlint.json]

FAIL (exit 1)
  Q1 quiz        4 options, valid `correct`, answer_line names the correct option, difficulty in the registry levels,
                 series registered (and active unless --allow-inactive)
  Q2 structure   voice.json roles in order hook → options → countdown → reveal → story(≥1) → cta; the countdown line is a
                 `silence` of ≥ 2 s; `reveal` beat not before the countdown ends; exactly one `countdown` beat
  Q3 length      total > 60 s (hard platform cap) · story share < 25 % of runtime (we promise a reveal WITH a reason)
  Q4 copy fits   question > 90 chars · an option > 24 chars · a fact > 140 chars · kicker > 28 chars (overflow = unreadable)
  Q5 beats       every beat references an existing scene/cue/stage/element; each element has an *_in beat; each fact has
                 `until`; each stage is used by ≥ 1 beat (map stages need ≥ 1 camera move or highlight)
  Q8 hand-offs   fact_in ≥ 0.45 s after card_out and after the previous fact's `until` (no band crossfades)
  Q6 motion      weighted visual-motion share below episode.json promise.min_motion (geo .75, globe/maptile 1, chart .5,
                 kenburns plate .25, colour 0) — a quiz card over a static plate is the "mass-produced" look we refuse
  Q7 release     timeline.json is estimated (--release) · mix.wav missing in hf/assets (--release)
WARN: total < 35 s, hashtags missing the house set, VO does not read the question/options, number < registry next_number.
"""
import argparse, json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORDER = ["hook", "options", "countdown", "reveal", "story", "cta"]
MOTION_W = {"geo": 0.75, "globe": 1.0, "maptile": 1.0, "chart": 0.5, "plate": 0.25, "color": 0.0, "clip": 1.0}
HOUSE_TAGS = {"#GKshorts", "#thequizwire", "#shorts"}
TIME_RE = re.compile(r"(end|s\w+?)(?:\.(end))?(?:@([\w-]+))?(?:([+-])([\d.]+))?")


def norm(s): return re.sub(r"[^a-z0-9 ]", "", str(s).lower())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("--hf"); ap.add_argument("--release", action="store_true")
    ap.add_argument("--allow-inactive", action="store_true"); ap.add_argument("--report")
    a = ap.parse_args(); ep = Path(a.ep).resolve()
    F, W = [], []
    E = json.loads((ep / "episode.json").read_text()); V = json.loads((ep / "voice.json").read_text())
    T = json.loads((ep / "timeline.json").read_text()) if (ep / "timeline.json").exists() else None
    X = json.loads((ep / "visuals.json").read_text()) if (ep / "visuals.json").exists() else {"stage": [], "elements": [], "beats": []}
    reg = json.loads((REPO / "series" / "series.json").read_text())
    series = next((s for s in reg["series"] if s["slug"] == E.get("series")), None)
    # ---- Q1
    q = E.get("quiz", {})
    if len(q.get("options", [])) != 4: F.append("Q1: quiz needs exactly 4 options")
    if not isinstance(q.get("correct"), int) or not 0 <= q.get("correct", -1) < 4: F.append("Q1: quiz.correct must be 0–3")
    else:
        co = norm(q["options"][q["correct"]]); al = norm(q.get("answer_line", ""))
        key = [w for w in co.split() if w not in ("the", "of", "a", "an", "peninsula", "river", "mountain", "ocean", "sea", "desert", "lake", "island", "islands", "country")] or co.split()
        if not any(w in al for w in key): F.append(f"Q1: answer_line '{q.get('answer_line')}' does not name the correct option '{q['options'][q['correct']]}'")
    if E.get("difficulty") not in reg["defaults"]["difficulty_levels"]: F.append(f"Q1: difficulty '{E.get('difficulty')}' not in {reg['defaults']['difficulty_levels']}")
    if not series: F.append(f"Q1: series '{E.get('series')}' not in series/series.json")
    elif not series.get("active") and not a.allow_inactive: F.append(f"Q1: series '{series['slug']}' is registered but inactive")
    elif E.get("number", 0) and E["number"] < series.get("next_number", 0) and ep.name != "_template": W.append(f"number {E['number']} < registry next_number {series['next_number']}")
    # ---- Q2 structure
    roles = [l.get("role") for l in V["lines"]]
    seq = [r for i, r in enumerate(roles) if i == 0 or r != roles[i - 1]]
    if seq != ORDER: F.append(f"Q2: roles {seq} must read {ORDER} (story may repeat)")
    cd = [l for l in V["lines"] if l.get("role") == "countdown"]
    if not cd or cd[0].get("silence") is None or float(cd[0]["silence"]) < 2: F.append("Q2: the countdown line must be a `silence` ≥ 2 s (the ring counts, nobody talks)")
    if len(cd) > 1: F.append("Q2: more than one countdown line")
    # ---- Q4 copy
    if len(q.get("question", "")) > 90: F.append(f"Q4: question is {len(q['question'])} chars (> 90 — 3 lines at 46 px)")
    for o in q.get("options", []):
        if len(o) > 24: F.append(f"Q4: option '{o}' is {len(o)} chars (> 24, single line)")
    for el in X.get("elements", []):
        if el.get("type") == "fact" and len(el.get("text", "")) > 140: F.append(f"Q4: fact {el['id']} is {len(el['text'])} chars (> 140)")
        if el.get("kicker") and len(el["kicker"]) > 28: F.append(f"Q4: kicker '{el['kicker']}' > 28 chars")
    # ---- VO reads the card
    vo_all = norm(" ".join(l.get("text", "") for l in V["lines"]))
    if norm(q.get("question", ""))[:40] not in vo_all: W.append("the VO does not read the question text (hook line should contain it)")
    for o in q.get("options", []):
        if norm(o).split()[-1] not in vo_all: W.append(f"option '{o}' is never spoken")
    # ---- timeline-dependent
    story_share = None; motion = None
    if T:
        total = T["total"]; SC = {s["id"]: s for s in T["scenes"]}
        if total > 60.0: F.append(f"Q3: total {total} s > 60 s")
        elif total < 35: W.append(f"total {total} s < 35 s (thin for a reveal + story)")
        story = sum(s["end"] - s["start"] for s in T["scenes"] if s.get("role") == "story"); story_share = story / total
        if story_share < 0.25: F.append(f"Q3: story share {story_share:.0%} of runtime (< 25 %)")
        if T.get("estimated"): (F if a.release else W).append("Q7: timeline.json is ESTIMATED (run the CI tts stage / voice.py words)")

        def tt(expr):
            if isinstance(expr, (int, float)): return float(expr)
            m = TIME_RE.fullmatch(expr.strip())
            if not m: raise ValueError(expr)
            base, end, cue, sign, off = m.groups()
            if base == "end": t = total
            elif base not in SC: raise KeyError(base)
            elif cue:
                if f"{base}@{cue}" not in T.get("cues", {}): raise KeyError(f"{base}@{cue}")
                t = T["cues"][f"{base}@{cue}"]
            elif end or sign == "-": t = SC[base]["end"]
            else: t = SC[base]["start"]
            return t + (float(off) * (1 if sign == "+" else -1) if sign and off else 0)
        stages = {s["id"]: s for s in X.get("stage", [])}; elements = {e["id"]: e for e in X.get("elements", [])}
        used_stage, elem_in, n_cd, t_cd_end, t_reveal, cam_moves = set(), set(), 0, None, None, {}
        t_card_out, facts = [], []                      # Q8: the caption band hands over, never crossfades
        for b in X.get("beats", []):
            try: t = tt(b["at"]); t1 = tt(b["until"]) if "until" in b else None
            except (KeyError, ValueError) as e: F.append(f"Q5: beat {b} — unknown time reference {e}"); continue
            do = b.get("do", "")
            if do == "card_out": t_card_out.append(t)
            if do == "fact_in":
                for tc in t_card_out:
                    if 0 <= t - tc < 0.45: F.append(f"Q8: fact_in at {t:.2f}s starts {t - tc:.2f}s after card_out — give the card 0.45 s to leave (crossfades in the band read as occluded text in `hyperframes check`)")
                for (f0, f1) in facts:
                    if f1 is not None and t < f1 + 0.05: F.append(f"Q8: fact_in at {t:.2f}s overlaps the previous fact (until {f1:.2f}s)")
                facts.append((t, t1))
            if do.startswith(("geo.", "chart.")) and "stage" in b:
                if b["stage"] not in stages: F.append(f"Q5: beat {do} references unknown stage {b['stage']}")
                else:
                    used_stage.add(b["stage"])
                    if do in ("geo.cam_to", "geo.spin", "geo.highlight_in", "geo.route_draw", "geo.pin_in"): cam_moves[b["stage"]] = cam_moves.get(b["stage"], 0) + 1
            if "id" in b:
                if b["id"] not in elements: F.append(f"Q5: beat {do} references unknown element {b['id']}")
                elif do.endswith("_in") or do == "counter_run" or do.startswith("chart."): elem_in.add(b["id"])
                if do == "fact_in" and t1 is None: F.append(f"Q5: fact_in {b['id']} needs `until`")
            if do == "countdown":
                n_cd += 1; t_cd_end = t + float(q.get("countdown", 3))
            if do == "reveal": t_reveal = t
            if t1 is not None and t1 < t: F.append(f"Q5: beat {do} `until` before `at`")
        if n_cd != 1: F.append(f"Q2: {n_cd} countdown beats (need exactly 1)")
        if t_reveal is None: F.append("Q2: no reveal beat")
        elif t_cd_end is not None and t_reveal + 0.01 < t_cd_end: F.append(f"Q2: reveal at {t_reveal:.2f}s before the countdown ends at {t_cd_end:.2f}s")
        for sid, st in stages.items():
            if sid not in used_stage and st["type"] in ("geo", "chart"): F.append(f"Q5: stage {sid} ({st['type']}) has no beats")
            if st["type"] == "geo" and cam_moves.get(sid, 0) == 0: F.append(f"Q5: map stage {sid} never moves (no cam_to/highlight/pin beats) — a static map is a plate")
        for eid, el in elements.items():
            if eid not in elem_in: F.append(f"Q5: element {eid} is never shown (no *_in beat)")
        # ---- Q6 motion share
        cover = 0.0
        for st in stages.values():
            try: t0 = 0.0 if st.get("from") in (None, "start") else tt(st["from"]); t1 = tt(st.get("to", "end"))
            except (KeyError, ValueError) as e: F.append(f"Q5: stage {st['id']} bad window {e}"); continue
            w = MOTION_W.get(st["type"], 0.0) * (1.0 if st["type"] != "plate" or st.get("kenburns") else 0.0)
            cover += w * max(0.0, min(t1, total) - max(t0, 0.0))
        motion = min(1.0, cover / total) if total else 0.0
        need = float(E.get("promise", {}).get("min_motion", 0.70))
        if motion < need: F.append(f"Q6: weighted motion share {motion:.0%} < promise {need:.0%}")
        if a.release:
            hf = Path(a.hf) if a.hf else Path.home() / ".cache/build" / ep.name / "hf"
            if not (hf / "assets" / "mix.wav").exists(): F.append("Q7: hf/assets/mix.wav missing (score stage)")
    else:
        W.append("no timeline.json — structure timing, beats and motion share not checked (run reelkit/plan.py)")
    tags = set(E.get("post", {}).get("hashtags", []))
    if not HOUSE_TAGS <= tags: W.append(f"post hashtags missing {sorted(HOUSE_TAGS - tags)}")
    for w in W: print("  WARN ", w)
    for f in F: print("  FAIL ", f)
    extra = f" · story {story_share:.0%} · motion {motion:.0%}" if story_share is not None else ""
    print(f"quizlint: {E.get('series')} #{E.get('number')} · {len(V['lines'])} lines{extra} → {'FAIL ' + str(len(F)) if F else 'OK'}")
    if a.report: Path(a.report).write_text(json.dumps({"fails": F, "warns": W, "story_share": story_share, "motion": motion}, indent=1))
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
