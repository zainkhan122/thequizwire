#!/usr/bin/env python3
"""engine/compose.py — data-driven HyperFrames composition for a QuizWire episode (no per-episode build.py needed).

    python3 engine/compose.py <episode_dir> [<hf_dir>]            default hf = ~/.cache/build/<ep>/hf

Reads  episode.json (series, number, quiz, difficulty, credits), timeline.json (reelkit/plan.py), visuals.json
       (stages, elements, beats), geo.json (map scene specs, optional), clips.json (optional, via engine/fx.py),
       series/series.json (brand per series).
Writes <hf>/index.html + hyperframes.json + meta.json + package.json, copies fonts + runtime JS.

visuals.json
  stage[]    = long-lived visual layers: {"id","type": "geo"|"chart"|"plate"|"color", ..., "from": "s01", "to": "end", "z"}
  elements[] = quiz copy created once: {"id","type": "answer"|"fact", ...} or charts {"type":"counter"|"bars"|"compare"|"callouts"|"strip"}
  beats[]    = timed actions: {"at": "<time expr>", "do": "<action>", ...}
  time expr  = "s03" (scene start) · "s03+0.4" · "s03-0.5" (before scene end) · "s03.end" · "s03@cue" (voice.json cue word)
               · "end" / "end-2.5" (composition end) · a bare number
  actions    = quiz: card_in card_out options_in countdown reveal answer_in answer_out fact_in end_in
               quiz v2 (episode.json format "quiz-v2", docs/PLAN_V2.md): hook_in hook_out chips_in beat reveal chips_out bug_in
               cta_in credit_in (+ "captions": {roles, max_words, max_chars, hold} → word-timed captions from timeline words)
               geo.<Scene method> (needs "stage"; "until" gives t1 for cam_to/spin/route_draw; geo.clear = loop-frame reset)
               hide (needs "id"; fades any element, e.g. a counter, before the loop frame)
               chart.<Charts method>_in / counter_run (needs "id"; "until" for counter_run)
               fx.flash
A bare `python3 engine/compose.py` on the template episode is the engine smoke test (tests/selftest.py).
"""
import json, re, shutil, sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
REPO = ENGINE.parent
sys.path.insert(0, str(ENGINE))
import fx, geo, quiz, charts  # noqa: E402

FONTS = ["Anton-Regular.ttf", "Oswald.ttf", "DMSerifDisplay-Regular.ttf", "DMSerifDisplay-Italic.ttf", "SpecialElite-Regular.ttf"]
INK, CREAM, SEA = "#0B1620", "#EFE6D2", "#0F2A3A"


def f(x): return f"{x:.3f}"


