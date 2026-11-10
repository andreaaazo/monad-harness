import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { get } from "node:http";
import { basename, join, sep } from "node:path";

import { expect, test } from "@playwright/test";

import { CANARY } from "./canary";
import { PROJECT, VIEWS, pages } from "./project";

const NEXT_PORT = 13765;
const DJANGO_PORT = 18765;
const OFFLINE_PORT = 13766;

test("la pagina dei progetti elenca il registro e dice da dove vengono i dati", async ({ page }) => {
  await page.goto("/");
  const row = page.getByRole("row", { name: new RegExp(PROJECT) });
  await expect(row).toContainText("10,80 $");
  await expect(row).toContainText("20,00 $");
  await expect(page.getByLabel("Provenienza dei dati")).toContainText("revisione 0007");
});

test("vista Run: quanto è costato, quanto è durato, chi ha lavorato quando", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: PROJECT }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(PROJECT);
  await expect(page.getByRole("link", { name: "Run" })).toHaveAttribute("aria-current", "page");
  const summary = page.getByLabel("Riepilogo");
  await expect(summary).toContainText("10,80 $");
  await expect(summary).toContainText("su 20,00 $");
  // 44 minuti dalla prima all'ultima chiamata, 6 fermi fra la presentazione e la decisione del cliente.
  await expect(summary).toContainText("38,0 min");
  await expect(summary).toContainText("più 6,0 min in attesa del cliente");
  await expect(summary.getByText("Fino alla presentazione")).toBeVisible();
  await expect(summary).toContainText("6,00 $");
  const timeline = page.getByRole("list", { name: "Timeline delle istanze" }).getByRole("listitem");
  await expect(timeline).toHaveCount(10);
  // In ordine di inizio: director-select (T-0001, minuto 12) viene dopo le esplorazioni di T-0002 e T-0003, e
  // l'attesa del gate sta fra la presentazione e la rifinitura.
  const order = [
    "director-plan",
    "explorer",
    "explorer",
    "director-select",
    "proposer",
    "director-present",
    "in attesa del cliente",
    "finisher",
    "critic",
    "finisher",
  ];
  for (const [position, phase] of order.entries()) await expect(timeline.nth(position)).toContainText(phase);
  await expect(timeline.nth(6)).toContainText("ferma per 6,0 min");
  const phases = page.getByRole("table", { name: "Fasi" });
  await expect(phases.getByRole("row", { name: /finisher/ })).toContainText("4,50 $");
  await expect(phases.getByRole("row", { name: /explorer/ })).toContainText("2,1 s");
  await expect(page.getByRole("table", { name: "Ticket" }).getByRole("row")).toHaveCount(7);
});

test("un progetto che non esiste ha la sua pagina e il suo stato, in ogni vista", async ({ page }) => {
  for (const path of VIEWS.map((view) => `/projects/fantasma${view}`)) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(404);
    await expect(page.getByRole("heading", { name: "Progetto sconosciuto" })).toBeVisible();
  }
});

test("se Django è spento le pagine lo dicono e dicono come riavviarlo", async ({ page }) => {
  for (const path of pages()) {
    await page.goto(`http://127.0.0.1:${OFFLINE_PORT}${path}`);
    // Next.js ha già un suo role="alert", l'annunciatore delle rotte: si cerca quello della pagina.
    const alert = page.getByRole("main").getByRole("alert");
    await expect(alert.getByRole("heading", { level: 1 })).toHaveText("Django non risponde");
    await expect(alert).toContainText("Django non risponde su http://127.0.0.1:18766");
    await expect(alert.getByRole("code")).toHaveText("uv run agency-server");
  }
});

test("il browser parla solo con Next.js: niente CDN, niente telemetria, niente Django diretto", async ({ page }) => {
  const requests: string[] = [];
  const failed: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  // Un prefetch annullato perché la pagina cambia non è un errore del server.
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText ?? "";
    if (reason !== "net::ERR_ABORTED") failed.push(`${reason} ${request.url()}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`);
  });
  for (const path of pages()) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
  }
  expect(requests.filter((url) => url.includes("/_next/static/")).length).toBeGreaterThan(0);
  expect(requests.filter((url) => !url.startsWith(`http://127.0.0.1:${NEXT_PORT}/`))).toEqual([]);
  // Il server standalone serve da sé i file statici: se la build non li copia, qui c'è un 404.
  expect(failed).toEqual([]);
});

