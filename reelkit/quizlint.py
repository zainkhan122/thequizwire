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

v3 (format "quiz-v3", docs/V3_LOOK.md) adds Q14 (no camera on the answer's fit bbox before the reveal unless k ≤ 0.5),
Q15 (full-bleed map stage, banner_in, sticker/character warning) and tighter Q4 copy limits (72 / 18 / kicker 16 + text ≤ 46).
v2 (episode.json "format": "quiz-v2", docs/PLAN_V2.md §2) replaces Q1/Q2's card rules and adds:
  Q9  hook       `hook_in` at ≤ 0.3 s; no card_in/options_in/countdown/end_in; `bug_in` (if any) ≥ 2.0 s — nothing but the
                 question and the moving visual in the first two seconds
  Q10 beat       the countdown line is a `silence` of 1.0–1.5 s and exactly one `beat` action sits on it
  Q11 reveal     a visual-state change (geo.highlight_in / cam_to / pin_in / route_draw / chart.*) within 1.5 s of `reveal`
  Q12 loop       the last `hook_in` is ≥ end-2.0 and a final `geo.cam_to` (until ≥ end-0.4) returns to the t=0 `geo.cam_set`
  Q13 length     exactly 3 options · total 22–40 s (FAIL) / 26–36 s (else WARN) · question ≤ 76 chars · option ≤ 26 chars ·
                 fact ≤ 80 chars (short plates under word-timed captions) · chips_out → fact_in hand-off ≥ 0.45 s
"""
import argparse, json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORDER = ["hook", "options", "countdown", "reveal", "story", "cta"]
MOTION_W = {"geo": 0.75, "globe": 1.0, "maptile": 1.0, "chart": 0.5, "plate": 0.25, "color": 0.0, "clip": 1.0}
HOUSE_TAGS = {"#GKshorts", "#thequizwire", "#shorts"}
TIME_RE = re.compile(r"(end|s\w+?)(?:\.(end))?(?:@([\w-]+))?(?:([+-])([\d.]+))?")


def norm(s): return re.sub(r"[^a-z0-9 ]", "", str(s).lower())

_SMALL = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
def num_word(tok):
    """'11' → 'eleven', '45' → 'forty five' (digits on chips are read as words by the VO)."""
    if not tok.isdigit() or int(tok) > 99: return tok
    n = int(tok)
    return _SMALL[n] if n < 20 else (_TENS[n // 10] + ("" if n % 10 == 0 else " " + _SMALL[n % 10]))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("--hf"); ap.add_argument("--release", action="store_true")
    ap.add_argument("--allow-inactive", action="store_true"); ap.add_argument("--report")
    a = ap.parse_args(); ep = Path(a.ep).resolve()
    F, W = [], []
    E = json.loads((ep / "episode.json").read_text()); V = json.loads((ep / "voice.json").read_text())
    T = json.loads((ep / "timeline.json").read_text()) if (ep / "timeline.json").exists() else None
    X = json.loads((ep / "visuals.json").read_text()) if (ep / "visuals.json").exists() else {"stage": [], "elements": [], "beats": []}
    GJ = json.loads((ep / "geo.json").read_text()) if (ep / "geo.json").exists() else {"scenes": {}}
    reg = json.loads((REPO / "series" / "series.json").read_text())
    series = next((s for s in reg["series"] if s["slug"] == E.get("series")), None)
    # ---- Q1
    q = E.get("quiz", {})
    v2 = E.get("format") in ("quiz-v2", "quiz-v3"); n_opt = 3 if v2 else 4
    if len(q.get("options", [])) != n_opt: F.append(f"{'Q13' if v2 else 'Q1'}: quiz needs exactly {n_opt} options")
    if not isinstance(q.get("correct"), int) or not 0 <= q.get("correct", -1) < n_opt: F.append(f"Q1: quiz.correct must be 0–{n_opt - 1}")
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
    if v2:
        if not cd or cd[0].get("silence") is None or not 1.0 <= float(cd[0]["silence"]) <= 1.5: F.append("Q10: the beat line must be a `silence` of 1.0–1.5 s (v2 has no countdown)")
    elif not cd or cd[0].get("silence") is None or float(cd[0]["silence"]) < 2: F.append("Q2: the countdown line must be a `silence` ≥ 2 s (the ring counts, nobody talks)")
    if len(cd) > 1: F.append("Q2: more than one countdown line")
    # ---- Q4 copy
    v3 = E.get("format") == "quiz-v3"
    q_max, o_max, f_max = (72, 18, 36) if v3 else (76, 26, 80) if v2 else (90, 24, 140)     # v3: 100-px question, 58-px pills, 84-px fact caption
    if len(q.get("question", "")) > q_max: F.append(f"Q4: question is {len(q['question'])} chars (> {q_max})")
    for o in q.get("options", []):
        if len(o) > o_max: F.append(f"Q4: option '{o}' is {len(o)} chars (> {o_max}, single line)")
    for el in X.get("elements", []):
        if el.get("type") == "fact" and len(el.get("text", "")) > f_max: F.append(f"Q4: fact {el['id']} is {len(el['text'])} chars (> {f_max})")
        if el.get("kicker") and len(el["kicker"]) > (16 if v3 else 28): F.append(f"Q4: kicker '{el['kicker']}' > {16 if v3 else 28} chars")
        if v3 and el.get("type") == "fact" and len(el.get("kicker", "")) + len(el.get("text", "")) > 46: F.append(f"Q4: fact {el['id']} kicker+text > 46 chars (two 84-px lines)")
    # ---- VO reads the card
    vo_all = norm(" ".join(l.get("text", "") for l in V["lines"]))
    if norm(q.get("question", ""))[:40] not in vo_all: W.append("the VO does not read the question text (hook line should contain it)")
    for o in q.get("options", []):
        last = norm(o).split()[-1]
        if last not in vo_all and num_word(last) not in vo_all: W.append(f"option '{o}' is never spoken")
    # ---- timeline-dependent
    story_share = None; motion = None
    if T:
        total = T["total"]; SC = {s["id"]: s for s in T["scenes"]}
        if v2:
            if not 22.0 <= total <= 40.0: F.append(f"Q13: total {total} s outside 22–40 s")
            elif not 26.0 <= total <= 36.0: W.append(f"Q13: total {total} s outside the 26–36 s target")
        elif total > 60.0: F.append(f"Q3: total {total} s > 60 s")
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
        v2b = {"hook_in": [], "bug_in": [], "beat": [], "visual": [], "cam_to": [], "cam_set": None, "banned": [], "banner_in": []}
        for b in X.get("beats", []):
            try: t = tt(b["at"]); t1 = tt(b["until"]) if "until" in b else None
            except (KeyError, ValueError) as e: F.append(f"Q5: beat {b} — unknown time reference {e}"); continue
            do = b.get("do", "")
            if do in ("card_out", "chips_out"): t_card_out.append(t)
            if v2:
                if do in v2b: v2b[do].append(t)
                if do in ("card_in", "options_in", "countdown", "end_in"): v2b["banned"].append(do)
                if do in ("geo.highlight_in", "geo.cam_to", "geo.pin_in", "geo.route_draw", "geo.spin") or do.startswith("chart."): v2b["visual"].append(t)
                if do == "geo.cam_to": v2b["cam_to"].append((t, t1, b.get("args", {})))
                if do == "geo.cam_set" and v2b["cam_set"] is None: v2b["cam_set"] = (t, b.get("args", {}))
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
            if do == "countdown" or (v2 and do == "beat"):
                n_cd += 1; t_cd_end = t + float(q.get("beat", 1.5) if v2 else q.get("countdown", 3))
            if do == "reveal": t_reveal = t
            if t1 is not None and t1 < t: F.append(f"Q5: beat {do} `until` before `at`")
        if n_cd != 1: F.append(f"{'Q10' if v2 else 'Q2'}: {n_cd} {'beat' if v2 else 'countdown'} beats (need exactly 1)")
        if t_reveal is None: F.append("Q2: no reveal beat")
        elif t_cd_end is not None and t_reveal + 0.01 < t_cd_end: F.append(f"Q2: reveal at {t_reveal:.2f}s before the {'beat' if v2 else 'countdown'} ends at {t_cd_end:.2f}s")
        if v2:
            # Q9 hook
            if not v2b["hook_in"] or min(v2b["hook_in"]) > 0.3: F.append("Q9: `hook_in` must happen at ≤ 0.3 s (the question is the first thing on screen)")
            if v2b["banned"]: F.append(f"Q9: v2 must not use {sorted(set(v2b['banned']))} (no card, no countdown ring, no full-screen end card)")
            if any(tb < 2.0 for tb in v2b["bug_in"]): F.append("Q9: `bug_in` before 2.0 s — no chrome before the question lands")
            # Q11 visual reveal
            if t_reveal is not None and not any(t_reveal - 0.2 <= tv <= t_reveal + 1.5 for tv in v2b["visual"]):
                F.append(f"Q11: no visual-state change within 1.5 s of the reveal at {t_reveal:.2f}s (highlight/cam/pin/route/chart)")
            # Q12 loop
            if not v2b["hook_in"] or max(v2b["hook_in"]) < total - 2.0: F.append("Q12: the hook must return for the loop (last `hook_in` ≥ end-2.0)")
            if v2b["cam_set"] and any(st.get("type") == "geo" for st in stages.values()):
                last = max(v2b["cam_to"], key=lambda c: c[1] or c[0]) if v2b["cam_to"] else None
                a0 = v2b["cam_set"][1]
                if not last or (last[1] or last[0]) < total - 0.4: F.append("Q12: the final `geo.cam_to` must run until ≥ end-0.4 (loop frame)")
                elif abs(float(last[2].get("k", 1)) - float(a0.get("k", 1))) > 0.02 or [round(float(x), 2) for x in last[2].get("lonlat", [])] != [round(float(x), 2) for x in a0.get("lonlat", [])]:
                    F.append(f"Q12: the final camera {last[2]} does not match the opening cam_set {a0} (last frame must equal the first)")
            if v3 and t_reveal is not None:
                # Q14 (v3): the answer region must not be on screen before the reveal — every camera that is visible before
                # t_reveal must sit outside the scene's fit bbox (the subject area) or be zoomed out to k ≤ 0.5.
                def inside(ll, bb): return bb and ll and bb[0] <= float(ll[0]) <= bb[2] and bb[1] <= float(ll[1]) <= bb[3]
                for st in stages.values():
                    if st.get("type") != "geo": continue
                    sc = GJ.get("scenes", {}).get(st.get("scene"), {}); bb = (sc.get("fit") or {}).get("bbox")
                    if not bb or not any(L.get("kind") == "highlight" and L.get("lift") for L in sc.get("layers", [])): continue
                    cams = ([(v2b["cam_set"][0], v2b["cam_set"][1])] if v2b["cam_set"] else []) + [(t, args) for t, _, args in v2b["cam_to"]]
                    for tc, args in cams:
                        if tc < t_reveal - 0.01 and float(args.get("k", 1)) > 0.5 and inside(args.get("lonlat"), bb):
                            F.append(f"Q14: camera {args} at {tc:.2f}s shows the answer region before the reveal ({t_reveal:.2f}s) — hook cameras must be off the fit bbox or k ≤ 0.5")
                    if st.get("box", [0, 0, 1080, 1180])[3] < 1900: F.append(f"Q15: v3 map stage {st['id']} must be full-bleed (box [0,0,1080,1920])")
                if not v2b.get("banner_in"): F.append("Q15: v3 needs a `banner_in` beat (the big answer)")
                if not any(e.get("type") in ("sticker", "character") for e in elements.values()): W.append("Q15: no sticker/character element — v3 see-it beats want one visual object each")
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
