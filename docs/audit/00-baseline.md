# 00 — Baseline before the sanity refactor

This is the reference point for the final before/after comparison. It records only what was observed: no tracked
file was changed, and nothing was fixed.

| | |
|---|---|
| Commit measured | `8d99a5ceac364a08758466071299da7915ca3f3b` (branch `audit/deep-review`, created from `main` at that commit) |
| Worktree | `/home/andreaaazo/Dev/design-agency-harness/.worktrees/audit/deep-review` |
| Baseline session | 2026-11-04, 00:06–00:15 (+01:00): session 2, the numbers below |
| Earlier session | 2026-11-03, 23:38–23:54, same commit, at the worktree's first location (§2.2) |
| Machine | Ubuntu 26.04.1 LTS, Linux 7.0.0-38-generic x86_64, 24 CPUs, 60 GB RAM, NVIDIA RTX 5080 Laptop (16 GB) |
| Tools | mise 2026.10.3, node 22.22.1, pnpm 12.14.0, uv 0.12.5, task 3.54.0 (all from `mise.toml`), CPython 3.13.15 (uv-managed), GNU Make 4.4.1, Docker 29.9.0, tokei 13.0.0, ripgrep 15.1.0 |

**History of the worktree.** It was created on 2026-11-03 at the sibling path
`/home/andreaaazo/Dev/design-agency-harness-audit-deep-review`, because `.worktrees/` was not ignored yet. After
`main` gained `/.worktrees/` in `.gitignore` (commit `ed92941`, which touches only `.gitignore`), the worktree was
moved with `git worktree move`. Every ignored build output was then deleted, and the whole baseline was run again.
`audit/deep-review` is still at `8d99a5c`, so the code measured is identical in both sessions.

**Clean state** means a fresh worktree of `8d99a5c`: no `.venv/`, `web/node_modules/`, `.next*/`, `.task/`, `.data/`,
`.env`, `__pycache__/` or tool caches. The only untracked file was this document. Machine-level caches were warm:
the uv cache, the pnpm store (`~/.local/share/pnpm/store/v11`), the mise installs and Playwright's `chromium-1248`.
`make setup` downloaded nothing (pnpm: "downloaded 0"). A machine with cold caches needs network access for setup;
that case was not measured.

After every run, `git status --porcelain --ignored` showed only ignored paths and `?? docs/audit/`: no tracked file
changed.

---

## 1. Codebase map

### 1.1 Build system and toolchain

- **mise** (`mise.toml`) pins node, pnpm, uv and task. Python ≥ 3.13 comes from `pyproject.toml` /
  `.python-version`, installed by uv (ADR-0034).
- **Task** (`Taskfile.yml`) is the single command entry point (ADR-0039). **Make** (`Makefile`) is an alias:
  `make <t>` runs `mise exec -- task <t>` for `check lint imports types test web e2e schemas doctor dashboard`.
  `make setup` runs `mise install` and then `task setup`. A bare `make` runs `setup`, the first target.
- **Python**: uv for the environment and the lock, hatchling as the build backend (wheel = `src/agency`). Quality
  tools are ruff, pyright (`standard`), import-linter (4 contracts) and pytest. uv `exclude-newer = 2026-10-17`
  quarantines new releases (ADR-0006).
- **Web** (`web/`): pnpm and Next.js 16.4.2 (Turbopack, `output: 'standalone'`), TypeScript 5.9.3 strict,
  `node --test` for unit tests and Playwright 1.64.1 for e2e. pnpm applies a supply-chain quarantine
  (`pnpm-workspace.yaml`).
- **Docker**: `docker/compose.yaml` (project `design-agency-dashboard`, services `api` and `web`),
  `docker/server.Dockerfile` and `docker/web.Dockerfile`, with base images pinned by digest. Both `.dockerignore`
  files are allowlists that start with `*`.
- **Not present**: CI workflows (`.github/`, `.gitlab-ci.yml`, `.circleci/`), `justfile`, `flake.nix`,
  pre-commit, tox/nox, `setup.cfg`. Nothing runs these checks automatically; `make check` is run by hand.

### 1.2 Size by area (tracked files only)

Counts come from `tokei --no-ignore` over the exact `git ls-files` list (see §4 for why `--no-ignore` matters).
"Code" excludes comments, docstrings and blank lines; Markdown counts as 0 code lines in tokei. Both sessions gave
identical figures.

