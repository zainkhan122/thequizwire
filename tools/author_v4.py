#!/usr/bin/env python3
"""author_v4.py — generate a complete v4 quiz episode (episode/voice/research/geo/visuals/media/clips json) from a compact spec.
  python3 tools/author_v4.py tools/specs/<id>.json          # writes series/<series>/<id>/*.json (refuses to overwrite unless --force)
The spec is deliberately small: the recipe that passed CI for Geo Blitz #16 (2026-10-18) is baked in here —
question-first hook read verbatim (Q17), options → 3-s beat → reveal with highlight + flag-balls, three one-line
story beats with cam moves / pins / stickers, outro without tease, loop frame. Authors supply facts, sources and geography.
Spec keys (see tools/specs/*.json): id, series, number, seed, question, keyword, difficulty, options[{text,flag,vo}],
correct, answer_sub, outro_headline, cover_emoji, post{premise,bait,keywords,hashtags,tags,sources_line},
variety{...}, intent, voice{v04,v05,v06,v07,v08 (text + cues)}, facts[4]{kicker,text}, stickers[3]{id,emoji,x,y,size,rot},
characters{mascot_face, a{flag,face,x,y}, b{flag,face,x,y}}, geo{fit_bbox, far_bbox, highlight_ids[], labels[], pins[],
scalebar{km,lonlat}, cams{start,s01,s04,s04b,s05,s05b,s06,s06b,s07,s07b}, pin_beats[{at,pid,out?}]},
research{topic, myths[], landscape{our_gap, existing[3]}, sources{...}, claims[]}.
"""
import argparse, json, pathlib, sys, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCREEN_EXEMPT = ["^GEO BLITZ", "^SPORTS SPRINT", "^BODY & BRAIN", "^WILD FILES", "^#\\d+$", "^(EASY|MEDIUM|HARD)$", "^THE ?QUIZ ?WIRE",
                 "km at \\d+°$", "^Map data:", "Voice: AI", "^TOO EASY\\?$", "^thequizwire\\.com$", "^GUESS BEFORE", "^A was right|^B was right|^C was right"]
GUARDRAILS = [{"never": "arabian gulf|persian gulf", "why": "Contested name — say 'the Gulf' or use both names (docs/BORDER_POLICY.md)."},
              {"never": "\\bowns?\\b.*(kashmir|crimea|taiwan|golan|western sahara)", "why": "Sovereignty language on disputed areas is banned; say administers / claims."}]
SERIES_LABEL = {"geo-blitz": "Geo Blitz", "sports-sprint": "Sports Sprint", "body-brain": "Body & Brain", "wild-files": "Wild Files"}
SERIES_EMOJI = {"geo-blitz": "🌍", "sports-sprint": "🏆", "body-brain": "🧠", "wild-files": "🐾"}
SERIES_TAGS = {"geo-blitz": ["#GeographyQuiz", "#MapQuiz", "#thequizwire"], "sports-sprint": ["#SportsQuiz", "#SportsTrivia", "#thequizwire"],
               "body-brain": ["#BodyFacts", "#BrainQuiz", "#thequizwire"], "wild-files": ["#AnimalQuiz", "#WildlifeFacts", "#thequizwire"]}


def letters(i): return "ABC"[i]


def story_beats(S):
    """The explanation as a list of beats. New specs write `story: [...]` (2–5 beats, each its own shape); old specs are
    converted from voice v05–v07 + facts[1:] + stickers so nothing already rendered changes."""
    if S.get("story"): return S["story"]
    vo, F, st, cams = S["voice"], S["facts"], S["stickers"], S["geo"]["cams"]
    out = []
    for i, key in enumerate(("v05", "v06", "v07")):
        sk = f"s{5 + i:02d}"
        out.append({"vo": vo[key], "card": F[i + 1], "sticker": {**st[i], "at": 0.6 if i < 2 else 0.8}, "cam": cams[sk], "cam_hold": cams[sk + "b"],
                    "pulse": [0.5, 0.6, 0.4][i], "direction": ["count it out", "let it land", "the number people repeat"][i], "energy": [3, 3, 4][i], "tone": ["resolute", "neutral", "resolute"][i]})
    return out


def story_lines(S):
    L = []
    for i, b in enumerate(story_beats(S)):
        n = 5 + i
        L.append({"id": f"v{n:02d}", "scene": f"s{n:02d}", "role": "story", "tone": b.get("tone", "resolute"), "energy": b.get("energy", 3), "pause_after": b.get("pause_after", 0.4),
                  "direction": b.get("direction", "say it like you just found out"), "text": b["vo"]["text"], "cues": b["vo"].get("cues", {})})
    return L


