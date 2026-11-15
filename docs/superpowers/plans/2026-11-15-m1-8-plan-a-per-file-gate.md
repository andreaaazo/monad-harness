# M1.8 quality gate, plan A (roadmap items 1–4: decisions, tools, configuration, the per-file gate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** decide every open point of M1.8, install the gate's tools inside the quarantine, write the gate's own
configuration, and build `quality_gate` up to its `file` mode: `uv run python -m quality_gate file PATH...` runs the
six per-file checks and prints the report of §7.6. The gate's own code meets every rule of the spec from its first
file.

**Architecture:** M1.8 takes three plans.
- **Plan A (this one)** builds the per-file gate.
- **Plan B** adds the modes `changed`, `full` and `staged`, the project checks, the integrity checks, `lock` and
  `BASELINE.md`.
- **Plan C** switches the daily check to the gate. It also adds pre-commit, the Claude Code hooks, `AGENTS.md`,
  mutation testing and the proofs, and ends with Andrea's lock.

Until the switch, today's `make check` keeps running unchanged on `src/` and `tests/`. The gate's code is held to the
spec's rules by a temporary `quality_gate/ruff.toml` (read by today's `ruff check .`) and by the strict self-check
that closes every task.

**Tech Stack:** Python 3.13 standard library only at run time (`argparse`, `tomllib`, `json`, `re`, `subprocess`,
`sysconfig`, `dataclasses`, `enum`, `logging`). The gate drives Ruff 0.17.1, flake8 7.4.1 with
wemake-python-styleguide 1.8.1, pydoclint 0.11.1 and basedpyright 1.40.2. It is tested with pytest 9.1.1,
pytest-randomly 5.0.0 and coverage 7.16.2.

**Spec:**
- `docs/quality-gate/SPEC.md`: the final state, P1–P5 and A1–A9;
- `docs/02-ROADMAP.md`, section M1.8: the parameters, the decisions to take and the order of work;
- `docs/adr/0055-il-quality-gate-prima-di-merlo4.md`: the conflicts with accepted decisions.

## Decisions (recorded by Task 0 in ADR-0060, ADR-0061 and ADR-0062)

Andrea delegated these ("Sei tu che fai decisioni"). ADR-0055 asks M1.8 to settle each conflict before the gate is
written.

