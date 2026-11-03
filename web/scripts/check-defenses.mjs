/**
 * Le difese di ADR-0024, controllate una per una: se una manca, `make web` si ferma e dice quale.
 * Gira prima della build, senza server: legge configurazione, script e sorgenti.
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

/** Il codice senza commenti: una regola si verifica su ciò che gira, non su ciò che lo descrive. */
const code = (text) => text.replace(/\/\*[\s\S]*?\*\/|(^|\s)\/\/.*$/gm, "$1");

function files(folder) {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

// La configurazione
expect(config.images?.unoptimized === true, "next.config: images.unoptimized deve restare attivo");
expect(config.output === "standalone", "next.config: output deve essere 'standalone'");
expect(config.poweredByHeader === false, "next.config: poweredByHeader deve essere spento");

// Gli script: ogni script che avvia Next.js lo fa con la telemetria spenta, senza la chiave e solo su loopback
const { scripts } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const runsNext = (script) => /(?:^|[\s;&|])next\s/.test(script);
const runsServer = (script) => /standalone\/server\.js/.test(script);
for (const name of ["dev", "build", "start", "typecheck"]) {
  expect(runsNext(scripts[name] ?? "") || runsServer(scripts[name] ?? ""), `script ${name}: deve avviare Next.js`);
}
for (const [name, script] of Object.entries(scripts)) {
  if (!runsNext(script) && !runsServer(script)) continue;
  expect(script.includes("NEXT_TELEMETRY_DISABLED=1"), `script ${name}: manca NEXT_TELEMETRY_DISABLED=1`);
  expect(
    script.includes("env -u ANTHROPIC_API_KEY -u AGENCY_ANTHROPIC_API_KEY"),
    `script ${name}: la chiave API deve uscire dall'ambiente`,
  );
  expect(!/\bnext start\b/.test(script), `script ${name}: con output 'standalone' si avvia server.js, non next start`);
  if (/\bnext dev\b/.test(script)) {
    expect(script.includes("-H 127.0.0.1"), `script ${name}: next dev ascolta su 0.0.0.0 senza -H 127.0.0.1`);
  }
  if (runsServer(script)) {
    expect(script.includes("HOSTNAME=127.0.0.1"), `script ${name}: server.js ascolta su 0.0.0.0 senza HOSTNAME=127.0.0.1`);
  }
}

// I sorgenti: una sola fetch, sempre senza cache; nessun secondo backend
const sources = files(join(root, "src")).filter((path) => /\.(ts|tsx|js|jsx|mjs)$/.test(path));
const client = join(root, "src", "api", "client.ts");
for (const path of sources) {
  const text = readFileSync(path, "utf8");
  const where = relative(root, path);
  if (path !== client) expect(!/\bfetch\(/.test(text), `${where}: fetch solo in src/api/client.ts`);
  expect(!/["']use server["']/.test(text), `${where}: niente Server Action, sarebbero un secondo backend`);
  expect(!/\/route\.(ts|tsx|js|mjs)$/.test(path), `${where}: niente Route Handler, sarebbero un secondo backend`);
  // Una pagina statica costruita con Django acceso porterebbe dentro la build i dati di quel momento.
  if (/[/\\]page\.(tsx|ts|jsx|js)$/.test(path)) {
    expect(
      /^export const dynamic = "force-dynamic";$/m.test(text),
      `${where}: ogni pagina è dinamica (export const dynamic = "force-dynamic")`,
    );
  }
  expect(!/\bgenerateStaticParams\b/.test(text), `${where}: niente generateStaticParams, si costruirebbe con i dati`);
}
// Conta il codice, non i commenti: ogni chiamata a fetch porta con sé cache: "no-store".
const calls = code(readFileSync(client, "utf8")).match(/\bfetch\([^;]*;/g) ?? [];
expect(
  calls.length > 0 && calls.every((call) => /\bcache:\s*"no-store"/.test(call)),
  "src/api/client.ts: ogni lettura con cache: 'no-store'",
);
// Fra il browser e le pagine c'è solo src/proxy.ts, che rifiuta gli Host non loopback (DNS rebinding), su ogni
// richiesta: niente matcher. middleware è il vecchio nome dello stesso file, e un secondo punto d'ingresso.
for (const folder of ["", "src"]) {
  for (const extension of ["ts", "js", "mjs"]) {
    const middleware = join(root, folder, `middleware.${extension}`);
    expect(!existsSync(middleware), `${relative(root, middleware)}: fra il browser e le pagine c'è solo src/proxy.ts`);
    const other = join(root, folder, `proxy.${extension}`);
    if (other !== join(root, "src", "proxy.ts")) {
      expect(!existsSync(other), `${relative(root, other)}: fra il browser e le pagine c'è solo src/proxy.ts`);
    }
  }
}
const proxy = join(root, "src", "proxy.ts");
const proxyCode = existsSync(proxy) ? code(readFileSync(proxy, "utf8")) : "";
expect(/\bisLoopbackHost\(/.test(proxyCode), "src/proxy.ts: deve rifiutare gli Host non loopback con isLoopbackHost");
expect(!/\bexport\s+const\s+config\b|\bmatcher\b/.test(proxyCode), "src/proxy.ts: senza matcher, vale per ogni richiesta");

// Nessun .env: Next.js li caricherebbe da solo nell'ambiente del server
const environments = readdirSync(root).filter((name) => name.startsWith(".env"));
expect(environments.length === 0, `niente file .env in web/: ${environments.join(", ")}`);

// La telemetria: questa versione di Next.js deve riconoscere la variabile che la spegne
const telemetry = spawnSync(join(root, "node_modules", ".bin", "next"), ["telemetry", "status"], {
  env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  encoding: "utf8",
});
expect(/disabled/i.test(telemetry.stdout ?? ""), `next telemetry status non dice Disabled: ${telemetry.stdout}`);

if (problems.length > 0) {
  console.error(`Difese di ADR-0024 mancanti:\n- ${problems.join("\n- ")}`);
  process.exit(1);
}
console.log("difese di ADR-0024 al loro posto");
