"""engine/quiz.py — the shared QuizWire quiz UI for every series (Python -> HTML/CSS/GSAP strings).

Layout (1080x1920, platform dead zones: top < 230, bottom > 1600, right > 960 are never used for text):
    0 … 1180   visual stage (map / globe / diagram / footage)      ← engine/geo.py, engine/charts.py, FX plates
    230        series bug (top-left) + difficulty badge (top-right ≤ 960)
    1190…1600  question card: question (≤ 3 lines) + countdown ring + 2x2 options  (the "caption band")
    1600…1920  nothing (platform UI)

Usage in build.py:
    import quiz
    Q = quiz.Quiz(J, series=SERIES, number=EP["number"])
    body.append(Q.bug()); body.append(Q.badge("MEDIUM"))
    body.append(Q.card("q1", question, options, correct_idx))          # static HTML, hidden until Q.card_in
    Q.card_in(t); Q.options_in(t + 0.4); Q.countdown(t0, seconds=3); Q.reveal(t, correct_idx)
    body.append(Q.answer_plate("a1", "Answer: ..."))      → Q.answer_in(t)
    body.append(Q.fact("f1", text, y=1230))               → Q.fact_in(t0, t1)
    body.append(Q.end_card(credit_line)); Q.end_in(t)
    CSS += quiz.CSS

Text goes in `tu` units so factcheck/textqa see every word. The card and its children carry
data-layout-allow-caption-zone (they ARE the band) and data-tq-dwell="off" where the copy is deliberately brief.
"""
import html

SEA, LAND, SAND, RED, CREAM, INK = "#0F2A3A", "#1D3A4A", "#E3A72F", "#C8102E", "#EFE6D2", "#0B1620"
RED_ON_DARK = "#FF4D4D"
SAFE_TOP = 230
LETTERS = "ABCD"
DISTRACTOR = ' data-fc="distractor"'


def f(x): return f"{x:.3f}"
def esc(s): return html.escape(str(s))


ALLOW = ' data-layout-allow-overlap="true" data-layout-allow-occlusion="true"'   # v3 UI floats over the map and under flashes on purpose
CAPZ = ' data-layout-allow-caption-zone="true"'                                      # intentional lower-third copy (pills end at 1240; captions at 1500)


