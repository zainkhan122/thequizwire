// Node unit test for engine/geo-runtime.js (compute only; DOM paths are covered by the smoke build + hfcheck).
import { createRequire } from "module"; import fs from "fs"; import path from "path"; import url from "url";
const here = path.dirname(url.fileURLToPath(import.meta.url)); const require = createRequire(import.meta.url);
const vend = path.join(here, "..", "engine", "vendor");
// resolve the vendored UMD bundles without node_modules
const Module = require("module"); const orig = Module._resolveFilename;
Module._resolveFilename = function (req, ...a) { const m = { "d3-geo": "d3-geo.min.js", "d3-array": "d3-array.min.js", "topojson-client": "topojson-client.min.js" }[req]; return m ? path.join(vend, m) : orig.call(this, req, ...a); };
const GeoRT = require(path.join(here, "..", "engine", "geo-runtime.js"));
const topo = JSON.parse(fs.readFileSync(path.join(here, "..", "engine", "data", "countries-110m.json")));
let fails = 0; const ok = (c, m) => { console.log((c ? "  ✓ " : "  ✗ ") + m); if (!c) fails++; };

// 1. flat map fitted to a bbox around South Asia, with pins + a disputed layer from GeoJSON + scalebar
const spec = { w: 1080, h: 1100, projection: "equalEarth", fit: { type: "bbox", bbox: [60, 5, 100, 38] }, padding: 40,
  layers: [{ kind: "land" }, { kind: "borders" }, { kind: "highlight", ids: ["356", "586"] },
    { kind: "disputed", source: "disputed", cls: "loc" }],
  pins: [{ id: "isb", lonlat: [73.05, 33.69], label: "Islamabad" }, { id: "del", lonlat: [77.21, 28.61], label: "New Delhi" }],
  labels: [{ id: "arab", lonlat: [65, 15], text: "Arabian Sea" }], scalebar: { km: 500, lonlat: [75, 20] } };
const data = { topo, geo: { disputed: { type: "FeatureCollection", features: [{ type: "Feature", id: "loc", properties: { controller: "India", claimants: ["Pakistan"] }, geometry: { type: "LineString", coordinates: [[73.9, 34.5], [74.6, 34.1], [75.9, 34.7], [76.9, 35.0]] } }] } } };
const C = GeoRT.compute(spec, data);
ok(C.paths.length === 5, `5 layers computed (highlight is per-feature by default) (${C.paths.map(p => p.id).join(", ")})`);
ok(C.paths.every(p => p.d.length > 0), "every layer has path data");
const land = C.paths[0].d.length, hl = C.paths.find(p => p.id === "highlight_356").d.length;
ok(land > 5000 && hl > 200 && hl < land, `land path ${land} chars, highlight India ${hl} chars`);
ok(C.paths.find(p => p.id === "disputed_loc").props.controller === "India", "disputed feature keeps properties (controller)");
const isb = C.pins[0], del = C.pins[1];
ok(isb.mx > 40 && isb.mx < 1040 && isb.my > 40 && isb.my < 1060, `Islamabad inside frame (${isb.mx.toFixed(0)},${isb.my.toFixed(0)})`);
ok(isb.mx < del.mx && isb.my < del.my, "Islamabad is north-west of Delhi on screen");
ok(C.scalebar && C.scalebar.px > 80 && C.scalebar.px < 200, `scalebar 500 km = ${C.scalebar.px.toFixed(1)} px`);
ok(C.proj.scale() > 800, `bbox fit really zooms in (scale ${C.proj.scale().toFixed(0)})`);
const wb = GeoRT.compute({ w: 1080, h: 1100, projection: "equalEarth", layers: [] }, data);
ok(C.proj.scale() > 3 * wb.proj.scale(), `bbox scale ≫ world scale (${wb.proj.scale().toFixed(0)})`);
// projection honesty table
ok(GeoRT.PROJ_KIND.mercator === "conformal" && GeoRT.PROJ_KIND.equalEarth === "equal-area", "projection kinds");
// 2. globe
const g = GeoRT.compute({ w: 1080, h: 1080, projection: "orthographic", rotate: [-70, -30, 0], layers: [{ kind: "sphere" }, { kind: "graticule" }, { kind: "land" }], pins: [{ id: "isb", lonlat: [73.05, 33.69] }, { id: "nyc", lonlat: [-74, 40.7] }] }, data);
ok(g.pins[0].vis === true && g.pins[1].vis === false, "globe back-face culling: Islamabad visible, New York hidden");
ok(g.paths[2].d.length > 1000, "globe land path");
// 3. features fit
const f = GeoRT.compute({ w: 1080, h: 1100, projection: "conicEqualArea", parallels: [20, 50], fit: { type: "features", ids: ["840"] }, layers: [{ kind: "countries", ids: ["840"] }] }, data);
ok(f.paths[0].d.length > 500, "fit to USA by id (conic equal-area)");
console.log(fails ? `FAIL ${fails}` : "all geo-runtime tests passed"); process.exit(fails ? 1 : 0);