def build(S):
    ep = S["id"]; series = S["series"]; n = S["number"]; q = S["question"]
    opts = S["options"]; ci = S["correct"]; ans = opts[ci]["text"]
    today = datetime.date.today().isoformat()
    # ---------------- episode.json
    E = {"id": ep, "format": "quiz-v3", "series": series, "number": n, "title": q, "difficulty": S.get("difficulty", "MEDIUM"), "seed": S["seed"],
         "quiz": {"question": q, "keyword": S["keyword"], "options": [o["text"] for o in opts], "correct": ci, "beat": 3.0,
                  "answer_line": ans, "answer_sub": S["answer_sub"], "option_meta": [{"flag": o["flag"]} for o in opts],
                  "banner": ans, "banner_sub": f"✓  {letters(ci)} was right · {S['answer_sub']}",
                  "outro": {"headline": S.get("outro_headline", "TOO EASY?"), "url": "thequizwire.com"}},
         "hook_type": "question-first", "promise": {"min_motion": 0.7}, "credits": ["Natural Earth"],
         "post": {"title": f"{q} {S.get('cover_emoji', SERIES_EMOJI[series])}", "premise": S["post"]["premise"], "bait": S["post"]["bait"],
                  "keywords": S["post"]["keywords"],
                  "description": f"{S['post']['premise']}. {S['post']['bait']}\n\nSources: {S['post']['sources_line']}.\nMap data: Natural Earth (public domain). Voice: AI (Kokoro).\n\n{SERIES_LABEL[series]} #{n}",
                  "hashtags": S["post"].get("hashtags", SERIES_TAGS[series]), "tags": S["post"]["tags"], "cover_emoji": S.get("cover_emoji", SERIES_EMOJI[series]), "copy": S["post"].get("copy", {})},
         "variety": {"question": S["variety"]["question"], "hook": "question-first", "opener": S["variety"]["opener"], "reveal": S["variety"]["reveal"],
                     "beats": S["variety"]["beats"], "cast": S["variety"]["cast"], "music": S["variety"].get("music", "bed:pad")},
         "status": "draft"}
    # ---------------- voice.json
    vo = S["voice"]
    opt_vo = ", ".join(o.get("vo", o["text"]) for o in opts[:-1]) + ", or " + opts[-1].get("vo", opts[-1]["text"]) + "?"
    V = {"version": 1, "episode": ep, "backend": "kokoro", "voice": "Kokoro am_michael (owner decision D3, 2026-10-14)",
         "kokoro_fallback": {"voice": "am_michael", "speed": 1.3}, "intent": S["intent"],
         "pacing_profile": "question read verbatim, three options, 3-s beat, reveal with the number, story beats shaped per episode (brief.md), punchline + short follow",
         "pause_policy": "Pause only at the marked ellipses; the beat is real silence (ticks come from quizscore.py).",
         "start_hold": 0.0, "end_hold": 2.4, "sample_line": "v04", "title": q,
         "lines": [
             {"id": "v01", "scene": "s01", "role": "hook", "tone": "urgent", "energy": 4, "pause_after": 0.3,
              "direction": "the question, cold — curiosity comes from the map moving under it", "text": S.get("question_vo") or q.replace(S["keyword"], S["keyword"].lower()),
              "cues": vo.get("v01_cues", {})},
             {"id": "v02", "scene": "s02", "role": "options", "tone": "neutral", "energy": 3, "pause_after": 0.3, "direction": "quick, each option its own beat",
              "text": opt_vo, "cues": {"a": opts[0]["cue"], "b": opts[1]["cue"], "c": opts[2]["cue"]}},
             {"id": "v03", "scene": "s03", "role": "countdown", "tone": "neutral", "energy": 1, "pause_after": 0.1, "direction": "silence — the bar drains", "silence": 3.0, "text": ""},
             {"id": "v04", "scene": "s04", "role": "reveal", "tone": "revelatory", "energy": 4, "pause_after": 0.45, "direction": "the map answers with you",
              "text": vo["v04"]["text"], "cues": vo["v04"]["cues"], "climax": True},
             ] + story_lines(S) + [
             {"id": f"v{len(story_beats(S)) + 5:02d}", "scene": f"s{len(story_beats(S)) + 5:02d}", "role": "cta", "tone": "tender", "energy": 3, "pause_after": 0.0, "direction": "punchline, then a short follow — the outro visual asks",
              "text": vo["v08"]["text"], "cues": ({"follow": "follow"} if "follow" in vo["v08"]["text"].lower() else {})}]}
    # ---------------- research.json
    R0 = S["research"]
    R = {"version": 1, "episode": ep, "topic": R0["topic"], "researched": today,
         "policy_note": "Every spoken or shown fact → a claim with ≥ 2 independent publishers; core claims need a primary/scholarly source.",
         "myths": R0.get("myths", []), "guardrails": GUARDRAILS + R0.get("guardrails", []), "screen_exempt": SCREEN_EXEMPT,
         "landscape": R0["landscape"], "sources": R0["sources"], "claims": R0["claims"]}
    # ---------------- geo.json
    g = S["geo"]
    layers = [{"kind": "land"}, {"kind": "borders"}]
    if g["highlight_ids"]:
        layers.append({"kind": "highlight", "id": "hl", "ids": g["highlight_ids"], "cls": g.get("highlight_cls", ""), "note": g.get("highlight_note", "answer country")})
        if g.get("lift"): layers[-1].update(lift=g["lift"], flag=g.get("lift_flag"))
    for extra in g.get("extra_layers", []): layers.append(extra)
    res = {"resolution": g["resolution"]} if g.get("resolution") else {}
    G = {"version": 1, "episode": ep, "policy": "docs/BORDER_POLICY.md",
         "scenes": {"main": {**res, "projection": "mercator", "fit": {"type": "bbox", "bbox": g["fit_bbox"]}, "padding": 20, "layers": layers,
                             "pins": g.get("pins", []), "labels": g.get("labels", []), "disputed": g.get("disputed", []), "sources": ["Natural Earth"],
                             "basemap": {"layer": "bluemarble", "k_max": 2.0, "far": {"bbox": g["far_bbox"], "k_min": 0.3}},
                             "projection_reason": g.get("projection_reason", "satellite raster (Web Mercator tiles) under a location story; numbers are stated, no area comparison is made (P1)"),
                             "scalebar": {"km": g["scalebar"]["km"], "lonlat": g["scalebar"]["lonlat"], "at": [60, 1130]}}}}
    # ---------------- visuals.json
    ch = S["characters"]; st = S.get("stickers", []); F = S["facts"]; cams = g["cams"]
    SB = story_beats(S); NS = len(SB); CTA = f"s{NS + 5:02d}"
    els = [{"id": "f1", "type": "fact", "kicker": F[0]["kicker"], "text": F[0]["text"]}]
    for i, b in enumerate(SB):
        if b.get("card"): els.append({"id": f"f{i + 2}", "type": "fact", "kicker": b["card"]["kicker"], "text": b["card"]["text"]})
        if b.get("sticker"):
            s_ = b["sticker"]; els.append({"id": s_["id"], "type": "sticker", "emoji": s_["emoji"], "x": s_.get("x", 740), "y": s_.get("y", 580), "size": s_.get("size", 220), "rot": s_.get("rot", 6)})
        for el in b.get("elements", []): els.append(el)                       # counters, bars, compare … (engine/charts.py)
    els += [{"id": "mascot", "type": "character", "flag": "un", "face": ch.get("mascot_face", "think"), "x": 860, "y": 1480, "size": 210, "rot": 6},
            {"id": "cha", "type": "character", "flag": ch["a"]["flag"], "face": ch["a"]["face"], "x": ch["a"].get("x", 230), "y": ch["a"].get("y", 820), "size": 220, "rot": -8},
            {"id": "chb", "type": "character", "flag": ch["b"]["flag"], "face": ch["b"]["face"], "x": ch["b"].get("x", 850), "y": ch["b"].get("y", 1000), "size": 200, "rot": 8}]
    M = "stage_map"
    def cam(at, until, c, ease): return {"at": at, "do": "geo.cam_to", "stage": M, "until": until, "args": {"k": c[0], "lonlat": c[1], "ease": ease}}
    B = [{"at": 0, "do": "character_in", "id": "mascot", "args": {"dur": 0.01}}, {"at": "s02+0.2", "do": "character_out", "id": "mascot"},
         {"at": 0, "do": "geo.cam_set", "stage": M, "args": {"k": cams["start"][0], "lonlat": cams["start"][1]}},
         cam("s01", "s03.end", cams["s01"], "none"),
         cam("s04", "s04+1.4", cams["s04"], "power2.inOut"), cam("s04+1.4", "s04.end", cams["s04b"], "none")]
    for fid in g["highlight_ids"]: B.append({"at": "s04+0.1", "do": "geo.highlight_in", "stage": M, "args": {"fid": fid, "layer": "hl", "dur": 0.5}})
    B += g.get("extra_beats", [])
    for L in g.get("labels", []):
        B.append({"at": L.get("in", "s04+1.2"), "do": "geo.label_in", "stage": M, "args": {"lid": L["id"]}})
        if L.get("out"): B.append({"at": L["out"], "do": "geo.label_out", "stage": M, "args": {"lid": L["id"]}})
    pulse = lambda at: ([{"at": at, "do": "geo.highlight_pulse", "stage": M, "args": {"fid": g["highlight_ids"][0], "layer": "hl"}}] if g["highlight_ids"] else [])
    B += pulse("s04+3.2") + [{"at": "s04+2.6", "do": "fact_in", "id": "f1", "until": "s04.end"}]
    for i, b in enumerate(SB):
        sc = f"s{5 + i:02d}"; nxt = f"s{6 + i:02d}"; last = i == NS - 1
        if b.get("cam"):
            glide = float(b.get("cam_dur", 1.3))
            B.append(cam(sc, f"{sc}+{glide}", b["cam"], b.get("cam_ease", "power2.inOut")))
            if b.get("cam_hold"): B.append(cam(f"{sc}+{glide}", f"{nxt}+0.2" if last else f"{sc}.end", b["cam_hold"], "none"))
        if b.get("pulse") is not None and b.get("pulse") is not False: B += pulse(f"{sc}+{b['pulse']}")
        if b.get("card"): B.append({"at": f"{sc}+{b.get('card_at', 0.4)}", "do": "fact_in", "id": f"f{i + 2}", "until": f"{sc}.end"})
        if b.get("sticker"):
            s_ = b["sticker"]; B += [{"at": f"{sc}+{s_.get('at', 0.6)}", "do": "sticker_in", "id": s_["id"]}, {"at": f"{sc}.end", "do": "sticker_out", "id": s_["id"]}]
        for d in b.get("devices", []):                                        # free-form: any engine beat, times relative to this scene
            d = dict(d); rel = lambda x: x.replace("@", sc, 1) if isinstance(x, str) else f"{sc}+{x}"   # "@+1.2" · "@.end" · "@@cue" → s06+1.2 · s06.end · s06@cue
            d["at"] = rel(d.get("at", 0))
            if "until" in d: d["until"] = rel(d["until"])
            if d["do"].startswith("geo.") : d.setdefault("stage", M)
            B.append(d)
    B += [{"at": CTA, "do": "geo.clear", "stage": M, "args": {"dur": 0.25}},
          cam(f"{CTA}+0.2", "end-0.3", cams["start"], "power1.inOut"),
          {"at": "s04+0.8", "do": "geo.scalebar_in", "stage": M}]
    for pb in g.get("pin_beats", []):
        B.append({"at": pb["at"], "do": "geo.pin_out" if pb.get("out") else "geo.pin_in", "stage": M, "args": {"pid": pb["pid"]}})
    B += [{"at": 0, "do": "hook_in"}, {"at": "s02", "do": "chips_in"}, {"at": "s03", "do": "bug_in"}, {"at": "s03", "do": "beat"},
          {"at": "s04", "do": "reveal"}, {"at": "s04+0.9", "do": "hook_out"}, {"at": "s04+1.2", "do": "chips_out"},
          {"at": "s04+1.3", "do": "banner_in"}, {"at": "s04+4.4", "do": "banner_out"},
          {"at": "s04+1.6", "do": "character_in", "id": "cha"}, {"at": "s04+1.9", "do": "character_in", "id": "chb"},
          {"at": "s05+0.8", "do": "character_out", "id": "chb"}, {"at": "s05+1.0", "do": "character_out", "id": "cha"},
          {"at": CTA, "do": "cta_in", "until": "end-1.0"}, {"at": CTA, "do": "credit_in", "until": "end-0.2"}, {"at": "end-1.0", "do": "hook_in"}]
    X = {"version": 3, "stage": [{"id": M, "type": "geo", "scene": "main", "from": "start", "to": "end", "box": [0, 0, 1080, 1920], "anchor": [540, 900], "z": 10}],
         "elements": els, "beats": B, "captions": {"roles": ["reveal", "story"], "max_words": 4, "max_chars": 26, "hold": 0.12}}
    MEDIA = {"version": 1, "files": {}, "generated": {}}
    CLIPS = {"version": 1, "template": {"negative": "text, watermark, logo, subtitles, blurry, low quality, deformed"}, "clips": []}
    return {"episode.json": E, "voice.json": V, "research.json": R, "geo.json": G, "visuals.json": X, "media.json": MEDIA, "clips.json": CLIPS}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    S = json.load(open(a.spec)); out = ROOT / "series" / S["series"] / S["id"]
    if out.exists() and not a.force: sys.exit(f"{out} exists — use --force to regenerate")
    out.mkdir(parents=True, exist_ok=True)
    tv = json.load(open(ROOT / "series/_template_v3/visuals.json")).get("version", 1)
    files = build(S); files["visuals.json"]["version"] = tv
    prev = out / "episode.json"
    if prev.exists():                                                        # --force keeps the review status; the content is what changes
        try: files["episode.json"]["status"] = json.loads(prev.read_text()).get("status", "draft")
        except Exception: pass
    for name, data in files.items(): (out / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(files)} files)")


if __name__ == "__main__":
    main()
