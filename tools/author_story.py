#!/usr/bin/env python3
"""author_story.py — generate a complete Geo Stories episode (format "story-v1") from a compact spec (docs/STORY_GUIDELINES.md).
  python3 tools/author_story.py tools/specs/story/<id>.json [--force]      → series/geo-stories/<id>/*.json
Spec keys:
  id, series ("geo-stories"), number, seed, place, headline ("*keyword*" allowed), search_term, cover{place, headline}, shape, intent,
  post{copy{youtube,instagram,facebook,twitter,threads,spoilers}, keywords, premise, bait, tags}, variety{shape, opener, music, cast, beats[]},
  open{vo{text,cues}, tone, energy, pause_after, kw?{text, at}, cam, cam_hold?, cam_dur?, devices[]}          # cold open: title block on screen
  beats[]{vo{text,cues}, tone, energy, pause_after, direction, kw{text,at}|null, card?{kicker,text,at}, sticker?, photo?, cam, cam_hold?, cam_dur?,
          cam_ease?, highlights[{fid, layer, at}], pulse?, elements[], devices[]}                            # times: "@@cue" · "@+1.2" · "@.end" (relative to the beat's scene)
  close{vo{text,cues}, text (screen line, *keyword*), tone, pause_after, cam?}                                # the answer to the opening line
  cta{vo{text}}, outro_headline,
  geo{fit_bbox, far_bbox, resolution?, layers[{id, ids[], cls}] (highlight layers: tint/solid/glow/zone1..6), extra_layers[], labels[], pins[], disputed[],
      scalebar{km,lonlat}|null, cams{start, open}, pin_beats[], size_claim_device?, projection_reason?},
  stickers_extra[], extra_elements[], research{topic, myths, landscape, sources, claims}
Scenes: s01 = open (role hook) · s02.. = beats (role story) · sNN-1 = close (role story, screen line) · sNN = cta.
"""
import argparse, json, pathlib, sys, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from author_v4 import SCREEN_EXEMPT, GUARDRAILS  # noqa: E402

SHAPES = {"line-that-shouldnt-exist", "cant-see-from-the-ground", "why-here-not-there", "number-nobody-believes", "before-after", "the-detour", "two-places-one-name", "the-edge-case"}
OPENERS = {"plunge", "wide-drift", "mystery-zoom-out", "night-lights"}


