# L'API del cruscotto (ADR-0040): Django in sola lettura, su 127.0.0.1 anche dentro il container.
# Immagini bloccate per digest, pubblicate da più di due settimane (ADR-0006). Le versioni sono quelle di
# mise.toml e di uv: un test le confronta.
ARG PYTHON=python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
ARG UV=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1

FROM ${UV} AS uv

FROM ${PYTHON} AS build
COPY --from=uv /uv /usr/local/bin/uv
# Il Python dell'immagine, mai uno scaricato; il bytecode compilato qui, non a runtime su un disco di sola lettura.
ENV UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/local/bin/python3 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
# Prima le dipendenze dal lock, poi il progetto: cambiare il codice non riscarica le librerie.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM ${PYTHON}
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AGENCY_DATA_DIR=/data
# Nessun utente con una shell e nessun privilegio: il processo legge il registro e risponde.
USER 10001:10001
ENTRYPOINT ["agency-server"]
CMD ["--host", "127.0.0.1", "--port", "8000"]
