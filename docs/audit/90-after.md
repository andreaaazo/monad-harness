# 90 — After the sanity refactor

This compares the final state with `00-baseline.md`. It reruns the commands of the baseline's §5, builds the same table
as its §2 with a delta column, and lists the findings closed per phase and the ones deferred. Nothing was changed to
produce it, apart from this document.

| | Baseline | After |
|---|---|---|
| Commit measured | `8d99a5c` (2026-11-03) | `08f125c67f84d4635e5888cd13f4b5b59e528578` (2026-11-13), 141 commits later |
| Checkout | a fresh `git worktree add` of the commit | a fresh `git clone --branch audit/deep-review` into a scratch folder (see below) |
| Run | 2026-11-04, session 2 | 2026-11-13, one session, rows in the order of the table |
| Machine | Ubuntu 26.04.1 LTS, Linux 7.0.0-38 | the same machine, Linux 7.0.0-43 |
| Tools | mise 2026.10.3; node 22.22.1, pnpm 12.14.0, uv 0.12.5, task 3.54.0; CPython 3.13.15 | mise 2026.11.5; the other versions are unchanged (`mise.toml`, `.python-version`) |

**Why a clone and not a worktree.** The audit rules forbid git commands that write to the repository, and
`git worktree add -b` creates a branch and writes the repository's worktree list. A clone only reads the repository.
Like the baseline's worktree, it has a `.git`, so the tests that need a git checkout run too. The clone is the
committed `HEAD` and nothing else: no `.venv/`, `web/node_modules/`, `.next*/`, `.task/`, `.data/` or `.env`. The
machine caches were warm, as for the baseline (uv cache, pnpm store, mise installs, Chromium 1248). After every row,
`git status --porcelain` in the clone printed nothing.

---

## 1. Commands and results

The same rows as the baseline's §2, run the same way (through `mise exec --`, as the Makefile does). **Duration** is
wall-clock time; the tool's own time is in parentheses. The baseline's rows 3a and 3b were one row: 3a failed only on
the baseline document's own Python block. Rows 22–24 are new: they run what Phase 5 added.

