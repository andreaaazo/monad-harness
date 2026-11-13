/**
 * The defenses of ADR-0024, checked one by one: if one is missing, `make web` stops and says which.
 * It runs before the build, without a server: it reads the configuration, the scripts and the sources.
 */
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import config from "../next.config.mjs";

const root = new URL("..", import.meta.url).pathname;
const problems = [];
const expect = (ok, problem) => {
  if (!ok) problems.push(problem);
};

/**
 * The code without its comments. Only the client.ts and proxy.ts checks below read it: the per-source checks read
 * the raw text, comments included, so no comment in src/ may contain `fetch(`, `use server` or
 * `generateStaticParams`, and a commented-out `force-dynamic` line would satisfy the page check.
 */
const code = (text) => text.replace(/\/\*[\s\S]*?\*\/|(^|\s)\/\/.*$/gm, "$1");

function files(folder) {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

// The configuration
expect(config.images?.unoptimized === true, "next.config: images.unoptimized must stay on");
expect(config.output === "standalone", "next.config: output must be 'standalone'");
expect(config.poweredByHeader === false, "next.config: poweredByHeader must be off");

// The scripts: every script that starts Next.js does so with telemetry off, without the key, on loopback only
const { scripts } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const runsNext = (script) => /(?:^|[\s;&|])next\s/.test(script);
const runsServer = (script) => /standalone\/server\.js/.test(script);
for (const name of ["dev", "build", "start", "typecheck"]) {
  expect(runsNext(scripts[name] ?? "") || runsServer(scripts[name] ?? ""), `script ${name}: must start Next.js`);
}
for (const [name, script] of Object.entries(scripts)) {
  if (!runsNext(script) && !runsServer(script)) continue;
  expect(script.includes("NEXT_TELEMETRY_DISABLED=1"), `script ${name}: NEXT_TELEMETRY_DISABLED=1 is missing`);
  expect(
    script.includes("env -u ANTHROPIC_API_KEY -u AGENCY_ANTHROPIC_API_KEY"),
    `script ${name}: the API key must be removed from the environment`,
  );
  expect(!/\bnext start\b/.test(script), `script ${name}: with output 'standalone', start server.js, not next start`);
  if (/\bnext dev\b/.test(script)) {
    expect(script.includes("-H 127.0.0.1"), `script ${name}: next dev listens on 0.0.0.0 without -H 127.0.0.1`);
  }
  if (runsServer(script)) {
    expect(script.includes("HOSTNAME=127.0.0.1"), `script ${name}: server.js listens on 0.0.0.0 without HOSTNAME=127.0.0.1`);
  }
}

// The sources: a single fetch, never cached; no second backend
const sources = files(join(root, "src")).filter((path) => /\.(ts|tsx|js|jsx|mjs)$/.test(path));
const client = join(root, "src", "api", "client.ts");
for (const path of sources) {
  const text = readFileSync(path, "utf8");
  const where = relative(root, path);
  if (path !== client) expect(!/\bfetch\(/.test(text), `${where}: fetch only in src/api/client.ts`);
  expect(!/["']use server["']/.test(text), `${where}: no Server Actions, they would be a second backend`);
  expect(!/\/route\.(ts|tsx|js|mjs)$/.test(path), `${where}: no Route Handlers, they would be a second backend`);
  // A static page built while Django is up would carry that moment's data into the build.
  if (path.startsWith(join(root, "src", "app")) && /[/\\]page\.(tsx|ts|jsx|js)$/.test(path)) {
    expect(
      /^export const dynamic = "force-dynamic";$/m.test(text),
      `${where}: every page is dynamic (export const dynamic = "force-dynamic")`,
    );
  }
  expect(!/\bgenerateStaticParams\b/.test(text), `${where}: no generateStaticParams, the page would be built with data`);
}
// The code counts, not the comments: every call to fetch carries cache: "no-store".
const calls = code(readFileSync(client, "utf8")).match(/\bfetch\([^;]*;/g) ?? [];
expect(
  calls.length > 0 && calls.every((call) => /\bcache:\s*"no-store"/.test(call)),
  "src/api/client.ts: every read with cache: 'no-store'",
);
// Between the browser and the pages there is only src/proxy.ts, which refuses any Host but loopback (DNS rebinding)
// on every request: no matcher. middleware is the old name of the same file, and would be a second entry point.
for (const folder of ["", "src"]) {
  for (const extension of ["ts", "js", "mjs"]) {
    const middleware = join(root, folder, `middleware.${extension}`);
    expect(!existsSync(middleware), `${relative(root, middleware)}: only src/proxy.ts stands between the browser and the pages`);
    const other = join(root, folder, `proxy.${extension}`);
    if (other !== join(root, "src", "proxy.ts")) {
      expect(!existsSync(other), `${relative(root, other)}: only src/proxy.ts stands between the browser and the pages`);
    }
  }
}
const proxy = join(root, "src", "proxy.ts");
const proxyCode = existsSync(proxy) ? code(readFileSync(proxy, "utf8")) : "";
expect(/\bisLoopbackHost\(/.test(proxyCode), "src/proxy.ts: must refuse every Host but loopback with isLoopbackHost");
expect(!/\bexport\s+const\s+config\b|\bmatcher\b/.test(proxyCode), "src/proxy.ts: no matcher, so that it applies to every request");

// No .env: Next.js would load it into the server's environment by itself
const environments = readdirSync(root).filter((name) => name.startsWith(".env"));
expect(environments.length === 0, `no .env files in web/: ${environments.join(", ")}`);

// The telemetry: this version of Next.js must recognise the variable that turns it off
const telemetry = spawnSync(join(root, "node_modules", ".bin", "next"), ["telemetry", "status"], {
  env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  encoding: "utf8",
});
expect(/disabled/i.test(telemetry.stdout ?? ""), `next telemetry status does not say Disabled: ${telemetry.stdout}`);

if (problems.length > 0) {
  console.error(`Missing ADR-0024 defenses:\n- ${problems.join("\n- ")}`);
  process.exit(1);
}
console.log("ADR-0024 defenses in place");