| Area | Tracked files | Lines | Code | Notes |
|---|---:|---:|---:|---|
| `src/` | 90 | 10,614 | 8,820 | Python package `agency` |
| `tests/` | 42 | 12,176 | 10,579 | 30 `.py` (8,488 lines / 6,929 code), 11 JSON snapshots (3,508), 1 SQL fixture (180) |
| `web/src/` | 31 | 2,954 | 2,587 | hand-written UI, including 5 `*.test.ts` and `globals.css` (622) |
| `web/src/api/schema.ts` | 1 | 1,415 | 934 | generated |
| `web/e2e/` | 8 | 566 | 470 | Playwright specs |
| `web/scripts/` | 2 | 138 | 108 | build helpers |
| `web/` config | 6 | 1,228 | 975 | includes `pnpm-lock.yaml` (1,052 lines) |
| `schemas/` | 1 | 2,894 | 2,894 | generated `openapi.json` |
| `registry/` | 3 | 535 | 535 | studio rules as JSON data |
| `prompts/` | 21 | 833 | — | Markdown prompts and skills |
| `docs/` | 53 | 2,788 | — | Markdown, including 43 ADRs |
| `docker/` | 5 | 132 | 94 | |
| `spikes/`, `evals/` | 2 | 47 | 23 | |
| root files | 10 | 496 | 284 | `uv.lock` (2,836 lines), `.env.example`, `.gitignore` and `.python-version` are not counted by tokei |
| `legacy/` | 151 | 14,701 | 8,777 | frozen backup, never edited |
| **Total** | **426** | | | |

Languages, excluding `legacy/` (these rows include the generated and lock files listed above):

| Language | Files | Lines | Code |
|---|---:|---:|---:|
| Python | 120 | 19,102 | 15,749 |
| JSON | 17 | 7,017 | 7,017 |
| TypeScript | 24 | 2,525 | 1,801 |
| TSX | 16 | 1,846 | 1,726 |
| YAML | 4 | 1,255 | 986 |
| CSS | 1 | 622 | 510 |
| TOML | 2 | 181 | 159 |
| SQL | 1 | 180 | 142 |
| JavaScript (`.mjs`) | 3 | 174 | 132 |
| Dockerfile | 4 | 73 | 51 |
| Shell | 1 | 26 | 23 |
| Makefile | 1 | 12 | 7 |
| Markdown | 77 | 3,803 | — |

### 1.3 Python modules (`src/agency`, code lines)

Package roll-up. The per-file figures are in §3.1.

| Package | Files | Lines | Code |
|---|---:|---:|---:|
| `agency.insights` | 17 | 2,816 | 2,304 |
| `agency.tools` | 9 | 1,812 | 1,526 |
| `agency.ledger` (incl. 6 migration files) | 11 | 1,315 | 1,105 |
| `agency.qa` (incl. 4 vendored scripts, 605 code) | 8 | 1,153 | 997 |
| `agency.graph` | 2 | 457 | 411 |
| `agency.contracts` | 10 | 491 | 360 |
| `agency.cli` | 1 | 367 | 318 |
| `agency.entrypoints` (Django server) | 9 | 401 | 307 |
| `agency.gateway` | 4 | 372 | 305 |
| `agency.agents` | 4 | 328 | 286 |
| `agency.telemetry` | 4 | 325 | 267 |
| `agency.evaluation` | 3 | 316 | 256 |
| `agency.artifacts` | 3 | 212 | 173 |
| `agency.runtime` | 1 | 133 | 115 |
| `agency.doctor` | 1 | 58 | 48 |
| `agency.config` | 1 | 54 | 39 |
| `agency` (`__init__`) | 1 | 3 | 2 |
| `agency.context` | 1 | 1 | 1 |

The largest single files are `tools/surface.py` (809 code), `graph/workflow.py` (410), `ledger/store.py` (396),
`insights/domain.py` (344) and `cli.py` (318).

### 1.4 Web modules (`web/`, code lines)

| File | Code | Unit test | Exercised by e2e |
|---|---:|---|---|
| `src/app/compare/page.tsx` | 400 | — | `compare.spec.ts` |
| `src/app/projects/[name]/page.tsx` | 203 | — | `run.spec.ts` |
| `src/app/projects/[name]/quality/page.tsx` | 193 | — | `quality.spec.ts` |
| `src/app/projects/[name]/replay/[instance]/page.tsx` | 171 | — | `replay.spec.ts` |
| `src/app/projects/[name]/phases/page.tsx` | 170 | — | `phases.spec.ts` |
| `src/components/context-chart.tsx` | 160 | — | `model.spec.ts` |
| `src/app/projects/[name]/model/page.tsx` | 126 | — | `model.spec.ts` |
| `src/components/timeline.tsx` | 67 | — | `run.spec.ts` |
| `src/api/client.ts` | 58 | — | all specs |
| `src/labels.ts` | 52 | `labels.test.ts` | |
| `src/app/projects/[name]/replay/page.tsx` | 52 | — | `replay.spec.ts` |
| `src/app/page.tsx` | 46 | — | `run.spec.ts` |
| `src/format.ts` | 34 | `format.test.ts` | |
| `src/components/unavailable.tsx` | 31 | — | `run.spec.ts` ("Django is off") |
| `src/app/layout.tsx` | 28 | — | all specs |
| `src/components/project-header.tsx` | 28 | — | all project specs |
| `src/chart.ts` | 27 | `chart.test.ts` | |
| `src/components/setbacks.tsx` | 26 | — | `phases.spec.ts` |
| `src/components/said.tsx` | 13 | — | `quality.spec.ts` |
| `src/app/not-found.tsx` | 12 | — | `run.spec.ts` |
| `src/timescale.ts` | 11 | `timescale.test.ts` | |
| `src/api/read.ts` | 11 | — | all specs |
| `src/proxy.ts` | 9 | — | `run.spec.ts` (Host checks) |
| `src/api/index.ts` | 8 | — | all specs |
| `src/loopback.ts` | 5 | `loopback.test.ts` | `run.spec.ts` |
| `src/app/globals.css` | 510 | — | `run.spec.ts` (phone width) |
| `scripts/check-defenses.mjs` | 89 | — | is itself a check (`pnpm run defenses`) |
| `scripts/standalone.mjs` | 19 | — | runs in every build |
| `next.config.mjs` | 24 | — | every build |