| # | Command | Baseline | After | Delta |
|---|---|---|---|---|
| 0 | `uv lock --check` | exit 0; 136 packages | exit 0; 79 packages | −57 packages (Tasks 6.1, 6.2) |
| 1 | `make setup` | exit 0; 0.9 s; 83 Python + 62 web packages | exit 0; 0.6 s; 76 Python + 62 web | −7 installed Python packages (6.1) |
| 2 | `ruff check .` | exit 0; 116 `.py` files | exit 0; 144 `.py` files | +28 files |
| 3 | `ruff format --check .` | exit 0 (3b); 194 files | exit 0; 240 files | +46 files (`.py` and Markdown) |
| 4 | `lint-imports` | 4 contracts kept; 132 files, 523 dependencies | 5 kept, 0 broken; 144 files, 618 dependencies | +1 contract: only the gateway imports `anthropic` (`23b89e1`) |
| 5 | `pyright` | 0/0/0; 6.0 s; 116 files | 0/0/0; 6.8 s; 144 files | +28 files, no new diagnostic |
| 6 | `pytest` (run 1) | 496 / 0 / 0; 53.3 s (50.25) | 1164 / 0 / 0; 91.7 s (88.56) | +668 tests; +38.4 s |
| 7 | `pnpm run api:check` | exit 0; 0.5 s | exit 0; 0.4 s | — |
| 8 | `pnpm run typecheck` | exit 0; 2.1 s | exit 0; 1.8 s | — |
| 9 | `pnpm run test` | 18 / 0 / 0 | 18 / 0 / 0 | — |
| 10 | `pnpm run defenses` | "difese di ADR-0024 al loro posto" | "ADR-0024 defenses in place" | the developer message is in English (Phase 3) |
| 11 | `pnpm run build:e2e` | 9 routes + proxy; 4.6 s | 9 routes + proxy; 4.4 s | — |
| 12 | `playwright test` (run 1) | 22 / 0 / 0; 13.5 s (13.1) | 24 / 0 / 0; 13.9 s (13.4) | +2 tests (Task 6.15's characterization) |
| 13 | `make doctor` | 13 ok / 1 `--`; 3.6 s | 15 ok / 1 `--`; 1.1 s | +the Chromium row (5.5) and the sandbox-limits row (SEC-005, ADR-0046); the `--` is still the optional API key |
| 14 | `task dashboard:build` | exit 0; 4.7 s | exit 0; 4.4 s | — |
| 15 | `bash spikes/sandbox_craft.sh` | 8 ok / 0 FAIL; 0.5 s | 8 ok / 0 FAIL; 0.9 s | now runs in the engine's own sandbox (5.10) |
| 16 | `make schemas` in a `git archive` export | outputs byte-identical | outputs byte-identical (`openapi.json` sha256 `e6d3bdd2…`, `schema.ts` `034fc4a3…`) | the files themselves changed with Phase 2; they still regenerate exactly |
| 17 | `make check` | 80.8 s; pytest 496 (48.62), web 18, Playwright 22 (13.1) | 112.8 s; `uv lock --check`, pytest 1164 (85.20), web 18, Playwright 24 (13.3) | +32.0 s, all of it pytest; one more step first (5.4) |
| 18 | `make test` | 496; 49.7 s (47.58) | 1164; 87.1 s (84.73) | +668 tests |
| 19 | `make e2e` (run 3) | 22; 15.1 s (12.5) | 24; 15.3 s (13.0) | +2 tests |
| 20 | `make e2e` (run 4) | 22; 15.3 s (12.6) | 24; 15.3 s (13.0) | +2 tests |
| 21 | pytest with the import recorder | 496; 51.2 s (49.09); 78 `agency.*` modules | 1164; 86.9 s (84.49); 86 modules | +8 modules imported by the tests |
| 22 | `task check:fast` | — | exit 0; 8.4 s | new (5.11): the pre-commit hook's checks |
| 23 | `.githooks/pre-commit`, `PATH=/usr/bin:/bin` | — | exit 0; 8.2 s | new (5.11): works without mise active |
| 24 | `task check:clean` | — | exit 0; 123.2 s; pytest 1160 / 0 / 4 skipped, web 18, Playwright 24 | new (5.11); the 4 skips are the tests that need a git clone, since the copy is the index (ADR-0051) |

**Warnings.** Every row reported 0 warnings of its own; pyright reported 0 errors, 0 warnings and 0 informations
everywhere. The only warning lines are in row 24: uv's "Failed to hardlink" and pnpm's store notice, both because
`check:clean`'s copy lives in `/tmp`, on another filesystem than the caches. That is the same situation the baseline
noted for its scratch export, and the README now documents it.

**Time.** The test suite grew from 496 to 1164 tests, and it accounts for the whole difference in `make check`:
pytest runs 85 s instead of 49 s. The slowest tests (row 21, `--durations=15`): `test_recording.py::
test_a_recorded_run_replays_to_the_same_ledger` 3.85 s, then `test_sketch_flow.py` tests between 1.6 s and 2.7 s and
the two sandbox-timeout tests of `test_agent_flow.py` at 2.0 s each. No test was skipped in rows 6, 17, 18 and 21:
VectorCraft, bwrap, Docker and a git checkout were all present.

**Files seen by the tools** (the baseline's §2.1 checks, run in the clone):

| Check | Baseline | After |
|---|---|---|
| tracked files (`git ls-files`) | 426 | 495 |
| `rg --files --hidden` (without `.git`) | 427 (426 tracked + the baseline document) | 494: every tracked file except `legacy/claude-code-v1/src/.claude/settings.local.json`, which `legacy/`'s own `.gitignore` names |
| `ruff check --show-files .` | 116 `.py` | 144 `.py` |
| pyright `filesAnalyzed` | 116 | 144 (0 errors, 0 warnings) |

---

## 2. Size by area (tracked files only)

Measured as in the baseline's §1.2: `tokei --no-ignore` over the exact `git ls-files -z` list. The baseline read the
list with `git ls-files`, which quotes a path with a non-ASCII character. One ADR has "ciò" in its name, so `-z` is
needed to pass it to tokei as it is. Markdown counts as 0 code lines.

| Area | Files | Lines | Code | Main reasons |
|---|---|---|---|---|
| `src/` | 90 → 102 (+12) | 10,614 → 12,978 (+2,364) | 8,820 → 10,740 (+1,920) | Phase 2's fixes, three chain migrations, the new contracts modules |
| `tests/` | 42 → 77 (+35) | 12,176 → 21,593 (+9,417) | 10,579 → 18,049 (+7,470) | Phase 1's characterization tests and every fix's test; 17 CLI help snapshots; `tests/support/` |
| `web/src/` | 31 → 32 (+1) | 2,954 → 2,951 (−3) | 2,587 → 2,570 (−17) | `ScrollRegion` and `measured` (6.15) |
| `web/src/api/schema.ts` | 1 → 1 | 1,415 → 1,419 | 934 → 934 | generated |
| `web/e2e/` | 8 → 8 | 566 → 660 (+94) | 470 → 555 (+85) | the scroll-region and compare-table characterization |
| `web/scripts/` | 2 → 2 | 138 → 142 | 108 → 106 | |
| `web/` config | 6 → 6 | 1,228 → 1,234 | 975 → 977 | |
| `schemas/` | 1 → 1 | 2,894 → 2,894 | 2,894 → 2,894 | generated |
| `registry/` | 3 → 3 | 535 → 535 | 535 → 535 | unchanged |
| `prompts/` | 21 → 21 | 833 → 833 | — | unchanged |
| `docs/` | 53 → 72 (+19) | 2,788 → 9,217 (+6,429) | — | the 10 audit reports and plan, 9 new ADRs (0044–0052) |
| `docker/` | 5 → 5 | 132 → 132 | 94 → 94 | unchanged |
| `.githooks/` | 0 → 1 | 0 → 14 | 0 → 10 | the pre-commit hook (5.11) |
| `spikes/`, `evals/` | 2 → 2 | 47 → 80 | 23 → 46 | the spike runs in the engine's sandbox (5.10) |
| root files | 10 → 11 | 496 → 699 | 284 → 367 | `.editorconfig` (5.13); the README (5.12) |
| `legacy/` | 151 → 151 | 14,701 → 14,701 | 8,777 → 8,777 | frozen: unchanged, as its hash test checks |
| **Total** | **426 → 495 (+69)** | | | |

By language, without `legacy/`: Python 120 → 148 files and 15,749 → 25,114 code lines, most of it tests; TypeScript
and TSX 40 → 41 files and 3,527 → 3,597 code lines; Markdown 77 → 97 files.

---

## 3. Findings closed, per phase

The seven audits reported 109 findings. The plan maps each one to its tasks; a finding that two phases touched, part
each, is listed under both.

| Phase | Tasks done / open | Findings it closes |
|---|---|---|
| 1. Characterization tests | 19 / 0 | TST-001 to TST-016; TST-017 (with 5.2); STR-002, STR-014; CMT-008 (with Phase 3) |
| 2. Bug fixes | 97 / 5 | COR-001 to COR-016; SEC-001 to SEC-009 except SEC-004; DX-003; STR-001, STR-005 (part), STR-008; SIM-001 (the crash), SIM-006 (part), SIM-008; TST-009 (with 1.8); CMT-007 (with 3.12) |
| 3. Comments and language | 22 / 0 | CMT-001 to CMT-019, except CMT-017 (by decision); STR-011 (the comment part) |
| 4. File structure | 6 / 0 | STR-003, STR-009, STR-015, STR-016; STR-004 (the `tools → agents` edge); STR-005 (one registry loader); SIM-005 and SIM-006 (the moves) |
| 5. Developer experience | 13 / 0 | DX-001, DX-002, DX-004 to DX-013 (DX-009 without its CI stage); SEC-008 (the spike); STR-011 (the Python pin); STR-012; STR-017 (the README part); TST-017, TST-018 |
| 6. Sanity refactor | 16 / 0 | SIM-001 (one reader), SIM-002, SIM-003, SIM-004 (declared), SIM-005 (the rest), SIM-007, SIM-009, SIM-010 (the runnable set and a drift test), SIM-011 (the hash), SIM-013, SIM-015, SIM-016, SIM-017; STR-005 (the check-kind literals); STR-006; STR-011 (the key names and e2e values) |

Phase 6 closed some findings only in part, on purpose; the plan records why for each:

- **SIM-007:** `Sandbox(read_only=…)` stayed. Since Task 5.10 the Craft spike passes it.
- **SIM-010:** the `closes` and `conditional` fields on `Tool` were rejected. They would have moved facts without
  removing any, because the reminder's list must keep its order. A test now keeps the two closer lists in step.
- **SIM-011:** the two `clip` helpers stay apart, because merging them changes output. The two `BUSY_SECONDS` stay
  apart too: they are two independent waits.

Each Phase 6 code hotspot went through `/ce-simplify-code`. Five first got a characterization unit for behaviour
no test pinned: 6.5, 6.7, 6.9, 6.11 and 6.15. Two got a guard test after the refactor: 6.8 keeps the closer lists in
step, and 6.13 ties the web files to the key names and e2e values.

---

## 4. Deferred and still open

**Deferred by decision** (the plan's "Not planned in this refactor"):

| Finding | Where it goes |
|---|---|
| STR-004 (beyond `tools → agents`), STR-007, STR-013, SIM-012 | M1.7: the `qa ↔ tools` cycle, the CLI renderer move, the large test files, the `surface.py` / `workflow.build` split (Q18, Q19) |
| SIM-004 (the `langchain_core` import) | Moves to the process layer in M1.7 (Q7); it is declared meanwhile (6.3) |
| CMT-014, CMT-015 (outside 3.20), CMT-017 | Closed by decision (Q14) |
| STR-010, STR-017 (empty package, ADR file name, `prompts/roles/`) | Closed by decision: they would change fingerprint keys or frozen files |
| SIM-014 | Drop the unused column in the next migration needed for its own sake |
| DX-009 (the CI stage) | When a Git remote exists, before M6 at the latest: CI runs `task check` on a clean checkout, and `check:clean` becomes the pre-push hook (ADR-0051) |

**Still open in the plan:**

- **Task 2.7 (SEC-004):** closed after this report as not reproduced. Every route its probe tried is now a test.
- **Tasks 2.F59–2.F62:** found during Phase 2, after the audits.
  - 2.F59: `write_new_under`, deleted after this report.
  - 2.F60: `Ledger.add_concept`, code that only the tests use.
  - 2.F61 and 2.F62: a second list of reviewer roles, and direction role names built from a letter.

**Left for a decision, from Phase 6** (each recorded under its task in `PLAN.md`):

- **Behaviour changes, not made:**
  - one `clip` for tool results and dashboard refusals;
  - the reason the closing reminder does not offer `reject_concept`, which no history records.
- **Larger than a hotspot:**
  - typing `registry.CHECKS` and `ROLES` as `CheckSpec` and `RoleSpec` (left from Task 4.2);
  - a `check_kind(name)` helper;
  - a per-module dependency check, which would also declare `langgraph-checkpoint` and `opentelemetry-api` (ADR-0052's limit);
  - two inline `Settings(...)` builds in `test_request_snapshots.py` and `test_gate_sandbox.py`.

**Left from Phase 5's second clean-clone walk-through** (`PLAN.md`, Phase 5 verification):

- the clone source the README cannot name until a remote exists;
- how to tell whether mise is already active;
- why the Chromium line carries `mise exec --`;
- uv's `UV_LINK_MODE` hint;
- a cold-cache time and size estimate.

---

## 5. How to reproduce

```sh
# A fresh clone of the final HEAD, outside the repository (a clone only reads it)
git clone --branch audit/deep-review /home/andreaaazo/Dev/design-agency-harness "$SCRATCH/after"
cd "$SCRATCH/after" && export MISE_TRUSTED_CONFIG_PATHS="$PWD"

# rows 0-21: the baseline's §5, in the same order
mise exec -- uv lock --check
make setup
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
mise exec -- uv run lint-imports
mise exec -- uv run pyright
mise exec -- uv run pytest -o addopts= -q
mise exec -- pnpm --dir web run api:check
mise exec -- pnpm --dir web run typecheck
mise exec -- pnpm --dir web run test
mise exec -- pnpm --dir web run defenses
mise exec -- pnpm --dir web run build:e2e
mise exec -- pnpm --dir web exec playwright test
make doctor
mise exec -- task dashboard:build
bash spikes/sandbox_craft.sh
# row 16: schemas in a git archive export, compared with the clone's files
make check
make test
make e2e
make e2e
AUDIT_MODULES_OUT=imported.txt PYTHONPATH=$PLUGINS mise exec -- uv run pytest -o addopts= -q -p audit_modules --durations=15 -rs

# rows 22-24: what Phase 5 added
mise exec -- task check:fast
env -i HOME="$HOME" PATH=/usr/bin:/bin MISE_TRUSTED_CONFIG_PATHS="$PWD" .githooks/pre-commit
mise exec -- task check:clean

# sizes: tracked files only, with their real names
git ls-files -z | xargs -0 tokei --no-ignore
```

The import recorder is the baseline's (`00-baseline.md`, §5). The findings per phase come from `PLAN.md`: its tasks'
checkboxes and its "Coverage check: finding → task" map.