| # | Decision | Why |
|---|---|---|
| Parameters | `<RUNNER>` `uv run`; `<ENV_PY>` `.venv/bin/python`; `<PY>` `3.13`; `<PKGS>` `agency`, in `src/agency`; `<TESTS>` `tests`; `<BASE_BRANCH>` none until a remote exists. `<T_SUITE>` is measured by Task 11 with `coverage run`. | As the roadmap proposes. `.python-version` pins 3.13.15. |
| D1 | **pyright and `[tool.pyright]` go at the switch (plan C),** together with the tool entries of the `dev` group (ruff, pyright, import-linter, django-stubs, pytest). Until then both groups list them, and the gate's pins live only in `quality`. `[tool.pytest.ini_options]` becomes `[tool.pytest]` at the switch. Nothing else exists to remove: there is no black, isort, mypy, `setup.cfg` or `.flake8` today. | `tests/test_dependencies.py` requires those tools to be in `dev`. Moving them now would change a test that the switch changes anyway. |
| D2 | **The two fixed contracts of §6.5 join today's 13.** The four contracts that count direct imports only (`allow_indirect_imports = true`) stay as they are. Their indirect versions go into `BASELINE.md` as pending contracts (plan B). | Deleting the four would weaken the boundaries of ADR-0057 and ADR-0058. Keeping them is stricter than removing them (§13: "almeno altrettanto severo"). `DEVIATIONS.md` records it with import-linter's output. |
| D3 | **The CI waits for a remote** (ADR-0051). When one exists, `changed` blocks at once and `full` only reports until the repo is clean. | This is the spec's default. |
| D4 | **`legacy/**` and `src/agency/qa/scripts/**` are excluded,** in `[tool.quality_gate].exclude` and in coverage `omit`. The ledger's Alembic migrations stay in. | `legacy/` is the frozen backup, and a test checks its hashes. The QA scripts are copied code, pinned by bytes, that runs in the toolchain's own Python. The migrations are written by hand. |
| D5 | **`CPY001` is ignored.** | A private repository with one owner. |
| C1 | **pre-commit replaces `.githooks/`** (plan C). The hook is the spec's `repo: local` hook. Andrea unsets `core.hooksPath` and runs `uv run pre-commit install` once. | A local hook downloads nothing, so ADR-0051's reason for refusing the framework does not apply. |
| C2 | **`task check` becomes `uv lock --check`, `task gate`, `web:static`, `web:unit`, `e2e`** (plan C).<ul><li>`check:fast`, `lint`, `format`, `imports` and `types` go; `task test` stays, for one test.</li><li>`check:clean` becomes a local clone of `HEAD` with the staged diff applied, so the gate runs inside a git repository.</li></ul> | `ruff format .` would rewrite every file and make the whole repo "changed". The post-edit hook formats one file at a time. In a plain copy of the index the gate exits 2, and the four git tests skip. |
| C3 | **The test files that change in M1.8** (A7's exceptions) are `tests/test_taskfile.py` (C1, C2) and `tests/test_dependencies.py` (D1). Both change at the switch, and as changed files both are cleaned whole. | These are the two tests that pin today's tools. |
| C4 | **Every pin is the newest release before `exclude-newer = 2026-10-17`** (ADR-0006), and each meets the spec's floors: pytest 9.1.1 (≥ 9.0), wemake-python-styleguide 1.8.1 (≥ 1.0), mutmut 3.8.0 (≥ 3) and coverage 7.16.2 (≥ 7). The date does not move. | Resolved on 2026-11-15 with `uv lock` in a scratch project with the same `exclude-newer`. |
| C5 | **Every changed file has complete Google docstrings** (Ruff `D`, pydoclint). There is still no campaign over untouched files. | ADR-0062 reverses the answer to Q14 for touched files only. |
| C6 | **`.claude/settings.json` can be versioned as it is.** `.gitignore` ignores only `memory/`, `sessions/`, `state/` and `settings.local.json` under `.claude/`. | ADR-0055 assumed the whole folder was ignored. ADR-0060 corrects that premise. |
| C7 | **The guard protects `~/.claude/**` except `~/.claude/projects/*/memory/**`** (plan C). | The memory holds no setting, hook or variable. Blocking it would lose what the assistant learns between sessions. This is a change to §9.2, recorded in ADR-0060 and `DEVIATIONS.md`. |
| C8 | **`env_passthrough` lists exactly what the sandbox tests need** under the cleaned environment. It is measured in plan B, when the `tests` check exists, and stays empty until then. | ADR-0046's `systemd-run --user` probably needs `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. A measurement decides. |
| C9 | **A skipped test fails the gate (§8.6).** This machine has VectorCraft and Docker (`make doctor`). The four git tests run once `check:clean` uses a clone (C2). Today's `skipif` lines stay until their files are touched. | The spec's rule stands. |
| B1 | **Build order.**<ul><li>The shared tables (`[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.importlinter]`) and `.editorconfig` change only at the switch.</li><li>The tables that only the gate reads are final from Task 2.</li><li>`quality_gate/ruff.toml` is temporary: it holds §6.1's tables for the gate's own files, and the switch deletes it.</li></ul> | Today's `task check` reads the shared tables. Putting the strict tables there early would turn `make check` red on all of `src/` and `tests/`. |
| B2 | **The gate finds the Python tools in the interpreter's scripts folder (§7.3), and finds git through `PATH`.** | git is not a Python package and cannot live in the venv. `DEVIATIONS.md` records it (Task 4). |
| B3 | **Every file reaches a tool as `./<path>`, never after `--`.** Parsers map each reported path back to a root-relative POSIX path. | basedpyright 1.40.2 reads `--` as a file name (checked on 2026-11-15). The `./` prefix stops any file name from being read as an option, by every tool alike. |

## Target tree after this plan

```
quality_gate/
  __init__.py
  __main__.py          sys.exit(main())
  cli.py               main, run_file_mode, exit_code
  model.py             Status, Violation, CheckResult, Report, GateError
  jsonvalue.py         load_json, is_array, is_table
  settings.py          Settings, load_settings
  execution.py         Completed, ToolFailure, Runner, clean_environment, runner_for (the only module that launches processes)
  discovery.py         find_root, discover, select_given
  report.py            render_text, render_json
  ruff.toml            TEMPORARY: §6.1 for the gate's files, deleted at the switch (plan C)
  checks/
    __init__.py
    verdict.py         Parser, CheckInput, ToolCheck, judge, run_tool_check, relative_path
    ruff_lint.py  ruff_format.py  wps.py  pydoclint.py  basedpyright.py  suppressions.py
    per_file.py        PER_FILE_CHECKS
  tests/
    __init__.py  conftest.py  fakes.py  test_*.py
```

Outside the package: the `quality` group and the gate's tables in `pyproject.toml`; `.flake8`; `/mutants/` in
`.gitignore`; `docs/quality-gate/DEVIATIONS.md`; and ADR-0060, ADR-0061 and ADR-0062.

## Global Constraints

- **No git writes.** Each task ends with `make check` exiting 0, then the READY FOR COMMIT block, then a wait for
  "committed". English code, comments and docstrings; Italian documents. One kind of change per task.
- **The gate imports nothing from `agency`,** and nothing outside the standard library at run time. Its tests use
  pytest. `agency` never imports `quality_gate`.
- **Only `quality_gate/execution.py` imports `subprocess`.** The temporary `ruff.toml` enforces this with
  `S404`/`S603`, ignored for that one file.
- **No `Any`, no `cast`.** JSON goes through `jsonvalue`: a `Callable[[str], object]` bound to `json.loads`, plus the
  `TypeIs` guards `is_array` and `is_table`. On 2026-11-15, basedpyright in mode `all` accepted this and refused the
  alternatives (`data: object = json.loads(...)` is `reportAny`, and `isinstance(x, dict)` leaves
  `dict[Unknown, Unknown]`). TOML goes through `tomllib` into an `object`, then the same guards.
- **No suppression text anywhere in `quality_gate/`,** in code or in tests. A test that needs a directive builds it
  from fragments (`'no' + 'qa'`), as §8.1 asks of the scanner.
- **No print.** Output goes through `sys.stdout.write` and `sys.stderr.write`, and the exit code through `sys.exit`
  (WPS363 refuses `raise SystemExit`).
- **Exit codes:** 0 when every check passes; 1 when one fails or errors; 2 for a usage or internal error, and outside
  a git repository.
- **The strict self-check.** It closes Tasks 3–11, beside `make check`. Every command exits 0, and the last one
  reports 100% (lines and branches, `fail_under = 100`):

  ```bash
  uv run ruff check --ignore-noqa quality_gate        # quality_gate/ruff.toml applies to the gate's files
  uv run ruff format --check quality_gate
  uv run flake8 --config .flake8 --disable-noqa --format default quality_gate
  uv run pydoclint --config pyproject.toml --quiet quality_gate
  uv run basedpyright --pythonpath .venv/bin/python quality_gate
  uv run coverage erase
  uv run coverage run -m pytest -W error --strict-markers --strict-config quality_gate/tests
  uv run coverage report --include='quality_gate/*'
  ```

  From Task 10 on, it also runs the gate on itself:
  `uv run python -m quality_gate file $(git ls-files -co --exclude-standard -- 'quality_gate/*.py')`, which exits 0.
- **A real-tool test runs in a temporary git repository** with its own small config. Tests never run a tool against
  this repository's files. Fake tools are executable Python scripts written into a temporary scripts folder by
  `quality_gate/tests/fakes.py`.

## Review Focus

These are the inputs the spec implies and a reasonable person expects to work, but no other test would reach. Each
line names the test that pins it and the task that owns it.

- **A per-file check with no files must not run its tool:** Ruff and basedpyright with no paths check the whole
  project. Pinned by `test_a_check_with_no_files_passes_without_running_its_tool` (Task 7).
- **A tool can never turn a failure into a pass.** Exit 0 with violations in its output, a failing exit with output
  that cannot be read, and an exit code nobody expects must never PASS. Pinned by the `judge` tests (Task 7).
- **Paths given to `file` that are not discovered files are not checked:** a Markdown file, an excluded path, a path
  outside the repository. A missing path exits 2. Pinned by
  `test_a_path_that_is_not_a_discovered_file_is_not_checked` and `test_main_with_a_missing_path_returns_two`
  (Task 10).
- **The caller's environment cannot steer a tool.** `PYTEST_ADDOPTS`, `RUFF_*`, `PYTHONPATH`, `COVERAGE_RCFILE` and
  `GIT_DIR` never reach it. Pinned by `test_the_tool_sees_only_the_cleaned_environment` (Task 4).
- **Odd file contents and names:** a file that is not UTF-8 fails the suppression scan, and CRLF line endings still
  give the right line. A name with spaces, accents or a leading dash reaches the tool intact and comes back as the
  same path. Pinned by `test_a_file_that_is_not_utf8_fails` and `test_the_position_is_line_and_column_of_the_match`
  (Task 9), and by `test_names_with_spaces_and_accents_are_kept_intact` (Task 5) and
  `test_files_reach_the_tool_after_its_options_as_dot_slash_paths` (Task 7).

---

## Phase 1: decisions, tools, configuration

### Task 0: ADR-0060, ADR-0061 and ADR-0062, the decisions of M1.8

**Files:**
- Create: `docs/adr/0060-il-quality-gate-parametri-decisioni-e-ordine.md`,
  `docs/adr/0061-il-commit-e-il-controllo-di-ogni-giorno-passano-dal-gate.md`,
  `docs/adr/0062-docstring-complete-nei-file-che-cambiano.md`
- Modify: `docs/adr/README.md` (three rows; 0039 and 0051 marked as corrected by 0061), `docs/02-ROADMAP.md`,
  `README.md`

- [ ] **Step 1:** write ADR-0060, in the style of ADR-0058: context, numbered decisions, consequences.
  - The decisions are the Parameters row, D1–D5, C3, C4 and C6–C9, and B1–B3 of the table above.
  - The consequences name the three plans, and what each decision leaves to plan B or C.
- [ ] **Step 2:** write ADR-0061 (C1, C2) and ADR-0062 (C5).
  - ADR-0061 says what it reverses: from ADR-0051, the hook in `.githooks/`, `check:fast` as the start of `task check`
    and `check:clean` as a copy of the index; from ADR-0039, the `lint`, `format`, `imports` and `types` tasks. It
    also says when each change lands (plan C).
  - ADR-0062 says it reverses Q14's answer in `docs/audit/PLAN.md` for changed files only.
- [ ] **Step 3:** update `docs/02-ROADMAP.md`.
  - The parameter table becomes "Parametri" with the confirmed values; `<T_SUITE>` reads "Task 11 del piano A".
  - The decisions bullet list points to the three ADRs, and item 1 is ticked.
  - The M1.8 status row reads "**in corso**, piano A", with a link to this plan.
  - "Primo passo concreto" names this plan.
  - `README.md` says "M1.8 in corso".
- [ ] **Step 4:** `make check` exits 0. Handoff with `docs: record the decisions of M1.8 in ADR-0060, ADR-0061 and ADR-0062`.

### Task 1: the `quality` group, pinned inside the quarantine

**Files:**
- Modify: `pyproject.toml` (`[dependency-groups]`, `[tool.uv]`), `uv.lock`

- [ ] **Step 1:** add the group with one command:

  ```bash
  uv add --group quality 'ruff==0.17.1' 'flake8==7.4.1' 'wemake-python-styleguide==1.8.1' 'pydoclint==0.11.1' \
    'basedpyright==1.40.2' 'import-linter==2.15' 'vulture==2.16' 'deptry==0.25.1' 'pylint==4.1.3' \
    'pytest==9.1.1' 'pytest-randomly==5.0.0' 'coverage==7.16.2' 'diff-cover==10.6.0' 'mutmut==3.8.0' \
    'pre-commit==4.7.0' 'django-stubs==5.2.9'
  ```

  The `dev` group stays as it is (D1).
- [ ] **Step 2:** add `default-groups = ["dev", "quality"]` to `[tool.uv]`, with a one-line comment: the gate's tools
  install with `uv sync`. Then `uv lock`. Expected: `uv lock --check` exits 0.
- [ ] **Step 3:** check that every installed version equals its pin:
  `uv run python -c "import importlib.metadata as m, tomllib; g = tomllib.load(open('pyproject.toml','rb'))['dependency-groups']['quality']; bad = [r for r in g if m.version(r.split('==')[0]) != r.split('==')[1]]; print(bad); raise SystemExit(bool(bad))"`.
  Expected: `[]`, exit 0.
- [ ] **Step 4:** pytest-randomly now shuffles every run. Run `uv run pytest` three times and note the three seeds it
  prints. Expected: all pass.
  - If a run fails, rerun it with `uv run pytest -p randomly --randomly-seed=<seed>` to confirm.
  - Then stop and report: a test that depends on order is a bug fix of its own, and Andrea decides when it runs.
- [ ] **Step 5:** `make check` exits 0. Handoff with `build(deps): add the quality group, pinned inside the quarantine`.

### Task 2: the tables only the gate reads, and `.flake8`

**Files:**
- Modify: `pyproject.toml`, `.gitignore` (add `/mutants/` with a one-line comment)
- Create: `.flake8`, `docs/quality-gate/DEVIATIONS.md`

- [ ] **Step 1:** add the tables below, exactly as §6.3, §6.4, §6.6, §6.7 (coverage only), §6.8 and §6.9 write them,
  with these values filled in:
  - `[tool.basedpyright]`: `pythonVersion = "3.13"`.
  - `[tool.coverage.run]`: `omit = ["legacy/*", "src/agency/qa/scripts/*"]` (D4, the only `omit` §6.7 allows).
  - `[tool.mutmut]`: `source_paths = ["src/agency", "quality_gate"]`.
  - `[tool.quality_gate]`: `exclude = ["legacy/**", "src/agency/qa/scripts/**"]`, `env_passthrough = []`,
    `check_timeout_seconds = 600`, `mutation_min_score = 0.90`.
  - `[tool.deptry]` stays an empty table.

  `.flake8` is §6.2 word for word. Each exception carries a one-line comment with its reason (§6.10).
- [ ] **Step 2:** confirm §13 for the tables this plan uses. The expected result follows each command.
  - `uv run basedpyright --outputjson src/agency/contracts | uv run python -c "import json,sys; print(json.load(sys.stdin)['summary']['errorCount'])"`
    prints a number above 0, while `uv run pyright src/agency/contracts` prints 0 errors. So basedpyright reads
    `[tool.basedpyright]` (mode `all`) even though `[tool.pyright]` exists (§13.3).
  - `uv run basedpyright --verbose src/agency/contracts/clock.py 2>&1 | grep -i -E "unknown|invalid|not a valid"`
    prints nothing. So `failOnWarnings` and `reportIgnoreCommentWithoutRule` are known settings.
  - `uv run pydoclint --config pyproject.toml --quiet src/agency/contracts/clock.py`: the output holds only `DOC`
    lines, with no option error, and the exit code is 0 or 1 (§13.9).
  - `uv run flake8 --config .flake8 --format default --no-show-source src/agency/contracts/clock.py` prints only
    `WPS` codes.
  - `uv run coverage debug config | grep -E "^ *(branch|source|run_omit|fail_under|exclude_list|partial_list):"` shows
    branch `True`, source `['.']`, fail_under `100.0`, exactly the two exclude patterns, partial_list `[]` and the
    two omit globs (§13.5, second half).
- [ ] **Step 3:** create `docs/quality-gate/DEVIATIONS.md`, in Italian.
  - Each entry gives what the spec says, what the repo does, why it is at least as strict (or which ADR changes the
    spec), and the proof as a command with its result.
  - Seed it with any difference Step 2 found, and with B1's temporary `quality_gate/ruff.toml` (proof: Task 3).
  - Plans B and C append the rest.
- [ ] **Step 4:** `make check` exits 0. Handoff with `build(quality): add the gate's own tool tables and .flake8`.

## Phase 2: the per-file gate

### Task 3: the package starts — model, JSON guards, settings

**Files:**
- Create: `quality_gate/__init__.py`, `quality_gate/model.py`, `quality_gate/jsonvalue.py`,
  `quality_gate/settings.py`, `quality_gate/ruff.toml`, `quality_gate/tests/__init__.py`,
  `quality_gate/tests/test_model.py`, `quality_gate/tests/test_jsonvalue.py`, `quality_gate/tests/test_settings.py`
- Modify: `pyproject.toml` (`[tool.pytest.ini_options].testpaths` gains `"quality_gate/tests"`)

**Interfaces:**
- Produces:
  - `model.Status(StrEnum)`: `PASS`, `FAIL`, `ERROR`.
  - `model.Violation(path: str, line: int, column: int, code: str, message: str)`, frozen, with
    `render() -> str`.
  - `model.CheckResult(name: str, status: Status, seconds: float, violations: tuple[Violation, ...], raw: str)`,
    frozen.
  - `model.Report(mode: str, base: str | None, python_files: int, checks: tuple[CheckResult, ...])`, frozen, with
    the properties `result -> Status`, `failed -> int` and `errors -> int`.
  - `model.GateError(Exception)`: a usage or internal error, exit 2.
  - `jsonvalue.load_json(text: str) -> object`, which raises `ValueError`; `is_array(candidate: object) -> TypeIs[list[object]]`;
    `is_table(candidate: object) -> TypeIs[dict[str, object]]`.
  - `settings.Settings(exclude: tuple[str, ...], env_passthrough: tuple[str, ...], check_timeout_seconds: int, mutation_min_score: float)`,
    frozen; `settings.load_settings(root: Path) -> Settings`.

- [ ] **Step 1:** create `quality_gate/ruff.toml` with §6.1's content.
  - The values are `required-version = "==0.17.1"` and `target-version = "py313"`.
  - The per-file globs are resolved from this folder: `"**/tests/**/*.py"` and `"**/conftest.py"` as written, and
    `"execution.py"` in place of `"quality_gate/execution.py"`.
  - The first line says the file is temporary and that the switch moves it into `pyproject.toml` (ADR-0060, B1).
- [ ] **Step 2:** write the failing tests.
  - `test_a_violation_renders_as_path_line_column_code_message`:
    `Violation('src/a.py', 10, 5, 'D103', 'Missing docstring in public function').render()` equals
    `src/a.py:10:5 D103 Missing docstring in public function`.
  - `test_a_report_passes_only_when_every_check_passes`: the result is PASS with `(PASS, PASS)` and FAIL with
    `(PASS, ERROR)`; `failed` and `errors` count FAIL and ERROR separately.
  - `test_load_json_returns_plain_values`: `load_json('{"a": [1, "x"]}')` equals `{'a': [1, 'x']}`.
  - `test_load_json_refuses_text_that_is_not_json`: `ValueError`.
  - `test_the_guards_tell_arrays_and_tables_apart`: `is_array([])`, `is_array({})`, `is_table({})` and
    `is_table([])` give `True`, `False`, `True`, `False`.
  - `test_settings_are_read_from_the_quality_gate_table`: a `pyproject.toml` with the four keys gives
    `Settings(('legacy/**',), ('XDG_RUNTIME_DIR',), 600, 0.9)`.
  - `test_a_missing_table_or_key_is_a_gate_error`, parametrized over no `pyproject.toml`, no `[tool.quality_gate]`,
    and each of the four keys missing: `GateError`, whose message names the table or the key.
  - `test_a_value_of_the_wrong_type_is_a_gate_error`, parametrized over `exclude = "x"`, `exclude = [1]`,
    `check_timeout_seconds` set to `"600"`, `0` or `true`, and `mutation_min_score` set to `1.5`, `-0.1` or `true`.
  - `test_the_repository_settings_are_the_decided_ones`: `load_settings(<repo root>)` equals
    `Settings(('legacy/**', 'src/agency/qa/scripts/**'), (), 600, 0.9)`.

  Run `uv run pytest quality_gate/tests`. Expected: FAIL on the missing modules.
- [ ] **Step 3:** implement the three modules.
  - `load_settings` reads `pyproject.toml` with `tomllib` into an `object` and narrows it with the guards.
  - A `bool` is refused where an `int` or `float` is expected. The timeout must be > 0, and the score must be in
    [0, 1].
- [ ] **Step 4:** the tests pass, the strict self-check passes, and `make check` exits 0.
  - Proof for B1: `uv run ruff check --show-settings quality_gate/model.py | grep -E "line_length|quote_style"`
    shows 80 and single quotes. Add it to `DEVIATIONS.md`.
- [ ] **Step 5:** handoff with `feat(quality): start the gate with its model, JSON guards and settings`.

### Task 4: execution, the only module that launches processes

**Files:**
- Create: `quality_gate/execution.py`, `quality_gate/tests/fakes.py`, `quality_gate/tests/conftest.py`,
  `quality_gate/tests/test_execution.py`
- Modify: `docs/quality-gate/DEVIATIONS.md` (B2)

**Interfaces:**
- Consumes: `Settings` (Task 3).
- Produces:
  - `Completed(exit_code: int, stdout: str, stderr: str, seconds: float)`, frozen.
  - `ToolFailure(Exception)`, raised for a missing executable or a timeout. Its message is
    `missing executable: <path>` or `timeout after <seconds>s`.
  - `ALLOWED_VARIABLES: Final = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'VIRTUAL_ENV')`.
  - `clean_environment(source: Mapping[str, str], passthrough: Sequence[str]) -> dict[str, str]`.
  - `Runner(root: Path, scripts: Path, environment: Mapping[str, str], timeout: float)`, frozen, with
    `tool(name: str, arguments: Sequence[str]) -> Completed` and `git(arguments: Sequence[str]) -> Completed`.
  - `runner_for(root: Path, passthrough: Sequence[str], timeout: float) -> Runner`. Its scripts folder is
    `Path(sysconfig.get_path('scripts'))`, and its environment is `clean_environment(os.environ, passthrough)`.
  - In `fakes.py`: `write_tool(scripts: Path, name: str, body: str) -> Path`. It writes an executable script whose
    shebang is `sys.executable` and whose body is the given Python. Fixtures: `scripts(tmp_path) -> Path`.

- [ ] **Step 1:** write the failing tests.
  - `test_a_tool_runs_from_the_scripts_folder_in_the_repository_root`: a fake prints `os.getcwd()`; stdout equals the
    root.
  - `test_a_tool_never_comes_from_path`: the tool exists only in a folder on the environment's `PATH`, so
    `ToolFailure('missing executable: …')` is raised.
  - `test_exit_code_and_both_streams_are_returned`: a fake writes `out` and `err` and exits 3. The result is
    `Completed(3, 'out', 'err', …)`, with `seconds >= 0`.
  - `test_arguments_reach_the_tool_unchanged`: `['./-x.py', './a b.py', './è.py']` comes back from a fake that echoes
    `sys.argv[1:]` as JSON.
  - `test_the_environment_keeps_only_the_allowed_variables`: `clean_environment` applied to `PATH`, `HOME`,
    `PYTEST_ADDOPTS`, `RUFF_CACHE_DIR`, `PYTHONPATH`, `COVERAGE_RCFILE`, `GIT_DIR` and `XDG_RUNTIME_DIR`, with
    passthrough `('XDG_RUNTIME_DIR',)`, keeps exactly `PATH`, `HOME` and `XDG_RUNTIME_DIR`.
  - `test_the_tool_sees_only_the_cleaned_environment`: a fake dumps `sorted(os.environ)`. The keys are those of the
    runner's environment, apart from what the interpreter adds by itself (`LC_CTYPE` if the platform sets it); the
    test lists those explicitly.
  - `test_a_tool_that_runs_too_long_is_a_failure`: a fake sleeps 5 s with timeout 0.5, so
    `ToolFailure('timeout after 0.5s')` is raised.
  - `test_git_comes_from_path`: `runner.git(['--version'])` stdout starts with `git version`.
  - `test_git_missing_from_path_is_a_failure`: the environment's `PATH` is an empty folder, so `ToolFailure` is
    raised.
  - `test_runner_for_takes_the_interpreter_scripts_and_cleans_the_environment` (monkeypatch `PYTEST_ADDOPTS`).
- [ ] **Step 2:** implement.
  - `subprocess.run` with an argument list: `cwd=root`, `env=environment`, `stdin=DEVNULL`, captured output,
    `encoding='utf-8'`, `errors='replace'`, `timeout`, `check=False`.
  - git is found with `shutil.which('git', path=environment['PATH'])`.
  - A missing `PATH` key is a `ToolFailure`, not a `KeyError`.
  - Time is measured with `time.perf_counter`.
- [ ] **Step 3:** add B2 to `DEVIATIONS.md`, with `test_git_comes_from_path` and `test_a_tool_never_comes_from_path`
  as proof.
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): run tools from the venv, in a clean environment, with a timeout`.

### Task 5: discovery

**Files:**
- Create: `quality_gate/discovery.py`, `quality_gate/tests/test_discovery.py`
- Modify: `quality_gate/tests/conftest.py` (fixture `repository(tmp_path) -> Runner`: a git repository made with
  `git init -q` through `Runner.git`, with `user.name` and `user.email` set in its local config)

**Interfaces:**
- Consumes: `Runner` (Task 4), `GateError` (Task 3).
- Produces:
  - `find_root(runner: Runner) -> Path`, from `git rev-parse --show-toplevel`. A nonzero exit raises
    `GateError('not inside a git repository')`.
  - `discover(runner: Runner, exclude: Sequence[str]) -> tuple[str, ...]`, returning sorted root-relative POSIX
    paths (§7.2).
  - `select_given(root: Path, given: Sequence[str], discovered: Sequence[str]) -> tuple[str, ...]`.

- [ ] **Step 1:** write the failing tests.
  - `test_tracked_and_untracked_python_files_are_found` (one file `git add`-ed in the temporary repo, one not).
  - `test_ignored_files_are_left_out`.
  - `test_a_python_file_in_a_new_folder_is_found` (`new/deep/x.py`).
  - `test_stub_files_and_python_scripts_without_suffix_are_found`:
    - `x.pyi` is found, and so is an executable `bin/tool` with `#!/usr/bin/env python3`;
    - an executable `bin/run` with `#!/bin/sh` is not;
    - a non-executable `bin/plain` with a Python shebang is not;
    - `README.md` is not.
  - `test_excluded_globs_are_left_out`: `('legacy/**',)` drops `legacy/a/b.py` and keeps `src/legacy.py`.
  - `test_a_tracked_file_deleted_from_disk_is_left_out`.
  - `test_names_with_spaces_and_accents_are_kept_intact`: `a b.py` and `è.py`, read from `-z` output.
  - `test_outside_a_repository_discovery_is_a_gate_error` (both `find_root` and `discover`).
  - `test_given_paths_keep_only_discovered_files`:
    - `./src/a.py` becomes `src/a.py`;
    - `README.md` and an excluded `legacy/x.py` are dropped;
    - the order follows `discovered`.
  - `test_a_given_path_that_does_not_exist_is_a_gate_error` and
    `test_a_given_path_outside_the_repository_is_a_gate_error`.