The e2e mapping above was read from the spec titles and routes. It is not a measurement.

### 1.5 Entry points

- Console scripts (`pyproject.toml`, `[project.scripts]`):
  - `agency` → `agency.cli:main`, with 14 subcommands: `doctor verify migrate run resume decide budget report runs
    compare judge artifacts restore insights`. `verify` is not listed in the README.
  - `agency-server` → `agency.entrypoints.server.serve:main`: Django + Django Ninja, read-only API, loopback only.
  - `agency-schemas` → `agency.entrypoints.server.schema:main`: writes `schemas/openapi.json`.
- `python -m agency.entrypoints.server` → `src/agency/entrypoints/server/__main__.py`.
- Django wiring: `entrypoints/server/{settings,urls,api,middleware}.py`.
- Alembic: `src/agency/ledger/migrations/env.py` and `versions/0001…0005`, run by `agency migrate`.
- QA scripts executed as programs inside the bwrap sandbox: `src/agency/qa/scripts/*.py`.
- Web: Next.js app router in `web/src/app` (9 routes plus the `proxy.ts` middleware); the `dev`, `build` and `start`
  scripts; the standalone server `web/.next/standalone/server.js`.
- Docker: `docker/compose.yaml` → images `design-agency/dashboard-api:local` and `design-agency/dashboard-web:local`.
- Test and verification only: `tests/dashboard_fixture.py` (builds the Playwright registry) and
  `spikes/sandbox_craft.sh` (the ADR-0005 sandbox check).

### 1.6 External dependencies

- **Python runtime** (versions from `uv.lock`; 136 packages resolved, 83 installed by `uv sync`): anthropic 1.15.0,
  langgraph 1.2.16, langgraph-checkpoint-sqlite 3.1.2, pydantic 2.14.1, pydantic-settings 2.16.0,
  sqlmodel 0.0.48, opentelemetry-sdk 1.45.1, opentelemetry-exporter-otlp-proto-http 1.45.1, pillow 13.0.0,
  alembic 1.20.0, django 5.2.18, django-ninja 1.7.1.
- **Python dev group**: pytest 9.1.1, ruff 0.17.1, pyright 1.1.414, import-linter 2.15, django-stubs 5.2.9.
- **Optional extras, declared and locked but not installed by `task setup`** (none can be imported in the
  environment): `context` (lancedb 0.40.0, transformers 5.20.1, torch 2.14.1), `qa` (trimesh 5.1.1,
  openimageio 3.2.1.3) and `telemetry` (langfuse 5.0.2).
- **Web** (exact pins; 62 packages installed): next 16.4.2, react 19.3.1, react-dom 19.3.1. Dev: @playwright/test
  1.64.1, @types/node 22.20.5, @types/react 19.3.0, @types/react-dom 19.3.0, openapi-typescript 7.13.0,
  typescript 5.9.3.
- **Machine binaries** (checked by `agency doctor`): vectorcraft-cli, effectcraft-cli, figcraft-cli, photocraft-cli,
  blender, ffmpeg, ffprobe, gs, bwrap, fc-match and docker are required; nvidia-smi is optional. All were present.
  Playwright also needs Chromium `chromium-1248` (present).
- **Docker base images**: `python:3.13.15-slim-trixie@sha256:7c61056e…`, `ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844…`,
  `node:22.22.1-trixie-slim@sha256:285a78d9…`.
- **External service**: the Anthropic API, used only through `agency.gateway` with the key from `.env`. No test calls it.

### 1.7 Paths that must never be edited

**Generated code (tracked)**

| Path | Generator | Guard |
|---|---|---|
| `schemas/openapi.json` | `uv run agency-schemas` (`task schemas`) | `tests/test_schemas.py`; regenerated byte-identical (§2) |
| `web/src/api/schema.ts` | `pnpm --dir web run api:types` | `pnpm --dir web run api:check`; regenerated byte-identical (§2) |
| `tests/snapshots/requests/*.json` (11) | `UPDATE_SNAPSHOTS=1 uv run pytest tests/test_request_snapshots.py` | `tests/test_request_snapshots.py` |

Generated and ignored (never commit them): `.venv/`, `web/node_modules/`, `web/.next/`, `web/.next-e2e/`,
`web/next-env.d.ts`, `web/tsconfig.tsbuildinfo`, `web/e2e/.data/`, `web/e2e/.results/`, `.task/`, `__pycache__/` and
the tool caches.

**Vendored code**

- `src/agency/qa/scripts/{logo_proof,optical_check,svg_audit,svg_parity}.py`: byte-identical copies of
  `legacy/claude-code-v1/src/.claude/skills/{logo-design,visual-qa}/scripts/`, excluded from ruff and pyright in
  `pyproject.toml`.
