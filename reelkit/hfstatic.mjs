// reelkit/hfstatic.mjs — run a built composition's scripts WITHOUT a browser (sandbox-friendly pre-flight).
//   node reelkit/hfstatic.mjs <hf_dir> [--json]
// What it does: loads the vendored runtime (gsap stub + real d3-geo/topojson/GeoRT), executes every inline <script>
// of index.html against a tiny fake DOM, and records each timeline op. FAIL on: a tween whose selector matches no
// element (static or created by GeoRT.mount), JS exceptions, forbidden non-determinism (Date/Math.random/timers/fetch),
// clip windows outside the composition, duplicate ids, missing composition contract attributes.
// It is NOT hyperframes check (no layout/contrast) — CI still runs reelkit/hfcheck.py; this catches 90 % earlier.
import fs from "fs"; import path from "path"; import vm from "vm"; import { createRequire } from "module";
const require = createRequire(import.meta.url);
const hf = path.resolve(process.argv[2] || "."); const asJson = process.argv.includes("--json");
const html = fs.readFileSync(path.join(hf, "index.html"), "utf8");
const F = [], W = [];

// ---------- static checks
const root = html.match(/<div id="root"[^>]*>/); if (!root) F.push("no #root composition element");
const total = root ? parseFloat((root[0].match(/data-duration="([\d.]+)"/) || [])[1]) : NaN;
if (!root || !/data-composition-id="main"/.test(root[0])) F.push('#root lacks data-composition-id="main"');
const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]);
const dup = ids.filter((x, i) => ids.indexOf(x) !== i); if (dup.length) F.push("duplicate ids: " + [...new Set(dup)].slice(0, 10).join(", "));
for (const m of html.matchAll(/<(?:div|audio|video)[^>]*class="[^"]*\bclip\b[^"]*"[^>]*>/g)) {
  const s = parseFloat((m[0].match(/data-start="([\d.]+)"/) || [])[1]), d = parseFloat((m[0].match(/data-duration="([\d.]+)"/) || [])[1]);
  const id = (m[0].match(/id="([^"]+)"/) || [])[1];
  if (!(s >= 0) || !(d > 0)) F.push(`clip ${id}: bad data-start/data-duration`);
  else if (s + d > total + 0.011) F.push(`clip ${id}: ends at ${(s + d).toFixed(2)} > composition ${total}`);
}
const scripts = [...html.matchAll(/<script(?:\s+type="([^"]*)")?(?:\s+id="([^"]*)")?[^>]*>([\s\S]*?)<\/script>/g)]
  .filter(m => !/\ssrc=/.test(m[0]));
