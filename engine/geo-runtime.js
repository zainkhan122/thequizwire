/* engine/geo-runtime.js — QuizWire map runtime (browser + Node). Own work, MIT-compatible with the repo licence.
 *
 * Pure compute + DOM mount for the `map` / `globe` motion types. Driven by a scene spec written by engine/geo.py
 * (which itself reads the episode's geo.json — the single source of truth for every map beat).
 *
 *   GeoRT.compute(spec, data)   -> projection, path strings, pin/label positions (no DOM; unit-tested in Node)
 *   GeoRT.mount(id, spec, data) -> fills #<id> (SVG layers + HTML label plates), registers a camera proxy
 *   GeoRT.cam(id)               -> the proxy object GSAP tweens ({k, x, y} flat · {lon, lat, k} globe)
 *   GeoRT.camTarget(id, vars)   -> GSAP vars for a camera move: {k, lonlat|bbox, duration, ease} -> {k, x, y, onUpdate}
 *   GeoRT.apply(id)             -> writes the camera to the DOM (called from tween onUpdate, and once at mount)
 *
 * Determinism: no Date, no Math.random, no async — data is inline JSON, everything is computed synchronously at
 * script time so the paused GSAP timeline sees a finished DOM. Flat maps move a single <g transform=matrix()>
 * (strokes use vector-effect:non-scaling-stroke so line weights stay constant); labels/pins are HTML children
 * positioned in screen space every update, so type never scales with the map. Globes re-project every update.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("d3-geo"), require("topojson-client"));
  else root.GeoRT = factory(root.d3, root.topojson);
})(typeof self !== "undefined" ? self : this, function (d3, topojson) {
  "use strict";
  const PROJ = {
    mercator: () => d3.geoMercator(),
    equalEarth: () => d3.geoEqualEarth(),
    naturalEarth1: () => d3.geoNaturalEarth1(),
    equirectangular: () => d3.geoEquirectangular(),
    orthographic: () => d3.geoOrthographic().clipAngle(90),
    azimuthalEqualArea: () => d3.geoAzimuthalEqualArea(),
    conicConformal: () => d3.geoConicConformal(),
    conicEqualArea: () => d3.geoConicEqualArea(),
    albers: () => d3.geoAlbers(),
    stereographic: () => d3.geoStereographic().clipAngle(120),
  };
  // Honest-use table (geolint enforces it): equal-area for size/area claims, conformal only for shape/navigation.
  const PROJ_KIND = { mercator: "conformal", conicConformal: "conformal", stereographic: "conformal",
    equalEarth: "equal-area", azimuthalEqualArea: "equal-area", conicEqualArea: "equal-area", albers: "equal-area",
    naturalEarth1: "compromise", equirectangular: "compromise", orthographic: "perspective" };

  function bboxFeature(b) {   // [w, s, e, n] -> GeoJSON polygon (densified so projections curve it properly)
    // d3-geo polygons are spherical: the exterior ring must run CLOCKWISE (west edge northwards first), otherwise
    // the ring encloses the rest of the planet and fitExtent silently fits the whole world (found by the unit test).
    const [w, s, e, n] = b, ring = [], N = 24;
    for (let i = 0; i <= N; i++) ring.push([w, s + (n - s) * i / N]);
    for (let i = 0; i <= N; i++) ring.push([w + (e - w) * i / N, n]);
    for (let i = 0; i <= N; i++) ring.push([e, n - (n - s) * i / N]);
    for (let i = 0; i <= N; i++) ring.push([e - (e - w) * i / N, s]);
    return { type: "Polygon", coordinates: [ring] };
  }

  function featuresOf(data, layer) {
    // data.topo: TopoJSON (world-atlas style). data.geo[name]: GeoJSON FeatureCollections supplied by geo.json.
    if (layer.geojson) return layer.geojson.features || [layer.geojson];
    if (layer.source && data.geo && data.geo[layer.source]) return data.geo[layer.source].features;
    const topo = data.topo, obj = layer.object || (layer.kind === "land" ? "land" : "countries");
    if (!topo) return [];
    if (!topo.objects[obj] && obj === "land" && topo.objects.countries)   // scene files carry countries only: merge them
      return [{ type: "Feature", id: "land", properties: {}, geometry: topojson.merge(topo, topo.objects.countries.geometries) }];
    if (!topo.objects[obj]) return [];
    let fs = topojson.feature(topo, topo.objects[obj]).features;
    if (layer.ids) { const want = new Set(layer.ids.map(String)); fs = fs.filter(f => want.has(String(f.id)) || want.has(String(f.properties && f.properties.name))); }
    return fs;
  }

  function fitProjection(spec, data) {
    const W = spec.w, H = spec.h, pad = spec.padding == null ? 40 : spec.padding;
    const proj = (PROJ[spec.projection] || PROJ.equalEarth)();
    if (spec.parallels && proj.parallels) proj.parallels(spec.parallels);
    const fit = spec.fit || { type: "world" };
    const extent = [[pad, pad], [W - pad, H - pad]];
    if (spec.projection === "orthographic") {
      proj.rotate(spec.rotate || [0, 0, 0]).translate([W / 2, H / 2]).scale(spec.scale || Math.min(W, H) / 2 - pad);
    } else if (fit.type === "bbox") {
      if (spec.rotate) proj.rotate(spec.rotate);
      proj.fitExtent(extent, bboxFeature(fit.bbox));
    } else if (fit.type === "features") {
      if (spec.rotate) proj.rotate(spec.rotate);
      const fs = featuresOf(data, { object: fit.object || "countries", ids: fit.ids });
      proj.fitExtent(extent, { type: "FeatureCollection", features: fs });
    } else {
      if (spec.rotate) proj.rotate(spec.rotate);
      proj.fitExtent(extent, { type: "Sphere" });
    }
    if (spec.scaleMul) proj.scale(proj.scale() * spec.scaleMul);
    if (spec.centerOffset) { const t = proj.translate(); proj.translate([t[0] + spec.centerOffset[0], t[1] + spec.centerOffset[1]]); }
    // Clip far-away geometry (flat maps): shorter paths, and renderers never see coordinates thousands of px out.
    // Margin = clipMargin × viewport each side (default 1.0 → camera zoom-outs down to k≈0.33 stay seamless).
    if (spec.projection !== "orthographic" && spec.clipMargin !== null) {
      const cm = spec.clipMargin == null ? 1.0 : spec.clipMargin;
      proj.clipExtent([[-W * cm, -H * cm], [W * (1 + cm), H * (1 + cm)]]);
    }
    return proj;
  }

  function layerPaths(spec, data, proj) {
    const path = d3.geoPath(proj), out = [];
    for (const L of spec.layers || []) {
      if (L.kind === "sphere") { out.push({ id: L.id || "sphere", cls: "g-sphere " + (L.cls || ""), d: path({ type: "Sphere" }) || "" }); continue; }
      if (L.kind === "graticule") { out.push({ id: L.id || "grat", cls: "g-grat " + (L.cls || ""), d: path(d3.geoGraticule().step(L.step || [15, 15])()) || "" }); continue; }
      if (L.kind === "borders") {
        const topo = data.topo, obj = L.object || "countries";
        if (topo && topo.objects[obj]) {
          const mesh = topojson.mesh(topo, topo.objects[obj], (a, b) => a !== b);
          out.push({ id: L.id || "borders", cls: "g-border " + (L.cls || ""), d: path(mesh) || "" });
        }
        continue;
      }
      const fs = featuresOf(data, L);
      if (L.kind === "highlight" && L.lift) {                                 // v3: lifted shape (flag or colour), one group per feature
        const fb = spec.fit && spec.fit.bbox ? path.bounds(bboxFeature(spec.fit.bbox)) : [[0, 0], [spec.w, spec.h]];
        const bw = fb[1][0] - fb[0][0], bh = fb[1][1] - fb[0][1];
        const wide = { x: fb[0][0] - bw * 0.5, y: fb[0][1] - bh * 0.5, w: bw * 2, h: bh * 2 };
        fs.forEach((f, i) => {
          const b = path.bounds(f), fw = b[1][0] - b[0][0], fh = b[1][1] - b[0][1];
          const sane = isFinite(fw) && isFinite(fh) && fw > 0 && fh > 0 && fw < bw * 3 && fh < bh * 3;        // antimeridian / world-spanning features fall back to the wide rect
          const rect = sane ? { x: b[0][0], y: b[0][1], w: fw, h: fh } : wide;
          const fit = L.flag_fit === "cover" || !sane ? "xMidYMid slice" : "none";                          // default: the flag is stretched into the shape (reference-channel look)
          out.push({ id: (L.id || L.kind) + "_" + (f.id != null ? f.id : (f.properties && f.properties.id) || i), cls: "g-lift " + (L.cls || ""), d: path(f) || "",
            lift: { kind: L.lift, flag: L.flag, color: L.color || "#C8102E", rect, fit, centroid: path.centroid(f) }, props: f.properties || {} });
        });
        continue;
      }
      if (L.kind === "highlight" || L.kind === "disputed" || L.kind === "route" || L.kind === "area" || L.kind === "feature") {
        if (L.perFeature === false) out.push({ id: L.id, cls: "g-" + L.kind + " " + (L.cls || ""), d: path({ type: "FeatureCollection", features: fs }) || "" });
        else fs.forEach((f, i) => out.push({ id: (L.id || L.kind) + "_" + (f.id != null ? f.id : (f.properties && f.properties.id) || i), cls: "g-" + L.kind + " " + (L.cls || ""), d: path(f) || "", props: f.properties || {} }));
      } else { // land / countries: one merged path (small DOM, fast seeks)
        out.push({ id: L.id || L.kind, cls: "g-" + L.kind + " " + (L.cls || ""), d: path({ type: "FeatureCollection", features: fs }) || "" });
      }
    }
    return out;
  }

  function visibleOnGlobe(proj, lonlat) {
    const r = proj.rotate(), c = [-r[0], -r[1]];
    return d3.geoDistance(lonlat, c) < Math.PI / 2 - 0.02;
  }

  function points(spec, proj) {
    const pin = (p) => { const xy = proj(p.lonlat) || [NaN, NaN]; return { ...p, mx: xy[0], my: xy[1], vis: spec.projection === "orthographic" ? visibleOnGlobe(proj, p.lonlat) : true }; };
    return { pins: (spec.pins || []).map(pin), labels: (spec.labels || []).map(pin) };
  }

  function scalebar(spec, proj) {
    const sb = spec.scalebar; if (!sb) return null;
    const at = sb.lonlat || (spec.fit && spec.fit.bbox ? [(spec.fit.bbox[0] + spec.fit.bbox[2]) / 2, (spec.fit.bbox[1] + spec.fit.bbox[3]) / 2] : [0, 0]);
    const km = sb.km || 500, dLon = km / (111.32 * Math.cos(at[1] * Math.PI / 180));
    const a = proj(at), b = proj([at[0] + dLon, at[1]]);
    if (!a || !b) return null;
    return { km, px: Math.hypot(b[0] - a[0], b[1] - a[1]), lat: at[1] };
  }

  function compute(spec, data) {
    const proj = fitProjection(spec, data || {});
    const paths = layerPaths(spec, data || {}, proj);
    const pts = points(spec, proj);
    return { proj, paths, pins: pts.pins, labels: pts.labels, scalebar: scalebar(spec, proj), kind: PROJ_KIND[spec.projection] || "unknown" };
  }

  // ------------------------------------------------------------------ DOM (browser only)
  const scenes = {};
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function mount(id, spec, data) {
    const el = document.getElementById(id); if (!el) throw new Error("GeoRT.mount: no element #" + id);
    const C = compute(spec, data);
    const W = spec.w, H = spec.h;
    const liftMarkup = (p) => {
      const pid = id + "_" + p.id, L = p.lift, r = L.rect, flag = L.flag && data && data.flags ? data.flags[L.flag.toLowerCase()] : null;
      const body = flag ? `<image href="${flag}" x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" preserveAspectRatio="${L.fit || "none"}" clip-path="url(#${pid}_clip)"></image>`
                        : `<path class="lift-fill" d="${p.d}" style="fill:${L.color}"></path>`;
      return `<g id="${pid}" class="${p.cls.trim()}" data-cx="${L.centroid[0].toFixed(1)}" data-cy="${L.centroid[1].toFixed(1)}"><defs><clipPath id="${pid}_clip"><path d="${p.d}"></path></clipPath></defs>` +
             `<path class="lift-shadow" d="${p.d}" filter="url(#${id}_liftShadow)"></path>${body}<path class="lift-outline" d="${p.d}" vector-effect="non-scaling-stroke"></path></g>`;
    };
    const svgLayers = `<defs><filter id="${id}_liftShadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000" flood-opacity="0.6"></feDropShadow></filter></defs>` +
      C.paths.map(p => p.lift ? liftMarkup(p) : `<path id="${id}_${p.id}" class="${p.cls.trim()}" d="${p.d}" vector-effect="non-scaling-stroke"></path>`).join("");
    let raster = "";
    if (data && data.basemap && spec.projection === "mercator") {          // v3: PD raster (Web Mercator tiles) aligned under the fitted projection
      const ref = spec.fit && spec.fit.bbox ? [(spec.fit.bbox[0] + spec.fit.bbox[2]) / 2, (spec.fit.bbox[1] + spec.fit.bbox[3]) / 2] : [0, 0];
      const place = (bm, sfx) => {                                           // same Mercator, different scale: matrix() maps raster px → scene px
        const bp = d3.geoMercator().scale(bm.scale).translate(bm.translate), f = C.proj.scale() / bm.scale;
        const a = C.proj(ref), b = bp(ref), ox = a[0] - f * b[0], oy = a[1] - f * b[1];
        return `<image id="${id}_basemap${sfx}" class="geo-basemap" href="${bm.src}" width="${bm.size[0]}" height="${bm.size[1]}" transform="matrix(${f} 0 0 ${f} ${ox} ${oy})" preserveAspectRatio="none"></image>`;
      };
      raster = (data.basemap.far ? place(data.basemap.far, "_far") : "") + place(data.basemap, "");
      el.classList.add("has-basemap");
    }
    el.innerHTML = `<svg class="geo-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><g id="${id}_cam">${raster}${svgLayers}</g></svg><div class="geo-ui" id="${id}_ui"></div>`;
    const ui = el.querySelector(".geo-ui");
    const html = [];
    for (const p of C.pins) html.push(`<div class="geo-pin ${p.cls || ""}${p.side === "left" ? " left" : ""}" id="${id}_pin_${p.id}" style="visibility:hidden;opacity:0" data-layout-allow-overlap="true"><div class="pinhead"></div>${p.label ? `<div class="pinlabel tu" data-layout-allow-overlap="true" data-layout-allow-occlusion="true">${esc(p.label)}</div>` : ""}</div>`);
    for (const l of C.labels) html.push(`<div class="geo-label tu ${l.cls || ""}" id="${id}_lbl_${l.id}" style="visibility:hidden;opacity:0" data-layout-allow-overlap="true" data-layout-allow-occlusion="true">${l.html ? l.html.replace(/^<div class="plate"/, '<div class="plate" data-layout-allow-overlap="true" data-layout-allow-occlusion="true"') : ("<span data-layout-allow-overlap=\"true\" data-layout-allow-occlusion=\"true\">" + esc(l.text || "") + "</span>")}</div>`);   // span = centred on the anchor (CSS translate(-50%,-50%)), like the SVG preview
    if (C.scalebar) html.push(`<div class="geo-scale tu" id="${id}_scale" data-km="${C.scalebar.km}" data-layout-allow-overlap="true" data-layout-allow-occlusion="true"><div class="bar"></div><span>${C.scalebar.km.toLocaleString("en-US")} km at ${Math.round(C.scalebar.lat)}°</span></div>`);
    ui.innerHTML = html.join("");
    const S = { id, spec, data, C, W, H, el,
      anchor: spec.anchor || [W / 2, H / 2],
      cam: spec.projection === "orthographic"
        ? { lon: (spec.rotate || [0, 0])[0], lat: (spec.rotate || [0, 0])[1], k: 1 }
        : { k: 1, x: W / 2, y: H / 2 },
      g: el.querySelector("#" + id + "_cam"),
      pinEls: C.pins.map(p => el.querySelector("#" + id + "_pin_" + p.id)),
      lblEls: C.labels.map(l => el.querySelector("#" + id + "_lbl_" + l.id)),
      scaleEl: C.scalebar ? el.querySelector("#" + id + "_scale") : null };
    if (spec.scalebar && spec.scalebar.at && S.scaleEl) { S.scaleEl.style.left = spec.scalebar.at[0] + "px"; S.scaleEl.style.top = spec.scalebar.at[1] + "px"; S.scaleEl.style.bottom = "auto"; }
    scenes[id] = S;
    apply(id);
    return S;
  }

  function screenXY(S, mx, my) {
    const c = S.cam; return [S.anchor[0] + (mx - c.x) * c.k, S.anchor[1] + (my - c.y) * c.k];
  }

  function apply(id) {
    const S = scenes[id]; if (!S) return;
    if (S.spec.projection === "orthographic") {
      // re-project: rotate + scale the globe (k multiplies the fitted radius)
      const proj = S.C.proj, base = S.baseScale || (S.baseScale = proj.scale());
      proj.rotate([S.cam.lon, S.cam.lat, (S.spec.rotate || [0, 0, 0])[2] || 0]).scale(base * S.cam.k);
      const paths = layerPaths(S.spec, S.data, proj);
      for (const p of paths) { const e = S.g.querySelector("#" + CSS.escape(id + "_" + p.id)); if (e) e.setAttribute("d", p.d); }
      const pts = points(S.spec, proj);
      pts.pins.forEach((p, i) => { const e = S.pinEls[i]; if (!e) return; e.style.left = p.mx + "px"; e.style.top = p.my + "px"; e.classList.toggle("back", !p.vis); });
      pts.labels.forEach((l, i) => { const e = S.lblEls[i]; if (!e) return; e.style.left = l.mx + "px"; e.style.top = l.my + "px"; e.classList.toggle("back", !l.vis); });
      return;
    }
    const c = S.cam, tx = S.anchor[0] - c.x * c.k, ty = S.anchor[1] - c.y * c.k;
    S.g.setAttribute("transform", `matrix(${c.k} 0 0 ${c.k} ${tx} ${ty})`);
    S.C.pins.forEach((p, i) => { const e = S.pinEls[i]; if (!e) return; const [x, y] = screenXY(S, p.mx, p.my); e.style.left = x + "px"; e.style.top = y + "px"; });
    S.C.labels.forEach((l, i) => { const e = S.lblEls[i]; if (!e) return; const [x, y] = screenXY(S, l.mx + (l.dx || 0), l.my + (l.dy || 0)); e.style.left = x + "px"; e.style.top = y + "px"; });
    if (S.scaleEl) { const bar = S.scaleEl.querySelector(".bar"); if (bar) bar.style.width = (S.C.scalebar.px * c.k) + "px"; }
  }

  function focus(id, where) {   // where: {lonlat:[..]} | {bbox:[w,s,e,n]} | {xy:[mx,my]}
    const S = scenes[id]; const proj = S.C.proj;
    if (where.xy) return { x: where.xy[0], y: where.xy[1] };
    if (where.lonlat) { const p = proj(where.lonlat); return { x: p[0], y: p[1] }; }
    if (where.bbox) {
      const b = d3.geoPath(proj).bounds(bboxFeature(where.bbox));
      return { x: (b[0][0] + b[1][0]) / 2, y: (b[0][1] + b[1][1]) / 2, w: b[1][0] - b[0][0], h: b[1][1] - b[0][1] };
    }
    return { x: S.W / 2, y: S.H / 2 };
  }

  function camTarget(id, v) {
    // v: {k?, lonlat?|bbox?|xy?, fitPad?, duration, ease, lon?, lat?}  ->  GSAP vars object for tl.to(GeoRT.cam(id), ...)
    const S = scenes[id], out = { duration: v.duration == null ? 1 : v.duration, ease: v.ease || "power2.inOut", onUpdate: () => apply(id) };
    if (S.spec.projection === "orthographic") {
      if (v.lonlat) { out.lon = -v.lonlat[0]; out.lat = -v.lonlat[1]; }
      if (v.lon != null) out.lon = v.lon; if (v.lat != null) out.lat = v.lat;
      if (v.k != null) out.k = v.k;
      return out;
    }
    const f = focus(id, v);
    out.x = f.x; out.y = f.y;
    if (v.bbox && v.k == null) { const pad = v.fitPad == null ? 0.82 : v.fitPad; out.k = Math.min(S.W / f.w, S.H / f.h) * pad; }
    else if (v.k != null) out.k = v.k;
    return out;
  }

  function centroid(id, pathId) {   // "x y" in SVG user units for GSAP svgOrigin (lift pops scale about the feature)
    const S = scenes[id]; const e = S && S.g.querySelector("#" + CSS.escape(id + "_" + pathId));
    return e && e.dataset && e.dataset.cx ? `${e.dataset.cx} ${e.dataset.cy}` : "0 0";
  }
  function cam(id) { return scenes[id].cam; }
  function setCam(id, v) { Object.assign(scenes[id].cam, camTarget(id, { ...v, duration: 0 })); apply(id); }
  function pathLength(id, layerId) { const e = scenes[id].g.querySelector("#" + CSS.escape(id + "_" + layerId)); return e && e.getTotalLength ? e.getTotalLength() : 0; }

  return { compute, mount, apply, cam, camTarget, setCam, focus, pathLength, centroid, bboxFeature, PROJ_KIND, scenes };
});
