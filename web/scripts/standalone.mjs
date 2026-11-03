/**
 * Completa la build `output: "standalone"` (ADR-0033). Next.js lascia fuori dalla cartella standalone i file
 * statici e `public/`, che `server.js` deve servire: si copiano accanto al server, come dice la documentazione.
 * La cartella della build la decide solo next.config.mjs.
 */
import { cpSync, existsSync, rmSync } from "node:fs";
import { join } from "node:path";

import config from "../next.config.mjs";

const root = new URL("..", import.meta.url).pathname;
const dist = config.distDir;
const standalone = join(root, dist, "standalone");

if (!existsSync(join(standalone, "server.js"))) {
  console.error(`manca ${join(dist, "standalone", "server.js")}: serve next build con output 'standalone'`);
  process.exit(1);
}
for (const [from, to] of [
  [join(root, dist, "static"), join(standalone, dist, "static")],
  [join(root, "public"), join(standalone, "public")],
]) {
  if (!existsSync(from)) continue;
  rmSync(to, { recursive: true, force: true });
  cpSync(from, to, { recursive: true });
}
console.log(`server standalone pronto in ${join(dist, "standalone")}`);