- `legacy/claude-code-v1/**` (151 files): the frozen backup. Its 150 hashes in `legacy/claude-code-v1/MANIFEST.sha256`
  are verified by `tests/test_registry.py:10` (`test_legacy_backup_is_frozen`).

**Lockfiles**: `uv.lock`, `web/pnpm-lock.yaml`, and the legacy ones (`legacy/…/tools/package-lock.json`,
`legacy/…/tools/requirements.lock`).

**User-facing strings and i18n resources**: there are no i18n resources (no catalogues, locale folders or message
files). Every string is an inline Italian literal. They are concentrated in:

- CLI: `src/agency/cli.py` (25 `help=` strings and the printed messages), `src/agency/doctor.py`, and the exception
  messages shown to the user across `src/agency` (for example `qa/evidence.py` and `ledger/schema.py`).
- Client-facing documents: `src/agency/tools/presentation.py`.
- Model-facing text: `prompts/**/*.md` (21 files), the 24 tool descriptions in `src/agency/tools/surface.py`, and the
  prefix composition in `src/agency/agents/prompts.py`. Changing any of them changes `tests/snapshots/requests/`.
- Dashboard copy: `web/src/labels.ts`, `web/src/format.ts`, `web/src/app/**/*.tsx` and `web/src/components/*.tsx`.

**Frozen by project rule** (hand-written, but immutable by convention)

- `src/agency/ledger/migrations/versions/0001…0005`: applied Alembic revisions; a schema change is a new revision.
- `tests/fixtures/ledger_schema_0001.sql`: the real 0001 schema, used by `tests/test_migrations.py:21`.
- `docs/adr/*.md`: a new or reversed decision is a new ADR (CLAUDE.md).
- `registry/*.json`: studio rules stored as data. Editing them changes behaviour, so it is never a refactor.

---

## 2. Commands and results

Sources searched: `Makefile`, `Taskfile.yml`, `web/package.json` scripts, `pyproject.toml`, `README.md`,
`docs/04-TOOLS.md` and `spikes/`. There is no CI, justfile or flake.

Every row ran in the worktree except row 16. The order was the # column, except row 3b, which ran right after row 5.
Granular rows call the Taskfile's own commands through `mise exec --`, as the Makefile does. **Duration** is
wall-clock time, including mise/uv start-up; the time the tool reports itself is in parentheses. **Warnings** is the
tool's own count where it prints one, otherwise the number of `warn|deprecat` lines in the log.

| # | Exact command | Exit | Duration (s) | Tests passed / failed / skipped | Warnings |
|---|---|---:|---:|---|---|
| 0 | `mise exec -- uv lock --check` (precaution, read-only) | 0 | 0.0 | — (lock up to date, 136 packages) | uv 0 |
| 1 | `make setup` | 0 | 0.9 | — (83 Python and 62 web packages installed) | mise 0, uv 0, pnpm 0 |
| 2 | `mise exec -- uv run ruff check .` | 0 | 0.1 | — ("All checks passed!", 116 `.py` files) | ruff 0 |
| 3a | `mise exec -- uv run ruff format --check .` | **1** | 0.1 | — ("1 file would be reformatted, 193 files already formatted") | ruff 0 |
| 3b | `mise exec -- uv run ruff format --check .` (retry) | 0 | 0.1 | — (194 files already formatted) | ruff 0 |
| 4 | `mise exec -- uv run lint-imports` | 0 | 0.3 | 4 contracts kept / 0 broken (132 files, 523 dependencies) | import-linter 0 |
| 5 | `mise exec -- uv run pyright` | 0 | 6.0 | — (116 files analysed) | pyright: 0 errors, 0 warnings, 0 informations |
| 6 | `mise exec -- uv run pytest` (run 1, cold) | 0 | 53.3 (50.25) | 496 / 0 / 0 | pytest 0 |
| 7 | `mise exec -- pnpm --dir web run api:check` | 0 | 0.5 | — (schema.ts matches openapi.json) | openapi-typescript 0 |
| 8 | `mise exec -- pnpm --dir web run typecheck` | 0 | 2.1 | — (`next typegen` + `tsc --noEmit`) | tsc 0 |
| 9 | `mise exec -- pnpm --dir web run test` | 0 | 0.2 | 18 / 0 / 0 (node --test) | node 0 |
| 10 | `mise exec -- pnpm --dir web run defenses` | 0 | 0.2 | — ("difese di ADR-0024 al loro posto") | 0 |
| 11 | `mise exec -- pnpm --dir web run build:e2e` | 0 | 4.6 | — (9 routes + proxy) | next 0 |
| 12 | `mise exec -- pnpm --dir web exec playwright test` (run 1) | 0 | 13.5 (13.1) | 22 / 0 / 0 | playwright 0 |
| 13 | `make doctor` | 0 | 3.6 | 13 ok / 1 `--` (API key, optional) | 0 |
| 14 | `mise exec -- task dashboard:build` | 0 | 4.7 | — (production standalone build) | next 0 |
| 15 | `bash spikes/sandbox_craft.sh` | 0 | 0.5 | 8 ok / 0 FAIL | 0 |
| 16 | `make schemas`, in a scratch export of `HEAD` (see below) | 0 | 0.9 | — (both outputs byte-identical to the committed files) | 0 |
| 17 | `make check` (run 2) | 0 | 80.8 | pytest 496 / 0 / 0 (48.62); web unit 18 / 0 / 0; Playwright 22 / 0 / 0 (13.1); ruff, import-linter and pyright as in rows 2, 3b, 4 and 5 | all 0 |
| 18 | `make test` (run 3) | 0 | 49.7 (47.58) | 496 / 0 / 0 | pytest 0 |
| 19 | `make e2e` (run 3) | 0 | 15.1 (12.5) | 22 / 0 / 0 | 0 |
| 20 | `make e2e` (run 4) | 0 | 15.3 (12.6) | 22 / 0 / 0 | 0 |
| 21 | pytest with the import recorder (§3; run 4) | 0 | 51.2 (49.09) | 496 / 0 / 0 | pytest 0 |

