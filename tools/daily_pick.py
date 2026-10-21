#!/usr/bin/env python3
"""tools/daily_pick.py — choose today's 1–3 episodes from the authored backlog (GitHub Actions `daily` workflow).

  python3 tools/daily_pick.py [--date YYYY-MM-DD] [--min 1] [--max 3] [--dry]

Backlog = every `series/*/ep*/episode.json` with `"status": "ready"` (set by the author once the local gates pass and the
episode has been reviewed) that has no scheduled/sent post in dispatch/ledger.json and is not already in dispatch/daily.json.
Count = a date-seeded random int in [min, max] (so reruns on the same day pick the same set; the cadence looks human:
some days one, some days three). Order = series rotation (the series published least recently goes first), then episode
number. Prints the chosen episode dirs space-separated on stdout; records the plan in dispatch/daily.json unless --dry.
"""
import argparse, json, random, sys
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def v4_ok(ep):
    """Hard v4 gate before an episode can be picked: quizlint (incl. Q11 authoring rules) + postkit check must pass."""
    import subprocess
    for cmd in (["python3", str(ROOT / "reelkit/quizlint.py"), str(ep)], ["python3", str(ROOT / "reelkit/postkit.py"), "check", str(ep)]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"daily_pick: SKIP {ep.name} — {cmd[1].split('/')[-1]} failed:\n" + "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "FAIL" in l)[:1500], file=sys.stderr)
            return False
    return True


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date"); ap.add_argument("--min", type=int, default=1); ap.add_argument("--max", type=int, default=3); ap.add_argument("--dry", action="store_true"); ap.add_argument("--if-unplanned", action="store_true", help="print nothing if today is already planned (safe cron retry)")
    a = ap.parse_args(); day = a.date or date.today().isoformat()
    ledger = json.loads((ROOT / "dispatch/ledger.json").read_text()).get("posts", [])
    done = {p["episode"] for p in ledger if p.get("state") in ("scheduled", "sending", "sent")}
    dp = ROOT / "dispatch/daily.json"; plan = json.loads(dp.read_text()) if dp.exists() else {"version": 1, "days": {}}
    planned = {e for eps in plan["days"].values() for e in eps}
    if day in plan["days"]:                                                                  # idempotent per day
        if a.if_unplanned: print("daily_pick: already planned today — retry is a no-op", file=sys.stderr); return
        print(" ".join(plan["days"][day])); return
    ready = []
    for ej in sorted(ROOT.glob("series/*/ep*/episode.json")):
        if "_template" in str(ej): continue
        E = json.loads(ej.read_text()); name = ej.parent.name
        if E.get("status") != "ready" or name in done or name in planned: continue
        if not v4_ok(ej.parent): continue                                                   # v4 gates are mandatory for anything that ships
        ready.append((E["series"], int(E.get("number", 0)), str(ej.parent.relative_to(ROOT)), ship_by(ej.parent)))
    if not ready: print("", end=""); print("daily_pick: backlog empty — author more episodes (status: ready)", file=sys.stderr); return
    # series rotation: last-published order from the ledger (+ planned days), least recent first
    last = {}
    for p in ledger:
        if p.get("state") in ("scheduled", "sent") and p.get("due_at"):
            s = ep_series(p["episode"]); last[s] = max(last.get(s, ""), p["due_at"])
    # ORDER = editorial, not random (docs/TOPIC_GUIDELINES.md): soonest "Ship by" first (the signal is cooling), then the series that
    # has waited longest, then episode number. Only the COUNT per day is random (cadence).
    ready.sort(key=lambda r: (r[3], last.get(r[0], ""), r[1]))
    n = random.Random(day).randint(a.min, a.max)
    urgent = [r for r in ready if r[3] <= day]                 # anything past its ship-by goes today regardless of rotation
    pick = [r[2] for r in urgent[:n]]; seen = {r[0] for r in urgent[:n]}
    for s, _, d, _ in ready:                                   # then one per series, then fill
        if len(pick) == n: break
        if s not in seen and d not in pick: pick.append(d); seen.add(s)
    for s, _, d, _ in ready:
        if len(pick) == n: break
        if d not in pick: pick.append(d)
    for d in pick: print(f"daily_pick: {d} — ship_by {dict((r[2], r[3]) for r in ready)[d]}", file=sys.stderr)
    if not a.dry:
        plan["days"][day] = pick; dp.write_text(json.dumps(plan, indent=1) + "\n")
    print(" ".join(pick))

def ship_by(ep):
    """Ship-by date from topic.md (Q22); episodes without one sort last ('9999')."""
    import re
    tp = ep / "topic.md"
    if not tp.exists(): return "9999-12-31"
    m = re.search(r"##\s+Ship by\s*\n+\s*(\d{4}-\d{2}-\d{2})", tp.read_text())
    return m.group(1) if m else "9999-12-31"

def ep_series(name):
    for ej in ROOT.glob(f"series/*/{name}/episode.json"): return ej.parent.parent.name
    return ""

if __name__ == "__main__":
    main()
