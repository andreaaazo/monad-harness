# The dashboard interface (ADR-0040): the Next.js standalone build, the same server as the Playwright tests.
# Image pinned by digest, published more than two weeks ago (ADR-0006); Node and pnpm at the versions of
# mise.toml: a test compares them.
ARG NODE=node:22.22.1-trixie-slim@sha256:285a78d9fdb7cd2e4a03639cc7bbf609755ce8c0aa4e3b00086211e3e86a7038
ARG PNPM=12.14.0

FROM ${NODE} AS build
ARG PNPM
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm install --global --no-fund --no-audit "pnpm@${PNPM}"
WORKDIR /app/web
# First the dependencies from the lock, with the quarantine of pnpm-workspace.yaml, then the sources.
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY web/ ./
# Django is in the same network namespace, on loopback: the /api rewrites are fixed here (ADR-0033).
ENV AGENCY_API_ORIGIN=http://127.0.0.1:8000
RUN pnpm run build

FROM ${NODE}
WORKDIR /app
COPY --from=build --chown=node:node /app/web/.next/standalone ./
# Inside the container it listens on every interface of its network namespace; outside, it is published only on
# the machine's 127.0.0.1 (ADR-0024). The Next.js proxy refuses any Host that is not loopback anyway.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 AGENCY_API_ORIGIN=http://127.0.0.1:8000
USER node
CMD ["node", "server.js"]