- [ ] **Step 2:** implement.
  - Discovery runs `git ls-files -z --cached --others --exclude-standard`. Exclusion uses `PurePosixPath.full_match`.
  - The shebang test reads only the first line, in bytes: it starts with `#!` and contains `python`.
  - `select_given` resolves each path against the root and refuses one that is outside it.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): discover the Python files git sees, minus the excluded globs`.

### Task 6: the report

**Files:**
- Create: `quality_gate/report.py`, `quality_gate/tests/test_report.py`

**Interfaces:**
- Consumes: `Report`, `CheckResult`, `Violation`, `Status` (Task 3).
- Produces: `render_text(report: Report) -> str`; `render_json(report: Report) -> str`.

- [ ] **Step 1:** write the failing tests. The first pins the whole text of §7.6:

  ```python
  def test_the_text_report_has_header_table_result_and_details() -> None:
      # Report('file', None, 3, (ruff-lint FAIL 0.41 s with two violations given out of order,
      #                          ruff-format PASS 0.08 s, basedpyright ERROR 600.0 s raw 'timeout after 600s'))
      assert render_text(report) == (
          "quality-gate file  python-files=3\n"
          "CHECK             STATUS  COUNT  SECONDS\n"
          "ruff-lint         FAIL        2     0.41\n"
          "ruff-format       PASS        0     0.08\n"
          "basedpyright      ERROR       -   600.00\n"
          "RESULT: FAIL  failed=1  errors=1  checks=3\n"
          "\n"
          "== ruff-lint (2) ==\n"
          "src/a.py:3:1 D103 Missing docstring in public function\n"
          "src/b.py:1:1 E501 Line too long\n"
          "== basedpyright (ERROR) ==\n"
          "timeout after 600s\n"
      )
  ```

  - `test_the_header_names_the_base_when_there_is_one`: the header reads
    `quality-gate changed  base=HEAD  python-files=3`.
  - `test_violations_are_sorted_by_path_then_line_as_numbers`: `a.py:2` comes before `a.py:10`, which comes before
    `b.py:1`.
  - `test_a_failure_without_violations_shows_the_raw_output`: the block reads `== wps (0) ==`, then the raw output.
  - `test_a_passing_report_ends_at_its_result_line`.
  - `test_the_json_report_carries_every_field`: `load_json(render_json(report))` is a table with `mode`, `base`
    (None), `result`, and `checks[]` items holding `name`, `status`, `seconds`, `violations[]` (`path`, `line`,
    `column`, `code`, `message`) and `raw`.
- [ ] **Step 2:** implement.
  - The row format is `f'{name:<18}{status:<6}{count:>7}{seconds:>9.2f}'`. The count of an ERROR is `-`.
  - Sorting is by `(path, line, column, code, message)`.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): render the report as text and as JSON`.

