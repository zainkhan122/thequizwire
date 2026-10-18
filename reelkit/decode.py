#!/usr/bin/env python3
"""reelkit/decode.py — decode how the high-traffic reference channels win: Script + TTS + Cover + Media + Heading +
Description, per video, so our Shorts are built from measured lessons instead of taste.

  python3 reelkit/decode.py channels  @gyanotrick @geomapunveiled25 ... [--latest 12] [--top 3] [--bottom 1]
  python3 reelkit/decode.py video     <youtube url>                      (one video, full decode)
  python3 reelkit/decode.py ours      series/*/ep* ...                   (same metrics on our own released masters)
  python3 reelkit/decode.py report    [--date YYYY-MM-DD]                → docs/DECODE_<date>.md (+ json)

Per video (yt-dlp, no login — the sandbox is not bot-gated as of 2026-10-18):
  heading      title, hook pattern (what-if / question / superlative / numbered / story), emoji, caps keyword, length
  description  first lines, length, link?, hashtag count, CTA?, keyword density (title words repeated)
  script       YouTube auto-captions (en) → words, wpm, first sentence (the spoken hook), CTA in speech, question count
  voice        parselmouth prosody on the mixed audio: pitch median/range (semitones), intensity range, voiced share
               (music bed included → compare relatively, within this sample)
  cover        maxres thumbnail saved; frame 0.5 s saved (what the Shorts feed shows while loading)
  media        frames at 0.5 s / 25 % / 50 % / 85 % → contact sheet; motion events per 10 s (frame-diff: cuts + big camera moves)
               text-on-screen is judged by EYE on the contact sheets (OCR proxies were unreliable on map edges)
  engagement   views, likes, comments, like/view ‰, comments/view ‰, age days, views/day

Raw media → ~/.cache/decode/<date>/<channel>/<id>/ (never in the repo). Committed: docs/DECODE_<date>.md and
docs/data/decode-<date>.json (metrics + ≤ 25-word excerpts; no full transcripts of other people's videos).
Adapted from zainkhan122/yt-tts reels-studio/tools/channel_decode.py (same taxonomy so the two studies compare).
"""
import argparse, datetime as dt, json, math, os, re, statistics as st, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date.today().isoformat()
RAW = Path(os.environ.get("DECODE_RAW", Path.home() / ".cache/decode"))


def ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ytdlp_json(args, timeout=300):
    r = run(["yt-dlp", "--no-warnings", "-q", "-J"] + args, timeout)
    if r.returncode != 0: raise RuntimeError(r.stderr[-300:])
    return json.loads(r.stdout)


# ---------------------------------------------------------------- taxonomy
def hook_type(text):
    t = (text or "").strip().lower()
    if re.match(r"^\W*what if\b", t): return "what-if"
    if re.search(r"\b(which|where|who|how many|what|why|can you|guess)\b.*\?", t[:90]): return "question"
    if re.search(r"\b(most|biggest|largest|smallest|only|first|last|fastest|deadliest|richest|poorest)\b", t[:80]): return "superlative"
    if re.match(r"^\W*(\d+|top \d+|\d+ (countries|facts|things))", t): return "numbered"
    if re.search(r"\b(in \d{3,4}|once|years ago|history|empire|returned|vanished)\b", t[:80]): return "story"
    if re.search(r"\b(you|your)\b", t[:60]): return "you-address"
    return "other"


def caps_keyword(title):
    return [w for w in re.findall(r"\b[A-Z]{3,}\b", title or "") if w not in ("USA", "UK", "UAE")] or [w for w in re.findall(r"\b[A-Z]{2,}\b", title or "")]