test("l'API arriva dal browser solo passando da Next.js, nella stessa origine", async ({ request }) => {
  const response = await request.get("/api/projects");
  expect(response.ok()).toBe(true);
  expect((await response.json()).map((project: { name: string }) => project.name)).toContain(PROJECT);
  expect((await request.post("/api/projects")).status()).toBe(405);
});

test("le pagine non restano in cache, non si incorniciano e non dicono chi le serve", async ({ request }) => {
  // Le dinamiche e anche quelle statiche: da sola, Next.js darebbe a /_not-found s-maxage=31536000.
  for (const path of [`/projects/${PROJECT}`, "/_not-found"]) {
    const headers = (await request.get(path)).headers();
    expect(headers["cache-control"], path).toContain("no-store");
    expect(headers["x-frame-options"], path).toBe("DENY");
    expect(headers["x-content-type-options"], path).toBe("nosniff");
    expect(headers["x-powered-by"], path).toBeUndefined();
  }
});

/** Lo stato e il corpo di una richiesta a Next.js con l'Host scelto: il browser non lascia cambiarlo. */
function ask(path: string, host: string, headers: Record<string, string> = {}): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const request = get({ host: "127.0.0.1", port: NEXT_PORT, path, headers: { ...headers, host } }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk: string) => (body += chunk));
      response.on("end", () => resolve({ status: response.statusCode ?? 0, body }));
    });
    request.on("error", reject);
  });
}

test("un nome che punta a 127.0.0.1 non legge il cruscotto: né pagine, né /api, né file statici", async ({ page }) => {
  await page.goto("/");
  const script = await page.locator('script[src*="/_next/static/"]').first().getAttribute("src");
  expect(script).not.toBeNull();
  for (const path of ["/", `/projects/${PROJECT}`, "/api/projects", `/api/projects/${PROJECT}/report`, script!]) {
    const hostile = await ask(path, `evil.example:${NEXT_PORT}`);
    expect(hostile.status, path).toBe(400);
    expect(hostile.body, path).not.toContain(PROJECT);
    // Una pagina ostile può aggiungere X-Forwarded-Host alle sue fetch, non cambiare Host: conta solo Host.
    const forged = await ask(path, `evil.example:${NEXT_PORT}`, { "x-forwarded-host": `127.0.0.1:${NEXT_PORT}` });
    expect(forged.status, path).toBe(400);
    expect((await ask(path, `localhost:${NEXT_PORT}`)).status, path).toBe(200);
  }
});

test("su un telefono nessuna vista scorre in orizzontale, neanche con i dettagli aperti", async ({ browser }) => {
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 } });
  for (const path of pages()) {
    await phone.goto(path);
    await phone.locator("details summary").evaluateAll((items) => items.forEach((item) => (item as HTMLElement).click()));
    expect(await phone.evaluate(() => document.documentElement.scrollWidth), path).toBeLessThanOrEqual(390);
  }
  await phone.close();
});

test("Next.js e Django ascoltano solo su loopback", async () => {
  // The kernel's own socket tables, not a connection attempt from outside: they need no second interface,
  // so the test never has to skip.
  const servers = [
    ["Next.js", NEXT_PORT],
    ["Next.js without Django", OFFLINE_PORT],
    ["Django", DJANGO_PORT],
  ] as const;
  for (const [name, port] of servers) {
    const addresses = listening(port);
    expect(addresses.length, `${name} is not listening on port ${port}`).toBeGreaterThan(0);
    for (const address of addresses) expect(LOOPBACK, `${name} listens on ${address}:${port}`).toContain(address);
  }
});

const LOOPBACK = ["127.0.0.1", "::1"];

/** The local addresses of the sockets listening on `port`, from /proc/net/tcp and /proc/net/tcp6. */
function listening(port: number): string[] {
  const wanted = port.toString(16).toUpperCase().padStart(4, "0");
  return ["/proc/net/tcp", "/proc/net/tcp6"]
    .filter((table) => existsSync(table))
    .flatMap((table) => readFileSync(table, "utf8").trim().split("\n").slice(1))
    .flatMap((line) => {
      const [, local = "", , state] = line.trim().split(/\s+/);
      const [hexAddress = "", hexPort] = local.split(":");
      return state === "0A" && hexPort === wanted ? [address(hexAddress)] : []; // 0A is TCP_LISTEN
    });
}