### Task 7: the verdict, and the checks of Ruff and WPS

**Files:**
- Create: `quality_gate/checks/__init__.py`, `quality_gate/checks/verdict.py`, `quality_gate/checks/ruff_lint.py`,
  `quality_gate/checks/ruff_format.py`, `quality_gate/checks/wps.py`, `quality_gate/tests/test_verdict.py`,
  `quality_gate/tests/test_ruff_checks.py`, `quality_gate/tests/test_wps_check.py`

**Interfaces:**
- Consumes: `Runner`, `Completed`, `ToolFailure` (Task 4); `CheckResult`, `Violation`, `Status` (Task 3);
  `load_json`, `is_array`, `is_table` (Task 3).
- Produces:
  - `type Parser = Callable[[str, Path], tuple[Violation, ...]]`: stdout and root to violations. It raises
    `ValueError` when the output cannot be read.
  - `CheckInput(runner: Runner, files: tuple[str, ...])` and
    `ToolCheck(name: str, tool: str, options: tuple[str, ...], parse: Parser, failing: frozenset[int])`, both
    frozen.
  - `judge(check: ToolCheck, completed: Completed, root: Path) -> CheckResult`.
  - `run_tool_check(check: ToolCheck, given: CheckInput) -> CheckResult`.
  - `relative_path(root: Path, reported: str) -> str`.
  - Per module: `CHECK: ToolCheck`, its parser, and `run(given: CheckInput) -> CheckResult`.
  - The three checks:

    | Check | Tool | Options | Failing exit codes |
    |---|---|---|---|
    | `ruff-lint` | `ruff` | `check --config pyproject.toml --no-cache --no-fix --ignore-noqa --output-format json` | `{1}` |
    | `ruff-format` | `ruff` | `format --config pyproject.toml --no-cache --check` | `{1}` |
    | `wps` | `flake8` | `--config .flake8 --disable-noqa --format default --no-show-source` | `{1}` |