const code = scripts.filter(m => !m[1] || m[1] === "text/javascript").map(m => m[3]).join("\n");
for (const bad of [/\bMath\.random\b/, /\bnew Date\b|\bDate\.now\b/, /\bsetTimeout\b|\bsetInterval\b|\brequestAnimationFrame\b/, /\bfetch\s*\(/])
  if (bad.test(code)) F.push("non-deterministic API in inline script: " + bad.source);
const ext = [...html.matchAll(/<script\s+src="([^"]+)"/g)].map(m => m[1]);
for (const s of ext) if (!fs.existsSync(path.join(hf, s))) F.push(`missing script file ${s}`);

// ---------- fake DOM
const idSet = new Set(ids);
function node(id, tag = "div") {
  const n = { id, tag, style: {}, attrs: {}, _cls: new Set(), children: [], textContent: "", _html: "",
    classList: { add: (c) => n._cls.add(c), remove: (c) => n._cls.delete(c), toggle: (c, f) => (f ? n._cls.add(c) : n._cls.delete(c)), contains: (c) => n._cls.has(c) },
    setAttribute: (k, v) => { n.attrs[k] = String(v); }, getAttribute: (k) => n.attrs[k], getTotalLength: () => 1000,
    querySelector: (q) => findSel(q), querySelectorAll: (q) => [findSel(q)].filter(Boolean) };
  Object.defineProperty(n, "innerHTML", { get: () => n._html, set: (v) => { n._html = v; for (const m of String(v).matchAll(/\sid="([^"]+)"/g)) { idSet.add(m[1]); nodes[m[1]] = nodes[m[1]] || node(m[1]); } } });
  return n;
}
const nodes = {}; for (const id of ids) nodes[id] = node(id);
function findSel(q) { const m = String(q).match(/#([\w-]+)/); if (!m) return node("_anon"); const id = m[1]; return idSet.has(id) ? nodes[id] : null; }
const document = { getElementById: (id) => (idSet.has(id) ? nodes[id] : null), querySelector: findSel, querySelectorAll: (q) => [findSel(q)].filter(Boolean),
  body: node("body"), fonts: { ready: Promise.resolve() } };
// inline JSON data blocks are reachable through getElementById(...).textContent
for (const m of scripts) if (m[1] === "application/json" && m[2]) { nodes[m[2]] = nodes[m[2]] || node(m[2], "script"); idSet.add(m[2]); nodes[m[2]].textContent = m[3]; }

// ---------- fake gsap (records + validates)
const ops = [];
function resolveTargets(t) {
  if (typeof t === "string") { const sels = t.split(",").map(s => s.trim()); const out = []; for (const s of sels) { const m = s.match(/#([\w-]+)/); if (!m || !idSet.has(m[1])) F.push(`tween target not found: '${s}'`); else out.push(nodes[m[1]]); } return out; }
  return [t];
}
const tween = (kind) => (target, a, b, c) => {
  const vars = kind === "fromTo" ? b : a; const at = kind === "fromTo" ? c : b;
  const tg = resolveTargets(target);
  ops.push({ kind, target: typeof target === "string" ? target : "<obj>", at, dur: vars && vars.duration });
  if (kind === "fromTo" && vars && vars.immediateRender !== false && typeof target === "string") W.push(`fromTo without immediateRender:false on ${target}`);
  if (vars && typeof vars.onUpdate === "function") {   // exercise proxy-driven updates (camera, counters) at the end state
    for (const t of tg) if (t && typeof t === "object" && !t.tag) for (const k of Object.keys(vars)) if (typeof vars[k] === "number" && !["duration", "delay", "repeat"].includes(k)) t[k] = vars[k];
    try { vars.onUpdate(); } catch (e) { F.push(`onUpdate threw for ${typeof target === "string" ? target : "proxy"}: ${e.message}`); }
  }
  return tl;
};
const tl = { to: tween("to"), from: tween("from"), fromTo: tween("fromTo"), set: tween("set"), seek: () => tl, add: () => tl, duration: () => total };
const gsap = { timeline: () => tl, to: tween("to"), set: tween("set"), registerPlugin: () => {} };

// ---------- run: vendored libs (real), then inline scripts in document order
const sandbox = { document, window: {}, console, JSON, Math, CSS: { escape: (s) => s }, gsap, self: undefined, globalThis: undefined };
sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const s of ext) {
  if (s === "gsap.min.js") continue;   // stubbed
  try { vm.runInContext(fs.readFileSync(path.join(hf, s), "utf8"), sandbox, { filename: s }); } catch (e) { F.push(`${s}: ${e.message}`); }
}
let i = 0;
for (const m of scripts) {
  if (m[1] && m[1] !== "text/javascript") continue;
  i++;
  try { vm.runInContext(m[3], sandbox, { filename: `inline-script-${i}` }); } catch (e) { F.push(`inline script ${i}: ${e.message}` + (e.stack ? " @ " + String(e.stack).split("\n")[1] : "")); }
}
if (!sandbox.__timelines || !sandbox.__timelines.main) F.push('window.__timelines["main"] not set');
const geoScenes = sandbox.GeoRT ? Object.keys(sandbox.GeoRT.scenes) : [];
const res = { fails: F, warns: W, ops: ops.length, total, geo_scenes: geoScenes, ids: idSet.size };
if (asJson) console.log(JSON.stringify(res, null, 1));
else {
  for (const x of W) console.log("  WARN  " + x);
  for (const x of F) console.log("  FAIL  " + x);
  console.log(`hfstatic: ${ops.length} timeline ops · ${idSet.size} elements · ${geoScenes.length} map scene(s) · total ${total}s → ${F.length ? "FAIL " + F.length : "OK"}`);
}
process.exit(F.length ? 1 : 0);
