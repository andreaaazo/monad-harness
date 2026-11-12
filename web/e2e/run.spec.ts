import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { get } from "node:http";
import { basename, join, sep } from "node:path";

import { expect, test } from "@playwright/test";

import { CANARY } from "./canary";
import { PROJECT, VIEWS, pages } from "./project";

const NEXT_PORT = 13765;
const DJANGO_PORT = 18765;
const OFFLINE_PORT = 13766;

test("the projects page lists the registry and says where the data comes from", async ({ page }) => {
  await page.goto("/");
  const row = page.getByRole("row", { name: new RegExp(PROJECT) });
  await expect(row).toContainText("10,80 $");
  await expect(row).toContainText("20,00 $");
  await expect(page.getByLabel("Provenienza dei dati")).toContainText("revisione 0008");
});

test("run view: what it cost, how long it took, who worked when", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: PROJECT }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(PROJECT);
  await expect(page.getByRole("link", { name: "Run" })).toHaveAttribute("aria-current", "page");
  const summary = page.getByLabel("Riepilogo");
  await expect(summary).toContainText("10,80 $");
  await expect(summary).toContainText("su 20,00 $");
  // 44 minutes from the first call to the last, 6 of them stopped between the presentation and the client's decision.
  await expect(summary).toContainText("38,0 min");
  await expect(summary).toContainText("più 6,0 min in attesa del cliente");
  await expect(summary.getByText("Fino alla presentazione")).toBeVisible();
  await expect(summary).toContainText("6,00 $");
  const timeline = page.getByRole("list", { name: "Timeline delle istanze" }).getByRole("listitem");
  await expect(timeline).toHaveCount(10);
  // In order of start: director-select (T-0001, minute 12) comes after the explorations of T-0002 and T-0003, and
  // the gate's wait lies between the presentation and the finishing.
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

test("a project that does not exist has its own page and status, in every view", async ({ page }) => {
  for (const path of VIEWS.map((view) => `/projects/fantasma${view}`)) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(404);
    await expect(page.getByRole("heading", { name: "Progetto sconosciuto" })).toBeVisible();
  }
});

test("with Django down the pages say so and say how to restart it", async ({ page }) => {
  for (const path of pages()) {
    await page.goto(`http://127.0.0.1:${OFFLINE_PORT}${path}`);
    // Next.js already has its own role="alert", the route announcer: the test looks for the page's.
    const alert = page.getByRole("main").getByRole("alert");
    await expect(alert.getByRole("heading", { level: 1 })).toHaveText("Django non risponde");
    await expect(alert).toContainText("Django non risponde su http://127.0.0.1:18766");
    await expect(alert.getByRole("code")).toHaveText("uv run agency-server");
  }
});

test("the browser talks only to Next.js: no CDN, no telemetry, no direct Django", async ({ page }) => {
  const requests: string[] = [];
  const failed: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  // A prefetch cancelled because the page changes is not a server error.
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
  // The standalone server serves the static files itself: if the build does not copy them, this is a 404.
  expect(failed).toEqual([]);
});

test("the browser reaches the API only through Next.js, on the same origin", async ({ request }) => {
  const response = await request.get("/api/projects");
  expect(response.ok()).toBe(true);
  expect((await response.json()).map((project: { name: string }) => project.name)).toContain(PROJECT);
  expect((await request.post("/api/projects")).status()).toBe(405);
});

test("pages are not cached, not framed, and do not say who serves them", async ({ request }) => {
  // The dynamic pages and the static ones too: on its own, Next.js would give /_not-found s-maxage=31536000.
  for (const path of [`/projects/${PROJECT}`, "/_not-found"]) {
    const headers = (await request.get(path)).headers();
    expect(headers["cache-control"], path).toContain("no-store");
    expect(headers["x-frame-options"], path).toBe("DENY");
    expect(headers["x-content-type-options"], path).toBe("nosniff");
    expect(headers["x-powered-by"], path).toBeUndefined();
  }
});

/** The status and the body of a request to Next.js with a chosen Host: a browser does not let one change it. */
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