- [ ] **Step 1:** write the failing verdict tests, with fakes.
  - `test_a_check_with_no_files_passes_without_running_its_tool`: the tool is absent, so running it would be an
    ERROR. The result is PASS, with count 0.
  - `test_exit_zero_with_nothing_reported_passes`.
  - `test_a_failing_exit_with_violations_fails_with_them`.
  - `test_a_failing_exit_with_nothing_parsed_fails_and_keeps_the_raw_output`.
  - `test_exit_zero_with_violations_reported_fails`.
  - `test_an_unexpected_exit_code_is_an_error`: exit 2 gives ERROR, and `raw` holds stdout and stderr.
  - `test_output_that_cannot_be_read_is_an_error`: the parser raises `ValueError`, so the result is ERROR.
  - `test_a_missing_tool_is_an_error`: `raw` starts with `missing executable:`.
  - `test_files_reach_the_tool_after_its_options_as_dot_slash_paths`: argv equals
    `[*options, './-x.py', './a b.py']`.
  - `test_reported_paths_are_made_relative_to_the_root`: `<root>/src/a.py`, `./src/a.py` and `src/a.py` all become
    `src/a.py`.
- [ ] **Step 2:** write the failing parser and real-tool tests.
  - Parser samples are captured from the pinned tools while writing the tests:
    - `ruff check --output-format json` is an array of `{code, message, filename, location: {row, column}}`. A
      `null` code (a syntax error) becomes `syntax`.
    - `ruff format --check` prints `Would reformat: ./src/a.py` lines, which become
      `Violation('src/a.py', 1, 1, 'format', 'file is not formatted')`. Every other line is ignored.
    - flake8 prints `path:line:col: CODE message` lines. Every other line is ignored.
  - Real-tool tests, in a temporary repository:
    - `test_ruff_lint_reports_a_real_violation`: `[tool.ruff.lint] select = ["D103"]` gives FAIL at
      `src/a.py:1:5 D103`.
    - `test_ruff_lint_ignores_suppression_comments`: the same file with a `noqa` built from fragments still FAILs.
    - `test_ruff_format_reports_an_unformatted_file`.
    - `test_wps_reports_a_real_violation`: `x = 1` gives `WPS111`.
    - `test_wps_ignores_suppression_comments`.
