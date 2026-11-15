# 99 — Result

The final state of `audit/deep-review` against `00-baseline.md`. It reruns every command of the baseline's §5 on the
final commit, measures coverage and sizes the same way, gives the final status of every finding, and checks that no
user-facing behaviour changed beyond the approved fixes. `90-after.md` measured the branch before its final review;
this report supersedes its numbers. Producing it changed no tracked file apart from the documents of the final unit.

| | Baseline | Result |
|---|---|---|
| Commit measured | `8d99a5c` (2026-11-03) | `df47e90483193bf4bbd80072c6d8b37326c8ede1` (2026-11-13), 159 commits later |
| Checkout | a fresh `git worktree add` of the commit | a fresh `git clone --branch audit/deep-review` into a scratch folder: a clone only reads the repository |
| Run | 2026-11-04, session 2 | 2026-11-13 16:26 UTC, one session, rows in the order of the table |
| Machine | Ubuntu 26.04.1 LTS, Linux 7.0.0-38 | the same machine, Linux 7.0.0-43 |
| Tools | mise 2026.10.3; node 22.22.1, pnpm 12.14.0, uv 0.12.5, task 3.54.0; CPython 3.13.15 | mise 2026.11.5; node, pnpm, uv and task unchanged in `mise.toml`; `.python-version` now pins 3.13.15 (`e001621`), the version the baseline already ran |

The clone has no `.venv/`, `web/node_modules/`, `.next*/`, `.task/`, `.data/` or `.env`; the machine caches were warm,
as for the baseline. After every row, `git status --porcelain` in the clone printed nothing (25 of 25 rows).

## 1. Before and after

