# L'interfaccia del cruscotto (ADR-0040): la build standalone di Next.js, lo stesso server delle prove Playwright.
# Immagine bloccata per digest, pubblicata da più di due settimane (ADR-0006); Node e pnpm alle versioni di
# mise.toml: un test le confronta.
ARG NODE=node:22.22.1-trixie-slim@sha256:285a78d9fdb7cd2e4a03639cc7bbf609755ce8c0aa4e3b00086211e3e86a7038
ARG PNPM=12.14.0

FROM ${NODE} AS build
ARG PNPM
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm install --global --no-fund --no-audit "pnpm@${PNPM}"
WORKDIR /app/web
# Prima le dipendenze dal lock, con la quarantena di pnpm-workspace.yaml, poi i sorgenti.
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY web/ ./
# Django sta nello stesso spazio di rete, su loopback: i rewrites di /api si fissano qui (ADR-0033).
ENV AGENCY_API_ORIGIN=http://127.0.0.1:8000
RUN pnpm run build

FROM ${NODE}
WORKDIR /app
COPY --from=build --chown=node:node /app/web/.next/standalone ./
# Dentro il container ascolta su tutte le interfacce del suo spazio di rete; fuori si pubblica solo su
# 127.0.0.1 della macchina (ADR-0024). Il proxy di Next.js rifiuta comunque ogni Host che non sia loopback.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 AGENCY_API_ORIGIN=http://127.0.0.1:8000
USER node
CMD ["node", "server.js"]
