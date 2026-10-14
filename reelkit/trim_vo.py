#!/usr/bin/env python3
"""Trim TTS clips to speech: decode -> 48 kHz mono float -> cut at |x| > threshold with head/tail pads.
usage: python3 reelkit/trim_vo.py <vo_dir_with_mp3s> <out_dir> [--thr 0.01 --head 0.04 --tail 0.12]
Matches the timings stored in words.json (dur per clip) so timelines stay frame-exact."""
import argparse, shutil, subprocess, json
from pathlib import Path
import numpy as np, soundfile as sf

SR = 48000
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--thr", type=float, default=0.01); ap.add_argument("--head", type=float, default=0.04)
ap.add_argument("--tail", type=float, default=0.12); ap.add_argument("--check", help="words.json to verify durations")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
ff = shutil.which("ffmpeg") or "ffmpeg"
durs = {}
for p in sorted(Path(a.src).glob("*.mp3")) + sorted(Path(a.src).glob("*.wav")):
    pcm = subprocess.run([ff, "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.float32)
    idx = np.flatnonzero(np.abs(x) > a.thr)
    s = max(0, idx[0] - int(a.head * SR)) if len(idx) else 0
    e = min(len(x), idx[-1] + int(a.tail * SR)) if len(idx) else len(x)
    y = x[s:e]
    sf.write(out / f"{p.stem}.wav", y, SR, subtype="FLOAT")
    durs[p.stem] = round(len(y) / SR, 3)
    print(f"{p.stem}: {durs[p.stem]:.3f}s")
if a.check:
    W = json.load(open(a.check)); bad = [(k, d, W[k]["dur"]) for k, d in durs.items() if k in W and abs(d - W[k]["dur"]) > 0.02]
    if bad: raise SystemExit(f"duration drift vs words.json (>20 ms): {bad}")
    print("durations match words.json ✓")
