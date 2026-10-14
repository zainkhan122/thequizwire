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


class Quiz:
    def __init__(self, J, series, number=None, accent=None):
        """series = series.json entry (needs name, slug, color); number = episode number for the bug."""
        self.J, self.series, self.number = J, series, number
        self.accent = accent or series.get("color", SAND)
        self.cards = {}

    # ---------------------------------------------------------------- chrome
    def bug(self):
        n = f' <b>#{self.number}</b>' if self.number else ""
        return (f'<div id="bug" class="bug tu" data-tq-dwell="off" style="--acc:{self.accent}">'
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
"""
