"""Fetch YouTube storyboards (seek-preview mosaics) so a video can be inspected frame by frame without downloading it.
usage: python3 yt_sb.py shorts <channel_handle> [N]   -> lists top-N short ids/titles from the channel's /shorts tab
       python3 yt_sb.py board <video_id> [level]      -> downloads storyboard mosaics for the video -> <id>_L<level>_<n>.jpg"""
import json, re, subprocess, sys, pathlib
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(url):
    return subprocess.run(["curl", "-sL", "-A", UA, "-H", "Accept-Language: en-US,en;q=0.9", "--compressed", url], capture_output=True, text=True, timeout=60).stdout
def walk(o, key, out):
    if isinstance(o, dict):
        if key in o: out.append(o)
        for v in o.values(): walk(v, key, out)
    elif isinstance(o, list):
        for v in o: walk(v, key, out)
def initial(html, name):
    i = html.find(name + " = ")
    if i < 0: i = html.find(name + "=")
    if i < 0: return None
    j = html.find("{", i)
    return json.JSONDecoder().raw_decode(html[j:])[0]
cmd = sys.argv[1]
if cmd == "shorts":
    handle, n = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12
    html = get(f"https://www.youtube.com/@{handle}/shorts")
    data = initial(html, "ytInitialData"); items = []
    walk(data, "shortsLockupViewModel", items)
    seen = set()
    for it in items:
        v = it["shortsLockupViewModel"]; vid = v.get("onTap", {}).get("innertubeCommand", {}).get("reelWatchEndpoint", {}).get("videoId") or v.get("entityId", "")[-11:]
        title = v.get("overlayMetadata", {}).get("primaryText", {}).get("content", ""); views = v.get("overlayMetadata", {}).get("secondaryText", {}).get("content", "")
        if vid in seen: continue
        seen.add(vid); print(vid, "|", views, "|", title[:90])
        if len(seen) >= n: break
    if not items:
        ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html); print("fallback ids:", list(dict.fromkeys(ids))[:n])
elif cmd == "board":
    vid, level = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2
    html = get(f"https://www.youtube.com/watch?v={vid}")
    pr = initial(html, "ytInitialPlayerResponse")
    title = pr.get("videoDetails", {}).get("title", "?"); secs = int(pr.get("videoDetails", {}).get("lengthSeconds", 0)); views = pr.get("videoDetails", {}).get("viewCount")
    spec = pr.get("storyboards", {}).get("playerStoryboardSpecRenderer", {}).get("spec")
    print(f"{vid}: {title!r} {secs}s views={views}")
    if not spec: print("no storyboard spec"); sys.exit(1)
    parts = spec.split("|"); base = parts[0]
    levels = parts[1:]; level = min(level, len(levels) - 1); L = levels[level].split("#")
    w, h, count, cols, rows, interval, name, sigh = int(L[0]), int(L[1]), int(L[2]), int(L[3]), int(L[4]), L[5], L[6], L[7]
    per = cols * rows; n_img = -(-count // per)
    print(f"level {level}: {w}x{h} tiles, {count} frames, {cols}x{rows} per image, {n_img} images, interval {interval} ms")
    for i in range(n_img):
        url = base.replace("$L", str(level)).replace("$N", name) + f"&sigh={sigh}"; url = url.replace("$M", str(i))
        out = pathlib.Path(f"{vid}_L{level}_{i}.jpg")
        subprocess.run(["curl", "-sL", "-A", UA, url, "-o", str(out)], timeout=60)
        print(" ", out, out.stat().st_size, "bytes")
