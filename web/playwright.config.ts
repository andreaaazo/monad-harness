import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

import { CANARY } from "./e2e/canary";

/**
 * The dashboard's smoke tests (07-EVALS.md): the two real servers, the Next.js production build, an invented
 * test registry. Ports of their own, so a dashboard already running does not get in the way.
 */
const NEXT = "http://127.0.0.1:13765";
const DJANGO = "http://127.0.0.1:18765";
/** The same build, pointed at a port with no Django: the dashboard as it is when the API is down. */
const NOBODY = "http://127.0.0.1:18766";
const withoutKey = "env -u ANTHROPIC_API_KEY -u AGENCY_ANTHROPIC_API_KEY";
/** Every server starts from an environment holding the fake key: `withoutKey` must remove it. */
const withCanary = { ANTHROPIC_API_KEY: CANARY, AGENCY_ANTHROPIC_API_KEY: CANARY };
/** The test registry, as an absolute path: the server refuses a relative AGENCY_DATA_DIR (ADR-0045). */
const DATA = fileURLToPath(new URL("e2e/.data", import.meta.url));

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/.results",
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [["list"]],
  // No traces, videos or screenshots: they would hold the pages' data.
  use: { ...devices["Desktop Chrome"], baseURL: NEXT, trace: "off", video: "off", screenshot: "off" },
  webServer: [
    {
      command:
        `uv run python ../tests/dashboard_fixture.py ${DATA} && ` +
        `${withoutKey} AGENCY_DATA_DIR=${DATA} uv run agency-server --port 18765`,
      url: `${DJANGO}/api/provenance`,
      env: withCanary,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // The standalone server, the same one that runs in Docker. Without HOSTNAME it would listen on 0.0.0.0.
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
      // Ready when it says so, not when it answers: its first page is exactly what is tested.
      wait: { stdout: /Ready in/ },
      env: withCanary,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
