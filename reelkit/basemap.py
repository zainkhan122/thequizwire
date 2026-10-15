"""reelkit/basemap.py — public-domain raster basemaps (NASA GIBS, Web Mercator tiles) stitched per map scene.

usage: python3 reelkit/basemap.py LON0,LAT0,LON1,LAT1 WIDTH_PX OUT.jpg [layer]
       from basemap import os, tempfile, stitch; meta = stitch(bbox, width_px, out_path, layer="bluemarble")

Picks the tile zoom whose px/° fits WIDTH_PX (the on-screen width the scene needs at its deepest camera), fetches the
tiles (cached in ~/.cache/basemap), writes OUT.jpg and returns the d3-mercator parameters of the image's pixel grid:
    {"scale": s, "translate": [tx, ty]}  →  d3.geoMercator().scale(s).translate([tx, ty]) maps lon/lat to image px.
engine/geo-runtime.js aligns the image under the fitted scene projection with these two numbers (Mercator scenes only).

Layers (all NASA, public domain — credit "NASA Blue Marble" / "NASA GIBS"):
  bluemarble  BlueMarble_ShadedRelief_Bathymetry  zoom ≤ 8 (≈ 611 m/px)  — the v3 default (ocean floor + relief)
  bmng        BlueMarble_NextGeneration           zoom ≤ 8                — flat deep-blue ocean
  night       VIIRS_CityLights_2012               zoom ≤ 8                — Black Marble night lights
Limits: image ≤ 4096 × 6144 px and ≤ 6 MB; tiles outside |lat| 85 are clamped; longitudes may exceed ±180 (tiles wrap)
so a bbox across the antimeridian stitches seamlessly; the 180° tile seam (a dark column in the source tiles) is blended.
"""
import concurrent.futures, io, json, math, os, pathlib, sys, tempfile, time, urllib.request

LAYERS = {"bluemarble": ("BlueMarble_ShadedRelief_Bathymetry", "GoogleMapsCompatible_Level8", "jpeg", 8, "NASA Blue Marble"),
          "bmng": ("BlueMarble_NextGeneration", "GoogleMapsCompatible_Level8", "jpeg", 8, "NASA Blue Marble"),
          "night": ("VIIRS_CityLights_2012", "GoogleMapsCompatible_Level8", "jpeg", 8, "NASA Black Marble")}
CACHE = pathlib.Path.home() / ".cache" / "basemap"
MAX_W, MAX_H, MAX_BYTES = 4864, 6144, 6_000_000
UA = "quizwire/1 (github zainkhan122/thequizwire)"


def _merc_y(lat): return (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2


def pick_zoom(bbox, width_px, zmax):
    lon0, _, lon1, _ = bbox
    z = 0
    while z < zmax and (lon1 - lon0) / 360 * 256 * 2 ** (z + 1) <= width_px * 1.25: z += 1
    return z


def stitch(bbox, width_px, out_path, layer="bluemarble", quality=86):
    from PIL import Image
    name, tms, ext, zmax, credit = LAYERS[layer]
    lon0, lat0, lon1, lat1 = bbox
    lat0, lat1 = max(lat0, -85.0), min(lat1, 85.0)
    z = pick_zoom(bbox, width_px, zmax); n = 2 ** z
    x0, x1 = int(math.floor((lon0 + 180) / 360 * n)), int(math.floor((lon1 + 180) / 360 * n))
    y0, y1 = int(math.floor(_merc_y(lat1) * n)), int(math.floor(_merc_y(lat0) * n))
    y0, y1 = max(y0, 0), min(y1, n - 1)
    while (x1 - x0 + 1) * 256 > MAX_W or (y1 - y0 + 1) * 256 > MAX_H:      # too big: step the zoom down
        z -= 1; n = 2 ** z
        x0, x1 = int(math.floor((lon0 + 180) / 360 * n)), int(math.floor((lon1 + 180) / 360 * n))
        y0, y1 = max(int(math.floor(_merc_y(lat1) * n)), 0), min(int(math.floor(_merc_y(lat0) * n)), n - 1)
    tiles = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    cache = CACHE / name / str(z); cache.mkdir(parents=True, exist_ok=True)

    def fetch(t):
        x, y = t; xw = x % n; p = cache / f"{y}_{xw}.{ext}"
        if not p.exists() and os.environ.get("BASEMAP_OFFLINE"):                 # tests: flat ocean-blue placeholder, never the network
            ph = pathlib.Path(tempfile.gettempdir()) / f"bm_placeholder_{z}_{y}_{xw}.{ext}"
            if not ph.exists(): Image.new("RGB", (256, 256), (16, 34, 58)).save(ph, quality=60)
            return t, ph
        if not p.exists():
            url = f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{name}/default/{tms}/{z}/{y}/{xw}.{ext}"
            for attempt in range(4):                                             # GIBS drops SSL connections now and then: retry with back-off
                try: p.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()); break
                except Exception as e:
                    if attempt == 3: raise SystemExit(f"basemap: tile fetch failed after 4 tries: {url} ({e})")
                    time.sleep(1.5 * (attempt + 1))
        return t, p

    img = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for (x, y), p in ex.map(fetch, tiles): img.paste(Image.open(p).convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
    for x in range(x0, x1 + 1):                                               # blend the 180° seam (dark column in the source tiles)
        if x % n == 0 and x != x0:
            c = (x - x0) * 256
            left, right = img.crop((c - 8, 0, c - 7, img.height)), img.crop((c + 3, 0, c + 4, img.height))   # the seam = last 4 columns of the x = n-1 tile
            for i in range(-7, 3): img.paste(left if i < 0 else right, (c + i, 0))
    out_path = pathlib.Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    q = quality
    while True:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() <= MAX_BYTES or q <= 60: break
        q -= 6
    out_path.write_bytes(buf.getvalue())
    s = 256 * n / (2 * math.pi)
    return {"layer": name, "zoom": z, "tiles": len(tiles), "size": list(img.size), "bytes": buf.tell(), "quality": q,
            "scale": s, "translate": [s * math.pi - x0 * 256, s * math.pi - y0 * 256], "bbox": [lon0, lat0, lon1, lat1],
            "credit": credit, "licence": "PD-USGov", "provider": "NASA GIBS"}


if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(__doc__)
    meta = stitch([float(v) for v in sys.argv[1].split(",")], int(sys.argv[2]), sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "bluemarble")
    print(json.dumps(meta))
