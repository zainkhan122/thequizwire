"""NASA GIBS (public domain) Web-Mercator basemap stitcher.
usage: python3 basemap.py LON0,LAT0,LON1,LAT1 WIDTH_PX OUT.jpg [layer]
Picks the zoom whose px/° fits WIDTH_PX, fetches the tiles, writes OUT.jpg and prints the d3 mercator params (scale, translate) for an overlay
drawn on a canvas whose (0,0) is the stitched image's top-left."""
import math, sys, io, json, pathlib, concurrent.futures, urllib.request
LAYERS = {"bluemarble": ("BlueMarble_ShadedRelief_Bathymetry", "GoogleMapsCompatible_Level8", "jpeg", 8),
          "bmng": ("BlueMarble_NextGeneration", "GoogleMapsCompatible_Level8", "jpeg", 8)}
from PIL import Image
def main():
    bbox = [float(v) for v in sys.argv[1].split(",")]; width = int(sys.argv[2]); out = sys.argv[3]; layer = sys.argv[4] if len(sys.argv) > 4 else "bluemarble"
    name, tms, ext, zmax = LAYERS[layer]
    lon0, lat0, lon1, lat1 = bbox; lat0, lat1 = max(lat0, -85), min(lat1, 85)
    def merc_y(lat): return (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2
    z = 0
    while z < zmax and (lon1 - lon0) / 360 * 256 * 2 ** (z + 1) <= width * 1.6: z += 1
    n = 2 ** z
    x0, x1 = int((lon0 + 180) / 360 * n), int((lon1 + 180) / 360 * n)
    y0, y1 = int(merc_y(lat1) * n), int(merc_y(lat0) * n)
    tiles = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    cache = pathlib.Path.home() / ".cache" / "basemap" / name / str(z); cache.mkdir(parents=True, exist_ok=True)
    def fetch(t):
        x, y = t; x = x % n; p = cache / f"{y}_{x}.{ext}"
        if not p.exists():
            url = f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{name}/default/{tms}/{z}/{y}/{x}.{ext}"
            try: p.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "quizwire/1"}), timeout=60).read())
            except Exception as e: raise SystemExit(f"tile fetch failed: {url} ({e})")
        return t, p
    img = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for (x, y), p in ex.map(fetch, tiles): img.paste(Image.open(p).convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
    img.save(out, quality=88)
    s = 256 * n / (2 * math.pi)
    print(json.dumps({"zoom": z, "tiles": len(tiles), "size": img.size, "scale": s, "translate": [s * math.pi - x0 * 256, s * math.pi - y0 * 256], "layer": name, "credit": "NASA GIBS / Blue Marble (public domain)"}))
main()