def build(S):
    ep, series, n = S["id"], S["series"], S["number"]; today = datetime.date.today().isoformat()
    shape = S["variety"]["shape"]; opener = S["variety"].get("opener", "plunge")
    if shape not in SHAPES: sys.exit(f"author_story: shape {shape!r} not in {sorted(SHAPES)}")
    if opener not in OPENERS: sys.exit(f"author_story: opener {opener!r} not in {sorted(OPENERS)}")
    beats = S["beats"]; NB = len(beats)
    if not 2 <= NB <= 5: sys.exit("author_story: 2–5 beats")
    sc = lambda i: f"s{i:02d}"                                  # s01 open · s02..s(NB+1) beats · s(NB+2) close · s(NB+3) cta
    CLOSE, CTA = sc(NB + 2), sc(NB + 3)
    headline_plain = S["headline"].replace("*", "")
    E = {"id": ep, "format": "story-v1", "series": series, "number": n, "title": headline_plain, "seed": S["seed"], "difficulty": "STORY",
         "story": {"place": S["place"], "headline": S["headline"], "search_term": S["search_term"], "shape": shape, "close": S["close"]["text"],
                   "cover": S.get("cover", {"place": "", "headline": S["headline"]}), "outro": {"headline": S.get("outro_headline", "KNOW A STRANGER PLACE?"), "url": "thequizwire.com"}},
         "hook_type": "cold-open", "promise": {"min_motion": 0.7}, "credits": ["Natural Earth"],
         "post": {"title": S["post"]["copy"]["youtube"]["title"], "premise": S["post"]["premise"], "bait": S["post"]["bait"], "keywords": S["post"]["keywords"],
                  "description": S["post"]["copy"]["youtube"]["description"], "hashtags": S["post"]["copy"]["youtube"].get("tags", []), "tags": S["post"]["tags"],
                  "cover_emoji": "", "cover_emoji_why": "stories carry no icon on the cover (title + place only)", "copy": S["post"]["copy"],
                  **({"cover": S["post"]["cover"]} if S["post"].get("cover") else {})},
         "variety": {"question": "story", "story_shape": shape, "hook": "cold-open", "opener": opener, "reveal": "none", "beats": S["variety"]["beats"],
                     "cast": S["variety"].get("cast", "none"), "music": S["variety"].get("music", "bed:drone")},
         "status": "draft"}
    O, C = S["open"], S["close"]
    lines = [{"id": "v01", "scene": "s01", "role": "hook", "tone": O.get("tone", "urgent"), "energy": O.get("energy", 4), "pause_after": O.get("pause_after", 0.35),
              "direction": O.get("direction", "the opening line, cold — the map is already moving"), "text": O["vo"]["text"], "cues": O["vo"].get("cues", {})}]
    for i, b in enumerate(beats):
        lines.append({"id": f"v{i + 2:02d}", "scene": sc(i + 2), "role": "story", "tone": b.get("tone", "resolute"), "energy": b.get("energy", 3), "pause_after": b.get("pause_after", 0.4),
                      "direction": b.get("direction", "one idea, let it land"), "text": b["vo"]["text"], "cues": b["vo"].get("cues", {}), **({"climax": True} if b.get("climax") else {})})
    lines.append({"id": f"v{NB + 2:02d}", "scene": CLOSE, "role": "story", "tone": C.get("tone", "revelatory"), "energy": C.get("energy", 5), "pause_after": C.get("pause_after", 0.5),
                  "direction": C.get("direction", "answer the opening line with the same noun"), "text": C["vo"]["text"], "cues": C["vo"].get("cues", {}),
                  **({} if any(b.get("climax") for b in beats) else {"climax": True})})                        # exactly one climax (voice gate)
    lines.append({"id": f"v{NB + 3:02d}", "scene": CTA, "role": "cta", "tone": "tender", "energy": 2, "pause_after": 0.0, "direction": "short follow — the outro visual does the work",
                  "text": S["cta"]["vo"]["text"], "cues": {}})
    V = {"version": 1, "episode": ep, "backend": "kokoro", "voice": "Kokoro am_michael (owner decision D3, 2026-10-14)", "kokoro_fallback": {"voice": "am_michael", "speed": 1.3},
         "intent": S["intent"], "pacing_profile": "documentary: cold open, place, why in 2–5 beats, twist, close answers the open, short CTA (docs/STORY_GUIDELINES.md §2)",
         "pause_policy": "Pause only at the marked ellipses.", "start_hold": 0.0, "end_hold": 2.4, "sample_line": "v01", "title": headline_plain, "lines": lines}
    R0 = S["research"]
    R = {"version": 1, "episode": ep, "topic": R0["topic"], "researched": today,
         "policy_note": "Every spoken or shown fact → a claim with ≥ 2 independent publishers; core claims need a primary/scholarly source.",
         "myths": R0.get("myths", []), "guardrails": GUARDRAILS + R0.get("guardrails", []), "screen_exempt": SCREEN_EXEMPT + ["^GEO STORIES", "^KNOW A STRANGER PLACE\\?$"],
         "landscape": R0["landscape"], "sources": R0["sources"], "claims": R0["claims"]}
    g = S["geo"]
    layers = [{"kind": "land"}, {"kind": "borders"}]
    traced = set()
    for L in g.get("layers", []):
        layers.append({"kind": "highlight", "id": L["id"], "ids": L["ids"], "cls": L.get("cls", "tint"), "note": L.get("note", "")})
        if L.get("trace", True):                                                                    # animated border: a per-feature outline layer the pen draws on highlight_in
            layers.append({"kind": "feature", "id": f"edge_{L['id']}", "ids": L["ids"], "cls": "draw trace", "note": f"outline trace for {L['id']}"}); traced.add(L["id"])
    layers += g.get("extra_layers", [])
    res = {"resolution": g["resolution"]} if g.get("resolution") else {}
    G = {"version": 1, "episode": ep, "policy": "docs/BORDER_POLICY.md",
         "scenes": {"main": {**res, "projection": "mercator", "fit": {"type": "bbox", "bbox": g["fit_bbox"]}, "padding": 20, "layers": layers,
                             "pins": g.get("pins", []), "labels": g.get("labels", []), "disputed": g.get("disputed", []), "sources": ["Natural Earth"],
                             "basemap": {"layer": "night" if opener == "night-lights" else "bluemarble", "k_max": g.get("k_max", 2.2), "far": {"bbox": g["far_bbox"], "k_min": 0.3}},
                             "projection_reason": g.get("projection_reason", "satellite raster (Web Mercator tiles) under a location story; numbers are stated, no area comparison is made (P1)"),
                             **({"size_claim_device": g["size_claim_device"]} if g.get("size_claim_device") else {}),
                             **({"scalebar": {"km": g["scalebar"]["km"], "lonlat": g["scalebar"]["lonlat"], "at": [60, 1130]}} if g.get("scalebar") else {})}}}
    # ---------------- visuals
    M = "stage_map"; cams = g["cams"]
    def cam(at, until, c, ease): return {"at": at, "do": "geo.cam_to", "stage": M, "until": until, "args": {"k": c[0], "lonlat": c[1], "ease": ease}}
    def rel(x, s):
        if isinstance(x, (int, float)): return f"{s}+{x}"
        return x.replace("@", s, 1) if isinstance(x, str) and x.startswith("@") else x
    els, B = [], []
    def trace_for(d):                                                                                 # highlight_in on a traced layer → the border draws itself first, the fill follows
        if d.get("do") == "geo.highlight_in" and d["args"].get("layer") in traced:
            at = d["at"]; L = d["args"]["layer"]; plus = (lambda x: f"{at}+{x}") if isinstance(at, str) else (lambda x: at + x)
            d["at"] = plus(0.7)
            return [{"at": at, "do": "geo.route_draw", "stage": M, "until": plus(1.5), "args": {"rid": d["args"]["fid"], "layer": f"edge_{L}"}},
                    {"at": plus(2.2), "do": "geo.route_out", "stage": M, "args": {"rid": d["args"]["fid"], "layer": f"edge_{L}", "dur": 0.8}}]
        return []
    k0, c0 = cams["start"]
    if opener == "mystery-zoom-out":
        B += [{"at": 0, "do": "geo.cam_set", "stage": M, "args": {"k": 0.5, "lonlat": cams["open"][1]}}, cam("s01", "s01.end", [max(0.3, k0), c0], "power1.inOut")]
    else:                                                                                   # plunge / wide-drift / night-lights: continuous move under the title
        B += [{"at": 0, "do": "geo.cam_set", "stage": M, "args": {"k": k0, "lonlat": c0}}, cam("s01", "s01.end" if opener != "plunge" else "s01+%.1f" % O.get("cam_dur", 2.4), cams["open"], "power2.inOut" if opener == "plunge" else "none")]
        if opener == "plunge" and O.get("cam_hold"): B.append(cam("s01+%.1f" % O.get("cam_dur", 2.4), "s01.end", O["cam_hold"], "none"))
    B += [{"at": 0, "do": "title_in"}, {"at": "s02+0.3", "do": "title_out"}]
    if O.get("kw"):
        els.append({"id": "kw01", "type": "kw", "text": O["kw"]["text"]}); B.append({"at": rel(O["kw"].get("at", "@+1.2"), "s01"), "do": "kw_in", "id": "kw01", "until": "s01.end"})
    for d in O.get("devices", []):
        d = dict(d); d["at"] = rel(d.get("at", 0), "s01"); d["until"] = rel(d["until"], "s01") if "until" in d else None
        if d["until"] is None: d.pop("until")
        if str(d["do"]).startswith("geo."): d.setdefault("stage", M)
        B.append(d); B += trace_for(d)
    for i, b in enumerate(beats):
        s = sc(i + 2); nxt = sc(i + 3)
        if b.get("cam"):
            glide = float(b.get("cam_dur", 1.4)); B.append(cam(s, f"{s}+{glide}", b["cam"], b.get("cam_ease", "power2.inOut")))
            hold = b.get("cam_hold") or [round(b["cam"][0] * 1.03, 3), b["cam"][1]]                       # slow drift after the glide (never a frozen frame)
            B.append(cam(f"{s}+{glide}", f"{s}+{glide + 1.2}", hold, "none"))
            if b.get("cam_path"):                                                                         # authored extra moves: [[at, until, [k, lonlat], ease?], ...]
                for mv in b["cam_path"]: B.append(cam(rel(mv[0], s), rel(mv[1], s), mv[2], mv[3] if len(mv) > 3 else "power2.inOut"))
            else:                                                                                         # default: a second, firmer push on the last cue, then a slow drift out
                cues_ = list(b["vo"].get("cues") or {}); lastc = cues_[-1] if cues_ else None
                mid, mid2 = (f"{s}@{lastc}-0.2", f"{s}@{lastc}+0.7") if lastc else (f"{s}+{glide + 1.2}", f"{s}+{glide + 2.1}")
                B.append(cam(f"{s}+{glide + 1.2}", mid, [round(hold[0] * 1.02, 3), hold[1]], "none"))
                B.append(cam(mid, mid2, [round(hold[0] * 1.12, 3), hold[1]], "power2.inOut"))
                B.append(cam(mid2, f"{s}.end", [round(hold[0] * 1.14, 3), hold[1]], "none"))
        for h in b.get("highlights", []):
            B.append({"at": rel(h.get("at", "@+0.2"), s), "do": "geo.highlight_in", "stage": M, "args": {"fid": h["fid"], "layer": h["layer"], "dur": h.get("dur", 0.5)}}); B += trace_for(B[-1])
            if h.get("out"): B.append({"at": rel(h["out"], s), "do": "geo.highlight_out", "stage": M, "args": {"fid": h["fid"], "layer": h["layer"]}})
        if b.get("pulse"): B.append({"at": rel(b["pulse"]["at"], s), "do": "geo.highlight_pulse", "stage": M, "args": {"fid": b["pulse"]["fid"], "layer": b["pulse"]["layer"], "dur": 0.7}})
        if b.get("kw"):
            kid = f"kw{i + 2:02d}"; els.append({"id": kid, "type": "kw", "text": b["kw"]["text"]})
            B.append({"at": rel(b["kw"].get("at", "@+0.6"), s), "do": "kw_in", "id": kid})
            B.append({"at": rel(b["kw"].get("until", "@.end"), s), "do": "kw_out", "id": kid})
        if b.get("card"):
            fid = f"f{i + 2:02d}"; els.append({"id": fid, "type": "fact", "kicker": b["card"]["kicker"], "text": b["card"]["text"], "y": b["card"].get("y", 1010)})
            B.append({"at": rel(b["card"].get("at", "@+0.5"), s), "do": "fact_in", "id": fid})
            B.append({"at": rel(b["card"].get("until", "@.end"), s), "do": "hide", "id": fid, "args": {"dur": 0.3}})
        if b.get("sticker"):
            st = b["sticker"]; els.append({"id": st["id"], "type": "sticker", "emoji": st["emoji"], "x": st.get("x", 740), "y": st.get("y", 580), "size": st.get("size", 200), "rot": st.get("rot", 6)})
            B += [{"at": rel(st.get("at", "@+0.6"), s), "do": "sticker_in", "id": st["id"], "args": {"frm": st.get("from", "rise")}}, {"at": rel(st.get("until", "@.end"), s), "do": "sticker_out", "id": st["id"]}]
        if b.get("photo"):
            p_ = b["photo"]; els.append({"id": p_["id"], "type": "photo", "commons": p_["commons"], "caption": p_.get("caption", ""), "x": p_.get("x", 440), "y": p_.get("y", 420), "w": p_.get("w", 580), "h": p_.get("h", 440), "rot": p_.get("rot", -3)})
            B += [{"at": rel(p_.get("at", "@+0.5"), s), "do": "photo_in", "id": p_["id"], "args": {"frm": p_.get("from", "pop")}}, {"at": rel(p_.get("until", "@.end"), s), "do": "photo_out", "id": p_["id"]}]
        for el in b.get("elements", []): els.append(el)
        # cue breath (docs/STORY_GUIDELINES.md §4): every spoken cue gets a visual answer — if nothing authored lands on it,
        # swell the keyword caption (once it is up) or pulse the story's subject highlight.
        used = {str(x.get("at", "")) for x in B} | {rel(h.get("at", "@+0.2"), s) for h in b.get("highlights", [])}
        kw_at = rel(b["kw"].get("at", "@+0.6"), s) if b.get("kw") else None
        subj = g.get("subject")
        for cue in (b["vo"].get("cues") or {}):
            at = f"{s}@{cue}"
            if any(at in u for u in used): continue
            if kw_at and (kw_at == at or kw_at.split("@")[-1] in list(b["vo"]["cues"])[:list(b["vo"]["cues"]).index(cue)]):
                B.append({"at": f"{at}+0.05", "do": "kw_pulse", "id": f"kw{i + 2:02d}"})
            if subj: B.append({"at": at, "do": "geo.highlight_pulse", "stage": M, "args": {"fid": subj["fid"], "layer": subj["layer"], "dur": 0.6}})
        for d in b.get("devices", []):
            d = dict(d); d["at"] = rel(d.get("at", 0), s)
            if "until" in d: d["until"] = rel(d["until"], s)
            if str(d["do"]).startswith("geo."): d.setdefault("stage", M)
            B.append(d)
    # close
    els.append({"id": "close", "type": "close", "text": C["text"], **({"y": C["y"]} if C.get("y") else {})})
    if C.get("cam"):
        B.append(cam(CLOSE, f"{CLOSE}+{C.get('cam_dur', 1.6)}", C["cam"], "power2.inOut"))
        B.append(cam(f"{CLOSE}+{C.get('cam_dur', 1.6)}", f"{CLOSE}.end", [round(C["cam"][0] * 0.96, 3), C["cam"][1]], "none"))     # slow pull during the close line
    B.append({"at": rel(C.get("at", "@+0.3"), CLOSE), "do": "close_in", "id": "close", "until": f"{CLOSE}.end"})
    if g.get("subject"):                                                                    # cue breath on the close line too
        for cue in (C["vo"].get("cues") or {}):
            B.append({"at": f"{CLOSE}@{cue}", "do": "geo.highlight_pulse", "stage": M, "args": {"fid": g["subject"]["fid"], "layer": g["subject"]["layer"], "dur": 0.6}})
    for d in C.get("devices", []):
        d = dict(d); d["at"] = rel(d.get("at", 0), CLOSE)
        if "until" in d: d["until"] = rel(d["until"], CLOSE)
        if str(d["do"]).startswith("geo."): d.setdefault("stage", M)
        B.append(d); B += trace_for(d)
    for L in g.get("labels", []):
        B.append({"at": L.get("in", "s02+1.0"), "do": "geo.label_in", "stage": M, "args": {"lid": L["id"]}})
        if L.get("out"): B.append({"at": L["out"], "do": "geo.label_out", "stage": M, "args": {"lid": L["id"]}})
    for pb in g.get("pin_beats", []): B.append({"at": pb["at"], "do": "geo.pin_out" if pb.get("out") else "geo.pin_in", "stage": M, "args": {"pid": pb["pid"]}})
    if g.get("scalebar"): B.append({"at": "s02+1.2", "do": "geo.scalebar_in", "stage": M})
    B += g.get("extra_beats", [])
    els += S.get("stickers_extra", []) + S.get("extra_elements", [])
    B += [{"at": CTA, "do": "geo.clear", "stage": M, "args": {"dur": 0.25}}, cam(f"{CTA}+0.2", "end-0.3", cams["start"], "power1.inOut"),
          {"at": CTA, "do": "cta_in", "until": "end-1.0"}]
    X = {"version": 3, "stage": [{"id": M, "type": "geo", "scene": "main", "from": "start", "to": "end", "box": [0, 0, 1080, 1920], "anchor": [540, 900], "z": 10}],
         "elements": els, "beats": B, "captions": {"roles": [], "max_words": 4, "max_chars": 26, "hold": 0.12}}
    return {"episode.json": E, "voice.json": V, "research.json": R, "geo.json": G, "visuals.json": X,
            "media.json": {"version": 1, "files": {}, "generated": {}}, "clips.json": {"version": 1, "template": {}, "clips": []}}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    S = json.load(open(a.spec)); out = ROOT / "series" / S["series"] / S["id"]
    if out.exists() and not a.force: sys.exit(f"{out} exists — use --force")
    out.mkdir(parents=True, exist_ok=True); files = build(S)
    prev = out / "episode.json"
    if prev.exists():
        try: files["episode.json"]["status"] = json.loads(prev.read_text()).get("status", "draft")
        except Exception: pass
    pm = out / "media.json"
    if pm.exists():
        try:
            old = json.loads(pm.read_text()); files["media.json"] = {**files["media.json"], **{k: old[k] for k in ("files", "release", "repo", "generated") if k in old}}
        except Exception: pass
    for name, data in files.items(): (out / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(files)} files)")


if __name__ == "__main__":
    main()
