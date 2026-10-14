#!/usr/bin/env python3
"""Content-addressed cache for generated/trimmed motion clips (OpenMontage lesson B6).

Why: a free ZeroGPU quota is ~3 Wan runs/day. A clip that was generated once must never be paid for again —
not after a sandbox wipe, not in CI, not in another episode that reuses the same plate+prompt.

Key   = sha256 of canonical JSON of the *exact call* (engine, space, every model parameter incl. negative prompt,
        seed, prompt text, sha256 of the input image) — or, for footage, (url, in, out, encode recipe).
        The same dict is what gets sent to the generator (clips.call_spec), so key and call cannot drift.
        The Space git sha is stored as metadata only (a Space rebuild must not silently orphan the cache).
Tiers = local blob ~/.cache/clipcache/<key>.mp4  →  GitHub release `cache-clips` asset <key>.mp4  →  generate.
Index = reelkit/cache/clips.jsonl (in git, append-only, one JSON object per key; flock + dedup on write).

  python3 reelkit/clipcache.py ls                       list manifest (key, engine, seed, size, where)
  python3 reelkit/clipcache.py verify [--remote]        sha-check local blobs (+ HEAD every release asset)
  python3 reelkit/clipcache.py sync                     upload local blobs that the release does not have yet
  python3 reelkit/clipcache.py key <ep> <clip_id>       print the key a clip would use now
"""
import argparse, fcntl, hashlib, json, os, shutil, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reelkit" / "cache" / "clips.jsonl"
LOCAL = Path(os.environ.get("CLIPCACHE_DIR", Path.home() / ".cache" / "clipcache"))
TAG = "cache-clips"
SCHEMA = 1


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def make_key(spec):
    """spec: JSON-able dict of the exact call. Floats are normalised so 5 == 5.0."""
    def norm(x):
        if isinstance(x, bool) or x is None or isinstance(x, str): return x
        if isinstance(x, (int, float)): return round(float(x), 6)
        if isinstance(x, dict): return {k: norm(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [norm(v) for v in x]
        raise TypeError(f"unhashable spec value {x!r}")
    blob = json.dumps({"schema": SCHEMA, **norm(spec)}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------- manifest ----------------
def load():
    out = {}
    if MANIFEST.exists():
        for i, line in enumerate(MANIFEST.read_text().splitlines(), 1):
            if not line.strip(): continue
            try: e = json.loads(line)
            except json.JSONDecodeError: sys.exit(f"clipcache: {MANIFEST}:{i} is not valid JSON — fix by hand (append-only file)")
            out[e["key"]] = e          # later line wins (re-registration after a re-upload)
    return out


def _append(entry):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(str(MANIFEST) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        cur = load().get(entry["key"])
        if cur and all(cur.get(k) == entry.get(k) for k in ("sha256", "remote")): return   # dedup
        with open(MANIFEST, "a") as f:
            f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())


# ---------------- storage tiers ----------------
def _blob(key): return LOCAL / f"{key}.mp4"


def _atomic_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dst.parent, suffix=".part"); os.close(fd)
    shutil.copyfile(src, tmp); os.replace(tmp, dst)


def _slug():
    sys.path.insert(0, str(ROOT / "reelkit")); import media
    return media, media.repo_slug()


def _download(key, dst):
    media, slug = _slug()
    url = f"https://github.com/{slug}/releases/download/{TAG}/{key}.mp4"
    fd, tmp = tempfile.mkstemp(dir=LOCAL, suffix=".part"); os.close(fd)
    try:
        rq = urllib.request.Request(url, headers={"User-Agent": "reelkit-clipcache"})
        with urllib.request.urlopen(rq, timeout=300) as r, open(tmp, "wb") as o: shutil.copyfileobj(r, o)
        os.replace(tmp, dst); return True
    except Exception as e:
        print(f"  · cache: release fetch failed ({str(e)[:80]})"); Path(tmp).unlink(missing_ok=True); return False


def _upload(key, path):
    try:
        media, slug = _slug()
        if not media.token(required=False): print("  · cache: no GitHub token — blob kept locally; run `clipcache.py sync` later"); return False
        rel = media.get_release(slug, TAG, title="Clip cache", notes="Content-addressed motion clips (reelkit/clipcache.py). Do not edit by hand.")
        media.upload(slug, rel, path, f"{key}.mp4", media.assets_of(slug, rel)); return True
    except SystemExit as e:
        print(f"  · cache: upload failed ({e}) — blob kept locally"); return False


def get(key, dst):
    """Materialise the clip for `key` at dst. Returns 'local' | 'remote' | None."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    ent = load().get(key); b = _blob(key)
    if b.exists() and (not ent or sha256_file(b) == ent["sha256"]):
        _atomic_copy(b, Path(dst)); return "local"
    if b.exists(): print(f"  ! cache: local blob {key[:12]} is corrupt — discarded"); b.unlink()
    if ent and ent.get("remote") and _download(key, b):
        if sha256_file(b) == ent["sha256"]: _atomic_copy(b, Path(dst)); return "remote"
        print(f"  ! cache: release blob {key[:12]} sha mismatch — ignored"); b.unlink()
    return None


def put(key, src, spec, meta):
    """Register a freshly produced clip: local blob → release → manifest line."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    b = _blob(key); _atomic_copy(Path(src), b)
    remote = _upload(key, b)
    e = {"key": key, "sha256": sha256_file(b), "size": b.stat().st_size, "remote": remote,
         "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "spec": spec, **meta}
    _append(e); return e


# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("ls"); v = sp.add_parser("verify"); v.add_argument("--remote", action="store_true")
    sp.add_parser("sync"); k = sp.add_parser("key"); k.add_argument("ep"); k.add_argument("clip")
    a = ap.parse_args(); man = load()
    if a.cmd == "ls":
        for key, e in man.items():
            where = ("L" if _blob(key).exists() else "-") + ("R" if e.get("remote") else "-")
            s = e["spec"]; print(f"{key[:16]}  {where}  {s.get('engine'):4} seed={s.get('seed', '-')!s:4} {e['size'] / 1e6:5.2f} MB  {e.get('label', '')}")
        print(f"{len(man)} entries · L=local blob R=release asset"); return
    if a.cmd == "key":
        sys.path.insert(0, str(ROOT / "reelkit")); import clips
        ep = Path(a.ep).resolve(); c = {x["id"]: x for x in json.load(open(ep / "clips.json"))["clips"]}[a.clip]
        print(make_key(clips.call_spec(c, ep))); return
    if a.cmd == "verify":
        bad = 0
        for key, e in man.items():
            b = _blob(key)
            if b.exists() and sha256_file(b) != e["sha256"]: print(f"FAIL local {key[:16]} sha mismatch"); bad += 1
            if a.remote and e.get("remote"):
                media, slug = _slug()
                try:
                    rq = urllib.request.Request(f"https://github.com/{slug}/releases/download/{TAG}/{key}.mp4", method="HEAD")
                    with urllib.request.urlopen(rq, timeout=60) as r: n = int(r.headers.get("Content-Length", -1))
                    if n != e["size"]: print(f"FAIL remote {key[:16]} size {n} != {e['size']}"); bad += 1
                except Exception as x: print(f"FAIL remote {key[:16]} {str(x)[:80]}"); bad += 1
        print(f"verify: {len(man)} entries, {bad} problem(s)"); sys.exit(1 if bad else 0)
    if a.cmd == "sync":
        n = 0
        for key, e in man.items():
            if e.get("remote") or not _blob(key).exists(): continue
            if _upload(key, _blob(key)): _append({**e, "remote": True}); n += 1
        print(f"sync: uploaded {n}")


if __name__ == "__main__":
    main()
