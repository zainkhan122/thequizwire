#!/usr/bin/env python3
"""Public, stable media URLs for Buffer — a tiny GitHub Pages site in a separate PUBLIC repo (media only, no code).

  python3 reelkit/mediahost.py setup                       # create the public media repo (if missing) + enable Pages
  python3 reelkit/mediahost.py push  <ep> [<ep> …] [--no-wait|--wait 900]   # git-push out/final.mp4 of every episode in ONE commit
                                                           #   → <ep>/out/media_url.txt + prints MEDIA_URL <ep> https://…/media/<sha12>/<stem>.mp4
  python3 reelkit/mediahost.py verify <url>                # public · direct · https · video/mp4 · ftyp
  python3 reelkit/mediahost.py prune [--apply]             # delete files whose posts were all sent ≥ retention days ago
  python3 reelkit/mediahost.py ls                          # list hosted files

Why a second repo: this repo is private, so its Release assets need a token (Buffer cannot fetch them) and GitHub
Pages is unavailable on the Free plan for private repos. A public media-only repo gives direct, permanent HTTPS URLs
that Buffer can fetch at publish time (its documented requirement). Paths are content-addressed (sha256 prefix), so a
re-render never overwrites a URL that is already queued.
Token: MEDIA_TOKEN (fine-grained PAT, Contents: read/write on the media repo — the only secret the dispatch job needs
besides BUFFER_API_KEY) → GH_TOKEN → ~/.cache/secrets/gh_token.
Upload path: plain `git push` from a blob-less sparse clone (the Contents API answers 422 "file is too large" for our
~45–50 MB masters, and the Git hard limit is 100 MB per file). All episodes of one dispatch go in ONE commit, so Pages
deploys once. Small files (setup, media-index.json on prune) still go through the Contents API.
"""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config/publishing.json").read_text())["media"]
API = "https://api.github.com"
UA = "TheQuizWire-reelkit/1"
LEDGER = ROOT / "dispatch/ledger.json"
INDEX_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>TheQuizWire media</title>
<style>body{font:16px/1.5 system-ui;background:#1b1b1b;color:#eee;display:grid;place-items:center;min-height:100vh;margin:0}main{text-align:center}h1{color:#FFD400;margin:0 0 8px}a{color:#fff}</style></head>
<body><main><h1>TheQuizWire</h1><p>Daily map &amp; trivia quizzes — <a href="https://thequizwire.com">thequizwire.com</a></p><p style="color:#888;font-size:13px">Media delivery for scheduled posts.</p></main></body></html>
"""


def token():
    t = os.environ.get("MEDIA_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not t:
        p = Path.home() / ".cache/secrets/gh_token"; t = p.read_text().strip() if p.exists() else None
    return t or sys.exit("mediahost: no token (MEDIA_TOKEN / GH_TOKEN / ~/.cache/secrets/gh_token)")


def req(method, url, data=None, raw=False, ok404=False, tries=4):
    body = None if data is None else (data if raw else json.dumps(data).encode())
    for i in range(tries):
        r = urllib.request.Request(url, data=body, method=method, headers={"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
                                                                             "X-GitHub-Api-Version": "2022-11-28", "User-Agent": UA, **({"Content-Type": "application/json"} if body else {})})
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                t = resp.read(); return json.loads(t) if t else {}
        except urllib.error.HTTPError as e:
            if e.code == 404 and ok404: return None
            if e.code in (409, 422) and method == "PUT" and i + 1 < tries: time.sleep(2); continue      # sha race on the index file
            if e.code in (429, 500, 502, 503, 504) and i + 1 < tries: time.sleep(3 * (i + 1)); continue
            sys.exit(f"mediahost: {method} {url} → HTTP {e.code}: {e.read()[:300]!r}")
    sys.exit("mediahost: retries exhausted")


def slug(): return CFG["repo"]


def contents(path, ok404=True): return req("GET", f"{API}/repos/{slug()}/contents/{path}", ok404=ok404)


def put(path, data: bytes, message, sha=None):
    body = {"message": message, "content": base64.b64encode(data).decode(), "branch": "main"}
    if sha: body["sha"] = sha
    return req("PUT", f"{API}/repos/{slug()}/contents/{path}", body)


def delete(path, sha, message): return req("DELETE", f"{API}/repos/{slug()}/contents/{path}", {"message": message, "sha": sha, "branch": "main"})


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""): h.update(ch)
    return h.hexdigest()


def stem_of(ep):
    sys.path.insert(0, str(ROOT / "reelkit")); import naming
    return naming.stem(ep)


def verify(url, timeout=30):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    r = urllib.request.Request(url, headers={"Range": "bytes=0-1023", "User-Agent": UA})
    try:
        with urllib.request.build_opener(NoRedirect).open(r, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", ""); head = resp.read(1024)
            total = resp.headers.get("Content-Range", "").rsplit("/", 1)[-1] if resp.status == 206 else resp.headers.get("Content-Length", "")
            if ctype.split(";")[0].strip() != "video/mp4": return False, f"content-type {ctype}"
            if len(head) < 12 or head[4:8] != b"ftyp": return False, "not an MP4 (no ftyp)"
            return True, int(total) if str(total).isdigit() else None
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:                                                    # noqa: BLE001 — surfaced to the caller as text
        return False, str(e)


def load_index():
    cur = contents("media-index.json")
    idx = json.loads(base64.b64decode(cur["content"])) if cur else {"version": 1, "files": {}}
    return idx, (cur or {}).get("sha")


def save_index(idx, sha, message):
    data = (json.dumps(idx, indent=1, ensure_ascii=False) + "\n").encode()
    for _ in range(3):
        try:
            return put("media-index.json", data, message, sha)
        except SystemExit:
            idx2, sha = load_index(); idx2["files"].update(idx["files"]); idx = idx2
    sys.exit("mediahost: could not update media-index.json")


# ---------------------------------------------------------------- commands
def cmd_setup(a):
    owner, name = slug().split("/")
    repo = req("GET", f"{API}/repos/{slug()}", ok404=True)
    if not repo:
        req("POST", f"{API}/user/repos", {"name": name, "private": False, "auto_init": True, "has_issues": False, "has_wiki": False, "has_projects": False,
                                          "description": "Media delivery for TheQuizWire scheduled posts (generated; no code)."})
        print(f"created public repo {slug()}"); time.sleep(3)
    elif repo.get("private"):
        sys.exit(f"mediahost: {slug()} is private — the media repo must be public for Buffer to fetch files")
    for path, data in ((".nojekyll", b""), ("index.html", INDEX_HTML.encode()), ("robots.txt", b"User-agent: *\nDisallow: /media/\n")):
        cur = contents(path)
        if not cur: put(path, data, f"mediahost: add {path}"); print(f"   added {path}")
    pages = None
    try:
        pages = req("GET", f"{API}/repos/{slug()}/pages", ok404=True)
        if not pages:
            req("POST", f"{API}/repos/{slug()}/pages", {"source": {"branch": "main", "path": "/"}}); print("   Pages enabled (main, /)")
            pages = req("GET", f"{API}/repos/{slug()}/pages", ok404=True)
    except SystemExit as e:                                                   # token without the Pages permission: say so, do not stop
        print(f"::warning::Pages API not reachable with this token ({str(e)[-120:]}). If {CFG['base_url']} stays 404, enable Pages by hand: "
              f"github.com/{slug()} → Settings → Pages → Deploy from a branch → main / (root)")
    pages = pages or {}
    print(f"mediahost: {slug()} · pages {pages.get('status') or 'unknown'} · {pages.get('html_url') or CFG['base_url']}")


def git(repo, *args, env=None, check=True, quiet=True):
    r = subprocess.run(["git", "-C", str(repo), *args], env=env, text=True, capture_output=True)
    if check and r.returncode:
        sys.exit(f"mediahost: git {' '.join(args[:2])} failed:\n{(r.stderr or r.stdout)[-800:]}")
    if not quiet and r.stdout.strip(): print(r.stdout.strip())
    return r


def git_workspace():
    """Blob-less sparse clone of the media repo (root files only) with token auth via GIT_ASKPASS — never in a URL or log."""
    work = Path(tempfile.mkdtemp(prefix="mediahost-", dir=os.environ.get("RUNNER_TEMP")))
    ask = work / "askpass.sh"
    ask.write_text('#!/bin/sh\ncase "$1" in *sername*) echo x-access-token;; *) printf %s "$MEDIAHOST_PUSH_TOKEN";; esac\n'); ask.chmod(0o700)
    env = {**os.environ, "GIT_ASKPASS": str(ask), "MEDIAHOST_PUSH_TOKEN": token(), "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    repo = work / "repo"
    r = subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none", "--sparse", "--branch", "main",
                        f"https://github.com/{slug()}.git", str(repo)], env=env, text=True, capture_output=True)
    if r.returncode: sys.exit(f"mediahost: clone of {slug()} failed (empty repo? run `mediahost.py setup` first):\n{r.stderr[-600:]}")
    git(repo, "config", "user.name", "quizwire-dispatch", env=env); git(repo, "config", "user.email", "dispatch@users.noreply.github.com", env=env)
    return repo, env


def cmd_push(a):
    eps = [Path(e) for e in a.episode]
    if a.file and len(eps) != 1: sys.exit("mediahost: --file needs exactly one episode")
    plan = []                                                                 # (ep, src, rel, url, digest)
    for ep in eps:
        f = Path(a.file) if a.file else ep / "out/final.mp4"
        if not f.exists(): sys.exit(f"mediahost: {f} missing (render first / fetch the release)")
        if f.stat().st_size > 95_000_000: sys.exit(f"mediahost: {f} > 95 MB — GitHub's hard limit is 100 MB per file")
        digest = sha256(f); stem = stem_of(ep); rel = f"media/{digest[:12]}/{stem}.mp4"
        plan.append((ep, f, rel, f"{CFG['base_url'].rstrip('/')}/{rel}", digest))
    repo, env = git_workspace()
    ipath = repo / "media-index.json"
    idx = json.loads(ipath.read_text()) if ipath.exists() else {"version": 1, "files": {}}
    total = sum(v.get("size", 0) for v in idx["files"].values()); new = []
    for ep, f, rel, url, digest in plan:
        if rel in idx["files"] and git(repo, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0:
            print(f"already hosted: {rel}")
        else:
            if total + f.stat().st_size > int(CFG.get("max_site_bytes", 900_000_000)): sys.exit("mediahost: site budget exceeded — run `mediahost.py prune --apply` first")
            total += f.stat().st_size; new.append((ep, f, rel))
        idx["files"][rel] = {"episode": ep.name, "stem": stem_of(ep), "size": f.stat().st_size, "sha256": digest, "url": url,
                             "pushed_at": idx["files"].get(rel, {}).get("pushed_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if new:
        git(repo, "sparse-checkout", "add", *sorted({str(Path(rel).parent) for _, _, rel in new}), env=env)
        for ep, f, rel in new:
            dst = repo / rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, dst); git(repo, "add", rel, env=env)
            print(f"   staged {rel} ({f.stat().st_size / 1e6:.1f} MB)")
    ipath.write_text(json.dumps(idx, indent=1, ensure_ascii=False) + "\n"); git(repo, "add", "media-index.json", env=env)
    if git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0:
        print("nothing new to push")
    else:
        git(repo, "commit", "-q", "-m", "media: " + ", ".join(ep.name for ep, *_ in plan)[:180], env=env)
        for i in range(4):
            r = git(repo, "push", "-q", "origin", "HEAD:main", env=env, check=False)
            if r.returncode == 0: break
            print(f"   push rejected (attempt {i + 1}): {r.stderr.strip()[-200:]}"); time.sleep(5)
            git(repo, "pull", "--rebase", "-q", "origin", "main", env=env)
        else: sys.exit("mediahost: push failed after 4 attempts")
        print(f"pushed {len(new)} file(s) in one commit → {slug()}")
    shutil.rmtree(repo.parent, ignore_errors=True)
    for ep, f, rel, url, _ in plan:
        (ep / "out").mkdir(parents=True, exist_ok=True); (ep / "out/media_url.txt").write_text(url + "\n")
    if not a.no_wait:
        deadline = time.time() + int(a.wait)
        for ep, f, rel, url, _ in plan:
            while True:
                ok, info = verify(url)
                if ok and (info is None or info == f.stat().st_size): print(f"live: {url}"); break
                if time.time() > deadline: sys.exit(f"mediahost: {url} not live after {a.wait}s ({info}) — Pages enabled? deploy pending? rerun later")
                print(f"   waiting for Pages deploy… ({info})"); time.sleep(20)
    for ep, f, rel, url, _ in plan: print(f"MEDIA_URL {ep} {url}")


def cmd_verify(a):
    deadline = time.time() + int(a.wait)
    while True:
        ok, info = verify(a.url)
        if ok or time.time() > deadline: break
        print(f"   waiting for Pages deploy… ({info})"); time.sleep(20)
    print(f"{'OK' if ok else 'FAIL'} {a.url} {info}"); sys.exit(0 if ok else 1)


def cmd_ls(a):
    idx, _ = load_index()
    for rel, v in sorted(idx["files"].items(), key=lambda kv: kv[1].get("pushed_at", "")):
        print(f"   {v.get('pushed_at', '')[:10]}  {v['size'] / 1e6:5.1f} MB  {rel}  ({v['episode']})")
    print(f"mediahost: {len(idx['files'])} file(s) · {sum(v['size'] for v in idx['files'].values()) / 1e6:.0f} MB")


def cmd_prune(a):
    idx, isha = load_index(); L = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"posts": []}
    keep_days = int(CFG.get("retention_days_after_sent", 14)); cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    by_url = {}
    for p in L["posts"]: by_url.setdefault(p.get("media_url"), []).append(p)
    victims = []
    for rel, v in idx["files"].items():
        posts = by_url.get(v["url"], [])
        if not posts:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(v["pushed_at"])
            if age > timedelta(days=45): victims.append((rel, "never dispatched, > 45 days old"))
            continue
        if all(p.get("state") == "sent" and p.get("sent_at") and datetime.fromisoformat(p["sent_at"].replace("Z", "+00:00")) < cutoff for p in posts):
            victims.append((rel, f"all {len(posts)} post(s) sent ≥ {keep_days} days ago"))
    for rel, why in victims:
        print(f"   {'DELETE' if a.apply else 'would delete'} {rel} — {why}")
        if a.apply:
            cur = contents(rel)
            if cur: delete(rel, cur["sha"], f"prune: {rel}")
            idx["files"].pop(rel, None)
    if a.apply and victims: save_index(idx, isha, "media-index: prune")
    print(f"mediahost: prune {'applied' if a.apply else 'dry-run'} · {len(victims)} file(s)")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("setup"); sp.add_parser("ls")
    p = sp.add_parser("push"); p.add_argument("episode", nargs="+"); p.add_argument("--file"); p.add_argument("--wait", default="900"); p.add_argument("--no-wait", action="store_true", help="upload + index only; verify later with `verify`")
    p = sp.add_parser("verify"); p.add_argument("url"); p.add_argument("--wait", default="0")
    p = sp.add_parser("prune"); p.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    {"setup": cmd_setup, "push": cmd_push, "verify": cmd_verify, "ls": cmd_ls, "prune": cmd_prune}[a.cmd](a)


if __name__ == "__main__":
    main()
