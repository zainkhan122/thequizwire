#!/usr/bin/env python3
"""Decision log: <ep>/decisions.jsonl — append-only record of consequential choices and approved exceptions.

  python3 reelkit/decide.py add <ep> --kind KIND --subject S --chosen C --reason R
                                [--options "a|b|c"] [--approved-by WHO] [--expires YYYY-MM-DD] [--value N]
  python3 reelkit/decide.py list <ep> [--kind KIND]

Kinds used by the gates:
  promise_exception  lets planlint pass a delivery-promise shortfall (needs approved_by + expires; --value = accepted minimum)
  clip_fallback      a declared clip shown as a still/Ken Burns instead (subject = clip id; needs approved_by + expires)
Other kinds are informational: voice, music, wording, edit, source, licence, layout, tool.
Never edit or delete lines: supersede with a new entry for the same kind+subject (the latest wins).
"""
import argparse, datetime, json, sys
from pathlib import Path

GATED = {"promise_exception", "clip_fallback"}


def load(ep):
    p = Path(ep) / "decisions.jsonl"
    if not p.exists():
        return []
    out = []
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{p}:{i}: invalid JSON ({e})")
    return out


def latest(ep, kind, subject):
    hits = [d for d in load(ep) if d.get("kind") == kind and d.get("subject") == subject]
    return hits[-1] if hits else None


def approval(ep, kind, subject, today=None):
    """(ok, reason): is there a live, approved decision for this gated exception?"""
    d = latest(ep, kind, subject)
    if not d:
        return False, "no decision logged"
    if not d.get("approved_by"):
        return False, "decision logged but not approved"
    today = today or datetime.date.today().isoformat()
    if d.get("expires") and d["expires"] < today:
        return False, f"approval expired {d['expires']}"
    return True, f"approved by {d['approved_by']} until {d.get('expires', '—')}: {d.get('reason', '')}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("add"); a.add_argument("ep")
    for k in ("kind", "subject", "chosen", "reason"):
        a.add_argument("--" + k, required=True)
    a.add_argument("--options"); a.add_argument("--approved-by"); a.add_argument("--expires"); a.add_argument("--value", type=float)
    l = sp.add_parser("list"); l.add_argument("ep"); l.add_argument("--kind")
    x = ap.parse_args()
    if x.cmd == "add":
        if x.kind in GATED and not (x.approved_by and x.expires):
            sys.exit(f"{x.kind} needs --approved-by and --expires (exceptions must not become permanent)")
        d = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": x.kind,
             "subject": x.subject, "options": x.options.split("|") if x.options else [], "chosen": x.chosen, "reason": x.reason}
        for k in ("approved_by", "expires", "value"):
            if getattr(x, k) is not None:
                d[k] = getattr(x, k)
        with open(Path(x.ep) / "decisions.jsonl", "a") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        print("logged:", d["kind"], d["subject"], "→", d["chosen"])
    else:
        for d in load(x.ep):
            if not x.kind or d.get("kind") == x.kind:
                print(f"{d['ts'][:10]}  {d['kind']:<17} {d['subject']:<22} → {d['chosen']}" + (f"  [approved: {d['approved_by']}, until {d.get('expires','—')}]" if d.get("approved_by") else ""))


if __name__ == "__main__":
    main()
