/**
 * Next.js è solo interfaccia (ADR-0024): niente dati propri, niente logica sul server, niente servizi esterni.
 * Ogni difesa qui sotto ha un controllo in scripts/check-defenses.mjs.
 */

/** Dove ascolta l'API Django. I rewrites lo fissano quando si costruisce: per un'altra porta si rifà la build. */
const api = process.env.AGENCY_API_ORIGIN ?? "http://127.0.0.1:8000";

/** @type {import("next").NextConfig} */
const config = {
  // Le prove costruiscono a parte, per le loro porte: la build vera non si confonde con quella di prova.
  distDir: process.env.AGENCY_NEXT_DIST ?? ".next",
  output: "standalone",
  poweredByHeader: false,
  // Le immagini ottimizzate finirebbero in .next/cache/images: copie dei materiali del cliente fuori da projects/.
  images: { unoptimized: true },
  // Il browser parla solo con Next.js, che inoltra /api a Django: stessa origine, niente CORS.
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