**Rows 3a/3b.** The failure came from this document, not from the codebase. ruff 0.17 also formats the Python code
blocks inside Markdown files, and every `.md` file counts: 193 = 116 `.py` + 77 tracked `.md` files outside
`legacy/`. The first draft of this file had an unformatted Python block. It was fixed in this file only, and the
check passed with 194 files (193 tracked plus this document). On the bare commit the count is 193, as in session 1.

**Row 16.** `schemas` overwrites two tracked files, so it ran in `git archive HEAD`, unpacked into a scratch folder
with its own `make setup`. `agency.config.REPO_ROOT` resolved to that folder, so nothing could reach the worktree. The
regenerated files matched the committed ones exactly in both sessions: `schemas/openapi.json` sha256
`2b0bcd51cdb62c5f…` and `web/src/api/schema.ts` sha256 `cbb7bb7ebd9f24b9…`. The scratch setup itself printed 27
warnings (pnpm slow-download notices and uv's "failed to hardlink" fallback), because `/tmp` is on another filesystem
than the caches. They belong to the scratch copy, not to the project.

Python test files: 27 `tests/test_*.py`, plus `conftest.py`, `dashboard_fixture.py` and `drawings.py`. No pytest test
was skipped in any run of either session: the VectorCraft-gated tests and the Docker-gated tests
(`docker compose config` only) all ran, because the binaries are present.

The slowest Python tests (row 21, `--durations=15`): 13 `test_sketch_flow.py` tests between 1.15 s and 2.29 s, plus
`test_doctor.py::test_doctor_never_exposes_the_key` 2.28 s and
`test_agent_flow.py::test_full_project_reaches_the_client_gate_and_is_approved` 1.68 s.

### 2.1 Checks of the nested location

The worktree now lives inside the main checkout, under the ignored `.worktrees/`. Each tool was checked to make sure
it doesn't read that parent `.gitignore` rule and silently skip the whole tree:

| Check | Result |
|---|---|
| `rg --files --hidden \| wc -l` | 427 = 426 tracked + this document |
| `ruff check --show-files .` | 116 `.py` files, the same set ruff formats |
| `pyright --outputjson` → `summary.filesAnalyzed` | 116 = 86 in `src` (vendored scripts excluded) + 30 in `tests` |
| `tokei src tests` (following ignore rules) | 120 Python files, the same as session 1 |
| §1 size tables, §3.1 module table | identical to session 1 (`diff` of the generated tables: no output) |
| `git status --porcelain` in the main checkout | clean: `.worktrees/` is ignored |
| Docker build context (main root) | `.worktrees/` excluded: both `.dockerignore` files are allowlists |

### 2.2 Session 1 (first location) compared

Session 1 ran the same commands from a fresh worktree at `/home/andreaaazo/Dev/design-agency-harness-audit-deep-review`.
Every row had the same exit code and the same test counts, except for the differences below.

| Row | Session 1 | Session 2 (baseline) |
|---|---|---|
| 3 `ruff format --check .` | exit 0, 193 files (this document did not exist yet) | 3a exit 1 / 3b exit 0, 194 files (see above) |
| 19 `make e2e` (run 3) | **21 / 0 / 1**: one test skipped (§4, F1) | 22 / 0 / 0 |
| 1 `make setup` | 2.3 s | 0.9 s |
| 5 `pyright` | 9.9 s | 6.0 s |
| 6 `pytest` (run 1) | 72.6 s (68.57) | 53.3 s (50.25) |
| 12 Playwright (run 1) | 20.0 s (19.4) | 13.5 s (13.1) |
| 17 `make check` | 77.9 s (pytest 48.75, Playwright 13.3) | 80.8 s (pytest 48.62, Playwright 13.1) |
| 18 `make test` | 52.5 s (50.34) | 49.7 s (47.58) |
| 20 `make e2e` (run 4) | 16.3 s, 22 / 0 / 0 | 15.3 s, 22 / 0 / 0 |
| 21 pytest + recorder | 53.5 s (51.36), 78 modules | 51.2 s (49.09), 78 modules |

### 2.3 Commands not run, and why

| Command | Why |
|---|---|
| `task docker:up` / `task docker:down` | Skipped by the user's decision. It would rebuild and re-tag the host's existing `design-agency/dashboard-{api,web}:local` images, built 2026-11-03 at 10:11 and 10:04 from an earlier commit, leave the old ones dangling, and start a long-running server. From a clean worktree it would also need `${AGENCY_DATA}` (default `<root>/.data`), which does not exist; that failure is expected but **not verified**. The static Compose checks in `tests/test_docker.py` ran as part of pytest. |
| `task dashboard`, `dashboard:dev`, `dashboard:api`, `dashboard:ui` | Long-running servers, not build or test commands. The same server programs (`agency-server`, the standalone Next.js server) are started and exercised by Playwright (rows 12, 19, 20). `dashboard:build` ran as row 14. |
| `uv run agency run/resume/decide/budget …` | They call the paid API. Not runnable here: there is no key in the worktree, and CLAUDE.md allows live runs only on request with a declared spending cap. |
| `uv run agency verify/report/runs/compare/artifacts/insights/migrate` | They need a real registry (`.data/`), which a clean worktree does not have. They are not build or test commands. |
| `UPDATE_SNAPSHOTS=1 uv run pytest tests/test_request_snapshots.py` | It rewrites tracked snapshots. The normal run already asserts that the snapshots match. |
| `ruff format .` (write mode) | Not a project command; only `--check` is defined. |
| `mise exec -- pnpm --dir web exec playwright install chromium` | It installs software; Chromium 1248 was already cached. |

---

## 3. Coverage

**There is no coverage tooling.** `uv.lock` and `pyproject.toml` contain no `coverage` or `pytest-cov`.
`web/package.json` and `pnpm-lock.yaml` contain no c8, istanbul, nyc or vitest. `node --test` runs without
`--experimental-test-coverage`. As the brief asks, this section therefore lists the modules with no tests at all,
using three measurements:

1. **Static**: an AST scan of `tests/*.py` for `import agency…` / `from agency… import …`. A module counts as
   imported "by name" when a test file names it, or imports it as a submodule.
2. **Dynamic**: the `agency.*` names present in `sys.modules` at the end of a full pytest session (row 21). The
   recorder plugin is in §5.
3. **Other paths**: a manual trace of code that tests run as a subprocess, inside the bwrap sandbox, or through
   Alembic's file loader. That code never appears as an `agency.*` import in the test process.

Status, for the 90 Python files: **direct** 60, **indirect** 18 (loaded during the session but imported by no test
file by name, for example through a package re-export such as `agency.ledger` → `ledger.store`), **other path** 9,
**none** 3.

### 3.1 Python modules with no tests at all

| Module | Code | Note |
|---|---:|---|
| `agency.context` | 1 | A docstring-only placeholder package (M1/M3). There is nothing to execute. |
| `agency.qa.scripts.logo_proof` | 174 | Vendored. Reachable through `run_check(check="logo_proof")` (`src/agency/qa/checks.py:46-55`), but no test requests that check, so that branch is untested too. |
| `agency.qa.scripts.optical_check` | 134 | Vendored. Same situation, `src/agency/qa/checks.py:37-45`. |

Per-file status (code lines; "by name" = the number of test files that import the module by name):

| Module | Code | By name | Status |
|---|---:|---:|---|
| `agency` | 2 | 7 | direct |
| `agency.agents` | 1 | 0 | indirect |
| `agency.agents.loop` | 183 | 3 | direct |
| `agency.agents.prompts` | 59 | 0 | indirect |
| `agency.agents.transcript` | 43 | 6 | direct |
| `agency.artifacts` | 4 | 7 | direct |
| `agency.artifacts.files` | 69 | 0 | indirect |
| `agency.artifacts.keeping` | 100 | 1 | direct |
| `agency.cli` | 318 | 7 | direct (also run as `uv run agency --help`) |
| `agency.config` | 39 | 16 | direct |
| `agency.context` | 1 | 0 | **none** |
| `agency.contracts` | 1 | 1 | direct |
| `agency.contracts.artifact` | 34 | 1 | direct |
| `agency.contracts.concept` | 10 | 1 | direct |
| `agency.contracts.gate` | 36 | 3 | direct |
| `agency.contracts.judgment` | 54 | 3 | direct |
| `agency.contracts.layout` | 34 | 4 | direct |
| `agency.contracts.outcome` | 20 | 4 | direct |
| `agency.contracts.phase` | 19 | 1 | direct |
| `agency.contracts.run` | 50 | 6 | direct |
| `agency.contracts.ticket` | 102 | 11 | direct |
| `agency.doctor` | 48 | 1 | direct |
| `agency.entrypoints` | 1 | 0 | indirect |
| `agency.entrypoints.server` | 5 | 2 | direct |
| `agency.entrypoints.server.__main__` | 3 | 0 | other path: subprocess `python -m` (`tests/test_server.py:396`) |
| `agency.entrypoints.server.api` | 148 | 0 | indirect (Django URLconf) |
| `agency.entrypoints.server.middleware` | 16 | 1 | direct |
| `agency.entrypoints.server.schema` | 36 | 1 | direct |
| `agency.entrypoints.server.serve` | 67 | 1 | direct |
| `agency.entrypoints.server.settings` | 26 | 0 | indirect (Django settings) |
| `agency.entrypoints.server.urls` | 5 | 0 | indirect (Django URLconf) |
| `agency.evaluation` | 1 | 2 | direct |
| `agency.evaluation.blind` | 104 | 2 | direct |
| `agency.evaluation.board` | 151 | 2 | direct |
| `agency.gateway` | 14 | 5 | direct |
| `agency.gateway.client` | 184 | 0 | indirect |
| `agency.gateway.pricing` | 36 | 1 | direct |
| `agency.gateway.transport` | 71 | 0 | indirect |
| `agency.graph` | 1 | 0 | indirect |
| `agency.graph.workflow` | 410 | 0 | indirect |
| `agency.insights` | 10 | 8 | direct |
| `agency.insights.adapters` | 1 | 0 | indirect |
| `agency.insights.adapters.projection` | 162 | 2 | direct |
| `agency.insights.adapters.registry` | 147 | 3 | direct |
| `agency.insights.adapters.stamps` | 10 | 0 | indirect |
| `agency.insights.adapters.traces` | 52 | 2 | direct |
| `agency.insights.adapters.transcripts` | 240 | 2 | direct |
| `agency.insights.application` | 127 | 2 | direct |
| `agency.insights.behaviour` | 122 | 2 | direct |
| `agency.insights.compare` | 232 | 2 | direct |
| `agency.insights.domain` | 344 | 9 | direct |
| `agency.insights.flow` | 185 | 2 | direct |
| `agency.insights.ports` | 92 | 6 | direct |
| `agency.insights.quality` | 134 | 2 | direct |
| `agency.insights.replay` | 140 | 2 | direct |
| `agency.insights.sums` | 38 | 0 | indirect |
| `agency.insights.views` | 268 | 5 | direct |
| `agency.ledger` | 4 | 15 | direct |
| `agency.ledger.chain` | 19 | 1 | direct |
| `agency.ledger.migrations.env` | 6 | 0 | other path: Alembic loader (`tests/test_migrations.py`) |
| `agency.ledger.migrations.versions.0001_baseline` | 264 | 0 | other path: Alembic loader (`tests/test_migrations.py`) |
| `agency.ledger.migrations.versions.0002_runs` | 38 | 0 | other path: Alembic loader (`tests/test_migrations.py`) |
| `agency.ledger.migrations.versions.0003_judgments` | 47 | 0 | other path: Alembic loader (`tests/test_migrations.py`) |
| `agency.ledger.migrations.versions.0004_usage_measures` | 19 | 0 | other path: Alembic loader (`tests/test_migrations.py`) |
| `agency.ledger.migrations.versions.0005_artifacts` | 45 | 0 | other path: Alembic loader (`tests/test_migrations.py`) |
| `agency.ledger.models` | 167 | 6 | direct |
| `agency.ledger.schema` | 100 | 2 | direct |
| `agency.ledger.store` | 396 | 0 | indirect (re-exported by `agency.ledger`) |
| `agency.qa` | 1 | 1 | direct |
| `agency.qa.checks` | 70 | 1 | direct |
| `agency.qa.delivery` | 209 | 1 | direct |
| `agency.qa.evidence` | 112 | 1 | direct |
| `agency.qa.scripts.logo_proof` | 174 | 0 | **none** |
| `agency.qa.scripts.optical_check` | 134 | 0 | **none** |
| `agency.qa.scripts.svg_audit` | 179 | 0 | other path: bwrap sandbox via `run_check` (`tests/test_agent_flow.py:93`) |
| `agency.qa.scripts.svg_parity` | 118 | 0 | other path: bwrap sandbox via `run_check` (`tests/test_agent_flow.py:518`) |
| `agency.runtime` | 115 | 3 | direct |
| `agency.telemetry` | 3 | 4 | direct |
| `agency.telemetry.fingerprint` | 64 | 2 | direct |
| `agency.telemetry.report` | 167 | 2 | direct |
| `agency.telemetry.setup` | 33 | 0 | indirect |
| `agency.tools` | 1 | 1 | direct |
| `agency.tools.board` | 128 | 1 | direct |
| `agency.tools.craft` | 119 | 6 | direct |
| `agency.tools.files` | 24 | 1 | direct |
| `agency.tools.master` | 100 | 0 | indirect |
| `agency.tools.presentation` | 193 | 1 | direct |
| `agency.tools.render` | 78 | 0 | indirect |
| `agency.tools.sandbox` | 74 | 5 | direct |
| `agency.tools.surface` | 809 | 5 | direct |

"Direct" or "indirect" means the module was loaded or named by tests. It does not mean its lines ran; only a real
coverage tool can measure that. Of the indirect modules, `graph/workflow.py` (410), `ledger/store.py` (396),
`gateway/client.py` (184) and `entrypoints/server/api.py` (148) are the largest.

### 3.2 Web modules

Unit tests exist only for `chart.ts`, `format.ts`, `labels.ts`, `loopback.ts` and `timescale.ts` (18 tests). Every
other file in `web/src` has no unit test. Every route is exercised by at least one Playwright spec (table in §1.4).
No web module is untested by both kinds of test, though line coverage is unknown.

---

## 4. Failures and flaky behaviour from a clean state

**No project command failed and no test failed** in either session. The only non-zero exit (row 3a) came from the
first draft of this document, as explained in §2.

**F1 — environment-dependent skip in e2e (flaky coverage, green exit).**
`web/e2e/run.spec.ts:173`, "Next.js e Django ascoltano solo su loopback", passed in 7 of the 8 e2e runs across both
sessions. It was **skipped** in session 1, run 3 (2026-11-03, 23:46:42–23:46:58), and the suite still exited 0. The
test calls `test.skip(addresses.length === 0, …)` (line 178) on the machine's non-internal IPv4 addresses
(`os.networkInterfaces()`, which leaves out interfaces that are not up and running). The NetworkManager journal shows
that `wlp99s0` lost its DHCP lease at 23:46:39 and got it back at 23:46:58; `docker0` was DOWN. So whenever the host
is offline, the "listens only on loopback" guarantee goes unchecked, and the run still looks green.
Reproduce: `journalctl -u NetworkManager --since "2026-11-03 23:46:00" --until "2026-11-03 23:47:30"`, or run
`make e2e` with networking disabled. Compare skip counts, not only exit codes, in the final comparison.

**F2 — first-run timing (not a failure).** Session 1's first pytest run reported 68.57 s; every other run in both
sessions reported between 47.58 and 51.36 s, including session 2's first run (50.25 s), which also started with no
`.venv` and no `__pycache__`. So cold bytecode is not the cause; the slow first run of session 1 is not explained
(OS file cache or machine load are possible but unverified). Playwright behaved the same way: 19.4 s in session 1's
first run, 12.5–13.6 s everywhere else. For timing comparisons, discard a first run and compare medians.

**Other observations from a clean state (not failures)**

- ruff 0.17 runs `ruff format --check` over every Markdown file and formats their Python code blocks. A Python
  snippet in any doc (including `docs/audit/`) is therefore part of `make check`.
- `agency doctor` reports the API key as `--` (optional): a fresh worktree has no `.env`. That is expected.
- `tests/conftest.py` makes the session fail if a test writes into the real `<root>/.data`. In a fresh worktree there
  is no `.data`, so this guard compares two empty snapshots. The baseline therefore does not exercise it; in the
  main checkout, where `.data` exists, it is active.
- tokei 13.0.0 skips `web/src/app/projects/**` (6 files, 965 lines) when it follows `.gitignore`: the `projects/`
  rule plus the `!/web/src/app/projects/` exception confuse it. Git tracks the files, and ripgrep 15.1.0 lists them
  correctly. The counts in §1 use `tokei --no-ignore` over `git ls-files`; any later count must do the same.

---

## 5. How to reproduce

```sh
# From the main checkout. A fresh equivalent of this worktree:
git worktree add .worktrees/audit/deep-review -b audit/deep-review 8d99a5c
cd .worktrees/audit/deep-review

mise exec -- uv lock --check
make setup
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
mise exec -- uv run lint-imports
mise exec -- uv run pyright
mise exec -- uv run pytest
mise exec -- pnpm --dir web run api:check
mise exec -- pnpm --dir web run typecheck
mise exec -- pnpm --dir web run test
mise exec -- pnpm --dir web run defenses
mise exec -- pnpm --dir web run build:e2e
mise exec -- pnpm --dir web exec playwright test
make doctor
mise exec -- task dashboard:build
bash spikes/sandbox_craft.sh
make check
make test
make e2e
make e2e

# schemas, without touching the worktree
mkdir -p "$SCRATCH/export" && git archive HEAD | tar -x -C "$SCRATCH/export"
cd "$SCRATCH/export" && MISE_TRUSTED_CONFIG_PATHS="$PWD" make setup && MISE_TRUSTED_CONFIG_PATHS="$PWD" make schemas
cmp schemas/openapi.json <worktree>/schemas/openapi.json
cmp web/src/api/schema.ts <worktree>/web/src/api/schema.ts

# sizes: tracked files only, without letting tokei follow .gitignore
git ls-files > files.txt && xargs -a files.txt -d '\n' tokei --no-ignore

# nested-location checks (§2.1)
rg --files --hidden | wc -l
mise exec -- uv run ruff check --show-files . | grep -c '\.py$'
mise exec -- uv run pyright --outputjson | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'])"
```

The import recorder used for §3 lives outside the repository. Put it in `$PLUGINS/audit_modules.py`:

```python
import os
import sys


def pytest_sessionfinish(session, exitstatus):
    names = sorted(n for n in sys.modules if n == "agency" or n.startswith("agency."))
    with open(os.environ["AUDIT_MODULES_OUT"], "w", encoding="utf-8") as out:
        out.write("\n".join(names) + "\n")
```

Then run `AUDIT_MODULES_OUT=imported.txt PYTHONPATH=$PLUGINS mise exec -- uv run pytest -p audit_modules --durations=15 -rs`.
It recorded 78 `agency.*` modules in both sessions.