/** The kernel prints each 32-bit word of the address in host byte order: little-endian on x86 and ARM. */
function address(hex: string): string {
  const bytes = (hex.match(/.{8}/g) ?? []).flatMap((word) => (word.match(/../g) ?? []).reverse());
  if (bytes.length === 4) return bytes.map((byte) => parseInt(byte, 16)).join(".");
  const groups = (bytes.join("").match(/.{4}/g) ?? []).map((group) => parseInt(group, 16).toString(16));
  const full = groups.join(":");
  return full === "0:0:0:0:0:0:0:1" ? "::1" : full;
}

/** I processi dei server di prova, con ciò che serve sapere del loro ambiente. Su Linux si leggono da /proc. */
function servers(): { program: string; port: string; keys: string[]; canary: boolean }[] {
  return readdirSync("/proc")
    .filter((pid) => /^\d+$/.test(pid))
    .flatMap((pid) => {
      try {
        const argv = readFileSync(`/proc/${pid}/cmdline`, "utf8").split("\0").filter(Boolean);
        // La shell che avvia il comando ha ancora la chiave finta: è env -u a toglierla al server.
        if (["sh", "bash", "dash", "zsh", "env"].includes(basename(argv[0] ?? ""))) return [];
        const environment = readFileSync(`/proc/${pid}/environ`, "utf8").split("\0");
        const port = environment.find((item) => item.startsWith("PORT="))?.slice(5) ?? argv.at(-1) ?? "";
        // Il server standalone si rinomina: in /proc resta solo "next-server (v…)".
        const next = (argv[0] ?? "").startsWith("next-server") && /^1376[56]$/.test(port);
        const django = argv.some((item) => item.endsWith("agency-server")) && argv.includes(String(DJANGO_PORT));
        if (!next && !django) return [];
        return [
          {
            program: next ? `Next.js su ${port}` : `Django (${basename(argv[0] ?? "")})`,
            port,
            // Solo i nomi e un sì o un no: un errore non deve stampare l'ambiente, che può contenere segreti.
            keys: environment.map((item) => item.split("=")[0] ?? "").filter((name) => name.includes("ANTHROPIC")),
            canary: environment.some((item) => item.includes(CANARY)),
          },
        ];
      } catch {
        return [];
      }
    });
}

test("né Next.js né Django ricevono la chiave, anche quando chi li avvia ce l'ha nell'ambiente", () => {
  test.skip(!existsSync("/proc/self/environ"), "serve /proc per leggere l'ambiente dei processi");
  const found = servers();
  expect(found.filter((server) => server.program.startsWith("Next.js")).map((server) => server.port).sort()).toEqual([
    String(NEXT_PORT),
    String(OFFLINE_PORT),
  ]);
  expect(found.some((server) => server.program.startsWith("Django"))).toBe(true);
  for (const server of found) {
    expect(server.keys, server.program).toEqual([]);
    expect(server.canary, server.program).toBe(false);
  }
});

function everything(folder: string): string[] {
  if (!existsSync(folder)) return [];
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? [path, ...everything(path)] : [path];
  });
}

test("nella build non restano dati del registro, immagini o file .env", async ({ page }) => {
  for (const path of pages()) {
    await page.goto(path);
  }
  // Tutto ciò che la build e il server scrivono, cache del server standalone compresa; non le librerie copiate.
  const written = everything(join(process.cwd(), ".next-e2e")).filter(
    (path) => !path.includes(`${sep}standalone${sep}node_modules${sep}`),
  );
  expect(written.filter((path) => /[/\\](images|fetch-cache)$/.test(path))).toEqual([]);
  // Le immagini del Replay passano dal proxy di Next.js: nessuna deve restare scritta nella build.
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
  expect(written.filter((path) => statSync(path).isFile() && readFileSync(path).subarray(0, 4).equals(png))).toEqual([]);
  expect(written.filter((path) => /[/\\]\.env[^/\\]*$/.test(path))).toEqual([]);
  const copies = written.filter(
    (path) => statSync(path).isFile() && /officina-e2e|Rifinitura X/.test(readFileSync(path, "latin1")),
  );
  expect(copies).toEqual([]);
});