class Quiz:
    def __init__(self, J, series, number=None, accent=None):
        """series = series.json entry (needs name, slug, color); number = episode number for the bug."""
        self.J, self.series, self.number = J, series, number
        self.accent = accent or series.get("color", SAND)
        self.cards = {}

    # ---------------------------------------------------------------- chrome
    def bug(self):
        n = f' <b data-layout-allow-occlusion="true" data-layout-allow-overlap="true">#{self.number}</b>' if self.number else ""
        return (f'<div id="bug" class="bug tu" data-tq-dwell="off" data-layout-allow-overlap="true" data-layout-allow-occlusion="true" style="--acc:{self.accent}">'
                f'<span class="dot"></span>{esc(self.series["name"]).upper()}{n}</div>')

    def badge(self, level="MEDIUM"):
        lv = level.upper()
        return f'<div id="badge" class="badge tu {lv.lower()}" data-tq-dwell="off">{esc(lv)}</div>'

    def wordmark(self, id_="wm"):
        return f'<div id="{id_}" class="wordmark tu" data-tq-dwell="off">THE<b>QUIZ</b>WIRE</div>'

    # ---------------------------------------------------------------- question card
    def card(self, cid, question, options, correct, seconds=3):
        assert len(options) == 4 and 0 <= correct < 4, "quiz card needs exactly 4 options and a correct index"
        self.cards[cid] = {"correct": correct, "options": options, "seconds": seconds}
        opts = "".join(
            f'<div class="opt tu" id="{cid}_o{i}"{"" if i == correct else " data-fc=\"distractor\""}><span class="let" data-fc="skip">{LETTERS[i]}</span><span class="otext">{esc(o)}</span></div>'
            for i, o in enumerate(options))
        nums = "".join(f'<div class="cnum tu" id="{cid}_n{k}" data-tq-dwell="off">{k}</div>' for k in range(seconds, 0, -1))
        r = 62; C = 2 * 3.14159265 * r
        ring = (f'<div class="ring" id="{cid}_ring"><svg width="150" height="150" viewBox="0 0 150 150">'
                f'<circle class="bg" cx="75" cy="75" r="{r}"></circle>'
                f'<circle class="fg" id="{cid}_fg" cx="75" cy="75" r="{r}" style="stroke-dasharray:{C:.2f};stroke-dashoffset:0"></circle></svg>{nums}</div>')
        return (f'<div id="{cid}" class="qcard" data-layout-allow-caption-zone="true" style="--acc:{self.accent}">'
                f'<div class="qtext tu" id="{cid}_q">{esc(question)}</div>{ring}<div class="opts" id="{cid}_opts">{opts}</div></div>')

    def card_in(self, t, cid=None, dur=0.45):
        cid = cid or next(iter(self.cards))
        self.J(f"tl.fromTo('#{cid}',{{autoAlpha:0,y:80}},{{autoAlpha:1,y:0,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t)});")

    def card_out(self, t, cid=None, dur=0.35):
        cid = cid or next(iter(self.cards))
        self.J(f"tl.to('#{cid}',{{autoAlpha:0,y:60,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    def options_in(self, t, cid=None, gap=0.12):
        cid = cid or next(iter(self.cards))
        for i in range(4):
            self.J(f"tl.fromTo('#{cid}_o{i}',{{autoAlpha:0,x:-30}},{{autoAlpha:1,x:0,duration:0.3,ease:'power2.out',immediateRender:false}},{f(t + i * gap)});")

    def countdown(self, t0, cid=None, seconds=None):
        """Ring drains over `seconds`; digits 3-2-1 swap on whole seconds (separate elements: no textContent writes)."""
        cid = cid or next(iter(self.cards)); n = seconds or self.cards[cid]["seconds"]
        C = 2 * 3.14159265 * 62
        self.J(f"tl.fromTo('#{cid}_ring',{{autoAlpha:0,scale:0.6}},{{autoAlpha:1,scale:1,duration:0.25,ease:'back.out(2)',immediateRender:false}},{f(t0 - 0.25)});")
        self.J(f"tl.fromTo('#{cid}_fg',{{strokeDashoffset:0}},{{strokeDashoffset:{C:.2f},duration:{f(n)},ease:'none',immediateRender:false}},{f(t0)});")
        for i, k in enumerate(range(n, 0, -1)):
            self.J(f"tl.set('#{cid}_n{k}',{{autoAlpha:1}},{f(t0 + i)});")
            self.J(f"tl.fromTo('#{cid}_n{k}',{{scale:1.25}},{{scale:1,duration:0.3,ease:'power2.out',immediateRender:false}},{f(t0 + i)});")
            self.J(f"tl.set('#{cid}_n{k}',{{autoAlpha:0}},{f(t0 + i + 1)});")
        self.J(f"tl.to('#{cid}_ring',{{autoAlpha:0,duration:0.2}},{f(t0 + n)});")
        return t0 + n

    def reveal(self, t, cid=None, correct=None):
        cid = cid or next(iter(self.cards)); c = self.cards[cid]["correct"] if correct is None else correct
        for i in range(4):
            if i == c:
                self.J(f"tl.to('#{cid}_o{i}',{{backgroundColor:'{SAND}',color:'{INK}',scale:1.04,duration:0.25,ease:'back.out(3)'}},{f(t)});")
                self.J(f"tl.to('#{cid}_o{i} .let',{{backgroundColor:'{INK}',color:'{SAND}',duration:0.25}},{f(t)});")
            else:
                self.J(f"tl.to('#{cid}_o{i}',{{opacity:0.32,duration:0.3}},{f(t)});")

    # ---------------------------------------------------------------- reveal copy + story
    def answer_plate(self, aid, text, y=980, sub=""):
        s = f'<div class="asub tu">{esc(sub)}</div>' if sub else ""
        return f'<div id="{aid}" class="answer" style="top:{y}px"><div class="amain tu">{esc(text)}</div>{s}</div>'

    def answer_in(self, t, aid, dur=0.4):
        self.J(f"tl.fromTo('#{aid}',{{autoAlpha:0,scale:0.9}},{{autoAlpha:1,scale:1,duration:{f(dur)},ease:'back.out(1.8)',immediateRender:false}},{f(t)});")

    def answer_out(self, t, aid, dur=0.3):
        self.J(f"tl.to('#{aid}',{{autoAlpha:0,duration:{f(dur)}}},{f(t)});")

    def fact(self, fid, text, y=1230, kicker=""):
        k = f'<div class="fkick tu">{esc(kicker)}</div>' if kicker else ""
        return f'<div id="{fid}" class="fact" data-layout-allow-caption-zone="true" style="top:{y}px">{k}<div class="ftext tu">{esc(text)}</div></div>'

    def fact_in(self, t0, t1, fid, dur=0.35):
        self.J(f"tl.fromTo('#{fid}',{{autoAlpha:0,y:40}},{{autoAlpha:1,y:0,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t0)});")
        if t1 is not None:
            self.J(f"tl.to('#{fid}',{{autoAlpha:0,y:-30,duration:0.3,ease:'power2.in'}},{f(t1 - 0.3)});")

    def end_card(self, credit_line, cta="What was your first guess?", follow="Comment below · Follow for daily quizzes"):
        return (f'<div id="endcard" class="endcard" data-layout-allow-caption-zone="true">{self.wordmark("wm_end")}'
                f'<div class="ecta tu" id="ecta">{esc(cta)}</div><div class="efollow2 tu" id="efollow">{esc(follow)}</div>'
                f'<div class="credit tu" id="ecredit">{esc(credit_line)}</div></div>')

    def end_in(self, t, clip_ids=()):
        # the stage (map / image clips) and the HUD leave BEFORE the end card arrives: no text may sit under the card
        # (hyperframes check: layout/text_occluded + content_overlap during the crossfade). Id selectors only (hfstatic).
        for cid in [*(f"{c}_in" for c in clip_ids), "bug", "badge"]:
            self.J(f"tl.to('#{cid}',{{autoAlpha:0,duration:0.3,ease:'power2.in'}},{f(max(0.0, t - 0.3))});")
        self.J(f"tl.fromTo('#endcard',{{autoAlpha:0}},{{autoAlpha:1,duration:0.4,immediateRender:false}},{f(t)});")
        self.J(f"tl.fromTo('#ecta',{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:0.4,ease:'power3.out',immediateRender:false}},{f(t + 0.3)});")
        self.J(f"tl.fromTo('#efollow',{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:0.4,ease:'power3.out',immediateRender:false}},{f(t + 0.6)});")

    def progress(self, total):
        """Thin bar at the very bottom (decorative, inside the platform band on purpose: no text)."""
        self.J(f"tl.fromTo('#prog',{{scaleX:0}},{{scaleX:1,duration:{f(total)},ease:'none',immediateRender:false}},0);")
        return '<div class="progress"><div id="prog"></div></div>'

    # ================================================================ v2 "Guess it → See it" (docs/PLAN_V2.md §2)
    # Band layout (1190…1600): hook line 1190–1310 · chips 1325/1405/1485 (h 70) · captions 1215 (one line) ·
    # fact plate 1350 · cta 1350 · credit 1548. Nothing wider than x 940. No card, no ring, no full-screen end card.
    def hook(self, hid, question, keyword=None):
        """The question as a caption on the visual (t = 0). `keyword` (one word/phrase from the question) is coloured."""
        txt = esc(question)
        if keyword and keyword.lower() in question.lower():
            i = question.lower().index(keyword.lower()); txt = esc(question[:i]) + f'<b>{esc(question[i:i + len(keyword)])}</b>' + esc(question[i + len(keyword):])
        return f'<div id="{hid}" class="hook tu" data-layout-allow-caption-zone="true" style="--acc:{self.accent}">{txt}</div>'

    def hook_in(self, t, hid="hook", dur=0.25):
        self.J(f"tl.fromTo('#{hid}',{{autoAlpha:0,y:24}},{{autoAlpha:1,y:0,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t)});")

    def hook_out(self, t, hid="hook", dur=0.3):
        self.J(f"tl.to('#{hid}',{{autoAlpha:0,y:-20,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    def chips(self, cid, options, correct):
        """Three compact option chips over the visual (v2 replaces the 2x2 card)."""
        assert len(options) == 3 and 0 <= correct < 3, "v2 chips need exactly 3 options and a correct index"
        self.cards[cid] = {"correct": correct, "options": options, "seconds": 1.5, "v2": True}
        rows = "".join(
            f'<div class="chip tu" id="{cid}_o{i}"{DISTRACTOR if i != correct else ""}><span class="let" data-fc="skip">{LETTERS[i]}</span><span class="otext">{esc(o)}</span></div>'
            for i, o in enumerate(options))
        return (f'<div id="{cid}" class="chips" data-layout-allow-caption-zone="true" style="--acc:{self.accent}">{rows}'
                f'<div class="beatbar" id="{cid}_beat"><div class="beatfill" id="{cid}_fill"></div></div></div>')

    def chips_in(self, t, cid=None, gap=0.1):
        cid = cid or next(iter(self.cards))
        self.J(f"tl.set('#{cid}',{{autoAlpha:1}},{f(t)});")
        for i in range(3):
            self.J(f"tl.fromTo('#{cid}_o{i}',{{autoAlpha:0,x:-30}},{{autoAlpha:1,x:0,duration:0.28,ease:'power2.out',immediateRender:false}},{f(t + i * gap)});")

    def beat(self, t0, cid=None, seconds=1.5):
        """The 1.5-s pulse that replaces the countdown: a thin bar drains under the chips, chips breathe once."""
        cid = cid or next(iter(self.cards)); n = float(seconds)
        self.J(f"tl.fromTo('#{cid}_beat',{{autoAlpha:0}},{{autoAlpha:1,duration:0.15,immediateRender:false}},{f(t0 - 0.15)});")
        self.J(f"tl.fromTo('#{cid}_fill',{{scaleX:1}},{{scaleX:0,duration:{f(n)},ease:'none',immediateRender:false}},{f(t0)});")
        for i in range(3):
            self.J(f"tl.to('#{cid}_o{i}',{{scale:1.02,duration:{f(n / 2)},ease:'sine.inOut',yoyo:true,repeat:1}},{f(t0)});")
        self.J(f"tl.to('#{cid}_beat',{{autoAlpha:0,duration:0.15}},{f(t0 + n)});")
        return t0 + n

    def reveal_chips(self, t, cid=None, correct=None):
        cid = cid or next(iter(self.cards)); c = self.cards[cid]["correct"] if correct is None else correct
        for i in range(3):
            if i == c:
                self.J(f"tl.to('#{cid}_o{i}',{{backgroundColor:'{SAND}',color:'{INK}',scale:1.04,duration:0.25,ease:'back.out(3)'}},{f(t)});")
                self.J(f"tl.to('#{cid}_o{i} .let',{{backgroundColor:'{INK}',color:'{SAND}',duration:0.25}},{f(t)});")
            else:
                self.J(f"tl.to('#{cid}_o{i}',{{opacity:0.3,duration:0.3}},{f(t)});")

    def chips_out(self, t, cid=None, dur=0.3):
        cid = cid or next(iter(self.cards))
        self.J(f"tl.to('#{cid}',{{autoAlpha:0,y:30,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    def captions(self, groups):
        """groups = [(gid, text)]: pre-split spoken phrases (≤ 4 words), one element each, shown by caption_show()."""
        return "".join(f'<div id="{gid}" class="cap tu" data-layout-allow-caption-zone="true" data-tq-dwell="off">{esc(txt)}</div>' for gid, txt in groups)

    def caption_show(self, gid, t0, t1):
        self.J(f"tl.set('#{gid}',{{autoAlpha:1}},{f(t0)});")
        self.J(f"tl.set('#{gid}',{{autoAlpha:0}},{f(t1)});")

    def bug_in(self, t, dur=0.3):
        self.J(f"tl.fromTo('#bug',{{autoAlpha:0,x:-20}},{{autoAlpha:1,x:0,duration:{f(dur)},ease:'power2.out',immediateRender:false}},{f(t)});")

    def cta(self, tease, line="One map question a day · Subscribe"):
        return (f'<div id="cta" class="cta" data-layout-allow-caption-zone="true"><div class="ctease tu">{esc(tease)}</div>'
                f'<div class="cline tu" data-tq-dwell="off">{esc(line)}</div></div>')

    def cta_in(self, t0, t1=None, dur=0.35):
        self.J(f"tl.fromTo('#cta',{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:{f(dur)},ease:'power3.out',immediateRender:false}},{f(t0)});")
        if t1 is not None: self.J(f"tl.to('#cta',{{autoAlpha:0,duration:0.3,ease:'power2.in'}},{f(t1 - 0.3)});")

    def credit_line(self, credit):
        return f'<div id="credit2" class="credit2 tu" data-layout-allow-caption-zone="true" data-tq-dwell="off">{esc(credit)}</div>'

    def credit_in(self, t0, t1=None):
        self.J(f"tl.fromTo('#credit2',{{autoAlpha:0}},{{autoAlpha:1,duration:0.3,immediateRender:false}},{f(t0)});")
        if t1 is not None: self.J(f"tl.to('#credit2',{{autoAlpha:0,duration:0.25}},{f(t1 - 0.25)});")

    # ================================================================ v3 "satellite quiz" (docs/V3_LOOK.md)
    # Full-bleed map; UI floats on scrims. Safe zones: bug 232, hook 300–620 (x 60–960), pills 790–1240 (text ≤ x 900),
    # ring 1275–1475 (200 px), tease 1512, answer banner 290/450, big fact 1250–1460 (x 60–960), word captions 1500, credit 1560.
    YELLOW = "#FFD400"

    def scrims(self):
        return '<div id="scrimtop" class="scrim scrim-top" data-layout-allow-overlap="true"></div><div id="scrimbot" class="scrim scrim-bot" data-layout-allow-overlap="true"></div>'

    def hook3(self, hid, question, keyword=None):
        txt = esc(question)
        if keyword and keyword.lower() in question.lower():
            i = question.lower().index(keyword.lower()); txt = esc(question[:i]) + f'<b{ALLOW}>{esc(question[i:i + len(keyword)])}</b>' + esc(question[i + len(keyword):])
        n = len(question); size = "s" if n > 58 else "m" if n > 42 else ""
        return f'<div id="{hid}" class="hook3 tu {size}" data-layout-allow-overlap="true" data-layout-allow-occlusion="true">{txt}</div>'

    def hook3_in(self, t, hid="hook", dur=0.4):
        self.J(f"tl.fromTo('#{hid}',{{autoAlpha:0,scale:0.82,y:30}},{{autoAlpha:1,scale:1,y:0,duration:{f(dur)},ease:'back.out(1.5)',immediateRender:false}},{f(t)});")
        if t > 0: self.J(f"tl.to('#scrimtop',{{opacity:1,duration:0.4}},{f(t - 0.2)});")

    def hook3_out(self, t, hid="hook", dur=0.3):
        self.J(f"tl.to('#{hid}',{{autoAlpha:0,y:-40,scale:0.96,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    def pills(self, cid, options, correct, meta=None):
        """Three option pills; meta[i] = {"flag": "nz"} | {"emoji": "1f3d4"} | {} (icon circle on the left of the label)."""
        assert len(options) == 3 and 0 <= correct < 3, "v3 pills need exactly 3 options and a correct index"
        self.cards[cid] = {"correct": correct, "options": options, "seconds": 1.5, "v2": True}
        meta = meta or [{}] * 3
        rows = []
        for i, o in enumerate(options):
            m = meta[i] if i < len(meta) else {}
            icon = (f'<span class="pflag" style="background-image:url(assets/geo/flags/{m["flag"].lower()}.svg)"></span>' if m.get("flag")
                    else f'<img class="pemo" src="assets/stickers/{m["emoji"]}.svg" alt="">' if m.get("emoji") else "")
            # pill C's bottom (≈ 1240) dips 50 px into the caption band (1190+); words sit at y 1500 so they never touch — declare it
            rows.append(f'<div class="pill tu" id="{cid}_o{i}"{DISTRACTOR if i != correct else ""}{ALLOW}{CAPZ}>'
                        f'<span class="let" data-fc="skip"{ALLOW}{CAPZ}>{LETTERS[i]}</span>{icon}<span class="otext"{ALLOW}{CAPZ}>{esc(o)}</span></div>')
        return (f'<div id="{cid}" class="pills" data-layout-allow-overlap="true">{"".join(rows)}</div>'
                f'<div class="ring3" id="{cid}_ring" data-layout-allow-overlap="true"><svg width="200" height="200" viewBox="0 0 200 200"><circle class="bg" cx="100" cy="100" r="88"></circle>'
                f'<circle class="fg" id="{cid}_arc" cx="100" cy="100" r="88" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0"></circle></svg>'
                + "".join(f'<div class="dg tu" id="{cid}_d{i}" data-tq-dwell="off" data-fc="skip"{ALLOW}>{i}</div>' for i in range(5, 0, -1)) + '</div>'
                f'<div class="tease3 tu" id="{cid}_tease" data-tq-dwell="off" data-fc="skip" data-layout-allow-overlap="true">GUESS BEFORE THE TIMER ENDS</div>')

    def pills_in(self, t, cid=None, gap=0.12):
        cid = cid or next(iter(self.cards))
        self.J(f"tl.set('#{cid}',{{autoAlpha:1}},{f(t)});")
        for i in range(3):
            self.J(f"tl.fromTo('#{cid}_o{i}',{{autoAlpha:0,x:-80,scale:0.9}},{{autoAlpha:1,x:0,scale:1,duration:0.38,ease:'back.out(1.4)',immediateRender:false}},{f(t + i * gap)});")

    def beat3(self, t0, cid=None, seconds=3.0):
        """The think-time: ring drains for `seconds` while big digits count down (3 · 2 · 1), pills breathe, tease line shows.
        Digits 5…1 exist in the markup; only the last round(seconds) of them are animated (quizscore ticks once per digit)."""
        cid = cid or next(iter(self.cards)); n = float(seconds); nd = max(1, int(round(n))); step = n / nd
        self.J(f"tl.fromTo('#{cid}_ring',{{autoAlpha:0,scale:0.6}},{{autoAlpha:1,scale:1,duration:0.3,ease:'back.out(2)',immediateRender:false}},{f(t0 - 0.3)});")
        self.J(f"tl.fromTo('#{cid}_tease',{{autoAlpha:0,y:20}},{{autoAlpha:1,y:0,duration:0.3,immediateRender:false}},{f(t0 - 0.3)});")
        self.J(f"tl.fromTo('#{cid}_arc',{{strokeDashoffset:0}},{{strokeDashoffset:100,duration:{f(n)},ease:'none',immediateRender:false}},{f(t0)});")
        for i in range(nd):
            d = nd - i; ts = t0 + i * step
            self.J(f"tl.fromTo('#{cid}_d{d}',{{autoAlpha:0,scale:1.6}},{{autoAlpha:1,scale:1,duration:0.22,ease:'back.out(2.5)',immediateRender:false}},{f(ts)});")
            self.J(f"tl.to('#{cid}_d{d}',{{autoAlpha:0,scale:0.5,duration:0.12,ease:'power2.in'}},{f(ts + step - 0.12)});")
        for i in range(3):
            self.J(f"tl.to('#{cid}_o{i}',{{scale:1.03,duration:{f(step / 2)},ease:'sine.inOut',yoyo:true,repeat:{2 * nd - 1}}},{f(t0)});")
        self.J(f"tl.to('#{cid}_ring',{{autoAlpha:0,scale:0.7,duration:0.2}},{f(t0 + n)});")
        self.J(f"tl.to('#{cid}_tease',{{autoAlpha:0,duration:0.2}},{f(t0 + n - 0.25)});")     # gone before the reveal caption lands
        return t0 + n

    def reveal_pills(self, t, cid=None, correct=None):
        cid = cid or next(iter(self.cards)); c = self.cards[cid]["correct"] if correct is None else correct
        for i in range(3):
            if i == c:
                self.J(f"tl.to('#{cid}_o{i}',{{backgroundColor:'#137A36',borderColor:'#ffffff',scale:1.06,duration:0.3,ease:'back.out(3)'}},{f(t)});")
                self.J(f"tl.to('#{cid}_o{i} .let',{{backgroundColor:'#ffffff',color:'#137A36',duration:0.3}},{f(t)});")
            else:
                self.J(f"tl.to('#{cid}_o{i}',{{opacity:0.32,scale:0.96,duration:0.3}},{f(t)});")

    def pills_out(self, t, cid=None, dur=0.35):
        cid = cid or next(iter(self.cards))
        for i in range(3):
            self.J(f"tl.to('#{cid}_o{i}',{{autoAlpha:0,x:90,duration:{f(dur)},ease:'power2.in'}},{f(t + i * 0.06)});")
        self.J(f"tl.set('#{cid}',{{autoAlpha:0}},{f(t + dur + 0.2)});")

    def banner(self, text, sub=""):
        n = len(text); size = "s" if n > 16 else "m" if n > 11 else ""
        return (f'<div id="banner" class="banner3 tu {size}" data-layout-allow-overlap="true" data-layout-allow-occlusion="true">{esc(text)}</div>'
                f'<div id="bannersub" class="bannersub tu" data-layout-allow-overlap="true" data-layout-allow-occlusion="true" data-tq-dwell="off" data-fc="skip">{esc(sub)}</div>')

    def banner_in(self, t, dur=0.45):
        self.J(f"tl.fromTo('#banner',{{autoAlpha:0,scale:0.6,y:40}},{{autoAlpha:1,scale:1,y:0,duration:{f(dur)},ease:'back.out(1.8)',immediateRender:false}},{f(t)});")
        self.J(f"tl.fromTo('#bannersub',{{autoAlpha:0,y:20}},{{autoAlpha:1,y:0,duration:0.3,ease:'power2.out',immediateRender:false}},{f(t + 0.25)});")

    def banner_out(self, t, dur=0.3):
        self.J(f"tl.to('#banner, #bannersub',{{autoAlpha:0,y:-30,duration:{f(dur)},ease:'power2.in'}},{f(t)});")
        self.J(f"tl.to('#scrimtop',{{opacity:0.35,duration:0.8,ease:'power1.inOut'}},{f(t)});")        # let the satellite breathe during the story

    def fact3(self, fid, text, kicker="", y=1250):
        k = f'<b{ALLOW}>{esc(kicker)}</b> ' if kicker else ""
        n = len(kicker) + len(text); size = "s" if n > 40 else "m" if n > 30 else ""
        return f'<div id="{fid}" class="fact3 tu {size}" style="top:{y}px" data-layout-allow-caption-zone="true" data-layout-allow-overlap="true">{k}{esc(text)}</div>'

    def fact3_in(self, t0, t1, fid, dur=0.4):
        self.J(f"tl.fromTo('#{fid}',{{autoAlpha:0,y:50,scale:0.92}},{{autoAlpha:1,y:0,scale:1,duration:{f(dur)},ease:'back.out(1.4)',immediateRender:false}},{f(t0)});")
        if t1 is not None: self.J(f"tl.to('#{fid}',{{autoAlpha:0,y:-20,duration:0.25,ease:'power1.in'}},{f(t1 - 0.25)});")

    def sticker(self, sid, src, x, y, size=240, rot=0, z=60):
        return (f'<img id="{sid}" class="sticker3" src="{src}" alt="" style="left:{x}px;top:{y}px;width:{size}px;height:{size}px;z-index:{z};--rot:{rot}deg" '
                f'data-layout-allow-overlap="true">')

    def sticker_in(self, t, sid, dur=0.45):
        self.J(f"tl.fromTo('#{sid}',{{autoAlpha:0,scale:0.3,rotation:'-=25'}},{{autoAlpha:1,scale:1,rotation:'+=25',duration:{f(dur)},ease:'back.out(2)',immediateRender:false}},{f(t)});")

    def sticker_out(self, t, sid, dur=0.25):
        self.J(f"tl.to('#{sid}',{{autoAlpha:0,scale:0.6,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    FACES = {
        "think": '<ellipse cx="-30" cy="-18" rx="22" ry="26" fill="#fff"/><ellipse cx="30" cy="-18" rx="22" ry="26" fill="#fff"/><circle cx="-24" cy="-14" r="11"/><circle cx="36" cy="-14" r="11"/><path d="M-56 -56q26 -14 52 -4" stroke="#1b1b1b" stroke-width="9" fill="none" stroke-linecap="round"/><path d="M8 -62q26 -8 50 10" stroke="#1b1b1b" stroke-width="9" fill="none" stroke-linecap="round"/><path d="M-20 44q30 -14 52 6" stroke="#1b1b1b" stroke-width="9" fill="none" stroke-linecap="round"/>',
        "wow": '<ellipse cx="-32" cy="-20" rx="24" ry="30" fill="#fff"/><ellipse cx="32" cy="-20" rx="24" ry="30" fill="#fff"/><circle cx="-30" cy="-16" r="12"/><circle cx="34" cy="-16" r="12"/><ellipse cx="0" cy="46" rx="26" ry="32" fill="#1b1b1b"/><ellipse cx="0" cy="56" rx="16" ry="14" fill="#e0505a"/>',
        "happy": '<ellipse cx="-30" cy="-18" rx="22" ry="26" fill="#fff"/><ellipse cx="30" cy="-18" rx="22" ry="26" fill="#fff"/><circle cx="-26" cy="-14" r="11"/><circle cx="34" cy="-14" r="11"/><path d="M-44 30q44 50 88 0" stroke="#1b1b1b" stroke-width="10" fill="none" stroke-linecap="round"/>',
        "sad": '<ellipse cx="-30" cy="-14" rx="22" ry="26" fill="#fff"/><ellipse cx="30" cy="-14" rx="22" ry="26" fill="#fff"/><circle cx="-26" cy="-8" r="11"/><circle cx="34" cy="-8" r="11"/><path d="M-56 -48q26 8 52 18" stroke="#1b1b1b" stroke-width="9" fill="none" stroke-linecap="round"/><path d="M4 -30q26 -10 52 -18" stroke="#1b1b1b" stroke-width="9" fill="none" stroke-linecap="round"/><path d="M-40 60q40 -40 80 0" stroke="#1b1b1b" stroke-width="10" fill="none" stroke-linecap="round"/>',
        "angry": '<ellipse cx="-30" cy="-14" rx="22" ry="26" fill="#fff"/><ellipse cx="30" cy="-14" rx="22" ry="26" fill="#fff"/><circle cx="-24" cy="-8" r="11"/><circle cx="24" cy="-8" r="11"/><path d="M-58 -58q30 6 50 22" stroke="#1b1b1b" stroke-width="10" fill="none" stroke-linecap="round"/><path d="M58 -58q-30 6 -50 22" stroke="#1b1b1b" stroke-width="10" fill="none" stroke-linecap="round"/><path d="M-36 56q36 -30 72 0" stroke="#1b1b1b" stroke-width="10" fill="none" stroke-linecap="round"/>',
        "cool": '<path d="M-66 -30h58v34h-58z M8 -30h58v34h-58z" fill="#1b1b1b"/><path d="M-70 -30h140" stroke="#1b1b1b" stroke-width="8"/><path d="M-40 34q40 40 80 0" stroke="#1b1b1b" stroke-width="10" fill="none" stroke-linecap="round"/>',
    }

    def character(self, cid, flag, face="happy", x=0, y=0, size=200, rot=0, z=62):
        """Own flag-ball character (flag-icons circle + an expression)."""
        eyes = self.FACES.get(face, self.FACES["happy"]); r = size / 2
        return (f'<svg id="{cid}" class="char3" style="left:{x - r:.0f}px;top:{y - r:.0f}px;z-index:{z};--rot:{rot}deg" width="{size}" height="{size}" viewBox="-110 -110 220 220" data-layout-allow-overlap="true">'
                f'<defs><clipPath id="{cid}_clip"><circle r="100"></circle></clipPath></defs>'
                f'<g clip-path="url(#{cid}_clip)"><image href="assets/geo/flags/{flag.lower()}.svg" x="-150" y="-110" width="300" height="220" preserveAspectRatio="xMidYMid slice"></image></g>'
                f'<circle r="100" fill="none" stroke="#ffffff" stroke-width="9"></circle><circle r="104" fill="none" stroke="rgba(0,0,0,.45)" stroke-width="3"></circle><g>{eyes}</g></svg>')

    def character_in(self, t, cid, dur=0.5):
        self.J(f"tl.fromTo('#{cid}',{{autoAlpha:0,scale:0.2,y:60}},{{autoAlpha:1,scale:1,y:0,duration:{f(dur)},ease:'back.out(2.2)',immediateRender:false}},{f(t)});")
        self.J(f"tl.to('#{cid}',{{y:-10,duration:0.9,ease:'sine.inOut',yoyo:true,repeat:5}},{f(t + dur)});")

    def character_out(self, t, cid, dur=0.3):
        self.J(f"tl.to('#{cid}',{{autoAlpha:0,scale:0.5,y:40,duration:{f(dur)},ease:'power2.in'}},{f(t)});")

    # ---- v3 outro (owner brief 2026-10-15): no "next video" tease. Logo + wordmark (no tagline), LIKE / SUBSCRIBE buttons that a cursor
    #      actually clicks (yellow → green "SUBSCRIBED"), social row (Facebook · Instagram · X · Threads) + thequizwire.com.
    #      Ids are fixed (hfstatic needs id selectors). Geometry: logo 480–780 · name 800 · head 936 · buttons 1030–1158 · socials 1190–1318 · url 1362–1454 · credit 1560 (no tagline — owner). Everything is declared lower-third-safe (no word captions in the cta role).
    OUTRO_SOCIAL = (("facebook", "#1877F2"), ("instagram", "#E1306C"), ("x", "#111111"), ("threads", "#101010"))

    def outro3(self, headline="DID YOU GET IT?", url="thequizwire.com"):
        soc = "".join(f'<div class="o-soc" id="o_s{i}" style="left:{196 + i * 180}px;background:{col}"{ALLOW}{CAPZ}><img src="assets/brand/{n}.svg" alt=""></div>'
                      for i, (n, col) in enumerate(self.OUTRO_SOCIAL))
        return (f'<div id="o_dim" class="o-dim"></div>'
                f'<div id="outro" class="outro3" data-fc="skip"{ALLOW}{CAPZ}>'
                f'<div class="o-logo" id="o_logo"{ALLOW}><img src="assets/brand/logo.png" alt=""></div>'
                f'<div class="o-name tu" id="o_name" data-tq-dwell="off" data-fc="skip"{ALLOW}>TheQuizWire</div>'
                f'<div class="o-head tu" id="o_head" data-tq-dwell="off" data-fc="skip"{ALLOW}>{esc(headline)}</div>'
                f'<div class="o-btn o-like" id="o_like"{ALLOW}{CAPZ}><img class="o-ico" id="o_thumb" src="assets/stickers/1f44d.svg" alt=""><span class="tu" data-tq-dwell="off" data-fc="skip"{ALLOW}>LIKE</span></div>'
                f'<div class="o-btn o-sub" id="o_sub"{ALLOW}{CAPZ}><img class="o-ico" id="o_bell" src="assets/stickers/1f514.svg" alt=""><span class="tu" id="o_sublbl" data-tq-dwell="off" data-fc="skip"{ALLOW}>SUBSCRIBE</span>'
                f'<span class="tu o-done" id="o_subdone" data-tq-dwell="off" data-fc="skip"{ALLOW}>✓ SUBSCRIBED</span></div>'
                f'<div class="o-burst" id="o_burst"></div>'
                f'<img class="o-cursor" id="o_cursor" src="assets/brand/cursor.svg" alt="">'
                f'{soc}'
                f'<div class="o-url tu" id="o_url" data-tq-dwell="off" data-fc="skip"{ALLOW}{CAPZ}>🌐 {esc(url)}</div>'
                f'</div>')

    def outro_in(self, t0, t1=None, **_):
        """Choreography (≈ 3.4 s to settle, then holds until t1): dim → logo pop → wordmark → buttons → cursor clicks LIKE
        (white → yellow, thumb bounce) → cursor clicks SUBSCRIBE (yellow → green, label swap, bell wiggle, burst) → socials
        pop in one by one → url pill. Between clicks the cursor eases like a real hand; after the second click it leaves."""
        J = self.J
        J(f"tl.fromTo('#o_dim',{{autoAlpha:0}},{{autoAlpha:1,duration:0.4,immediateRender:false}},{f(t0 + 0.4)});")     # after geo.clear (0.25 s) has taken map text away
        J(f"tl.set('#outro',{{autoAlpha:1}},{f(t0)});")
        J(f"tl.fromTo('#o_logo',{{autoAlpha:0,scale:0.2,rotation:-25}},{{autoAlpha:1,scale:1,rotation:0,duration:0.55,ease:'back.out(1.8)',immediateRender:false}},{f(t0 + 0.05)});")
        J(f"tl.to('#o_logo',{{y:-8,duration:1.1,ease:'sine.inOut',yoyo:true,repeat:-1}},{f(t0 + 0.7)});")
        J(f"tl.fromTo('#o_name',{{autoAlpha:0,y:40,scale:0.9}},{{autoAlpha:1,y:0,scale:1,duration:0.4,ease:'back.out(1.6)',immediateRender:false}},{f(t0 + 0.3)});")
        J(f"tl.fromTo('#o_head',{{autoAlpha:0,scale:0.8}},{{autoAlpha:1,scale:1,duration:0.35,ease:'back.out(2)',immediateRender:false}},{f(t0 + 0.6)});")
        J(f"tl.fromTo('#o_like',{{autoAlpha:0,x:-70,scale:0.9}},{{autoAlpha:1,x:0,scale:1,duration:0.4,ease:'back.out(1.6)',immediateRender:false}},{f(t0 + 0.75)});")
        J(f"tl.fromTo('#o_sub',{{autoAlpha:0,x:70,scale:0.9}},{{autoAlpha:1,x:0,scale:1,duration:0.4,ease:'back.out(1.6)',immediateRender:false}},{f(t0 + 0.85)});")
        # cursor: enters from bottom-right, hovers LIKE, clicks, glides to SUBSCRIBE, clicks, leaves
        J(f"tl.fromTo('#o_cursor',{{autoAlpha:0,x:360,y:380}},{{autoAlpha:1,x:0,y:0,duration:0.55,ease:'power2.out',immediateRender:false}},{f(t0 + 1.05)});")
        tc1 = t0 + 1.7
        J(f"tl.to('#o_cursor',{{scale:0.82,duration:0.08,ease:'power2.in',yoyo:true,repeat:1}},{f(tc1)});")
        J(f"tl.to('#o_like',{{scale:0.92,duration:0.08,yoyo:true,repeat:1}},{f(tc1)});")
        J(f"tl.to('#o_like',{{backgroundColor:'#FFD400',borderColor:'#FFD400',duration:0.2}},{f(tc1 + 0.1)});")
        J(f"tl.fromTo('#o_thumb',{{rotation:0,scale:1}},{{rotation:-22,scale:1.35,duration:0.18,ease:'back.out(3)',yoyo:true,repeat:1,immediateRender:false}},{f(tc1 + 0.08)});")
        J(f"tl.fromTo('#o_burst',{{autoAlpha:0.9,scale:0.4,x:0}},{{autoAlpha:0,scale:1.9,duration:0.5,ease:'power2.out',immediateRender:false}},{f(tc1 + 0.08)});")
        J(f"tl.to('#o_cursor',{{x:470,y:0,duration:0.5,ease:'power2.inOut'}},{f(tc1 + 0.25)});")
        tc2 = tc1 + 0.85
        J(f"tl.to('#o_cursor',{{scale:0.82,duration:0.08,ease:'power2.in',yoyo:true,repeat:1}},{f(tc2)});")
        J(f"tl.to('#o_sub',{{scale:0.92,duration:0.08,yoyo:true,repeat:1}},{f(tc2)});")
        J(f"tl.to('#o_sub',{{backgroundColor:'#137A36',borderColor:'#ffffff',color:'#ffffff',duration:0.22}},{f(tc2 + 0.1)});")
        J(f"tl.to('#o_sublbl',{{autoAlpha:0,y:-14,duration:0.16}},{f(tc2 + 0.1)});")
        J(f"tl.fromTo('#o_subdone',{{autoAlpha:0,y:14}},{{autoAlpha:1,y:0,duration:0.2,ease:'back.out(2)',immediateRender:false}},{f(tc2 + 0.2)});")
        J(f"tl.fromTo('#o_bell',{{rotation:0}},{{rotation:24,duration:0.09,ease:'sine.inOut',yoyo:true,repeat:5,immediateRender:false}},{f(tc2 + 0.1)});")
        J(f"tl.fromTo('#o_burst',{{autoAlpha:0.9,scale:0.4,x:470}},{{autoAlpha:0,scale:2.0,x:470,duration:0.55,ease:'power2.out',immediateRender:false}},{f(tc2 + 0.08)});")
        J(f"tl.to('#o_cursor',{{autoAlpha:0,x:560,y:140,duration:0.4,ease:'power2.in'}},{f(tc2 + 0.4)});")
        for i in range(len(self.OUTRO_SOCIAL)):
            J(f"tl.fromTo('#o_s{i}',{{autoAlpha:0,scale:0.2,y:30}},{{autoAlpha:1,scale:1,y:0,duration:0.38,ease:'back.out(2.2)',immediateRender:false}},{f(tc2 + 0.55 + i * 0.1)});")
            J(f"tl.to('#o_s{i}',{{y:-6,duration:0.9,ease:'sine.inOut',yoyo:true,repeat:-1}},{f(tc2 + 1.0 + i * 0.12)});")
        J(f"tl.fromTo('#o_url',{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:0.4,ease:'back.out(1.5)',immediateRender:false}},{f(tc2 + 1.0)});")
        J(f"tl.to('#o_sub',{{scale:1.04,duration:0.6,ease:'sine.inOut',yoyo:true,repeat:-1}},{f(tc2 + 1.2)});")
        if t1 is not None:
            J(f"tl.to('#outro',{{autoAlpha:0,duration:0.3,ease:'power2.in'}},{f(t1 - 0.3)});")
            J(f"tl.to('#o_dim',{{autoAlpha:0,duration:0.3}},{f(t1 - 0.3)});")

    def credit3(self, credit):
        return f'<div id="credit2" class="credit3 tu" data-layout-allow-caption-zone="true" data-layout-allow-overlap="true" data-tq-dwell="off">{esc(credit)}</div>'



CSS = f"""
.bug{{position:absolute;left:40px;top:{SAFE_TOP}px;font-family:'Oswald';font-weight:600;font-size:30px;letter-spacing:.2em;color:{CREAM};background:{INK};padding:10px 20px 8px 16px;border-left:8px solid var(--acc,{SAND});z-index:80}}
.bug b{{color:var(--acc,{SAND})}}
.bug .dot{{display:none}}
.badge{{position:absolute;right:120px;top:{SAFE_TOP + 4}px;font-family:'Oswald';font-weight:700;font-size:26px;letter-spacing:.24em;color:{INK};background:{CREAM};padding:10px 18px 8px 22px;border-radius:40px;z-index:80}}
.badge.easy{{background:#8FD694}} .badge.medium{{background:{SAND}}} .badge.hard{{background:{RED_ON_DARK}}}
.wordmark{{font-family:'Anton';font-size:44px;letter-spacing:.14em;color:{CREAM}}}
.wordmark b{{color:{RED_ON_DARK};font-weight:400}}
.qcard{{position:absolute;left:40px;top:1190px;width:1000px;height:400px;background:rgba(11,22,32,.95);border-left:10px solid var(--acc,{SAND});box-shadow:0 18px 50px rgba(0,0,0,.45);z-index:70;visibility:hidden;opacity:0}}
.qtext{{position:absolute;left:34px;top:22px;width:700px;font-family:'Oswald';font-weight:600;font-size:46px;line-height:1.16;color:{CREAM}}}
.ring{{position:absolute;left:790px;top:16px;width:150px;height:150px;visibility:hidden;opacity:0}}
.ring svg{{position:absolute;left:0;top:0;transform:rotate(-90deg)}}
.ring circle{{fill:none;stroke-width:10}}
.ring .bg{{stroke:rgba(239,230,210,.18)}}
.ring .fg{{stroke:#4FD1E0;stroke-linecap:round}}
.cnum{{position:absolute;left:0;top:0;width:150px;height:150px;line-height:150px;text-align:center;font-family:'Anton';font-size:76px;color:#4FD1E0;visibility:hidden;opacity:0}}
.opts{{position:absolute;left:30px;top:188px;width:940px}}
.opt{{position:absolute;width:450px;height:84px;background:rgba(239,230,210,.08);border:2px solid rgba(239,230,210,.22);border-radius:12px;color:{CREAM};font-family:'Oswald';font-weight:500;font-size:34px;line-height:84px;white-space:nowrap;overflow:hidden;visibility:hidden;opacity:0}}
.opt:nth-child(1){{left:0;top:0}} .opt:nth-child(2){{left:480px;top:0}} .opt:nth-child(3){{left:0;top:100px}} .opt:nth-child(4){{left:480px;top:100px}}
.opt .let{{display:inline-block;width:56px;height:56px;line-height:56px;margin:0 16px 0 14px;text-align:center;border-radius:50%;background:var(--acc,{SAND});color:{INK};font-weight:700;font-size:30px;vertical-align:middle;position:relative;top:-3px}}
.answer{{position:absolute;left:60px;width:960px;text-align:center;z-index:75;visibility:hidden;opacity:0}}
.amain{{display:inline-block;font-family:'Anton';font-size:64px;letter-spacing:.03em;color:{INK};background:{SAND};padding:14px 34px 8px;box-shadow:0 12px 30px rgba(0,0,0,.4)}}
.asub{{margin-top:12px;font-family:'DM Serif';font-style:italic;font-size:38px;color:{CREAM};text-shadow:0 2px 12px rgba(0,0,0,.7)}}
.fact{{position:absolute;left:60px;width:880px;z-index:70;visibility:hidden;opacity:0}}   /* right edge 940 < 960: clear of the Shorts action column */
.fkick{{font-family:'Oswald';font-weight:700;font-size:28px;letter-spacing:.24em;color:{SAND};margin-bottom:10px}}
.ftext{{font-family:'Oswald';font-weight:500;font-size:48px;line-height:1.2;color:{CREAM};background:rgba(11,22,32,.9);padding:22px 28px 18px;border-left:10px solid {RED}}}
.endcard{{position:absolute;left:0;top:0;width:1080px;height:1920px;background:rgba(11,22,32,.97);text-align:center;padding-top:560px;z-index:90;visibility:hidden;opacity:0}}
.endcard .wordmark{{font-size:72px}}
.ecta{{margin-top:70px;font-family:'DM Serif';font-style:italic;font-size:62px;color:{CREAM};visibility:hidden;opacity:0}}
.efollow2{{margin-top:34px;font-family:'Oswald';font-weight:600;font-size:40px;letter-spacing:.12em;color:{SAND};visibility:hidden;opacity:0}}
.credit{{position:absolute;left:60px;width:960px;top:1440px;font-family:'Oswald';font-size:26px;letter-spacing:.06em;line-height:1.35;color:rgba(239,230,210,.78)}}
.progress{{position:absolute;left:0;bottom:0;width:1080px;height:8px;background:rgba(239,230,210,.18);z-index:95}}
#prog{{width:1080px;height:8px;background:{RED};transform-origin:0 50%}}
/* ---- v2 "Guess it → See it" ---- */
.hook{{position:absolute;left:60px;top:1190px;width:880px;font-family:'Oswald';font-weight:600;font-size:52px;line-height:1.14;color:{CREAM};text-shadow:0 3px 18px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9);z-index:72;visibility:hidden;opacity:0}}
.hook b{{color:var(--acc,{SAND});font-weight:600}}
.chips{{position:absolute;left:60px;top:1325px;width:880px;height:250px;z-index:70;visibility:hidden;opacity:0}}
.chip{{position:absolute;left:0;width:880px;height:70px;background:rgba(11,22,32,.86);border:2px solid rgba(239,230,210,.26);border-radius:14px;color:{CREAM};font-family:'Oswald';font-weight:500;font-size:34px;line-height:66px;white-space:nowrap;overflow:hidden;visibility:hidden;opacity:0;transform-origin:50% 50%}}
.chip:nth-child(1){{top:0}} .chip:nth-child(2){{top:80px}} .chip:nth-child(3){{top:160px}}
.chip .let{{display:inline-block;width:48px;height:48px;line-height:48px;margin:0 16px 0 12px;text-align:center;border-radius:50%;background:var(--acc,{SAND});color:{INK};font-weight:700;font-size:28px;vertical-align:middle;position:relative;top:-2px}}
.beatbar{{position:absolute;left:0;top:240px;width:880px;height:6px;background:rgba(239,230,210,.18);border-radius:3px;visibility:hidden;opacity:0}}
.beatfill{{width:880px;height:6px;background:#4FD1E0;border-radius:3px;transform-origin:0 50%}}
.cap{{position:absolute;left:60px;top:1215px;width:880px;text-align:center;font-family:'Oswald';font-weight:600;font-size:58px;line-height:1.1;color:{CREAM};text-shadow:0 3px 18px rgba(0,0,0,.9),0 0 3px rgba(0,0,0,.9);z-index:72;visibility:hidden;opacity:0}}
.cta{{position:absolute;left:60px;top:1350px;width:880px;text-align:center;z-index:70;visibility:hidden;opacity:0}}
.ctease{{font-family:'DM Serif';font-style:italic;font-size:44px;color:{CREAM};text-shadow:0 2px 12px rgba(0,0,0,.8)}}
.cline{{margin-top:14px;font-family:'Oswald';font-weight:600;font-size:34px;letter-spacing:.1em;color:{SAND};text-shadow:0 2px 12px rgba(0,0,0,.8)}}
.credit2{{position:absolute;left:60px;top:1546px;width:900px;font-family:'Oswald';font-size:20px;letter-spacing:.03em;line-height:1.3;color:rgba(239,230,210,.72);text-shadow:0 1px 6px rgba(0,0,0,.9);z-index:70;visibility:hidden;opacity:0;white-space:normal;overflow:visible}}

/* ---- v3 "satellite quiz" (docs/V3_LOOK.md) ---- */
.v3 .scrim{{position:absolute;left:0;width:1080px;z-index:20;pointer-events:none}}
.v3 .scrim-top{{top:0;height:780px;background:linear-gradient(180deg,rgba(0,0,0,.82) 0%,rgba(0,0,0,.6) 55%,rgba(0,0,0,0) 100%)}}
.v3 .scrim-bot{{top:1180px;height:740px;background:linear-gradient(0deg,rgba(0,0,0,.9) 0%,rgba(0,0,0,.78) 40%,rgba(0,0,0,.62) 72%,rgba(0,0,0,.3) 92%,rgba(0,0,0,0) 100%)}}   /* fact band (1250–1460) keeps ≥ 3:1 over bright terrain / colour fills */
.v3 .bug{{left:48px;top:232px;font-family:'Lilita';font-weight:400;font-size:30px;letter-spacing:.1em;color:#fff;background:#C8102E;border:0;padding:14px 22px 12px;border-radius:12px;box-shadow:0 8px 20px rgba(0,0,0,.4)}}
.v3 .bug b{{color:#FFD400}}
.v3 .hook3{{position:absolute;left:60px;top:300px;width:900px;text-align:center;font-family:'Lilita';font-size:100px;line-height:1.04;text-transform:uppercase;color:#fff;
  -webkit-text-stroke:3px #141414;paint-order:stroke fill;text-shadow:0 7px 0 rgba(0,0,0,.6),0 0 22px rgba(0,0,0,.9),0 16px 32px rgba(0,0,0,.7);z-index:72;visibility:hidden;opacity:0}}
.v3 .hook3.m{{font-size:86px}} .v3 .hook3.s{{font-size:74px}}
.v3 .hook3 b{{color:#FFD400;font-weight:400}}
.v3 .pills{{position:absolute;left:70px;top:790px;width:940px;height:450px;z-index:70;visibility:hidden;opacity:0}}
.v3 .pill{{position:absolute;left:0;width:940px;height:124px;display:flex;align-items:center;gap:26px;padding:0 34px 0 22px;background:rgba(10,16,28,.74);border:3px solid rgba(255,255,255,.4);border-radius:70px;
  box-shadow:0 10px 30px rgba(0,0,0,.45);color:#fff;font-family:'Oswald';font-weight:600;font-size:58px;letter-spacing:.02em;white-space:nowrap;overflow:hidden;visibility:hidden;opacity:0;transform-origin:50% 50%}}
.v3 .pill:nth-child(1){{top:0}} .v3 .pill:nth-child(2){{top:150px}} .v3 .pill:nth-child(3){{top:300px}}
.v3 .pill .let{{flex:0 0 76px;width:76px;height:76px;line-height:76px;margin:0;text-align:center;border-radius:50%;background:#fff;color:#0B1620;font-family:'Anton';font-weight:400;font-size:46px;top:0}}
.v3 .pill .pflag{{flex:0 0 88px;width:88px;height:88px;border-radius:50%;background-size:cover;background-position:center;border:3px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.5)}}
.v3 .pill .pemo{{flex:0 0 84px;width:84px;height:84px;filter:drop-shadow(0 4px 8px rgba(0,0,0,.5))}}
.v3 .pill .otext{{line-height:1}}
.v3 .ring3{{position:absolute;left:440px;top:1275px;width:200px;height:200px;z-index:70;visibility:hidden;opacity:0}}
.v3 .ring3 svg{{position:absolute;left:0;top:0;transform:rotate(-90deg)}}
.v3 .ring3 circle{{fill:none;stroke-width:14}} .v3 .ring3 .bg{{stroke:rgba(255,255,255,.22)}} .v3 .ring3 .fg{{stroke:#FFD400;stroke-linecap:round}}
.v3 .ring3 .dg{{position:absolute;left:0;top:0;width:200px;height:200px;line-height:200px;text-align:center;font-family:'Lilita';font-size:130px;color:#fff;-webkit-text-stroke:2px #141414;paint-order:stroke fill;text-shadow:0 5px 0 rgba(0,0,0,.55),0 10px 22px rgba(0,0,0,.6);visibility:hidden;opacity:0}}
.v3 .tease3{{position:absolute;left:60px;top:1512px;width:900px;text-align:center;font-family:'Oswald';font-weight:600;font-size:40px;letter-spacing:.2em;color:#FFD400;-webkit-text-stroke:1.2px #141414;paint-order:stroke fill;text-shadow:0 3px 0 rgba(0,0,0,.6),0 6px 16px rgba(0,0,0,.85);z-index:70;visibility:hidden;opacity:0}}
.v3 .banner3{{position:absolute;left:40px;top:290px;width:1000px;text-align:center;font-family:'Lilita';font-size:150px;line-height:1;text-transform:uppercase;color:#FFD400;
  -webkit-text-stroke:3px #4a2b00;paint-order:stroke fill;text-shadow:0 10px 0 #7a4b00,0 22px 40px rgba(0,0,0,.7);z-index:74;visibility:hidden;opacity:0;white-space:nowrap}}
.v3 .banner3.m{{font-size:118px}} .v3 .banner3.s{{font-size:92px}}
.v3 .bannersub{{position:absolute;left:60px;top:462px;width:960px;text-align:center;font-family:'Oswald';font-weight:600;font-size:52px;letter-spacing:.18em;text-transform:uppercase;color:#fff;-webkit-text-stroke:1.5px #141414;paint-order:stroke fill;text-shadow:0 4px 0 rgba(0,0,0,.6),0 8px 18px rgba(0,0,0,.85);z-index:74;visibility:hidden;opacity:0}}
.v3 .fact3{{position:absolute;left:60px;width:900px;text-align:center;font-family:'Anton';font-size:84px;line-height:1.08;text-transform:uppercase;color:#fff;
  text-shadow:0 5px 0 rgba(0,0,0,.6),0 12px 28px rgba(0,0,0,.7);z-index:72;visibility:hidden;opacity:0;white-space:normal}}
.v3 .fact3.m{{font-size:74px}} .v3 .fact3.s{{font-size:64px}}
.v3 .fact3 b{{color:#FFD400;font-weight:400}}
.v3 .cap{{top:1500px;left:60px;width:900px;font-family:'Anton';font-weight:400;font-size:56px;letter-spacing:.02em;color:#fff;-webkit-text-stroke:1.5px #141414;paint-order:stroke fill;text-shadow:0 4px 0 rgba(0,0,0,.5),0 8px 20px rgba(0,0,0,.6)}}
.v3 .sticker3{{position:absolute;filter:drop-shadow(0 14px 22px rgba(0,0,0,.6));transform:rotate(var(--rot,0deg));visibility:hidden;opacity:0}}
.v3 .char3{{position:absolute;filter:drop-shadow(0 12px 18px rgba(0,0,0,.55));transform:rotate(var(--rot,0deg));visibility:hidden;opacity:0;overflow:visible}}
.v3 .o-dim{{position:absolute;left:0;top:0;width:1080px;height:1920px;background:radial-gradient(ellipse at 50% 45%,rgba(6,14,30,.55) 0%,rgba(6,14,30,.86) 70%);z-index:60;visibility:hidden;opacity:0}}
.v3 .outro3{{position:absolute;left:0;top:0;width:1080px;height:1920px;z-index:72;visibility:hidden;opacity:0}}
.v3 .o-logo{{position:absolute;left:390px;top:480px;width:300px;height:300px;border-radius:50%;background:#fff;box-shadow:0 0 0 10px rgba(255,212,0,.95),0 18px 40px rgba(0,0,0,.6);overflow:hidden;visibility:hidden;opacity:0}}
.v3 .o-logo img{{width:100%;height:100%;display:block}}
.v3 .o-name{{position:absolute;left:40px;top:800px;width:1000px;text-align:center;font-family:'Lilita';font-size:104px;line-height:1;color:#fff;-webkit-text-stroke:3px #141414;paint-order:stroke fill;text-shadow:0 6px 0 rgba(0,0,0,.55),0 14px 30px rgba(0,0,0,.6);visibility:hidden;opacity:0}}
.v3 .o-head{{position:absolute;left:60px;top:936px;width:960px;text-align:center;font-family:'Lilita';font-size:60px;line-height:1;color:#fff;-webkit-text-stroke:2px #141414;paint-order:stroke fill;text-shadow:0 4px 0 rgba(0,0,0,.55),0 10px 24px rgba(0,0,0,.6);visibility:hidden;opacity:0}}
.v3 .o-btn{{position:absolute;top:1030px;width:420px;height:128px;border-radius:64px;display:flex;align-items:center;justify-content:center;gap:18px;font-family:'Lilita';font-size:54px;line-height:1;color:#141414;border:5px solid #fff;box-shadow:0 10px 0 rgba(0,0,0,.35),0 18px 36px rgba(0,0,0,.55);visibility:hidden;opacity:0}}
.v3 .o-like{{left:100px;background:#ffffff}} .v3 .o-sub{{left:560px;background:#FFD400;border-color:#FFD400}}
.v3 .o-btn .o-ico{{width:72px;height:72px;filter:drop-shadow(0 3px 4px rgba(0,0,0,.35))}}
.v3 .o-btn .o-done{{position:absolute;left:0;top:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:48px;color:#fff;visibility:hidden;opacity:0}}
.v3 .o-burst{{position:absolute;left:230px;top:1014px;width:160px;height:160px;border-radius:50%;border:10px solid #FFD400;box-shadow:0 0 30px rgba(255,212,0,.8);visibility:hidden;opacity:0;pointer-events:none}}
.v3 .o-cursor{{position:absolute;left:270px;top:1060px;width:120px;height:120px;filter:drop-shadow(0 8px 10px rgba(0,0,0,.6));visibility:hidden;opacity:0;z-index:5}}
.v3 .o-soc{{position:absolute;top:1190px;width:128px;height:128px;border-radius:50%;border:5px solid #fff;box-shadow:0 10px 24px rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;visibility:hidden;opacity:0}}
.v3 .o-soc img{{width:68px;height:68px;filter:invert(1)}}
.v3 .o-url{{position:absolute;left:190px;top:1362px;width:700px;height:92px;line-height:92px;text-align:center;border-radius:46px;background:#141414;border:4px solid #FFD400;font-family:'Oswald';font-weight:600;font-size:46px;letter-spacing:.08em;color:#FFD400;box-shadow:0 12px 30px rgba(0,0,0,.55);visibility:hidden;opacity:0}}
.v3 .cta3{{position:absolute;left:60px;top:1250px;width:900px;text-align:center;z-index:70;visibility:hidden;opacity:0}}
.v3 .ctease3{{font-family:'Lilita';font-size:66px;line-height:1.1;text-transform:uppercase;color:#FFD400;-webkit-text-stroke:2px #4a2b00;paint-order:stroke fill;text-shadow:0 6px 0 #7a4b00,0 14px 28px rgba(0,0,0,.6)}}
.v3 .cline3{{margin-top:26px;font-family:'Oswald';font-weight:600;font-size:40px;letter-spacing:.12em;color:#fff;-webkit-text-stroke:1.2px #141414;paint-order:stroke fill;text-shadow:0 3px 0 rgba(0,0,0,.6),0 6px 16px rgba(0,0,0,.85)}}
.v3 .credit3{{position:absolute;left:60px;top:1560px;width:900px;text-align:center;font-family:'Oswald';font-size:22px;letter-spacing:.06em;line-height:1.3;color:rgba(255,255,255,.8);text-shadow:0 1px 6px rgba(0,0,0,.9);z-index:70;visibility:hidden;opacity:0;white-space:normal}}
.v3 .progress{{display:none}}
"""
