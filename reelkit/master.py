#!/usr/bin/env python3
"""Shared final mastering for every episode (called at the end of each episode's score.py).

    from master import finish
    report = finish(mix, OUT, vo=vo, music=music_ducked, sfx=sfx_ducked)

What it does, in order:
  1. Writes mix_raw.wav plus stems (vo / music / sfx) for debugging.
  2. Two-pass EBU R128 loudnorm to -14 LUFS integrated, with true peak capped at -2.0 dBTP. The extra 0.5 dB of headroom
     absorbs AAC encoder overshoot, so the delivered file stays at or below -1.5 dBTP (YouTube/TikTok spec).
  3. Measures what a mix engineer would check and writes mix_report.json:
       · integrated LUFS / true peak / LRA of the master
       · VO-over-music gap while speaking (RMS dB): target ≥ 15 dB (pro range 15–20; W3C asks 20 for pure speech)
       · VO-over-SFX gap while speaking: target ≥ 6 dB
  Warnings are printed and recorded. The hard pass/fail gate is reelkit/qa.py on the encoded file.
"""
from __future__ import annotations
import json, re, shutil, subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

SR = 48000
TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -2.0, 11
MIN_VO_OVER_MUSIC_DB, MIN_VO_OVER_SFX_DB = 15.0, 6.0


def _ff(args: list[str]) -> str:
    return subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-nostats", "-y"] + args,
                          capture_output=True, text=True).stderr


def _loud(path: Path) -> dict:
    st = _ff(["-i", str(path), "-af", f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json", "-f", "null", "-"])
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", st, re.S).group(0))


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12))


def finish(mix: np.ndarray, out: Path, vo: np.ndarray | None = None, music: np.ndarray | None = None,
           sfx: np.ndarray | None = None, sr: int = SR) -> dict:
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    raw = out / "mix_raw.wav"
    sf.write(raw, mix.astype(np.float32), sr, subtype="FLOAT")
    for name, stem in (("vo", vo), ("music", music), ("sfx", sfx)):
        if stem is not None:
            sf.write(out / f"stem_{name}.wav", stem.astype(np.float32), sr, subtype="FLOAT")

    m = _loud(raw)
    af = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    _ff(["-i", str(raw), "-af", af + ",aresample=48000", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out / "mix.wav")])
    m2 = _loud(out / "mix.wav")
    rep = {"lufs": float(m2["input_i"]), "true_peak": float(m2["input_tp"]), "lra": float(m2["input_lra"]),
           "loudnorm_mode": m2.get("normalization_type", "?"), "warnings": []}

    if vo is not None:
        v = vo.mean(1) if vo.ndim == 2 else vo
        win = int(0.05 * sr); nwin = len(v) // win
        frames = v[:nwin * win].reshape(nwin, win)
        e = np.sqrt((frames ** 2).mean(1))
        speech = e > (e.max() * 0.08)                                 # 50 ms windows where the narrator is audible
        rep["speech_seconds"] = round(float(speech.sum() * 0.05), 1)
        mask = np.repeat(speech, win)
        vdb = _rms_db(v[:nwin * win][mask])
        for name, stem, floor in (("music", music, MIN_VO_OVER_MUSIC_DB), ("sfx", sfx, MIN_VO_OVER_SFX_DB)):
            if stem is None: continue
            s = (stem.mean(1) if stem.ndim == 2 else stem)[:nwin * win][mask]
            gap = round(vdb - _rms_db(s), 1)
            rep[f"vo_over_{name}_db"] = gap
            if gap < floor:
                rep["warnings"].append(f"VO only {gap} dB over {name} while speaking (target ≥ {floor} dB)")
    if rep["true_peak"] > -1.5:
        rep["warnings"].append(f"master true peak {rep['true_peak']} dBTP > -1.5")
    if abs(rep["lufs"] - TARGET_I) > 0.5:
        rep["warnings"].append(f"master {rep['lufs']} LUFS off target {TARGET_I}")
    (out / "mix_report.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(f"master: {rep['lufs']} LUFS · TP {rep['true_peak']} dBTP · LRA {rep['lra']} · "
          f"VO/music {rep.get('vo_over_music_db', '-')} dB · VO/sfx {rep.get('vo_over_sfx_db', '-')} dB")
    for w in rep["warnings"]: print("  ! " + w)
    return rep
