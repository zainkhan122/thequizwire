#!/usr/bin/env python3
"""Sandbox renderer (no hyperframes): drives the built composition's GSAP timeline frame by frame in headless Chromium and
encodes with imageio-ffmpeg. Same HTML, same seek semantics as the CI renderer, so it is a faithful preview for iteration.

  python3 reelkit/local_render.py <episode_dir> [--fps 30] [--crf 20] [--scale 1] [--out final.mp4] [--t0 0 --t1 END]

Reads $BUILD/hf/index.html (BUILD = ~/.cache/build/<name>), writes <out> next to it plus a contact sheet (<out>.contact.jpg).
Needs: pip install --user playwright imageio-ffmpeg && python3 -m playwright install chromium   (reelkit/setup.sh does this).
"""
import argparse, json, os, pathlib, subprocess, sys, time
# sandbox: Chromium's system libs (nss, atk, xkbcommon, asound…) are unpacked user-side by reelkit/setup.sh into ~/.cache/ulib
_ulib = pathlib.Path.home() / ".cache/ulib"
if _ulib.exists():
    os.environ["LD_LIBRARY_PATH"] = ":".join([str(_ulib / "usr/lib/x86_64-linux-gnu"), str(_ulib / "lib/x86_64-linux-gnu"), os.environ.get("LD_LIBRARY_PATH", "")]).strip(":")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--scale", type=float, default=1.0, help="0.5 = 540x960 preview"); ap.add_argument("--out", default="final.mp4")
    ap.add_argument("--t0", type=float, default=0.0); ap.add_argument("--t1", type=float, default=None); ap.add_argument("--sheet", type=int, default=12)
    ap.add_argument("--no-cover", action="store_true", help="skip the frame-0 cover burn (debug only)")
    a = ap.parse_args()
    ep = pathlib.Path(a.ep).resolve(); build = pathlib.Path(os.environ.get("BUILD") or pathlib.Path.home() / ".cache/build" / ep.name); hf = build / "hf"
    html = hf / "index.html"; assert html.exists(), f"no composition at {html} (run episode.sh <ep> build)"
    total = float(json.loads((ep / "timeline.json").read_text())["total"]); t1 = min(a.t1 if a.t1 is not None else total, total)
    import imageio_ffmpeg; from playwright.sync_api import sync_playwright
    ff = imageio_ffmpeg.get_ffmpeg_exe(); W, H = int(1080 * a.scale) // 2 * 2, int(1920 * a.scale) // 2 * 2
    out = (build / a.out) if not os.path.isabs(a.out) else pathlib.Path(a.out); tmp = out.with_suffix(".video.mp4")
    n = int(round((t1 - a.t0) * a.fps)); t_start = time.time()
    enc = subprocess.Popen([ff, "-v", "error", "-y", "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(a.fps), "-i", "-",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    sheet = []; sheet_at = {int(round(i * (n - 1) / max(1, a.sheet - 1))) for i in range(a.sheet)}
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none", "--autoplay-policy=no-user-gesture-required"])
        pg = br.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=a.scale)
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(html.as_uri(), wait_until="load"); pg.wait_for_function("() => !!(window.__timelines && window.__timelines.main)"); pg.wait_for_function("() => document.fonts.status === 'loaded'")
        pg.evaluate("document.querySelectorAll('audio,video').forEach(e => { e.muted = true; try { e.pause(); } catch (_) {} })")
        pg.evaluate("() => { window.__timelines.main.pause(); }"); pg.wait_for_timeout(300)   # never return the timeline object (unserialisable → hang)
        for i in range(n):
            t = a.t0 + i / a.fps
            pg.evaluate("t => { const tl = window.__timelines.main; tl.pause(); tl.seek(t, false); }", t)
            if i == 0: pg.wait_for_timeout(200)
            jpg = pg.screenshot(type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            enc.stdin.write(jpg)
            if i in sheet_at: sheet.append((t, jpg))
            if i % (a.fps * 5) == 0: print(f"  {i:5d}/{n}  t={t:6.2f}s  {time.time() - t_start:5.0f}s elapsed", flush=True)
        br.close()
    enc.stdin.close(); enc.wait(); assert enc.returncode == 0, "ffmpeg video encode failed"
    mix = hf / "assets" / "mix.wav"
    if mix.exists():
        subprocess.run([ff, "-v", "error", "-y", "-i", str(tmp), "-ss", f"{a.t0:.3f}", "-t", f"{t1 - a.t0:.3f}", "-i", str(mix), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True); tmp.unlink()
    else: tmp.rename(out)
    # production rule (owner 2026-11-19): frame 0 of every full reel is its cover — burn it here too, so the local review copy IS what ships
    if a.t0 == 0 and a.t1 is None and not a.no_cover:
        plain = out.with_name(out.stem + ".plain.mp4"); out.rename(plain)
        r = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("cover.py")), str(ep), "--video", str(plain), "--out", str(out.with_name("cover.png")),
                            "--jpg", str(out.with_name("cover.jpg")), "--burn", str(out)], capture_output=True, text=True)
        if r.returncode == 0: plain.unlink(); print("cover: burned into frame 0 ·", out.with_name("cover.jpg"))
        else: plain.rename(out); print("cover: burn FAILED — plain render kept (fix before publishing):", (r.stderr or r.stdout).strip()[-400:])
    # contact sheet
    try:
        from PIL import Image, ImageDraw; import io
        cols = 4; rows = (len(sheet) + cols - 1) // cols; tw, th = 270, 480; S = Image.new("RGB", (cols * tw, rows * th), "black"); d = ImageDraw.Draw(S)
        for k, (t, jpg) in enumerate(sheet):
            im = Image.open(io.BytesIO(jpg)).convert("RGB").resize((tw, th)); S.paste(im, ((k % cols) * tw, (k // cols) * th)); d.text(((k % cols) * tw + 8, (k // cols) * th + 8), f"{t:.1f}s", fill="yellow")
        S.save(out.with_suffix(".contact.jpg"), quality=85)
    except Exception as e: print("contact sheet skipped:", e)
    if errs: print("page errors:", *errs[:10], sep="\n  ")
    print(f"local_render: {out} · {n} frames @ {a.fps} fps · {W}x{H} · {time.time() - t_start:.0f}s")

if __name__ == "__main__": main()
