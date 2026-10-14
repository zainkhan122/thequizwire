#!/usr/bin/env python3
"""Drive cloud renders from any session (stdlib only).
  python3 reelkit/cloud.py render <episode_dir> [more...] [--tag T] [--wait] [--download DIR]
  python3 reelkit/cloud.py status            last 5 render runs
  python3 reelkit/cloud.py fetch <tag> [DIR] download a release (<Story-Title>.mp4/.jpg, POST_KIT.md, gate reports)
  python3 reelkit/cloud.py why [RUN_ID]      gate failures of a run (default: the latest render run)
Pushes must be done first (tools/sync.sh). The run is pinned to the local HEAD sha (workflow input `sha`), so a later
push can never change what gets rendered. On failure, --wait prints the gate failures from the job log."""
import argparse, datetime, json, os, re, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import req, repo_slug, API, assets_of, get_release

def runs(slug, n=5):
    r = req("GET", f"{API}/repos/{slug}/actions/workflows/render.yml/runs?per_page={n}") or {"workflow_runs": []}
    return r["workflow_runs"]

def git(*args):
    import subprocess
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1]).stdout.strip()


def token_expiry_warning(slug):
    """Fine-grained PATs expire; GitHub reports the date in a response header. Warn 7 days ahead."""
    tk = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tk: return
    try:
        r = urllib.request.Request(f"{API}/repos/{slug}", headers={"Authorization": f"Bearer {tk}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(r, timeout=20) as resp: exp = resp.headers.get("github-authentication-token-expiration")
        if not exp: return
        when = datetime.datetime.strptime(exp[:19], "%Y-%m-%d %H:%M:%S"); days = (when - datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)).days
        if days <= 7: print(f"! GitHub token expires {exp} ({days} d): ask the owner for a new one (AGENTS.md → secrets)")
    except Exception: pass


def why(slug, run_id=None, n=40):
    """Print the gate failures of a render run (job logs, filtered)."""
    run_id = run_id or runs(slug, 1)[0]["id"]
    jobs = req("GET", f"{API}/repos/{slug}/actions/runs/{run_id}/jobs")["jobs"]
    for j in jobs:
        if j.get("conclusion") not in ("failure", "cancelled", "timed_out"): continue
        step = next((st["name"] for st in j.get("steps", []) if st.get("conclusion") == "failure"), "?")
        print(f"✗ {j['name']}  (failed step: {step[:60]})")
        log = req("GET", f"{API}/repos/{slug}/actions/jobs/{j['id']}/logs", raw=True) or b""
        lines = [re.sub(r"^\S+Z ", "", ln) for ln in log.decode("utf-8", "replace").splitlines()]
        hits = [ln for ln in lines if re.search(r"FAIL|##\[error\]|Traceback|Error:|error:", ln) and not re.search(r"FAIL 0\b", ln)]
        for ln in (hits or lines)[-n:]: print("   " + ln[:240])


def wait_remote_head(slug, head, timeout=90):
    """The runner checks out `main` at dispatch time: refuse to render anything but the local HEAD."""
    t0 = time.time()
    while True:
        ref = req("GET", f"{API}/repos/{slug}/git/ref/heads/main") or {}
        if ref.get("object", {}).get("sha") == head: return
        if time.time() - t0 > timeout:
            sys.exit(f"origin/main is {ref.get('object', {}).get('sha', '?')[:7]}, local HEAD is {head[:7]} — push first (tools/sync.sh)")
        time.sleep(5)


def render(a):
    slug = repo_slug(); head = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"): print("! uncommitted changes are NOT rendered (runner uses origin/main)")
    wait_remote_head(slug, head); token_expiry_warning(slug)
    before = {r["id"] for r in runs(slug, 10)}
    eps = " ".join(a.episodes)
    req("POST", f"{API}/repos/{slug}/actions/workflows/render.yml/dispatches",
        {"ref": "main", "inputs": {"episodes": eps, "tag": a.tag or "", "crf": str(a.crf), "sha": head}})
    run = None
    for _ in range(30):
        time.sleep(4)
        new = [r for r in runs(slug, 10) if r["id"] not in before]
        if new: run = new[0]; break
    if not run: sys.exit("dispatched, but no run appeared yet — check Actions tab")
    print(f"run #{run['run_number']}  {run['html_url']}  rendering {head[:7]} (pinned)")
    if not a.wait: return
    t0 = time.time()
    while run["status"] != "completed":
        time.sleep(30)
        run = req("GET", f"{API}/repos/{slug}/actions/runs/{run['id']}")
        jobs = req("GET", f"{API}/repos/{slug}/actions/runs/{run['id']}/jobs")["jobs"]
        steps = [f"{j['name']}: " + next((s['name'] for s in j.get('steps', []) if s['status'] == 'in_progress'), j['status']) for j in jobs]
        print(f"  {int(time.time()-t0)//60:>3}m  {run['status']:<11} " + " | ".join(steps)[:200], flush=True)
    print(f"conclusion: {run['conclusion']}  ({int(time.time()-t0)//60} min)")
    if run["conclusion"] != "success": why(slug, run["id"])
    if run["conclusion"] == "success" and a.download:
        for ep in a.episodes:
            tag = a.tag or f"{Path(ep).name}-r{run['run_number']}"
            fetch_tag(slug, tag, Path(a.download) / Path(ep).name)
    sys.exit(0 if run["conclusion"] == "success" else 1)

def fetch_tag(slug, tag, out):
    rel = get_release(slug, tag, create=False)
    if not rel: sys.exit(f"no release {tag}")
    out.mkdir(parents=True, exist_ok=True)
    for name, asset in assets_of(slug, rel).items():
        data = req("GET", asset["url"], headers={"Accept": "application/octet-stream"}, raw=True)
        (out / name).write_bytes(data); print(f"  ↓ {out / name} ({len(data)/1e6:.1f} MB)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("render"); p.add_argument("episodes", nargs="+"); p.add_argument("--tag"); p.add_argument("--crf", default=18)
    p.add_argument("--wait", action="store_true"); p.add_argument("--download")
    sp.add_parser("status"); w = sp.add_parser("why"); w.add_argument("run_id", nargs="?")
    p = sp.add_parser("fetch"); p.add_argument("tag"); p.add_argument("dir", nargs="?", default=".")
    a = ap.parse_args()
    if a.cmd == "render": render(a)
    elif a.cmd == "why": why(repo_slug(), a.run_id)
    elif a.cmd == "status":
        for r in runs(repo_slug()): print(f"#{r['run_number']} {r['status']:<10} {r['conclusion'] or '':<9} {r['created_at']} {r['display_title']} {r['html_url']}")
    else: fetch_tag(repo_slug(), a.tag, Path(a.dir))
