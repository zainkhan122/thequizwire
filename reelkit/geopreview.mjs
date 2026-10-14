// reelkit/geopreview.mjs — still preview of a built map scene without a browser (ImageMagick rasterises the SVG).
//   node reelkit/geopreview.mjs <hf_dir> <scene_id> <out.png> [--k 2.4 --lonlat 47,22] [--show pins,labels,highlights]
// Reads the scene spec + inline data from index.html, computes paths with the real runtime, applies the camera the
// same way GeoRT.apply does, writes <out>.svg and converts it to PNG. Labels are drawn as SVG text (fonts differ from
// the real render — this is a geometry/camera/palette check, not a typography check).
import fs from "fs"; import path from "path"; import vm from "vm"; import { execFileSync } from "child_process";
const [hf, sid, out] = process.argv.slice(2, 5);
const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const html = fs.readFileSync(path.join(hf, "index.html"), "utf8");
const m = html.match(new RegExp(`GeoRT\\.mount\\("geo_${sid}", (\\{[\\s\\S]*?\\}), JSON\\.parse\\(document\\.getElementById\\("geo_${sid}_data"\\)`));
if (!m) { console.error("scene not found in index.html: " + sid); process.exit(2); }
const spec = JSON.parse(m[1]);
const data = JSON.parse(html.match(new RegExp(`<script type="application/json" id="geo_${sid}_data">([\\s\\S]*?)</script>`))[1].replace(/<\\\//g, "</"));
const sb = { module: {}, exports: {}, require: (n) => { const f = { "d3-geo": "d3-geo.min.js", "d3-array": "d3-array.min.js", "topojson-client": "topojson-client.min.js" }[n]; const s = { module: { exports: {} }, exports: {}, require: sb.require }; s.module.exports = s.exports; vm.runInNewContext(fs.readFileSync(path.join(hf, f), "utf8"), s); return s.module.exports; } };
sb.module.exports = sb.exports; vm.runInNewContext(fs.readFileSync(path.join(hf, "geo-runtime.js"), "utf8"), sb);
const GeoRT = sb.module.exports;
const C = GeoRT.compute(spec, data);
const W = spec.w, H = spec.h, anchor = spec.anchor || [W / 2, H / 2];
let k = parseFloat(arg("k", "1")), focus = [W / 2, H / 2];
const ll = arg("lonlat"); if (ll) { const p = C.proj(ll.split(",").map(Number)); focus = [p[0], p[1]]; }
const tx = anchor[0] - focus[0] * k, ty = anchor[1] - focus[1] * k;
const show = new Set(arg("show", "pins,labels,highlights,scalebar").split(","));
const css = { "g-sphere": "fill:#0F2A3A", "g-grat": "fill:none;stroke:rgba(239,230,210,.14);stroke-width:1", "g-land": "fill:#1D3A4A", "g-countries": "fill:#1D3A4A",
  "g-border": "fill:none;stroke:rgba(239,230,210,.38);stroke-width:1.2", "g-highlight": "fill:#E3A72F;stroke:#EFE6D2;stroke-width:1.6", "g-highlight alt": "fill:#C8102E;stroke:#EFE6D2;stroke-width:1.6",
  "g-route": "fill:none;stroke:#E3A72F;stroke-width:4", "g-disputed": "fill:none;stroke:#EFE6D2;stroke-width:3;stroke-dasharray:10 8", "g-disputed policy": "fill:rgba(239,230,210,.16);stroke:#EFE6D2;stroke-width:3;stroke-dasharray:10 8",
  "g-area": "fill:rgba(227,167,47,.35);stroke:#E3A72F;stroke-width:1.4", "g-feature": "fill:none;stroke:#EFE6D2;stroke-width:2" };
const sc = ([x, y]) => [anchor[0] + (x - focus[0]) * k, anchor[1] + (y - focus[1]) * k];
let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="#0F2A3A"/><g transform="matrix(${k} 0 0 ${k} ${tx} ${ty})">`;
for (const p of C.paths) {
  const cls = p.cls.trim(); const st = css[cls] || css[cls.split(" ")[0]] || "fill:none;stroke:#fff";
  if (/g-highlight|g-disputed|g-route/.test(cls) && !show.has("highlights")) continue;
  svg += `<path d="${p.d}" style="${st}" vector-effect="non-scaling-stroke"/>`;
}
svg += "</g>";
if (show.has("labels")) for (const l of C.labels) { const [x, y] = sc([l.mx + (l.dx || 0), l.my + (l.dy || 0)]); const txt = (l.text || String(l.html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()).slice(0, 60); svg += `<text x="${x}" y="${y}" text-anchor="middle" font-family="DejaVu Sans" font-size="${l.cls === "policy" ? 22 : 28}" fill="#EFE6D2" opacity=".85">${txt.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</text>`; }
if (show.has("pins")) for (const p of C.pins) { const [x, y] = sc([p.mx, p.my]); svg += `<circle cx="${x}" cy="${y}" r="13" fill="#C8102E" stroke="#EFE6D2" stroke-width="4"/>` + (p.label ? `<rect x="${x + 22}" y="${y - 26}" width="${p.label.length * 19 + 28}" height="46" fill="#0B1620"/><rect x="${x + 22}" y="${y - 26}" width="6" height="46" fill="#C8102E"/><text x="${x + 40}" y="${y + 8}" font-family="DejaVu Sans Condensed" font-weight="bold" font-size="32" fill="#EFE6D2">${p.label}</text>` : ""); }
if (show.has("scalebar") && C.scalebar) { const at = (spec.scalebar && spec.scalebar.at) || [40, H - 60]; const px = C.scalebar.px * k; svg += `<rect x="${at[0]}" y="${at[1]}" width="${px}" height="8" fill="#EFE6D2"/><text x="${at[0]}" y="${at[1] + 36}" font-family="DejaVu Sans" font-size="24" fill="#EFE6D2">${C.scalebar.km.toLocaleString("en-US")} km at ${Math.round(C.scalebar.lat)}°</text>`; }
svg += `<text x="${W - 16}" y="${H - 16}" text-anchor="end" font-family="DejaVu Sans" font-size="20" fill="#EFE6D2" opacity=".6">${spec.projection} · ${C.kind} · k=${k}</text></svg>`;
fs.writeFileSync(out.replace(/\.png$/, ".svg"), svg);
// PIL rasteriser (reelkit/svgraster.py): ImageMagick's internal SVG renderer drops large clipped paths.
try { execFileSync("python3", [path.join(path.dirname(new URL(import.meta.url).pathname), "svgraster.py"), out.replace(/\.png$/, ".svg"), out]); console.log("wrote", out, `(${spec.projection}, ${C.kind}, k=${k}, ${C.paths.length} paths, ${C.pins.length} pins, ${C.labels.length} labels)`); }
catch (e) { console.log("wrote", out.replace(/\.png$/, ".svg"), "(rasteriser failed:", e.message.split("\n")[0] + ")"); }
