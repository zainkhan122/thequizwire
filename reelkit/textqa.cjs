// Readability probe for a HyperFrames composition (driven by reelkit/textqa.py — run that, not this).
// For sampled times: emulate clip windows + seek the GSAP timeline + seek videos, find every visible text unit,
// screenshot its box WITH text and with ONLY the glyphs hidden (plates/backgrounds stay) -> pairs for contrast math.
// node textqa.cjs <hf_dir> <out_dir> <t1,t2,...>
const fs = require("fs"), path = require("path");
const puppeteer = require("puppeteer-core");
const [hf, out, timesArg] = process.argv.slice(2);
const times = timesArg.split(",").map(Number);
const UNIT = ".tu,.tag,.cap,.stamp,.node,.strip,.kicker,.quote,.bigserif,.hr,.filmlabel,.filmcredit,.credit,.ename,.efollow," +
             ".clabel,.fivelabel,.bug,.waitbox,.counter,.startglow,.eklogo,.qby,.num,.title";
function chrome() {
  if (process.env.CHROME) return process.env.CHROME;
  const base = path.join(process.env.HOME, ".cache/hyperframes/chrome/chrome-headless-shell");
  for (const v of fs.readdirSync(base)) {
    const p = path.join(base, v, "chrome-headless-shell-linux64/chrome-headless-shell");
    if (fs.existsSync(p)) return p;
  }
  throw new Error("chrome-headless-shell not found");
}
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const b = await puppeteer.launch({ executablePath: chrome(), args: ["--no-sandbox", "--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required"] });
  const pg = await b.newPage();
  await pg.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  await pg.goto("file://" + path.resolve(hf, "index.html"), { waitUntil: "load" });
  await pg.evaluate(async () => { await document.fonts.ready; });
  await pg.addStyleTag({ content: ".__tqh,.__tqh *{color:transparent!important;text-shadow:none!important;-webkit-text-stroke:0 transparent!important}" });
  const meta = []; const last = {}; const seen = {};
  for (const t of times) {
    const units = await pg.evaluate(async (t, UNIT) => {
      const root = document.querySelector("[data-composition-id]");
      for (const el of document.querySelectorAll("[data-start]")) {
        if (el === root || el.tagName === "AUDIO") continue;
        const s = +el.dataset.start, d = +(el.dataset.duration || 1e9);
        const on = t >= s && t < s + d;
        el.style.display = on ? "" : "none";
        if (el.tagName === "VIDEO" && on) {
          el.pause(); const want = t - s + +(el.dataset.mediaStart || 0);
          if (Math.abs(el.currentTime - want) > 0.02) await new Promise(r => { el.onseeked = r; el.currentTime = want; setTimeout(r, 1500); });
        }
      }
      window.__timelines.main.seek(t, false);
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const op = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden") return 0; o *= +cs.opacity; } return o; };
      const found = new Map();
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n; (n = w.nextNode());) {
        if (!n.nodeValue.trim()) continue;
        const el = n.parentElement; if (!el || el.closest("script,style")) continue;
        const unit = el.closest(UNIT) || el;
        if (op(el) < 0.95) continue;
        const r = document.createRange(); r.selectNodeContents(n); const bb = r.getBoundingClientRect();
        if (bb.width < 2 || bb.height < 2 || bb.right < 0 || bb.bottom < 0 || bb.left > 1080 || bb.top > 1920) continue;
        if (!unit.id) unit.id = "tq" + Math.random().toString(36).slice(2, 8);
        const u = found.get(unit.id) || { id: unit.id, text: "", colors: [], box: [1e9, 1e9, -1e9, -1e9], size: 0,
          cls: String(unit.className || ""), spoken: !!unit.closest('.cap,[data-tq-spoken]'), dwellOff: !!unit.closest('[data-tq-dwell="off"]'), safeOff: !!unit.closest('[data-tq-safe="off"]') };
        u.text += n.nodeValue; const c = getComputedStyle(el).color; if (!u.colors.includes(c)) u.colors.push(c);
        u.size = Math.max(u.size, parseFloat(getComputedStyle(el).fontSize));
        const cs = getComputedStyle(el), sw = parseFloat(cs.webkitTextStrokeWidth || "0");
        if (sw >= 3) u.stroke = { w: sw, color: cs.webkitTextStrokeColor };
        u.box = [Math.min(u.box[0], bb.left), Math.min(u.box[1], bb.top), Math.max(u.box[2], bb.right), Math.max(u.box[3], bb.bottom)];
        found.set(unit.id, u);
      }
      return [...found.values()];
    }, t, UNIT);
    for (const u of units) {
      const sv = seen[u.id] || (seen[u.id] = { id: u.id, first: t, last: t, text: "", spoken: u.spoken, dwellOff: u.dwellOff, safeOff: u.safeOff, cls: u.cls, boxes: [] });
      sv.last = t; if (u.text.trim().length > sv.text.length) sv.text = u.text.trim();
      sv.boxes.push([t, u.box.map(Math.round)]);                     // per-sample box -> persistent dead-zone intrusions only
      if (process.env.TQ_LAYOUT_ONLY) continue;                       // layout-only: boxes are all we need (no screenshots)
      const key = u.id + "|" + u.text.trim();
      if (last[key] !== undefined && t - last[key] < 1.5) continue;
      last[key] = t;
      const x = Math.max(0, Math.floor(u.box[0]) - 4), y = Math.max(0, Math.floor(u.box[1]) - 4);
      const clip = { x, y, width: Math.min(1080, Math.ceil(u.box[2]) + 4) - x, height: Math.min(1920, Math.ceil(u.box[3]) + 4) - y };
      if (clip.width < 4 || clip.height < 4) continue;
      const tag = `${String(meta.length).padStart(4, "0")}`;
      await pg.screenshot({ path: path.join(out, tag + "_t.png"), clip });
      await pg.evaluate(id => document.getElementById(id).classList.add("__tqh"), u.id);
      await pg.screenshot({ path: path.join(out, tag + "_b.png"), clip });
      await pg.evaluate(id => document.getElementById(id).classList.remove("__tqh"), u.id);
      meta.push({ tag, t, id: u.id, text: u.text.trim().slice(0, 80), colors: u.colors, size: u.size, stroke: u.stroke, clip });
    }
  }
  fs.writeFileSync(path.join(out, "meta.json"), JSON.stringify(meta, null, 1));
  fs.writeFileSync(path.join(out, "seen.json"), JSON.stringify(Object.values(seen), null, 1));
  await b.close();
  console.log(`probed ${meta.length} text appearances at ${times.length} times`);
})().catch(e => { console.error(e); process.exit(2); });