- [ ] **Step 3:** implement `verdict.py` and the three modules. `judge` follows these rules, in order:

  ```text
  exit not in {0} | failing          -> ERROR, raw = stdout + stderr
  parse raises ValueError            -> ERROR, raw = stdout + stderr
  exit 0 and no violations           -> PASS
  otherwise                          -> FAIL with the violations, raw = stdout + stderr
  ```

  `run_tool_check` returns PASS, with count 0, for an empty `files` without calling the runner. It turns a
  `ToolFailure` into an ERROR, timed around the call.
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): judge a tool by its exit code and check Ruff and WPS`.

### Task 8: the checks of pydoclint and basedpyright

**Files:**
- Create: `quality_gate/checks/pydoclint.py`, `quality_gate/checks/basedpyright.py`,
  `quality_gate/tests/test_pydoclint_check.py`, `quality_gate/tests/test_basedpyright_check.py`

**Interfaces:**
- Consumes: `ToolCheck`, `CheckInput`, `run_tool_check`, `relative_path` (Task 7).
- Produces: `CHECK`, the parser and `run` for both modules:

  | Check | Tool | Options | Failing exit codes |
  |---|---|---|---|
  | `pydoclint` | `pydoclint` | `--config pyproject.toml --quiet` | `{1}` |
  | `basedpyright` | `basedpyright` | `--project pyproject.toml --pythonpath <sys.executable> --outputjson` | `{1}` |

- [ ] **Step 1:** write the failing tests.
  - The pydoclint parser. Output captured from 0.11.1 is a path line, then indented `LINE: CODE: message` lines, for
    one or more files. Each indented line becomes a violation with column 1, under the last path.
  - The basedpyright parser, on JSON output:
    - each `generalDiagnostics` entry of severity `error` or `warning` becomes a violation at line `start.line + 1`
      and column `start.character + 1`;
    - its code is the entry's `rule`, or `basedpyright` when there is none;
    - `information` entries are left out;
    - a missing `summary` is a `ValueError`;
    - a summary whose `errorCount` or `warningCount` is above 0 with no diagnostics gives one violation, coded
      `summary`, at the first file, line 1.
  - Real-tool tests:
    - `test_pydoclint_reports_an_undocumented_argument` (`DOC101`);
    - `test_basedpyright_reports_a_real_error`;
    - `test_basedpyright_reads_its_own_table_over_pyright_s`: a temporary `pyproject.toml` has `[tool.pyright]` in
      mode `basic` and `[tool.basedpyright]` in mode `all`, and a file only mode `all` refuses
      (`v = json.loads('1')`) FAILs.
- [ ] **Step 2:** implement.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): check docstrings with pydoclint and types with basedpyright`.

