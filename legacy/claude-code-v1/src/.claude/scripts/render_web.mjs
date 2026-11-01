// Screenshot a pagina intera di un URL o file HTML a 1440 e 390 px (usato da render.py).
//   .claude/scripts/node .claude/scripts/render_web.mjs <url> <cartella> <prefisso>
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.env.DESIGN_AGENCY_NODE_MODULES || ".", "noop.js"));
const { chromium } = require("playwright");
const [url, out, stem] = process.argv.slice(2);
const browser = await chromium.launch();
for (const [width, scale] of [[1440, 1], [390, 2]]) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: scale });
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(out, `${stem}_w${width}.png`), fullPage: true });
  await page.close();
}
await browser.close();
