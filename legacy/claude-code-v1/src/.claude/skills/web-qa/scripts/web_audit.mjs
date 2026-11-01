// Audit di una pagina web a più breakpoint: screenshot, overflow orizzontale, axe (WCAG 2.2 AA),
// target interattivi < 24px, testo < 12px, immagini senza alt, font non caricati, errori console
// e richieste fallite, LCP e CLS di laboratorio, screenshot con prefers-reduced-motion.
//
//   .claude/scripts/node .claude/skills/web-qa/scripts/web_audit.mjs <url|file.html> --out proofs/web \
//        [--widths 360,768,1280,1920] [--lighthouse]
//
// Esce con 1 se trova violazioni axe serious/critical, overflow, errori console o richieste fallite.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const require = createRequire(join(process.env.DESIGN_AGENCY_NODE_MODULES || ".", "noop.js"));
const { chromium } = require("playwright");
const { default: AxeBuilder } = require("@axe-core/playwright");

const args = process.argv.slice(2);
const target = args.find((a) => !a.startsWith("--") && args[args.indexOf(a) - 1] !== "--out" && args[args.indexOf(a) - 1] !== "--widths");
const opt = (name, dflt) => (args.includes(name) ? args[args.indexOf(name) + 1] : dflt);
if (!target) {
  console.error("uso: web_audit.mjs <url|file.html> --out DIR [--widths 360,768,1280,1920] [--lighthouse]");
  process.exit(2);
}
const url = /^https?:|^file:/.test(target) ? target : pathToFileURL(resolve(target)).href;
const out = resolve(opt("--out", "web-audit"));
const widths = opt("--widths", "360,768,1280,1920").split(",").map(Number);
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const report = { url, viewports: [], failures: [] };

for (const width of widths) {
  const height = width < 768 ? 800 : 900;
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: width < 768 ? 2 : 1 });
  const page = await context.newPage();
  const consoleErrors = [];
  const failed = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  page.on("requestfailed", (r) => failed.push(`${r.url()} — ${r.failure()?.errorText}`));
  await page.addInitScript(() => {
    window.__cls = 0;
    window.__lcp = 0;
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
      .observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((l) => { const e = l.getEntries().at(-1); if (e) window.__lcp = e.startTime; })
      .observe({ type: "largest-contentful-paint", buffered: true });
  });
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);

  const metrics = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const overflow = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > vw + 1 || r.left < -1) && getComputedStyle(el).position !== "fixed") {
        overflow.push(`${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : ""} (${Math.round(r.left)}→${Math.round(r.right)})`);
      }
    }
    const interactive = [...document.querySelectorAll("a[href], button, input, select, textarea, [role=button], [tabindex]:not([tabindex='-1'])")];
    const smallTargets = interactive.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && (r.width < 24 || r.height < 24);
    }).map((el) => `${el.tagName.toLowerCase()} "${(el.innerText || el.getAttribute("aria-label") || "").trim().slice(0, 30)}" ${Math.round(el.getBoundingClientRect().width)}×${Math.round(el.getBoundingClientRect().height)}`);
    const smallText = new Set();
    for (const el of document.querySelectorAll("body *")) {
      if (!el.childNodes.length || ![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < 12) smallText.add(`${el.tagName.toLowerCase()} ${fs}px "${el.textContent.trim().slice(0, 30)}"`);
    }
    const families = new Set();
    for (const el of document.querySelectorAll("body *")) families.add(getComputedStyle(el).fontFamily.split(",")[0].trim().replace(/["']/g, ""));
    const generic = new Set(["serif", "sans-serif", "monospace", "system-ui", "cursive", "fantasy", "inherit", "-apple-system"]);
    // document.fonts.check() è true anche per famiglie inesistenti: si misura il testo renderizzato.
    // Se la larghezza con la famiglia coincide con quella dei fallback generici, la famiglia non c'è.
    const ctx = document.createElement("canvas").getContext("2d");
    const probe = "mmmmmmmmmmlliWWQ@#0123456789";
    const width = (font) => { ctx.font = font; return ctx.measureText(probe).width; };
    const notLoaded = [...families].filter((f) => !generic.has(f) &&
      ["monospace", "serif"].every((g) => width(`72px "${f}", ${g}`) === width(`72px ${g}`)));
    const noAlt = [...document.images].filter((i) => !i.hasAttribute("alt")).map((i) => i.currentSrc || i.src);
    return {
      scrollWidth: document.documentElement.scrollWidth, clientWidth: vw,
      overflow: overflow.slice(0, 15), smallTargets: smallTargets.slice(0, 20), smallText: [...smallText].slice(0, 15),
      fontsNotLoaded: notLoaded, imagesWithoutAlt: noAlt.slice(0, 15),
      lcpMs: Math.round(window.__lcp), cls: Number(window.__cls.toFixed(4)),
    };
  });

  await page.screenshot({ path: join(out, `w${width}.png`), fullPage: true });
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  const violations = axe.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload({ waitUntil: "networkidle" });
  await page.screenshot({ path: join(out, `w${width}_reduced-motion.png`), fullPage: false });

  const vp = { width, ...metrics, consoleErrors, failedRequests: failed, axe: violations };
  report.viewports.push(vp);
  if (metrics.scrollWidth > metrics.clientWidth + 1) report.failures.push(`${width}px: overflow orizzontale (${metrics.scrollWidth} > ${metrics.clientWidth})`);
  for (const v of violations) if (v.impact === "serious" || v.impact === "critical") report.failures.push(`${width}px: axe ${v.impact} ${v.id} (${v.nodes})`);
  if (consoleErrors.length) report.failures.push(`${width}px: ${consoleErrors.length} errori console`);
  if (failed.length) report.failures.push(`${width}px: ${failed.length} richieste fallite`);
  if (metrics.fontsNotLoaded.length) report.failures.push(`${width}px: font non caricati ${metrics.fontsNotLoaded.join(", ")}`);
  await context.close();
}

if (args.includes("--lighthouse")) {
  const chrome = chromium.executablePath();
  const lh = spawnSync("lighthouse", [url, "--quiet", "--output=json", `--output-path=${join(out, "lighthouse.json")}`,
    "--chrome-flags=--headless=new --no-sandbox", "--only-categories=performance,accessibility,best-practices,seo"],
  { env: { ...process.env, CHROME_PATH: chrome }, encoding: "utf8" });
  report.lighthouse = lh.status === 0 ? join(out, "lighthouse.json") : `fallito: ${(lh.stderr || "").slice(-400)}`;
}
await browser.close();

writeFileSync(join(out, "web_audit.json"), JSON.stringify(report, null, 2));
for (const vp of report.viewports) {
  console.log(`${vp.width}px  LCP ${vp.lcpMs}ms  CLS ${vp.cls}  axe ${vp.axe.length}  target<24 ${vp.smallTargets.length}  testo<12 ${vp.smallText.length}  no-alt ${vp.imagesWithoutAlt.length}`);
}
for (const f of report.failures) console.log(`ERRORE ${f}`);
console.log(`${report.failures.length ? "FAIL" : "PASS"} — dettagli e screenshot in ${out}`);
process.exit(report.failures.length ? 1 : 0);
