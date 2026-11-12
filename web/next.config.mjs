/**
 * Next.js is only the interface (ADR-0024): no data of its own, no server logic, no outside services.
 * scripts/check-defenses.mjs checks `images`, `output` and `poweredByHeader`. e2e/run.spec.ts checks the
 * Cache-Control, X-Frame-Options and X-Content-Type-Options headers, and e2e/replay.spec.ts goes through the
 * rewrites. Referrer-Policy has no check.
 */

/** Where the Django API listens. The rewrites fix it at build time: another port needs a new build. */
const api = process.env.AGENCY_API_ORIGIN ?? "http://127.0.0.1:8000";

/** @type {import("next").NextConfig} */
const config = {
  // The tests build apart, for their own ports: the real build is never mixed up with the test one.
  distDir: process.env.AGENCY_NEXT_DIST ?? ".next",
  output: "standalone",
  poweredByHeader: false,
  // Optimized images would end up in .next/cache/images: copies of the client's materials outside projects/.
  images: { unoptimized: true },
  // The browser talks only to Next.js, which forwards /api to Django: same origin, no CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/((?!_next/static).*)",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default config;