| Measure | Baseline | Result | Delta |
|---|---|---|---|
| Python tests (pytest, passed / failed / skipped) | 496 / 0 / 0 | 1218 / 0 / 0 | +722 |
| Web unit tests (`node --test`) | 18 / 0 / 0 | 18 / 0 / 0 | — |
| Playwright e2e | 22 / 0 / 0 | 24 / 0 / 0 | +2 |
| Clean-checkout gate (`task check:clean`) | did not exist | 1214 passed, 4 skipped (they need a git clone), web 18, Playwright 24 | new |
| Module coverage: `agency` modules with a test by name / loaded only / run another way / none | 60 / 18 / 9 / 3 of 90 | 72 / 14 / 13 / 3 of 102 | +12 direct; the same 3 untested |
| `agency.*` modules loaded in a full session | 78 | 86 | +8 |
| Warnings: ruff, ruff format, import-linter, pyright, pytest, tsc, `node --test`, `next build`, Playwright | 0 each | 0 each | — |
| pyright | 0 errors, 0 warnings, 0 informations (116 files) | 0 errors, 0 warnings, 0 informations (148 files) | +32 files, no diagnostic |
| import-linter | 4 contracts kept, 0 broken | 5 kept, 0 broken | +1: only the gateway imports `anthropic` |
| Build time: `build:e2e` / `dashboard:build` | 4.6 s / 4.7 s | 4.4 s / 4.5 s | −0.2 s each |
| `make check` wall time (pytest's own time) | 80.8 s (48.6 s) | 111.7 s (84.6 s) | +30.9 s, all of it the +722 tests |
| Code lines in `src/agency` (tokei) | 8,820 | 10,888 | +2,068 |
| Code lines in `tests/` | 10,579 | 18,620 | +8,041 |
| Locked Python packages (`uv lock --check`) | 136 | 79 | −57: the unused extras and OTLP exporter removed (`4ab753b`, `9da57c3`), imported packages declared (`ab7d394`) |
| Tracked files | 426 | 502 | +76 |

**Coverage method.** There is still no line-coverage tool: adding one is a dependency decision (a package under the
two-week quarantine, ADR-0006), so the measure is the baseline's §3. A module is **by name** when a test file imports
it, **loaded** when it is in `sys.modules` at the end of a full session (the recorder of the baseline's §5), and **run
another way** when the tests reach it through a subprocess, the sandbox or Alembic's loader (the migration modules,
`__main__`, `svg_audit` and `svg_parity`). The static scan reproduces the baseline's 60 when run on the tests of
`8d99a5c`. It now reads `tests/support/` too, which did not exist then. The three modules with no test are the same as
at the baseline: `agency.context` (a placeholder) and the vendored `logo_proof` and `optical_check`, which are pinned
by their bytes but never run.

**Warnings.** Every tool reported zero warnings of its own. The only warning lines are in row 1 and row 24: uv's "Failed
to hardlink files" and pnpm's store notice, because the clone and the `check:clean` copy live in `/tmp`, on another
filesystem than the caches. The baseline saw the same in its scratch export, and the README documents it. The same
fallback explains `make setup` taking 5.4 s instead of 0.9 s: uv copies the 76 packages instead of linking them.

### 1.1 Code lines per module (`src/agency`, tokei, code lines)

| Package | Files | Lines | Code | Delta (code) | Main reasons |
|---|---|---|---|---|---|
| `agency.insights` | 17 → 17 | 2,816 → 2,847 | 2,304 → 2,326 | +22 | ticket order, broken streams, torn transcript lines |
| `agency.tools` | 9 → 9 | 1,812 → 2,250 | 1,526 → 1,896 | +370 | no-follow reads and writes, replay safety, sandbox limits and environment |
| `agency.ledger` | 11 → 15 | 1,315 → 2,013 | 1,105 → 1,700 | +595 | hash chain v2 and its replay; migrations 0006–0009 |
| `agency.qa` | 8 → 8 | 1,153 → 1,221 | 997 → 1,052 | +55 | no-follow hashing and globbing; `svg_audit` fixes |
| `agency.contracts` | 10 → 16 | 491 → 1,112 | 360 → 819 | +459 | `files` (no-follow helpers, `land`), `registry`, `layout`, `project`, `media`, `text`, `secrets` |
| `agency.cli` | 1 → 1 | 367 → 544 | 318 → 467 | +149 | locks, refusals before any work, one-line outside text |
| `agency.graph` | 2 → 2 | 457 → 480 | 411 → 431 | +20 | no-follow copies in the nodes |
| `agency.gateway` | 4 → 5 | 372 → 461 | 305 → 381 | +76 | budget reservation, retries, fallback charges, recording |
| `agency.entrypoints` | 9 → 9 | 401 → 447 | 307 → 343 | +36 | data root, project names, help text kept as constants |
| `agency.agents` | 4 → 4 | 328 → 365 | 286 → 319 | +33 | fallback and context-window handling |
| `agency.telemetry` | 4 → 4 | 325 → 346 | 267 → 289 | +22 | unreadable fingerprints, control characters |
| `agency.evaluation` | 3 → 3 | 316 → 338 | 256 → 277 | +21 | judge in the sandbox, paths walked with `land` |
| `agency.artifacts` | 3 → 3 | 212 → 254 | 173 → 212 | +39 | restore through the no-follow helpers |
| `agency.runtime` | 1 → 1 | 133 → 197 | 115 → 167 | +52 | project lock, brief validation |
| `agency.doctor` | 1 → 1 | 58 → 119 | 48 → 100 | +52 | Chromium, sandbox scope |
| `agency.config` | 1 → 1 | 54 → 104 | 39 → 80 | +41 | `.env` holds only the key, absolute roots |
| `agency.registry` | — → 1 | — → 37 | — → 23 | +23 | the studio rules, loaded once |
| `agency`, `agency.context` | 2 → 2 | 4 → 8 | 3 → 6 | +3 | docstrings |
| **Total** | **90 → 102** | **10,614 → 13,161** | **8,820 → 10,888** | **+2,068** | |

### 1.2 Size by area (tracked files)

`tokei --no-ignore` over `git ls-files -z`, as the baseline's §1.2. Markdown counts as 0 code lines.

| Area | Files | Lines | Code |
|---|---|---|---|
| `src/` | 90 → 103 | 10,614 → 13,161 | 8,820 → 10,888 |
| `tests/` | 42 → 80 | 12,176 → 22,294 | 10,579 → 18,620 |
| `web/src/` (hand-written) | 31 → 32 | 2,954 → 2,951 | 2,587 → 2,570 |
| `web/src/api/schema.ts` (generated) | 1 → 1 | 1,415 → 1,419 | 934 → 934 |
| `web/e2e/` | 8 → 8 | 566 → 660 | 470 → 555 |
| `web/scripts/` | 2 → 2 | 138 → 142 | 108 → 106 |
| `web/` config | 6 → 6 | 1,228 → 1,234 | 975 → 977 |
| `schemas/` (generated) | 1 → 1 | 2,894 → 2,894 | 2,894 → 2,894 |
| `registry/` | 3 → 3 | 535 → 535 | 535 → 535 |
| `prompts/` | 21 → 21 | 833 → 833 (byte-identical) | — |
| `docs/` | 53 → 75 | 2,788 → 9,756 | — |
| `docker/` | 5 → 5 | 132 → 132 | 94 → 94 |
| `spikes/`, `evals/` | 2 → 2 | 47 → 89 | 23 → 51 |
| root files and `.githooks/` | 10 → 12 | 496 → 713 | 284 → 377 |
| `legacy/` | 151 → 151 | 14,701 → 14,701 | 8,777 → 8,777 (frozen, unchanged) |
| **Total** | **426 → 502** | | |

`schemas/openapi.json`, `registry/roles.json` and the `docker/` files changed content at the same size: translated
descriptions and comments (Task 3.2, `e8a4531`), the role tool sets (Task 2.34), and the data-root variable (STR-001).
The two new files at the root are `.editorconfig` and `.githooks/pre-commit`. File counts come from `git ls-files -z`:
one ADR has a non-ASCII name that a plain `git ls-files` quotes.

## 2. Every command of the baseline

The rows of the baseline's §2 and §5, run the same way (`mise exec --`, as the Makefile does), plus the three rows
Phase 5 added. **Duration** is wall-clock seconds; the tool's own time is in parentheses.

| # | Command | Baseline | Result |
|---|---|---|---|
| 0 | `uv lock --check` | exit 0; 136 packages | exit 0; 79 packages |
| 1 | `make setup` | exit 0; 0.9 s; 83 Python + 62 web packages | exit 0; 5.4 s; 76 Python + 62 web (copied, see Warnings) |
| 2 | `ruff check .` | exit 0; 116 `.py` files | exit 0; 148 `.py` files |
| 3 | `ruff format --check .` | exit 0 (3b); 194 files | exit 0; 247 files (`.py` and Markdown) |
| 4 | `lint-imports` | 4 kept; 132 files, 523 dependencies | 5 kept, 0 broken; 144 files, 620 dependencies |
| 5 | `pyright` | 0/0/0; 6.0 s; 116 files | 0/0/0; 6.6 s; 148 files |
| 6 | `pytest` (run 1) | 496 / 0 / 0; 53.3 s (50.25) | 1218 / 0 / 0; 91.8 s (88.73) |
| 7 | `pnpm run api:check` | exit 0; 0.5 s | exit 0; 0.4 s |
| 8 | `pnpm run typecheck` | exit 0; 2.1 s | exit 0; 1.8 s |
| 9 | `pnpm run test` | 18 / 0 / 0 | 18 / 0 / 0 |
| 10 | `pnpm run defenses` | "difese di ADR-0024 al loro posto" | "ADR-0024 defenses in place" (developer message, Phase 3) |
| 11 | `pnpm run build:e2e` | 9 routes + proxy; 4.6 s | 9 routes + proxy; 4.4 s |
| 12 | `playwright test` (run 1) | 22 / 0 / 0; 13.5 s (13.1) | 24 / 0 / 0; 13.9 s (13.4) |
| 13 | `make doctor` | 13 ok / 1 `--`; 3.6 s | 15 ok / 1 `--`; 1.1 s (Chromium and the sandbox scope added; the `--` is the optional key) |
| 14 | `task dashboard:build` | exit 0; 4.7 s | exit 0; 4.5 s |
| 15 | `bash spikes/sandbox_craft.sh` | 8 ok / 0 FAIL; 0.5 s | 9 ok / 0 FAIL; 0.7 s (the ninth is R8's "no key in the sandbox") |
| 16 | `make schemas` in a `git archive` export | outputs byte-identical | outputs byte-identical: `openapi.json` sha256 `e6d3bdd2…`, `schema.ts` `034fc4a3…` |
| 17 | `make check` | 80.8 s; pytest 496 (48.62), web 18, Playwright 22 (13.1) | 111.7 s; `uv lock --check`, pytest 1218 (84.63), web 18, Playwright 24 (13.1) |
| 18 | `make test` | 496; 49.7 s (47.58) | 1218; 87.0 s (84.70) |
| 19 | `make e2e` (run 3) | 22; 15.1 s (12.5) | 24; 15.6 s (13.2) |
| 20 | `make e2e` (run 4) | 22; 15.3 s (12.6) | 24; 15.6 s (13.2) |
| 21 | pytest with the import recorder | 496; 51.2 s (49.09); 78 modules; 0 skipped | 1218; 87.7 s (85.50); 86 modules; 0 skipped |
| 22 | `task check:fast` | — | exit 0; 8.3 s |
| 23 | `.githooks/pre-commit` with `PATH=/usr/bin:/bin` | — | exit 0; 8.2 s |
| 24 | `task check:clean` | — | exit 0; 120.7 s; pytest 1214 / 0 / 4 skipped, web 18, Playwright 24 |

No test was skipped in rows 6, 17, 18 and 21: VectorCraft, bwrap, the systemd user session, Docker and a git checkout
were all present. The baseline's flaky e2e skip (F1) is gone: the loopback test reads `/proc/net/tcp` and never skips
(Task 1.11). The slowest tests (row 21) are `test_recording.py::test_a_recorded_run_replays_to_the_same_ledger` at
3.82 s, then `test_sketch_flow.py` flows between 1.6 s and 2.4 s and two sandbox-timeout tests at about 2.0 s.

**Files seen by the tools** (the baseline's §2.1): 502 tracked; `rg --files --hidden` without `.git` lists 501, every
tracked file except `legacy/claude-code-v1/src/.claude/settings.local.json`, which `legacy/`'s own `.gitignore` names;
`ruff check --show-files` and pyright both see 148 `.py` files.

## 3. Findings

The audit reported 109 findings. `SUMMARY.md`, section "Final status", gives each one its status with the commits
that close it:

| Status | Count | |
|---|---|---|
| Fixed | 101 | 8 of them leave a remainder that is deferred or rejected, named in the table |
| Deferred | 5 | STR-004, STR-007, STR-013, SIM-012 (to M1.7); SIM-014 (to the next migration with a reason of its own) |
| Rejected | 3 | CMT-014, CMT-017, STR-010, all by the owner's decision |

By severity: the 1 Critical, the 5 High and the 17 Medium findings are all Fixed. Of the 72 Low, 66 are Fixed (one
merged into another), 4 Deferred and 2 Rejected; of the 14 Nits, 12 are Fixed, 1 Deferred and 1 Rejected.

**The final review** (`/ce-code-review`, four rounds; `PLAN.md`, "Final review" and the sections after it) found no P0
or P1 introduced by the branch; the one P1 (R1) was there at the baseline. Andrea chose which findings to fix; the
fixes are eleven units, each its own commit:

| Unit | Severity | What | Commit |
|---|---|---|---|
| R1 | P1, pre-existing | the API key was readable inside the sandbox at `/proc/1/environ` | `1959bd1` |
| R2 | P3 | `agency judge` lost the project for a path with `..` (and `restore` wrote through a planted link) | `0ea7aa0` |
| R3 | testing gap | the tests read the operator's `AGENCY_*` variables and key | `5739f5d` |
| R4 | P2 | the hash chain did not bind a ticket's project (ADR-0053, migration 0009) | `fb3952b` |
| R5 | P3 ×3 | R2 went too far: one path rule for judge and restore | `ac5afe1` |
| R6 | P3 | the isolation fixture missed lower-case key names; 0009's order unpinned | `3290bf9` |
| R7 | P2 | `agency verify` compares the project of every event (ADR-0054) | `59649c7` |
| R8 | P3, pre-existing | the Craft spike started bwrap with the whole shell environment | `cff7084` |
| R9 | P2 | judge and restore walk typed paths as the kernel does (`land`) | `6f78d2b` |
| R10 | testing gap | the spike's key probe had no positive control | `3e1feff` |
| R11 | P3 ×2 | `land` stops at a file; restore refuses a dangling link again | `df47e90` |

The independent cross-model reviewer (Codex, `gpt-6-luna`) ran in rounds 3 and 4, with Andrea's authorization: over
the whole branch `main...HEAD`, then over R9 and R10. R11 closes round 4's findings and was not reviewed again: its
evidence is its tests and the full run of §2, made on R11's commit. The reports of rounds 3 and 4 are in
`/tmp/compound-engineering-1000/ce-code-review/`; those of rounds 1 and 2 are no longer there, so `PLAN.md` is the
record of all four.

## 4. User-facing behaviour

Checked surface by surface, each against the baseline commit `8d99a5c`:

- **Model-facing text: unchanged.** `git diff 8d99a5c HEAD -- tests/snapshots/requests prompts` prints nothing, so
  every request the agents send has the same system prompt and tool definitions. `registry/roles.json` changed only
  in `85cb4fb` (Task 2.34: each role declares its tool set and Craft apps), and the unchanged request snapshots show
  that no role's tool set moved.
  One model-facing text changed by decision: the sketch warning says "del lato più lungo del disegno" instead of
  "della larghezza", because that is what it measures (D1). It is a tool result, not part of the snapshots.
- **CLI help: unchanged except the approved `--record`.** The help of all 17 commands (`agency`, its 14
  subcommands, `agency-server`, `agency-schemas`) is pinned since `b9e3617`. Rendered from `8d99a5c`'s code the way
  `tests/test_cli_help.py` renders it, all 17 equal those snapshots byte for byte; `git diff b9e3617 HEAD --
  tests/snapshots/cli` adds only the `--record` option of `run`, `resume` and `decide` (Task 2.33, approved). The
  help of `agency`, `agency-server` and `agency-schemas` used the module docstring; `93e9dd4` copied each docstring
  into a constant before Phase 3 translated the docstrings, and the constants equal the old docstrings exactly.
- **Dashboard: unchanged.** The string literals and JSX text of the hand-written `web/src` (tests excluded) are the
  same set at both commits; only import paths changed, because the helpers moved to `lib/` and one component was
  added. The 14 scroll regions and the compare rows were shared into helpers (Task 6.15), and two e2e
  characterization tests written before the change pin them cell by cell. The OpenAPI schema and `schema.ts`
  regenerate byte-identical (row 16); their descriptions were translated to English by Task 3.2 (approved), and no
  field, enum or `operationId` changed.
- **Messages printed or returned in Italian.** An AST scan of every string literal in `src/agency` (docstrings and the
  vendored QA scripts excluded) at both commits finds 24 Italian-looking strings removed and 47 added. Each traces
  to an approved change:
  - removed: developer-facing exception messages and field descriptions translated in Phase 3 (Tasks 3.1–3.22, D3,
    D4); the sketch warning (D1); the refusal "manca il primo sguardo del critico", replaced by "la tavola del giro
    … non è stata valutata con rate_board" when the ratings moved into the registry (2.F24); "API NON DISPONIBILE"
    with a leading `\n` in the literal, now printed as `"\n" + one_line(…)` so the outside text stays on one line
    (2.F64);
  - added: the help constants of `agency-server` and `agency-schemas` (above), and the refusals and messages of the
    bug fixes, each named in `PLAN.md`: `.env` holding a setting (2.16, approved), a relative data root (2.15,
    approved), an invalid project name (2.24, approved), a missing registry (2.14, approved), a busy project or
    registry (2.12 approved, 2.F30, 2.F63), the brief not in UTF-8 (2.10), the sandbox without its scope (2.19
    approved, 2.F43), the doctor's Chromium, `node_modules` and scope rows (5.5 approved, 2.19), the context-window
    block and a cut-off turn (2.23), the `/ops` folder (2.3, approved), a FIFO and the image and file size limits
    (2.F21, 2.18, 2.F41), a Craft app the role does not list (2.34), missing draft pages and an unrated board
    (2.F26, 2.F24), an unreadable fingerprint (2.32), the append-only triggers and the `agency verify` lines of the
    hash chain (2.31 approved, 2.F56–2.F58, R4).
- **Behaviour the final review restored.** R5 and R11 put back three refusals an earlier fix had dropped without
  approval (a `restore` destination outside the projects folder read by the kernel, a dangling link, `..` after a
  file), and kept `restore`'s messages naming the destination as typed. The only behaviour R9 changed on purpose is
  the one it fixes: a path that reaches a link a sandbox left below `projects/` is refused, whatever its spelling.

So no user-facing behaviour changed beyond the approved fixes.

## 5. Still open

Deferred by decision, with where each goes:
- To M1.7: STR-004 (the qa↔tools cycle and the sandbox's QA mount), STR-007, STR-013, SIM-012, and the remainders
  of STR-003 (the `langgraph` and ledger-port import rules) and SIM-004 (where `langchain_core` is imported).
- SIM-014: the next migration needed for its own sake.
- DX-009's CI stage: when a Git remote exists, before M6 (ADR-0051). DX-008's web formatter and linter: its own ADR.
- STR-005's remainder: typing `ROLES` and `CHECKS` as `RoleSpec` and `CheckSpec` (Task 6.9). Done in M1.7, b618742.

Decisions the final review left for Andrea:
- `agency budget` re-reads the project row and re-binds it whole, so a hand edit of its model or effort stops showing
  in `agency verify`; the same holds for concept rows (round 3, #3). It needs an ADR.
- `agency resume` of a ticket whose project was changed by hand works in the other client's folder until `agency
  verify` runs (ADR-0053/0054 detect it afterwards; refusing before the run is the alternative).
- A project folder that is itself a link out of `projects/` keeps its work folder outside the guarded root (round 4).
- `CommandIndex.load` runs `vectorcraft-cli --version` on the host with the full environment (`PLAN.md`, R1).
  Resolved after the merge, on 2026-11-14: the CLI now starts with `PATH` alone (`tests/test_craft_index.py`).
- The contract and opening hashes (`spec_sha256`, `inputs_sha256`) are re-bound by the next event as found, the gap
  ADR-0054 closed for the project; ADR-0054 records it as a separate decision.

Machine note: the real registry is at revision 0005 (35 tickets, 319 events). The engine refuses it until `agency
migrate` runs; a scratch copy reached 0009, and `agency verify` exited 0 on it (R4, R7).

## 6. How to reproduce

```sh
# A fresh clone of the final HEAD, outside the repository (a clone only reads it)
git clone --branch audit/deep-review /home/andreaaazo/Dev/design-agency-harness "$SCRATCH/after"
cd "$SCRATCH/after" && export MISE_TRUSTED_CONFIG_PATHS="$PWD"
# rows 0-24: the commands of the table above, in order, through `mise exec --` as the Makefile does; row 16 runs
# `make setup && make schemas` in a `git archive HEAD` export and compares both outputs with `cmp`
# sizes: tracked files only, with their real names
git ls-files -z | xargs -0 tokei --no-ignore
```

The runner used for this report is `run-rows.sh`, with `coverage.py` (module coverage), `loc.py` (code lines per
package) and `strings.py` (string literals at a revision). They lived in the session's scratch folder and are not
versioned; the baseline's §3 and §5 describe the method each follows. The import recorder is the baseline's §5
plugin. The baseline's CLI help was rendered from `8d99a5c`'s `src/` the way `tests/test_cli_help.py` renders it.
