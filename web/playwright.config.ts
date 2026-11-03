import { defineConfig, devices } from "@playwright/test";

import { CANARY } from "./e2e/canary";

/**
 * Le prove di fumo del cruscotto (07-EVALS.md): i due server veri, la build di produzione di Next.js, un
 * registro di prova inventato. Porte proprie, così un cruscotto già aperto non disturba.
 */
const NEXT = "http://127.0.0.1:13765";
const DJANGO = "http://127.0.0.1:18765";
/** La stessa build, puntata su una porta dove Django non c'è: com'è il cruscotto quando l'API è spenta. */
const NOBODY = "http://127.0.0.1:18766";
const withoutKey = "env -u ANTHROPIC_API_KEY -u AGENCY_ANTHROPIC_API_KEY";
/** Ogni server parte da un ambiente con la chiave finta: `withoutKey` deve toglierla. */
const withCanary = { ANTHROPIC_API_KEY: CANARY, AGENCY_ANTHROPIC_API_KEY: CANARY };

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/.results",
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [["list"]],
  // Niente tracce, video o schermate: conterrebbero i dati delle pagine.
  use: { ...devices["Desktop Chrome"], baseURL: NEXT, trace: "off", video: "off", screenshot: "off" },
  webServer: [
    {
      command:
        `uv run python ../tests/dashboard_fixture.py e2e/.data && ` +
        `${withoutKey} AGENCY_DATA_DIR=e2e/.data uv run agency-server --port 18765`,
      url: `${DJANGO}/api/provenance`,
      env: withCanary,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // Il server standalone, lo stesso che girerà in Docker. Senza HOSTNAME ascolterebbe su 0.0.0.0.
      command:
        `${withoutKey} NEXT_TELEMETRY_DISABLED=1 HOSTNAME=127.0.0.1 PORT=13765 AGENCY_API_ORIGIN=${DJANGO} ` +
        `node .next-e2e/standalone/server.js`,
      url: NEXT,
      env: withCanary,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        `${withoutKey} NEXT_TELEMETRY_DISABLED=1 HOSTNAME=127.0.0.1 PORT=13766 AGENCY_API_ORIGIN=${NOBODY} ` +
        `node .next-e2e/standalone/server.js`,
      // Pronto quando lo dice, non quando risponde: la sua prima pagina è proprio ciò che si prova.
      wait: { stdout: /Ready in/ },
      env: withCanary,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