### Task 9: the suppression scan

**Files:**
- Create: `quality_gate/checks/suppressions.py`, `quality_gate/tests/test_suppressions.py`

**Interfaces:**
- Consumes: `CheckInput` (Task 7).
- Produces:
  - `scan_text(path: str, text: str) -> tuple[Violation, ...]` and `run(given: CheckInput) -> CheckResult`, whose
    name is `suppressions`.
  - The codes follow the rows of §8.1, in order:

    | Code | Pattern (case-insensitive) | Honoured by |
    |---|---|---|
    | SUP001 | `\bnoqa\b` | Ruff, flake8, vulture, pydoclint |
    | SUP002 | `type:\s*ignore` | the type checker |
    | SUP003 | `pyright:` | basedpyright |
    | SUP004 | `pragma:\s*no\s*(cover\|branch\|mutate)` | coverage, mutmut |
    | SUP005 | `pylint:\s*\w` | pylint |
    | SUP006 | `fmt:\s*(off\|on\|skip)` | ruff format |
    | SUP007 | `isort:\s*\w` | Ruff's import sorting |
    | SUP008 | `pytest\.mark\.(skip\|skipif\|xfail)` | pytest |
    | SUP009 | `(pytest\|unittest)\.(skip\|xfail\|importorskip\|SkipTest)` | pytest |
    | SUP010 | `collect_ignore\|pytest_collection_modifyitems\|pytest_ignore_collect\|pytest_plugins` | pytest |
    | SUP000 | the file is not UTF-8 | the scan itself |

  - The message is `'<matched text>' silences <honoured by>`.

