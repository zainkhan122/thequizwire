#!/usr/bin/env python3
"""
tests/selftest.py — proves the offline half of the QuizWire toolchain on any machine (sandbox or CI) in ~20 s.

  python3 tests/selftest.py            # everything below
  python3 tests/selftest.py --quick    # skip the audio mix (saves ~12 s)

What it proves
  1. node tests/test_geo_runtime.mjs — d3-geo projections, clipExtent, world-atlas ids, bbox winding
  2. series/_template and tests/fixtures/ep-disputed (Kashmir, disputed-border path) each pass
     plan --estimate → geodata prep → compose → hfstatic → quizlint → geolint → factcheck → provenance
     (copies are built in a temp dir; the fixtures in git stay byte-identical)
  3. negative cases — the gates FAIL when they must:
       geolint  : a zoomed Kashmir scene with no `disputed` entries
       quizlint : a quiz with three options / answer_line naming a distractor
       factcheck: a narrated sentence that is not in the claims ledger; sovereignty wording hitting a guardrail
  4. quizscore produces mix.wav (+ mix_report.json) for the template without ffmpeg (peak-normalised preview)

Geodata: uses ~/.cache/geodata when present, otherwise the committed Kashmir fixture (GEO_FIXTURE) — so it never needs network.
Exit 1 on the first broken expectation; prints one line per check.
"""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RK = ROOT / "reelkit"
EPISODE = RK / "episode.sh"
NE_DISPUTED = Path(os.environ.get("GEODATA_CACHE", Path.home() / ".cache/geodata")).expanduser() / "natural-earth/ne_10m_admin_0_disputed_areas.geojson"
FIXTURE = ROOT / "tests/fixtures/ne_disputed_kashmir.geojson"
OFFLINE = "plan geo build static quizlint geolint facts provenance"
t0 = time.time()


def say(ok, what, extra=""):
    print(f"  {'✓' if ok else '✗'} {what}{('  ' + extra) if extra else ''}")
    if not ok:
        print(f"\nselftest: FAILED after {time.time() - t0:.1f}s"); sys.exit(1)


def run(cmd, env=None, cwd=ROOT):
    e = {**os.environ, "GEOLINT_ONLINE": "0", **(env or {})}
    if not NE_DISPUTED.exists(): e["GEO_FIXTURE"] = str(FIXTURE)
    return subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)


def stages(ep, which=OFFLINE, env=None):
    return run(["bash", str(EPISODE), str(ep), *which.split()], env)


def expect_ok(ep, label, which=OFFLINE):
    r = stages(ep, which)
    say(r.returncode == 0, f"{label}: {which}", "" if r.returncode == 0 else "\n" + (r.stdout + r.stderr)[-1500:])


def expect_fail(ep, label, which, needle):
    r = stages(ep, which)
    out = r.stdout + r.stderr
    say(r.returncode != 0 and needle.lower() in out.lower(), f"{label} must FAIL ({needle})",
        "" if r.returncode != 0 and needle.lower() in out.lower() else "\n" + out[-1500:])


def copy_ep(src, tmp, name=None):
    dst = tmp / (name or src.name)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("out", "__pycache__"))
    return dst


def edit_json(p, fn):
    d = json.loads(Path(p).read_text()); fn(d); Path(p).write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def main():
    quick = "--quick" in sys.argv
    print(f"== selftest  (geodata: {'cache' if NE_DISPUTED.exists() else 'fixture'})")
    r = run(["node", str(ROOT / "tests/test_geo_runtime.mjs")])
    say(r.returncode == 0, "map runtime unit tests", r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])

    tmp = Path(tempfile.mkdtemp(prefix="qw-selftest-"))
    try:
        tpl = copy_ep(ROOT / "series/_template", tmp)
        dis = copy_ep(ROOT / "tests/fixtures/ep-disputed", tmp)
        expect_ok(tpl, "_template")
        expect_ok(dis, "ep-disputed")
        # voice gate token normaliser: script words vs whisper digits must compare equal (decimals, scales, UK/US spelling)
        sys.path.insert(0, str(RK)); import voice as _voice
        tok = lambda s: [t for t, _ in _voice.tokens(s)]
        pairs = [("around three point two million square kilometres", "around 3 .2 million square kilometers."),
                 ("three million people", "3 million people"), ("eight point eight kilometres", "8.8 kilometers"),
                 ("nineteen eighty-three", "in 1983."[3:]), ("two hundred and sixty-nine", "269"),
                 ("the twenty-first century", "the 21st century"), ("twelve hundred metres", "1,200 meters"),
                 ("one point five million", "1.5 million"), ("at eleven eighteen", "at 11:18")]
        badp = [(a, b, tok(a), tok(b)) for a, b in pairs if tok(a) != tok(b)]
        say(not badp, f"voice tokens: {len(pairs) - len(badp)}/{len(pairs)} script/ASR pairs normalise equal", str(badp[:2]))
        for ep in (tpl, dis):
            r = run(["python3", str(RK / "voice.py"), "check", str(ep), "--plan-only"])
            say(r.returncode == 0, f"{ep.name}: voice plan gate (tones, pauses, climax, arc)", "" if r.returncode == 0 else (r.stdout + r.stderr)[-600:])

        # negative 1: zoomed Kashmir scene with no disputed entries → geolint P4
        nod = copy_ep(ROOT / "tests/fixtures/ep-disputed", tmp, "ep-nodisp")
        edit_json(nod / "geo.json", lambda g: g["scenes"]["main"].__setitem__("disputed", []))
        edit_json(nod / "visuals.json", lambda v: v.__setitem__("beats", [b for b in v["beats"] if b.get("do") != "geo.disputed_in"]))
        expect_fail(nod, "geolint", "plan geo build geolint", "P4")

        # negative 2: three options + answer_line naming a distractor → quizlint Q1
        bad = copy_ep(ROOT / "series/_template", tmp, "ep-badquiz")
        def break_quiz(e):
            e["quiz"]["options"] = e["quiz"]["options"][:3]; e["quiz"]["answer_line"] = e["quiz"]["options"][1]
        edit_json(bad / "episode.json", break_quiz)
        expect_fail(bad, "quizlint", "plan quizlint", "Q1")

        # negative 3: an unsourced sentence in the narration → factcheck coverage; sovereignty wording → guardrail
        unf = copy_ep(ROOT / "tests/fixtures/ep-disputed", tmp, "ep-unsourced")
        def break_vo(v):
            for l in v["lines"]:
                if l["id"] == "v05": l["text"] += " The whole region belongs to Pakistan, and K2 is the tallest mountain in Asia."
        edit_json(unf / "voice.json", break_vo)
        expect_fail(unf, "factcheck", "plan geo build facts", "[coverage] VO")
        r = stages(unf, "facts"); say("guardrail" in (r.stdout + r.stderr).lower(), "factcheck guardrail fires on 'belongs to'")

        if not quick:
            r = run(["python3", str(RK / "quizscore.py"), str(tpl)])
            rep = Path.home() / ".cache/build/_template/mix_report.json"
            ok = r.returncode == 0 and rep.exists() and (Path.home() / ".cache/build/_template/mix.wav").exists()
            say(ok, "quizscore → mix.wav + mix_report.json", "" if ok else (r.stdout + r.stderr)[-800:])
            if ok:
                j = json.loads(rep.read_text()); say(j.get("mastered") in (True, False), f"mix_report mastered={j.get('mastered')} peak={j.get('peak_dbfs', '?')} dBFS missing_vo={len(j.get('missing_vo', []))}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"selftest: OK in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