# ---------------------------------------------------------------- script
def captions_text(info):
    """Auto/manual English captions via yt-dlp subtitle JSON3 URL → plain words."""
    for pool in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang, fmts in pool.items():
            if not lang.startswith("en"): continue
            url = next((f["url"] for f in fmts if f.get("ext") == "json3"), None) or next((f["url"] for f in fmts if f.get("ext") == "vtt"), None)
            if not url: continue
            try:
                raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8", "ignore")
            except Exception:
                continue
            if raw.lstrip().startswith("{"):
                try:
                    J = json.loads(raw); words = []
                    for ev in J.get("events", []):
                        for s in ev.get("segs", []) or []:
                            w = s.get("utf8", "").replace("\n", " ").strip()
                            if w: words.append(w)
                    txt = re.sub(r"\s+", " ", " ".join(words)).strip()
                    if len(txt.split()) >= 5: return txt, f"captions:{lang}"
                except Exception:
                    pass
            else:
                lines, seen = [], set()
                for line in raw.splitlines():
                    line = re.sub(r"<[^>]+>", "", line).strip()
                    if not line or line == "WEBVTT" or "-->" in line or line.startswith(("Kind:", "Language:")): continue
                    if line not in seen: seen.add(line); lines.append(line)
                txt = " ".join(lines)
                if len(txt.split()) >= 5: return txt, f"captions:{lang}"
    return "", ""


_fw = None
def whisper(audio):
    global _fw
    if _fw is None:
        from faster_whisper import WhisperModel
        _fw = WhisperModel("base", device="cpu", compute_type="int8")   # multilingual: reference VO is often Hindi/Urdu
    import wave, numpy as np                                  # feed samples directly (PyAV/ffmpeg-less path)
    with wave.open(str(audio), "rb") as w: pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype("float32") / 32768.0
    segs, inf = _fw.transcribe(pcm, task="translate", vad_filter=True)   # → English text whatever the spoken language
    return " ".join(s.text.strip() for s in segs), inf.language


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# ---------------------------------------------------------------- voice
def prosody(audio):
    import parselmouth
    snd = parselmouth.Sound(str(audio)); dur = snd.get_total_duration()
    if dur < 3: return {}
    pitch = snd.to_pitch_ac(time_step=0.01, pitch_floor=60, pitch_ceiling=500)
    f0 = [f for f in pitch.selected_array["frequency"] if f > 0]
    inten = snd.to_intensity(time_step=0.01, minimum_pitch=70); iv = [v for v in inten.values[0] if v > 0]
    out = {"audio_s": round(dur, 1), "voiced_share": round(len(f0) / max(1, len(pitch.selected_array["frequency"])), 2)}
    if len(f0) > 30:
        q = st.quantiles(f0, n=100); lo, hi = q[4], q[94]
        out.update(pitch_median_hz=round(st.median(f0)), pitch_range_st=round(12 * math.log2(hi / lo), 1) if lo > 0 else None)
    if iv: out["intensity_range_db"] = round(max(iv) - st.median(iv), 1)
    # loudness (LUFS) via ffmpeg ebur128 — tells us how hot their mix is vs our −14
    r = run([ff(), "-v", "info", "-i", str(audio), "-af", "ebur128=peak=true", "-f", "null", "-"], 300)
    m = re.findall(r"I:\s*(-?\d+\.\d) LUFS", r.stderr)
    if m: out["lufs"] = float(m[-1])
    return out


