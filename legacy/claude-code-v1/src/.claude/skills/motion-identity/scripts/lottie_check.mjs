// Verifica che un Lottie esportato si renda davvero con lottie-web (il player più diffuso sul web):
// metadati, feature a rischio (espressioni, effetti, maschere, livelli immagine/testo), errori di rendering,
// frame campione in PNG da confrontare con il master.
//
//   .claude/scripts/node .claude/skills/motion-identity/scripts/lottie_check.mjs anim.json --out proofs/lottie [--frames 0,0.5,1]
//
// --frames: posizioni normalizzate 0–1 sulla durata. Esce con 1 su errori di caricamento o rendering.
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve, join } from "node:path";

const require = createRequire(join(process.env.DESIGN_AGENCY_NODE_MODULES || ".", "noop.js"));
const { chromium } = require("playwright");
const lottiePath = require.resolve("lottie-web/build/player/lottie.min.js");

const args = process.argv.slice(2);
const file = args[0];
const opt = (n, d) => (args.includes(n) ? args[args.indexOf(n) + 1] : d);
if (!file) { console.error("uso: lottie_check.mjs anim.json --out DIR [--frames 0,0.5,1]"); process.exit(2); }
const out = resolve(opt("--out", "lottie-check"));
const positions = opt("--frames", "0,0.25,0.5,0.75,1").split(",").map(Number);
mkdirSync(out, { recursive: true });

const data = JSON.parse(readFileSync(file, "utf8"));
const risks = new Set();
(function walk(node) {
  if (Array.isArray(node)) return node.forEach(walk);
  if (node && typeof node === "object") {
    if (typeof node.x === "string") risks.add("espressioni (supporto variabile tra player)");
    if (Array.isArray(node.ef) && node.ef.length) risks.add("effetti di livello (spesso ignorati dai player)");
    if (node.hasMask) risks.add("maschere (costo di rendering, differenze tra player)");
    if (node.ty === 2) risks.add("livelli immagine (asset esterni o incorporati)");
    if (node.ty === 5) risks.add("livelli testo (font da incorporare o convertire in forme)");
    Object.values(node).forEach(walk);
  }
})(data);

const meta = { file, version: data.v, fps: data.fr, inPoint: data.ip, outPoint: data.op, size: [data.w, data.h],
  durationS: Number(((data.op - data.ip) / data.fr).toFixed(3)), layers: (data.layers || []).length,
  assets: (data.assets || []).length, risks: [...risks] };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: data.w, height: data.h } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.setContent(`<html><body style="margin:0;background:transparent"><div id="a" style="width:${data.w}px;height:${data.h}px"></div></body></html>`);
await page.addScriptTag({ path: lottiePath });
const loaded = await page.evaluate((anim) => new Promise((ok) => {
  const a = window.lottie.loadAnimation({ container: document.getElementById("a"), renderer: "svg", loop: false, autoplay: false, animationData: anim });
  window.__anim = a;
  a.addEventListener("DOMLoaded", () => ok({ ok: true, frames: a.totalFrames }));
  a.addEventListener("data_failed", () => ok({ ok: false }));
  setTimeout(() => ok({ ok: false, timeout: true }), 10000);
}), data);
if (!loaded.ok) errors.push("animazione non caricata" + (loaded.timeout ? " (timeout)" : ""));
const shots = [];
if (loaded.ok) {
  for (const pos of positions) {
    const frame = Math.min(loaded.frames - 1, Math.max(0, Math.round(pos * (loaded.frames - 1))));
    await page.evaluate((f) => window.__anim.goToAndStop(f, true), frame);
    const path = join(out, `frame_${String(frame).padStart(4, "0")}.png`);
    await page.locator("#a").screenshot({ path, omitBackground: true });
    shots.push(path);
  }
}
await browser.close();

const report = { ...meta, rendered: loaded.ok, totalFrames: loaded.frames, frames: shots, errors };
writeFileSync(join(out, "lottie_check.json"), JSON.stringify(report, null, 2));
console.log(`${file}: ${meta.size.join("×")} @ ${meta.fps}fps, ${meta.durationS}s, ${meta.layers} livelli, ${meta.assets} asset`);
for (const r of meta.risks) console.log(`AVVISO ${r}`);
for (const e of errors) console.log(`ERRORE ${e}`);
console.log(`${errors.length ? "FAIL" : "PASS"} — ${shots.length} frame in ${out}`);
process.exit(errors.length ? 1 : 0);
