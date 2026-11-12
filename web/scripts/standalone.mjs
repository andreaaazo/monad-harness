/**
 * Completes the `output: "standalone"` build (ADR-0033). Next.js leaves the static files and `public/` out of the
 * standalone folder, though `server.js` must serve them: they are copied beside the server, as the documentation
 * says. Only next.config.mjs decides the build folder.
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
