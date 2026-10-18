#!/usr/bin/env python3
"""Delivery QA gate for Shorts. Fails (exit 1) when a hard spec is missed.
usage: python3 reelkit/qa.py final.mp4 [--words timeline.json] [--report qa.json]
FAIL: 1080x1920 · 30 fps · H.264/AAC 48 kHz · ≤ 3 min · −14 ±1 LUFS · true peak ≤ −1.0 dBTP · video ≥ 5 Mbps
      (platforms re-encode harder below that) · no black stretches > 2 s · narration intelligibility (faster-whisper) ≥ 0.90.
WARN: true peak > −1.5 dBTP · video < 8 Mbps · silence > 2.5 s · frozen picture > 2.5 s."""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--words"); ap.add_argument("--report")
a = ap.parse_args()
FF, FP = shutil.which("ffmpeg") or "ffmpeg", shutil.which("ffprobe") or "ffprobe"
res, fails, warns = {}, [], []
pr = json.loads(subprocess.run([FP, "-v", "error", "-show_streams", "-show_format", "-of", "json", a.video], capture_output=True, text=True).stdout)
v = next(s for s in pr["streams"] if s["codec_type"] == "video"); au = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
res.update(width=v["width"], height=v["height"], fps=v["r_frame_rate"], vcodec=v["codec_name"], acodec=au and au["codec_name"],
           sample_rate=au and int(au["sample_rate"]), duration=round(float(pr["format"]["duration"]), 2), size_mb=round(int(pr["format"]["size"]) / 1e6, 1))
if (res["width"], res["height"]) != (1080, 1920): fails.append("resolution")
if res["fps"] not in ("30/1", "30000/1001"): fails.append("fps")
if res["vcodec"] != "h264" or res["acodec"] != "aac": fails.append("codec")
if res["duration"] > 180: fails.append("duration>180s")
vbr = int(v.get("bit_rate") or 0) or int(int(pr["format"]["bit_rate"]) - (int(au.get("bit_rate", 0)) if au else 0))
res["video_mbps"] = round(vbr / 1e6, 2)
if res["video_mbps"] < 5: fails.append("bitrate<5Mbps")
elif res["video_mbps"] < 8: warns.append(f"video bitrate {res['video_mbps']} Mbps < 8 (upload master target 10-12)")
st = subprocess.run([FF, "-hide_banner", "-nostats", "-i", a.video, "-af", "loudnorm=I=-14:TP=-1.5:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", st, re.S).group(0))
res.update(lufs=float(m["input_i"]), true_peak=float(m["input_tp"]))
if abs(res["lufs"] + 14) > 1: fails.append("loudness")
if res["true_peak"] > -1.0: fails.append("true_peak")
elif res["true_peak"] > -1.5: warns.append(f"true peak {res['true_peak']} dBTP > -1.5")
sil = subprocess.run([FF, "-hide_banner", "-nostats", "-i", a.video, "-af", "silencedetect=n=-45dB:d=2.5", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
res["silences"] = [round(float(x), 2) for x in re.findall(r"silence_start: ([\d.]+)", sil)]
res["silences"] = [x for x in res["silences"] if x < res["duration"] - 3.0]          # tail fade-out is fine
if res["silences"]: warns.append(f"silence > 2.5 s at {res['silences']}")
fz = subprocess.run([FF, "-hide_banner", "-nostats", "-i", a.video, "-vf", "freezedetect=n=0.001:d=2.5,blackdetect=d=2:pix_th=0.05", "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
res["freezes"] = re.findall(r"freeze_start: ([\d.]+)", fz); res["black"] = re.findall(r"black_start:([\d.]+)", fz)
if res["black"]: fails.append("black_frames")
if res["freezes"]: warns.append(f"frozen picture > 2.5 s at {res['freezes']}")
try:
    import numpy as np
    from faster_whisper import WhisperModel
    import difflib
    if a.words:
        pcm = subprocess.run([FF, "-v", "error", "-i", a.video, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
        segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768, beam_size=1, language="en")
        try:                                   # voice.py canonical tokens: numbers → words, UK/US spelling, hyphens (same normaliser as the voice gate)
            sys.path.insert(0, str(Path(__file__).resolve().parent)); from voice import tokens as _vt
            norm = lambda s: [t for t, _ in _vt(s)]
        except Exception:
            norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
        W = json.load(open(a.words)); W = W["words"] if "words" in W else [w for k in sorted(W) for w in W[k]]
        ref = norm(" ".join(w.get("w") or w.get("word", "") for w in W)); hyp = norm(" ".join(s.text for s in segs))
        res["asr_match"] = round(difflib.SequenceMatcher(None, ref, hyp).ratio(), 3)
        if res["asr_match"] < 0.90: fails.append("intelligibility")
except ImportError:
    res["asr_match"] = "skipped (faster-whisper not installed)"
# ---- v4 delivery gates (decode 2026-10-18): pace and motion measured on the master itself, not on the plan
try:
    import numpy as np, cv2, os
    if a.words:
        W = json.load(open(a.words)); W = W["words"] if "words" in W else [w for k in sorted(W) for w in W[k]]
        spoken_s = sum(1 for w in W if (w.get("w") or w.get("word")))
        speech_span = max(0.1, (max(float(w.get("e", w.get("end", 0))) for w in W) - min(float(w.get("s", w.get("start", 0))) for w in W)))
        res["wpm"] = round(spoken_s / (res["duration"] / 60))
        res["wpm_while_speaking"] = round(spoken_s / (speech_span / 60))
        if res["wpm_while_speaking"] < 140: fails.append(f"pace {res['wpm_while_speaking']} wpm < 140 (v4: 150–175)")
    cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS) or 30; prev = None; cuts = 0; i = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        i += 1
        if i % 3: continue
        g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (48, 85)).astype("float32")
        if prev is not None and float(np.mean(np.abs(g - prev))) > 18: cuts += 1
        prev = g
    cap.release()
    res["motion_per_10s"] = round(cuts / max(1.0, res["duration"]) * 10, 1)
    floor = float(os.environ.get("V4_MOTION_MIN", "6"))                                  # hard floor now; raise via env as the look catches up
    if res["motion_per_10s"] < floor: fails.append(f"motion {res['motion_per_10s']} events/10 s < {floor:g} (winners ≈27)")
    elif res["motion_per_10s"] < 10: warns.append(f"motion {res['motion_per_10s']} events/10 s < 10 (winners ≈27) — add pop-ins/pulses/camera moves")
except ImportError:
    warns.append("v4 pace/motion gate skipped (opencv missing)")
res["pass"] = not fails; res["fails"] = fails; res["warnings"] = warns
print(json.dumps(res, indent=1))
if a.report: open(a.report, "w").write(json.dumps(res, indent=1) + "\n")
sys.exit(1 if fails else 0)