test("a name pointing at 127.0.0.1 cannot read the dashboard: no pages, no /api, no static files", async ({ page }) => {
  await page.goto("/");
  const script = await page.locator('script[src*="/_next/static/"]').first().getAttribute("src");
  expect(script).not.toBeNull();
  for (const path of ["/", `/projects/${PROJECT}`, "/api/projects", `/api/projects/${PROJECT}/report`, script!]) {
    const hostile = await ask(path, `evil.example:${NEXT_PORT}`);
    expect(hostile.status, path).toBe(400);
    expect(hostile.body, path).not.toContain(PROJECT);
    // A hostile page can add X-Forwarded-Host to its requests, but not change Host: only Host counts.
    const forged = await ask(path, `evil.example:${NEXT_PORT}`, { "x-forwarded-host": `127.0.0.1:${NEXT_PORT}` });
    expect(forged.status, path).toBe(400);
    expect((await ask(path, `localhost:${NEXT_PORT}`)).status, path).toBe(200);
  }
});

test("on a phone no view scrolls sideways, not even with the details open", async ({ browser }) => {
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 } });
  for (const path of pages()) {
    await phone.goto(path);
    await phone.locator("details summary").evaluateAll((items) => items.forEach((item) => (item as HTMLElement).click()));
    expect(await phone.evaluate(() => document.documentElement.scrollWidth), path).toBeLessThanOrEqual(390);
  }
  await phone.close();
});

test("Next.js and Django listen only on loopback", async () => {
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

/** The test servers' processes, with what matters about their environment. On Linux they are read from /proc. */
function servers(): { program: string; port: string; keys: string[]; canary: boolean }[] {
  return readdirSync("/proc")
    .filter((pid) => /^\d+$/.test(pid))
    .flatMap((pid) => {
      try {
        const argv = readFileSync(`/proc/${pid}/cmdline`, "utf8").split("\0").filter(Boolean);
        // The shell that starts the command still holds the fake key: env -u is what removes it from the server.
        if (["sh", "bash", "dash", "zsh", "env"].includes(basename(argv[0] ?? ""))) return [];
        const environment = readFileSync(`/proc/${pid}/environ`, "utf8").split("\0");
        const port = environment.find((item) => item.startsWith("PORT="))?.slice(5) ?? argv.at(-1) ?? "";
        // The standalone server renames itself: /proc keeps only "next-server (v…)".
        const next = (argv[0] ?? "").startsWith("next-server") && /^1376[56]$/.test(port);
        const django = argv.some((item) => item.endsWith("agency-server")) && argv.includes(String(DJANGO_PORT));
        if (!next && !django) return [];
        return [
          {
            program: next ? `Next.js on ${port}` : `Django (${basename(argv[0] ?? "")})`,
            port,
            // Only the names and a yes or a no: an error must not print the environment, which can hold secrets.
            keys: environment.map((item) => item.split("=")[0] ?? "").filter((name) => name.includes("ANTHROPIC")),
            canary: environment.some((item) => item.includes(CANARY)),
          },
        ];
      } catch {
        return [];
      }
    });
}

test("neither Next.js nor Django gets the key, even when whoever starts them has it in the environment", () => {
  test.skip(!existsSync("/proc/self/environ"), "needs /proc to read the processes' environment");
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

test("no registry data, images or .env files stay in the build", async ({ page }) => {
  for (const path of pages()) {
    await page.goto(path);
  }
  // Everything the build and the server write, the standalone server's cache included; not the copied libraries.
  const written = everything(join(process.cwd(), ".next-e2e")).filter(
    (path) => !path.includes(`${sep}standalone${sep}node_modules${sep}`),
  );
  expect(written.filter((path) => /[/\\](images|fetch-cache)$/.test(path))).toEqual([]);
  // The replay view's images go through the Next.js proxy: none may stay written in the build.
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
  expect(written.filter((path) => statSync(path).isFile() && readFileSync(path).subarray(0, 4).equals(png))).toEqual([]);
  expect(written.filter((path) => /[/\\]\.env[^/\\]*$/.test(path))).toEqual([]);
  const copies = written.filter(
    (path) => statSync(path).isFile() && /officina-e2e|Rifinitura X/.test(readFileSync(path, "latin1")),
  );
  expect(copies).toEqual([]);
});
