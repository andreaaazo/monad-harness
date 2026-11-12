# The dashboard API (ADR-0040): read-only Django, on 127.0.0.1 even inside the container.
# Images pinned by digest, published more than two weeks ago (ADR-0006). The versions are those of
# .python-version (Python) and mise.toml (uv): a test compares them.
ARG PYTHON=python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
ARG UV=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1

FROM ${UV} AS uv

FROM ${PYTHON} AS build
COPY --from=uv /uv /usr/local/bin/uv
# The image's Python, never a downloaded one; bytecode compiled here, not at runtime on a read-only disk.
ENV UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/local/bin/python3 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
# First the dependencies from the lock, then the project: changing the code does not download the libraries again.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM ${PYTHON}
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AGENCY_DATA_DIR=/data
# No user with a shell and no privilege: the process reads the registry and answers.
USER 10001:10001
ENTRYPOINT ["agency-server"]
CMD ["--host", "127.0.0.1", "--port", "8000"]