class Composer:
    def __init__(self, ep: Path, hf: Path):
        self.ep, self.hf = ep, hf
        self.E = json.loads((ep / "episode.json").read_text())
        self.TL = json.loads((ep / "timeline.json").read_text())
        self.V = json.loads((ep / "visuals.json").read_text())
        gp = ep / "geo.json"
        self.GEO = json.loads(gp.read_text()) if gp.exists() else {"scenes": {}}
        reg = json.loads((REPO / "series" / "series.json").read_text())
        self.series = next(s for s in reg["series"] if s["slug"] == self.E["series"])
        self.SC = {s["id"]: s for s in self.TL["scenes"]}
        self.TOTAL = self.TL["total"]
        self.body, self.js, self.css = [], [], []
        self.J = self.js.append
        self.FX = fx.FX(self.J, ep / "clips.json", self.SC, seed=int(self.E.get("seed", 2026)), hf=hf)
        self.G = geo.Geo(self.J, hf, REPO, data_dir=hf.parent / "geo")      # reelkit/geodata.py prep writes <build>/geo/<scene>.json
        self.Q = quiz.Quiz(self.J, self.series, self.E.get("number"))
        self.CH = charts.Charts(self.J)
        self.stages, self.credit_bits = {}, list(self.E.get("credits", []))

    # ---------------------------------------------------------------- time expressions
    def T(self, expr):
        if isinstance(expr, (int, float)): return float(expr)
        m = re.fullmatch(r"(end|s\w+?)(?:\.(end))?(?:@([\w-]+))?(?:([+-])([\d.]+))?", expr.strip())
        if not m: raise ValueError(f"bad time expr {expr!r}")
        base, end, cue, sign, off = m.groups()
        if base == "end": t = self.TOTAL
        else:
            s = self.SC[base]
            if cue: t = self.TL["cues"][f"{base}@{cue}"]
            elif end or sign == "-": t = s["end"]
            else: t = s["start"]
        if sign and off: t += float(off) * (1 if sign == "+" else -1)
        return round(t, 3)

    # ---------------------------------------------------------------- build
    def clip(self, id_, start, end, inner, z=10, style=""):
        self.clip_ids = getattr(self, "clip_ids", []) + [id_]
        # content lives in a child wrapper: the HyperFrames runtime owns the clip's visibility, so fades (end card)
        # tween #<id>_in, never the clip element itself (lint/gsap_animates_clip_element)
        self.body.append(f'<div id="{id_}" class="clip" data-start="{f(start)}" data-duration="{f(end - start)}" data-track-index="{z // 10}" style="z-index:{z};{style}">'
                         f'<div id="{id_}_in" class="clipin">{inner}</div></div>')

    def stage(self, st):
        t0 = self.T(st.get("from", "s01")) if st.get("from") != "start" else 0.0
        t0 = 0.0 if st.get("from") in (None, "start") or st.get("from") == self.TL["scenes"][0]["id"] else t0
        t1 = self.T(st.get("to", "end"))
        z = st.get("z", 10); kind = st["type"]
        if kind == "geo":
            spec = self.GEO["scenes"][st["scene"]]
            if spec.get("disputed"):
                spec = {**spec, "labels": spec.get("labels", []) + geo.policy_labels(spec["disputed"]),
                        "layers": spec.get("layers", []) + [{"kind": "disputed", "source": "disputed", "cls": "policy"}],
                        "geo": {**spec.get("geo", {}), "disputed": {"type": "FeatureCollection", "features": [
                            {"type": "Feature", "id": d["id"], "properties": {k: d[k] for k in ("name", "controller", "claimants") if k in d}, "geometry": d["geometry"]}
                            for d in spec["disputed"] if d.get("geometry")]}}}
            box = tuple(st.get("box", (0, 0, 1080, 1180)))
            sc = self.G.scene(st["scene"], spec, box=box, z=0, anchor=st.get("anchor"))
            self.stages[st["id"]] = sc
            self.clip(st["id"], t0, t1, sc.html(), z=z)
        elif kind == "chart":
            html = getattr(self.CH, st["chart"])(st["id"], **st.get("args", {}))
            self.clip(st["id"] + "_w", t0, t1, html, z=z)
            self.stages[st["id"]] = ("chart", st["chart"])
        elif kind == "plate":
            img = st["image"]
            self.clip(st["id"], t0, t1, f'<div class="kb" id="{st["id"]}_kb">{self.FX.plate(img, st["id"] + "_kb")}</div>', z=z)
            if st.get("kenburns"):
                a, b = st["kenburns"]
                self.J(f"tl.fromTo('#{st['id']}_kb',{{scale:{a}}},{{scale:{b},duration:{f(t1 - t0)},ease:'none',immediateRender:false}},{f(t0)});")
            if st.get("credit"): self.credit_bits.append(st["credit"])
        elif kind == "color":
            self.clip(st["id"], t0, t1, "", z=z, style=f"position:absolute;left:0;top:0;width:1080px;height:1920px;background:{st.get('color', SEA)}")
        else:
            raise ValueError(f"stage {st['id']}: unknown type {kind}")

    def element(self, el):
        k = el["type"]
        if k == "answer": self.body.append(self.Q.answer_plate(el["id"], el["text"], y=el.get("y", 980), sub=el.get("sub", "")))
        elif k == "fact": self.body.append(self.Q.fact(el["id"], el["text"], y=el.get("y", 1230), kicker=el.get("kicker", "")))
        elif k in ("counter", "bars", "compare", "callouts", "strip"):
            args = {kk: vv for kk, vv in el.items() if kk not in ("id", "type", "z")}
            if k in ("bars", "compare"): args["rows" if k == "bars" else "items"] = [tuple(r) for r in args.pop("rows" if k == "bars" else "items")]
            if k == "callouts": args["points"] = [tuple(p) for p in args["points"]]
            html = getattr(self.CH, k)(el["id"], **args)
            self.body.append(f'<div style="position:absolute;left:0;top:0;z-index:{el.get("z", 40)}">{html}</div>')
        else:
            raise ValueError(f"element {el['id']}: unknown type {k}")

    def beat(self, b):
        t = self.T(b["at"]); do = b["do"]; args = dict(b.get("args", {}))
        t1 = self.T(b["until"]) if "until" in b else None
        if do.startswith("geo."):
            sc = self.stages[b["stage"]]; m = getattr(sc, do[4:])
            if do in ("geo.cam_to", "geo.spin", "geo.route_draw", "geo.fade"): m(t, t1 if t1 is not None else t + float(b.get("dur", 1.2)), **args)
            else: m(t, **args)
        elif do.startswith("chart."):
            m = getattr(self.CH, do[6:])
            if do == "chart.counter_run": m(t, t1 if t1 is not None else t + float(b.get("dur", 1.5)), b["id"], **args)
            else: m(t, b["id"], **args)
        elif do == "fx.flash": self.FX.flash(t, **args)
        elif do == "reveal": (self.Q.reveal_chips if self.v2 else self.Q.reveal)(t, **args)
        elif do in ("card_in", "card_out", "options_in", "countdown"): getattr(self.Q, do)(t, **args)
        elif do in ("hook_in", "hook_out", "chips_in", "chips_out", "bug_in"): getattr(self.Q, do)(t, **args)        # v2
        elif do == "beat": self.Q.beat(t, seconds=float(self.E["quiz"].get("beat", 1.5)), **args)                   # v2
        elif do == "cta_in": self.Q.cta_in(t, t1, **args)                                                             # v2
        elif do == "credit_in": self.Q.credit_in(t, t1, **args)                                                       # v2
        elif do in ("answer_in", "answer_out"): getattr(self.Q, do)(t, b["id"], **args)
        elif do == "fact_in": self.Q.fact_in(t, t1, b["id"], **args)
        elif do == "hide": self.J(f"tl.to('#{b['id']}',{{autoAlpha:0,duration:{float(args.get('dur', 0.4))},ease:'power1.in'}},{t:.3f});")   # any element (counter, chart…)
        elif do == "end_in": self.Q.end_in(t, getattr(self, "clip_ids", []))
        else: raise ValueError(f"beat: unknown action {do}")

    # ---------------------------------------------------------------- v2 captions (docs/PLAN_V2.md §2: word-timed, ≤ 4 words)
    def caption_groups(self):
        cfg = self.V.get("captions", {})
        if cfg is False or cfg.get("off"): return []
        roles = set(cfg.get("roles", ["reveal", "story", "cta"])); max_w = int(cfg.get("max_words", 4)); max_c = int(cfg.get("max_chars", 26))
        hold = float(cfg.get("hold", 0.12)); groups, cur, k = [], [], 0
        scene_role = {s["id"]: s.get("role") for s in self.TL["scenes"]}
        words = [w for w in self.TL.get("words", []) if scene_role.get(w.get("scene")) in roles]

        def flush():
            nonlocal cur, k
            if cur:
                k += 1; groups.append((f"cap{k:02d}", " ".join(w["w"] for w in cur), cur[0]["s"], cur[-1]["e"])); cur = []
        for w in words:
            if cur and (w["scene"] != cur[-1]["scene"] or len(cur) >= max_w or len(" ".join(x["w"] for x in cur + [w])) > max_c or (w["s"] - cur[-1]["e"]) > 0.6):
                flush()
            cur.append(w)
            if w["w"].rstrip('"\'')[-1:] in ".?!…": flush()
        flush()
        out = []
        for i, (gid, txt, s, e) in enumerate(groups):
            nxt = groups[i + 1][2] if i + 1 < len(groups) else self.TOTAL
            out.append((gid, txt, round(s, 3), round(min(e + hold, nxt - 0.02, self.TOTAL), 3)))
        return out

    def run(self):
        E, Q = self.E, self.Q
        q = E["quiz"]
        self.v2 = E.get("format") == "quiz-v2"
        # chrome
        self.body.append(Q.bug())
        if not self.v2: self.body.append(Q.badge(E.get("difficulty", "MEDIUM")))
        for st in self.V.get("stage", []): self.stage(st)
        mapc = self.G.credits() if self.G.scenes else ""
        bits = [b for b in self.credit_bits if b not in mapc]                                   # "Natural Earth" is already in the map-data credit
        credit = " · ".join(dict.fromkeys(([f"Map data: {mapc}"] if mapc else []) + bits + ["Voice: AI (Kokoro) · thequizwire.com"]))
        if self.v2:
            self.J("tl.set('#bug',{autoAlpha:0},0);")                                   # Q9: no chrome before the question lands
            self.body.append(Q.hook("hook", q["question"], q.get("keyword")))
            self.body.append(Q.chips("q1", q["options"], q["correct"]))
            caps = self.caption_groups()
            self.body.append(Q.captions([(g, t) for g, t, _, _ in caps]))
            for g, _, t0, t1 in caps: Q.caption_show(g, t0, t1)
            self.body.append(Q.cta(q.get("tease", "Tomorrow: a new question"), q.get("cta_line", "One map question a day · Subscribe")))
            self.body.append(Q.credit_line(credit))
            self.caption_count = len(caps)
        else:
            self.body.append(Q.card("q1", q["question"], q["options"], q["correct"], seconds=q.get("countdown", 3)))
        for el in self.V.get("elements", []): self.element(el)
        if not self.v2: self.body.append(Q.end_card(credit))
        self.body.append(Q.progress(self.TOTAL))
        self.body.append(self.FX.overlays())
        for b in self.V.get("beats", []): self.beat(b)
        self.body.append(self.FX.video_layers())
        return self.write()

    def write(self):
        hf = self.hf; hf.mkdir(parents=True, exist_ok=True)
        (hf / "fonts").mkdir(exist_ok=True)
        for fn in FONTS: shutil.copy(REPO / "fonts" / fn, hf / "fonts" / fn)
        shutil.copy(ENGINE / "vendor" / "gsap.min.js", hf / "gsap.min.js")
        css = f"""
@font-face{{font-family:'Oswald';src:url('fonts/Oswald.ttf');font-weight:200 700}}
@font-face{{font-family:'Anton';src:url('fonts/Anton-Regular.ttf')}}
@font-face{{font-family:'DM Serif';src:url('fonts/DMSerifDisplay-Regular.ttf')}}
@font-face{{font-family:'DM Serif';src:url('fonts/DMSerifDisplay-Italic.ttf');font-style:italic}}
@font-face{{font-family:'Elite';src:url('fonts/SpecialElite-Regular.ttf')}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:{INK}}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:{INK};color:{CREAM}}}
.clipin{{position:absolute;left:0;top:0;width:100%;height:100%}}
.clip{{position:absolute;left:0;top:0;width:1080px;height:1920px;overflow:hidden}}
.kb{{position:absolute;left:-108px;top:-201px;width:1296px;height:2322px;transform-origin:50% 50%}}
.kb img{{position:absolute;left:0;top:0;width:1296px;height:2322px;object-fit:cover}}
{fx.CSS}{geo.CSS}{quiz.CSS}{charts.CSS}
"""
        title = f"{self.series['name']} #{self.E.get('number', '')}: {self.E['title']}"
        audio = f'<audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{f(self.TOTAL)}" data-track-index="9"></audio>' if (hf / "assets" / "mix.wav").exists() else ""
        doc = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{quiz.esc(title)}</title>