- [ ] **Step 1:** write the failing tests. Every sample is built from fragments.
  - `test_each_directive_is_found`, parametrized over SUP001–SUP010.
  - `test_the_match_ignores_case`.
  - `test_a_directive_inside_a_string_is_found_too`.
  - `test_the_position_is_line_and_column_of_the_match`, on CRLF text with the directive on line 2.
  - `test_a_file_that_is_not_utf8_fails`: the bytes `b'\xff'` give `SUP000` at line 1, column 1.
  - `test_the_scanner_does_not_report_itself`: scanning `suppressions.py`'s own text returns `()`.
  - `test_clean_files_pass`.
  - `test_run_reads_the_files_from_the_root`.
- [ ] **Step 2:** implement. The patterns are compiled from fragments at import time. Files are read as bytes and
  decoded strictly as UTF-8.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): refuse every suppression directive, in comments and strings alike`.

### Task 10: the `file` mode and the entry point

**Files:**
- Create: `quality_gate/checks/per_file.py`, `quality_gate/cli.py`, `quality_gate/__main__.py`,
  `quality_gate/tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `PER_FILE_CHECKS: tuple[Callable[[CheckInput], CheckResult], ...]`, in the order `ruff-lint`, `ruff-format`,
    `wps`, `pydoclint`, `basedpyright`, `suppressions` (§7.4).
  - `run_file_mode(runner: Runner, settings: Settings, given: Sequence[str]) -> Report`.
  - `exit_code(report: Report) -> int`.
  - `main(argv: Sequence[str] | None = None) -> int`.
  - The usage is `python -m quality_gate file PATH... [--format text|json]`. argparse uses one sub-command per mode,
    and `--format` (default `text`) sits on the sub-command.

- [ ] **Step 1:** write the failing tests. The first four use fake tools:
  - `test_file_mode_runs_the_six_checks_in_order`;
  - `test_every_check_runs_even_after_a_failure`;
  - `test_exit_code_is_zero_only_when_every_check_passes`;
  - `test_a_path_that_is_not_a_discovered_file_is_not_checked`. The fakes exit 99, which would be an ERROR. Given
    `README.md` and an excluded path, every check is PASS with count 0, and `python_files == 0`.

  The rest use the real tools, in a temporary repository with the gate's tables and one clean module
  (`"""A module."""`):
  - `test_main_prints_the_text_report_and_returns_its_exit_code`: exit 0, and stdout starts with
    `quality-gate file  python-files=1`;
  - `test_main_prints_json_when_asked`;
  - `test_main_outside_a_repository_returns_two`: stderr starts with `quality-gate:`;
  - `test_main_with_a_missing_path_returns_two`;
  - `test_an_unexpected_error_is_logged_and_returns_two`: monkeypatch `run_file_mode` to raise `RuntimeError`; the
    traceback reaches stderr;
  - `test_python_m_quality_gate_exits_with_the_code_of_main`: `runpy.run_module('quality_gate', run_name='__main__')`
    with `sys.argv` patched, under `pytest.raises(SystemExit)`;
  - `test_an_unknown_mode_exits_two`, the same way.
- [ ] **Step 2:** implement.
  - `main` builds a probe runner from `runner_for(Path.cwd(), (), 60.0)`, finds the root, loads the settings and
    builds the real runner. Then it discovers, selects, runs the checks and writes the report to stdout.
  - `GateError` writes `quality-gate: <message>` to stderr and returns 2.
  - Any other exception is logged with `logging.exception`, which Ruff's BLE001 accepts, and returns 2.
  - `__main__.py` is `sys.exit(main())`.
- [ ] **Step 3:** the strict self-check passes, including the gate's run on itself, and `make check` exits 0.
  Handoff with `feat(quality): add the file mode and the python -m entry point`.

### Task 11: plan A closes — self-check, `<T_SUITE>`, documents

**Files:**
- Modify: `docs/02-ROADMAP.md`, `docs/quality-gate/DEVIATIONS.md`, `docs/01-ARCHITECTURE.md`

- [ ] **Step 1:** run the gate on itself, and the strict self-check. Record both results.
- [ ] **Step 2:** measure `<T_SUITE>`: `uv run coverage erase && time uv run coverage run -m pytest`, on the whole
  suite. Then `uv run coverage report | grep -c "^\.venv/"` prints 0, so the virtual environment is not measured
  (§13.5).
- [ ] **Step 3:** update the documents.
  - **Roadmap.** Item 2 is ticked. Items 3 and 4 say what plan A did ("tabelle proprie del gate; Ruff, pytest e
    import-linter al passaggio" and "modo `file` e controlli per file"). `<T_SUITE>` gets the measured value and its
    date.
  - **`DEVIATIONS.md`.** It is complete for plan A.
  - **`01-ARCHITECTURE.md`.** One paragraph on `quality_gate/`: outside the engine, standard library only, never
    imported by `agency`, with ADR-0060.
- [ ] **Step 4:** `make check` exits 0. Handoff with `docs: close plan A of M1.8 with the measured suite time`.

---

## After this plan

Plans B and C are written once this one has closed and its final review is done. They argue from the same spec and
ADRs.
- **Plan B (items 4–7).**
  - Modes `changed` (merge-base, untracked files, the ratchet's rules), `full` and `staged`.
  - The project checks: `import-contracts`, `dead-code`, `dependencies`, `duplication`, `tests` with JUnit
    integrity, `coverage` with consistent file sets, and `diff-coverage`.
  - The integrity checks: `shadow-config`, `config-lock` with the `lock` mode, `hook-integrity`, `tool-versions` and
    `lock-staged`.
  - `env_passthrough`, measured (C8), and `BASELINE.md`.
- **Plan C (items 8–12).** It starts with the switch:
  - the shared tables become §6, and `quality_gate/ruff.toml` is deleted;
  - `.editorconfig` goes to 80;
  - pyright and the dev tool entries go, with `tests/test_dependencies.py`;
  - `task check` runs through `gate`, `check:clean` becomes a clone, and pre-commit replaces `.githooks/`.

  Then the hooks with their truncated output (§7.6) and `AGENTS.md`, mutation and P5, the proofs A4–A7, and
  Andrea's lock. From the switch on, every
  change to the gate needs Andrea's `make gate-lock` before its commit (§8.3).
