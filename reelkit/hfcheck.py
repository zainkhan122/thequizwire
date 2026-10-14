#!/usr/bin/env python3
"""Composition gate: wraps `hyperframes check` (lint + runtime + layout + motion in one browser session).

    python3 reelkit/hfcheck.py <hf_dir> [--report check.json] [--samples 12]

FAIL (exit 1) on:
  · lint errors        — broken composition contract (bad data-* timing, nested timed media, …)
  · runtime errors     — console errors or exceptions while seeking
  · layout errors      — text blocks colliding, or content clipped off canvas, at sampled times + transition seams
  · caption-zone       — any non-caption text inside the caption band (that's how the ep01 memorial credit hid a caption)
Lint and layout WARNINGS are reported but don't fail (structure hints like "split into sub-compositions").

Intentional overlaps (stamps on documents, a quote mark behind a quote, crossfading counter digits) must be DECLARED
in the markup with HyperFrames' own attribute data-layout-allow-overlap="true". That way every overlap is a reviewed
decision, not a silenced checker. Contrast is skipped here (--no-contrast): reelkit/textqa.py is the stricter
readability gate (glyph-level WCAG p10 over moving video).
"""
import argparse, json, os, shutil, subprocess, sys
from collections import Counter
from pathlib import Path

# Caption band of the series layout (y 1340-1540 of 1920): no other text may sit there while captions run.
# Captions themselves (and deliberate band copy like the end-card CTA) carry data-layout-allow-caption-zone.
CAPTION_ZONE = os.environ.get("CAPTION_ZONE", "x0=0;y0=0.698;x1=1;y1=0.802;severity=error;seek=.25,.5,.75")
ap = argparse.ArgumentParser(); ap.add_argument("hf"); ap.add_argument("--report"); ap.add_argument("--samples", type=int, default=12)
a = ap.parse_args()
hf = Path(a.hf).resolve()
exe = shutil.which("hyperframes") or sys.exit("hfcheck: hyperframes CLI not on PATH (run reelkit/setup.sh)")
env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1"}
r = subprocess.run([exe, "check", "--json", "--no-contrast", "--at-transitions", "--max-transition-samples", "60",
                    "--samples", str(a.samples), "--caption-zone", CAPTION_ZONE, "--max-issues", "400", "--timeout", "15000"],
                   cwd=hf, capture_output=True, text=True, env=env)
try:
    d = json.loads(r.stdout[r.stdout.index("{"):])
except ValueError:
    print(r.stdout[-1500:], r.stderr[-1500:]); sys.exit("hfcheck: could not parse `hyperframes check --json` output")

errors, warnings = [], []
for sec in ("lint", "runtime", "layout", "motion"):
    for f in (d.get(sec) or {}).get("findings", []) or []:
        item = {"section": sec, "code": f.get("code"), "t": round(f.get("time") or 0, 2), "selector": f.get("selector"),
                "text": (f.get("text") or "")[:60], "message": (f.get("message") or "")[:140], "fix": (f.get("fixHint") or "")[:160]}
        if f.get("severity") == "error": errors.append(item)
        elif f.get("severity") == "warning": warnings.append(item)

def dedup(items):                                  # one line per (code, selector, text): the first time it happens
    out = {}
    for i in items: out.setdefault((i["section"], i["code"], i["selector"], i["text"]), i)
    return list(out.values())
errors, warnings = dedup(errors), dedup(warnings)

for e in errors:
    print(f"  FAIL  {e['section']}/{e['code']}  t={e['t']}s  {e['selector']}  {e['text']!r}  — {e['fix'] or e['message']}")
wc = Counter(f"{w['section']}/{w['code']}" for w in warnings)
if wc: print("  warnings: " + ", ".join(f"{k}×{v}" for k, v in wc.most_common()))
print(f"hyperframes check: {len(errors)} error(s), {len(warnings)} warning(s)")
if a.report:
    Path(a.report).write_text(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings,
                                          "hyperframes_ok": d.get("ok")}, indent=1, ensure_ascii=False) + "\n")
sys.exit(1 if errors else 0)