<script src="gsap.min.js"></script>
{geo.head_scripts()}
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{f(self.TOTAL)}" data-width="1080" data-height="1920">
{audio}
{chr(10).join(self.body)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(self.js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
        (hf / "index.html").write_text(doc)
        (hf / "hyperframes.json").write_text('{\n  "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",\n  "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},\n  "media": {"autoProxy": false}\n}\n')
        (hf / "meta.json").write_text(json.dumps({"id": self.E["id"], "name": title, "estimated_timeline": bool(self.TL.get("estimated"))}) + "\n")
        (hf / "package.json").write_text(json.dumps({"name": self.E["id"], "private": True, "type": "module",
                                                      "scripts": {"check": "npx --yes hyperframes@0.8.137 check", "render": "npx --yes hyperframes@0.8.137 render"}}, indent=2) + "\n")
        return {"index_kb": len(doc) // 1024, "ops": len(self.js), "stages": len(self.stages), "total": self.TOTAL, "estimated": bool(self.TL.get("estimated")), "captions": getattr(self, "caption_count", 0)}


def main():
    ep = Path(sys.argv[1]).resolve()
    hf = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / ".cache/build" / ep.name / "hf"
    r = Composer(ep, hf).run()
    print(f"index.html: {r['index_kb']} KB, {r['ops']} timeline ops, {r['stages']} stages, total {r['total']} s" + ("  [ESTIMATED timeline]" if r["estimated"] else ""))


if __name__ == "__main__":
    main()