# ---------------------------------------------------------------- media
def frames_and_cuts(video, out_dir, vid):
    import cv2, numpy as np
    cap = cv2.VideoCapture(str(video)); fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n <= 0: return {}
    dur = n / fps; picks = {"f0": 0.5, "f25": 0.25 * dur, "f50": 0.5 * dur, "f85": 0.85 * dur}
    saved, imgs = {}, []
    for name, t in picks.items():
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
        if ok:
            p = out_dir / f"{vid}-{name}.jpg"; cv2.imwrite(str(p), fr, [cv2.IMWRITE_JPEG_QUALITY, 82]); saved[name] = p.name; imgs.append(fr)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0); prev, cuts, idx, text_hits, samples = None, 0, 0, 0, 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        idx += 1
        if idx % 3: continue
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY); small = cv2.resize(g, (48, 85)).astype("float32")
        if prev is not None and float(np.mean(np.abs(small - prev))) > 18: cuts += 1
        prev = small
    cap.release()
    if imgs:                                                # contact sheet 4-up
        h = 480; tiles = [cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h)) for im in imgs]
        sheet = np.concatenate(tiles, axis=1); cv2.imwrite(str(out_dir / f"{vid}-sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return {"frames": saved, "sheet": f"{vid}-sheet.jpg", "cuts_per_10s": round(cuts / dur * 10, 1), "video_s": round(dur, 1)}


# ---------------------------------------------------------------- one video
def decode_video(url, work, light=False):
    info = ytdlp_json([url]); vid = info["id"]; work = work / vid; work.mkdir(parents=True, exist_ok=True)
    (work / "info.json").write_text(json.dumps({k: info.get(k) for k in ("id", "title", "description", "tags", "view_count", "like_count", "comment_count", "duration", "upload_date", "channel", "channel_follower_count", "categories", "thumbnail")}, indent=1))
    title, desc, dur = info.get("title") or "", info.get("description") or "", info.get("duration") or 0
    script, src = captions_text(info)
    media, voice, cover = {}, {}, ""
    if not light:
        run(["yt-dlp", "--no-warnings", "-q", "--ffmpeg-location", ff(), "-f", "bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]/bv*[vcodec^=avc1]+ba/b[height<=480]/b", "--merge-output-format", "mp4", "-o", str(work / "video.mp4"), url])
        video = work / "video.mp4"
        if video.exists():
            run([ff(), "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(work / "audio.wav")])
            if (work / "audio.wav").exists():
                if len(script.split()) < 8:
                    try: script, lang = whisper(work / "audio.wav"); src = f"whisper-translate:{lang}"
                    except Exception as e: print(f"  whisper failed {vid}: {e}", file=sys.stderr)
                try: voice = prosody(work / "audio.wav")
                except Exception as e: print(f"  prosody failed {vid}: {e}", file=sys.stderr)
            try: media = frames_and_cuts(video, work, vid)
            except Exception as e: print(f"  frames failed {vid}: {e}", file=sys.stderr)
        if info.get("thumbnail"):
            try:
                urllib.request.urlretrieve(info["thumbnail"], work / "cover.jpg"); cover = "cover.jpg"
            except Exception: pass
    words = script.split(); sents = sentences(script)
    up = info.get("upload_date"); age = (dt.date.today() - dt.datetime.strptime(up, "%Y%m%d").date()).days if up else None
    views = info.get("view_count") or 0
    tw = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", title)}
    desc_words = re.findall(r"[A-Za-z]{4,}", desc)
    row = {
        "id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "channel": info.get("channel"), "subs": info.get("channel_follower_count"),
        "views": views, "likes": info.get("like_count"), "comments": info.get("comment_count"), "age_days": age,
        "views_per_day": round(views / max(1, age or 1)), "like_permille": round(1000 * (info.get("like_count") or 0) / max(1, views), 1),
        "comment_permille": round(1000 * (info.get("comment_count") or 0) / max(1, views), 2), "duration": dur,
        "heading": title[:160], "heading_len": len(title), "heading_hook": hook_type(title), "heading_emoji": len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", title)),
        "heading_caps": caps_keyword(title), "heading_has_question": "?" in title,
        "description_first_lines": [l.strip() for l in desc.splitlines() if l.strip()][:3], "description_len": len(desc),
        "description_has_link": bool(re.search(r"https?://|www\.", desc)), "hashtags": re.findall(r"#\w+", desc)[:12],
        "hashtag_count": len(re.findall(r"#\w+", desc)), "description_cta": bool(re.search(r"subscribe|comment|follow|share|like", desc, re.I)),
        "description_title_overlap": round(sum(1 for w in desc_words if w.lower() in tw) / max(1, len(desc_words)), 2), "tags": (info.get("tags") or [])[:10],
        "script_source": src, "script_words": len(words), "wpm": round(len(words) / (dur / 60)) if dur and words else None,
        "script_hook": " ".join(words[:25]), "script_hook_type": hook_type(sents[0] if sents else ""), "script_sentences": len(sents),
        "script_questions": sum(1 for s in sents if s.endswith("?")), "script_cta": bool(re.search(r"\b(comment|follow|save|subscribe|like|share)\b", script, re.I)),
        "script_you": len(re.findall(r"\b(you|your)\b", script, re.I)), "script_numbers": len(re.findall(r"\b\d[\d,.]*\b", script)),
        "cover": cover, **voice, **media,
    }
    (work / "decode.json").write_text(json.dumps(row, indent=1)); return row


# ---------------------------------------------------------------- commands
def cmd_channels(a):
    date_dir = RAW / TODAY; rows = []
    for acc in a.channels:
        url = acc if acc.startswith("http") else f"https://www.youtube.com/{acc if acc.startswith('@') else '@' + acc}/shorts"
        print(f"== {url}")
        try: listing = ytdlp_json(["--flat-playlist", "--playlist-end", str(a.latest), url])
        except Exception as e: print(f"  listing failed: {e}", file=sys.stderr); continue
        name = (listing.get("uploader_id") or listing.get("channel") or acc).strip("@")
        ents = [e for e in listing.get("entries") or [] if e.get("id") and e.get("view_count") is not None]
        ranked = sorted(ents, key=lambda e: -e["view_count"])
        picks = ranked[:a.top] + (ranked[-a.bottom:] if a.bottom and len(ranked) > a.top else [])
        listed = [{"id": e["id"], "views": e["view_count"], "title": (e.get("title") or "")[:120]} for e in ents]
        print(f"  {len(ents)} listed · median views {int(st.median([e['views'] for e in listed])) if listed else 0:,} · decoding {len(picks)}")
        work = date_dir / name; work.mkdir(parents=True, exist_ok=True)
        (work / "listing.json").write_text(json.dumps({"channel": name, "url": url, "listed": listed}, indent=1))
        for i, p in enumerate(picks):
            try:
                r = decode_video(f"https://www.youtube.com/shorts/{p['id']}", work); r["account"] = name
                r["tier"] = "top" if i < a.top else "bottom"; r["channel_median_views"] = int(st.median([e["views"] for e in listed])); rows.append(r)
                print(f"   {r['tier']:<6} {r['views']:>10,} {r['duration']:>4}s {r.get('wpm') or '-':>4}wpm pitch {r.get('pitch_range_st') or '-'}st cuts {r.get('cuts_per_10s') or '-'}  {r['heading'][:60]}")
            except Exception as e:
                print(f"  decode failed {p['id']}: {e}", file=sys.stderr)
    save_rows(rows, "channels")


def cmd_video(a):
    r = decode_video(a.url, RAW / TODAY / "single"); print(json.dumps(r, indent=1)); save_rows([r], "channels")


def cmd_ours(a):
    """Same metrics on our masters (release mp4 in <ep>/out/final.mp4 or --video), script from voice.json."""
    rows = []
    for ep in a.episodes:
        ep = Path(ep); E = json.loads((ep / "episode.json").read_text()); V = json.loads((ep / "voice.json").read_text())
        video = ep / "out/final.mp4"
        if not video.exists(): print(f"  {ep.name}: no out/final.mp4 (cloud.py fetch first)"); continue
        work = RAW / TODAY / "ours" / ep.name; work.mkdir(parents=True, exist_ok=True)
        run([ff(), "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(work / "audio.wav")])
        script = " ".join(l["text"] for l in V["lines"] if l.get("text")); words = script.split(); sents = sentences(script)
        voice = prosody(work / "audio.wav") if (work / "audio.wav").exists() else {}
        media = frames_and_cuts(video, work, ep.name)
        dur = media.get("video_s") or 0
        rows.append({"id": ep.name, "account": "thequizwire", "tier": "ours", "heading": E["title"], "heading_hook": hook_type(E["title"]), "heading_caps": caps_keyword(E["title"]),
                     "duration": dur, "script_words": len(words), "wpm": round(len(words) / (dur / 60)) if dur else None, "script_hook": " ".join(words[:25]),
                     "script_hook_type": hook_type(sents[0] if sents else ""), "script_cta": bool(re.search(r"subscribe|like|comment", script, re.I)),
                     "script_you": len(re.findall(r"\b(you|your)\b", script, re.I)), "script_numbers": len(re.findall(r"\b\d[\d,.]*\b", script)), **voice, **media})
        print(f"   ours   {dur:>5}s {rows[-1]['wpm']}wpm pitch {voice.get('pitch_range_st')}st lufs {voice.get('lufs')} cuts {media.get('cuts_per_10s')}  {E['title'][:60]}")
    save_rows(rows, "ours")


def save_rows(rows, kind):
    out = ROOT / "docs/data" / f"decode-{TODAY}.json"; out.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(out.read_text()) if out.exists() else []
    seen = {(r.get("account"), r.get("id")) for r in rows}
    rows = rows + [r for r in old if (r.get("account"), r.get("id")) not in seen]
    for r in rows: r.pop("description", None)
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False)); print(f"wrote {out} ({len(rows)} rows)")


def med(rows, k):
    v = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
    return round(st.median(v), 1) if v else None


def cmd_report(a):
    date = a.date or TODAY; rows = json.loads((ROOT / "docs/data" / f"decode-{date}.json").read_text())
    top = [r for r in rows if r.get("tier") == "top"]; bot = [r for r in rows if r.get("tier") == "bottom"]; ours = [r for r in rows if r.get("tier") == "ours"]
    keys = ["views", "duration", "script_words", "wpm", "pitch_range_st", "pitch_median_hz", "voiced_share", "lufs", "cuts_per_10s", "heading_len", "heading_emoji", "description_len", "hashtag_count", "like_permille", "comment_permille", "script_questions", "script_you", "script_numbers"]
    L = [f"# Decode {date} — reference channels vs TheQuizWire (numbers)", "", "Tool: `reelkit/decode.py` (yt-dlp · YouTube captions · parselmouth prosody · OpenCV frames). Medians; pitch measured on mixed audio (music included) → compare relatively.", "",
         "| metric | top tier (n=%d) | bottom tier (n=%d) | ours (n=%d) |" % (len(top), len(bot), len(ours)), "|---|---|---|---|"]
    for k in keys: L.append(f"| {k} | {med(top, k)} | {med(bot, k)} | {med(ours, k)} |")
    def share(rs, k): return f"{round(100 * sum(1 for r in rs if r.get(k)) / max(1, len(rs)))}%"
    for k in ("script_cta", "heading_has_question", "description_has_link", "description_cta"):
        L.append(f"| {k} (share) | {share(top, k)} | {share(bot, k)} | {share(ours, k)} |")
    L += ["", "## Hook patterns (heading → spoken)", "", "| tier | heading hooks | spoken hooks |", "|---|---|---|"]
    from collections import Counter
    for name, rs in (("top", top), ("bottom", bot), ("ours", ours)):
        L.append(f"| {name} | {dict(Counter(r.get('heading_hook') for r in rs))} | {dict(Counter(r.get('script_hook_type') for r in rs))} |")
    L += ["", "## Per video", "", "| tier | channel | views | s | words | wpm | pitch st | cuts/10s | heading | spoken hook (≤25 words) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -(r.get("views") or 0)):
        L.append(f"| {r.get('tier')} | {r.get('account')} | {r.get('views') or 0:,} | {r.get('duration')} | {r.get('script_words')} | {r.get('wpm')} | {r.get('pitch_range_st')} | {r.get('cuts_per_10s')} | {str(r.get('heading'))[:70].replace('|', '/')} | {str(r.get('script_hook'))[:160].replace('|', '/')} |")
    L += ["", "## Descriptions (first lines) and tags", ""]
    for r in [r for r in rows if r.get("tier") == "top"][:12]:
        L.append(f"- **{r.get('account')}** · {r.get('views') or 0:,} views · {r.get('heading')}")
        for ln in r.get("description_first_lines") or []: L.append(f"  - {ln[:200].replace(chr(10), ' ')}")
        L.append(f"  - hashtags {r.get('hashtag_count')} · link {r.get('description_has_link')} · tags {r.get('tags')}")
    out = ROOT / "docs" / f"DECODE_{date}.md"; out.write_text("\n".join(L) + "\n"); print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("channels"); p.add_argument("channels", nargs="+"); p.add_argument("--latest", type=int, default=12); p.add_argument("--top", type=int, default=3); p.add_argument("--bottom", type=int, default=1)
    p = sp.add_parser("video"); p.add_argument("url")
    p = sp.add_parser("ours"); p.add_argument("episodes", nargs="+")
    p = sp.add_parser("report"); p.add_argument("--date")
    a = ap.parse_args(); {"channels": cmd_channels, "video": cmd_video, "ours": cmd_ours, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
