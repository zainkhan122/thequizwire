#!/usr/bin/env python3
"""Fail if git would hold bloat. Media belongs in Release assets (reelkit/media.py), not in git.
Rules: no tracked media extensions outside the allow-list · no tracked file > 1 MB · total tracked < 15 MB."""
import subprocess, sys
from pathlib import Path
MEDIA = {".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".onnx", ".pt", ".safetensors", ".zip", ".tar", ".gz"}
ALLOW = {"docs/img/", "brand/"}               # tiny doc images · channel brand kit (logo ≤ 80 KB)
MAX_FILE, MAX_TOTAL = 1_000_000, 15_000_000
files = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True).stdout.split("\0")
bad, total = [], 0
for f in filter(None, files):
    p = Path(f)
    if not p.exists(): continue
    sz = p.stat().st_size; total += sz
    if p.suffix.lower() in MEDIA and not any(f.startswith(a) for a in ALLOW): bad.append(f"media in git: {f}")
    if sz > MAX_FILE: bad.append(f"file > 1 MB: {f} ({sz/1e6:.1f} MB)")
if total > MAX_TOTAL: bad.append(f"tracked total {total/1e6:.1f} MB > 15 MB")
print(f"tracked: {len([f for f in files if f])} files, {total/1e6:.2f} MB")
if bad: print("\n".join(bad)); sys.exit(1)
print("repo guard ✓")
