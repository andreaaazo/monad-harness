# M1.8 quality gate, plan B (roadmap items 4–7: modes, project checks, integrity, baseline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** give `quality_gate` its modes `staged`, `changed` and `full`. Add the seven project checks, the five integrity
checks and the `lock` mode, measure `env_passthrough`, and write `BASELINE.md`. When this plan ends,
`python -m quality_gate full` runs every check of §7.4 but mutation, and `changed` applies the ratchet of §7.5.

**Architecture:** the per-file layer of plan A stays. Its project checks join it, in `quality_gate/checks/`. Each one
is built on plan A's verdict, or on a small function of its own when one tool run is not the whole check (coverage,
deptry). The integrity checks live in `quality_gate/integrity/`, as §4 lays out. `modes.py` composes the checks of each
mode and keeps their temporary files outside the repository. The daily check still does not run the gate: plan C makes
that switch. Until then, `hook-integrity`, `config-lock` and `shadow-config` fail on this repository by design (B3).

**Tech Stack:** Python 3.13 standard library at run time; the pinned tools of the `quality` group (import-linter 2.15,
vulture 2.16, deptry 0.25.1, pylint 4.1.3, coverage 7.16.2, pytest 9.1.1, diff-cover 10.6.0, pre-commit 4.7.0).

**Spec:**
- `docs/quality-gate/SPEC.md`: §7.2, §7.4, §7.5, §8 and A1–A9;
- `docs/adr/0060-il-quality-gate-parametri-decisioni-e-ordine.md`: the build order and the decisions plan B carries
  out (D2, C8, B1);
- `docs/superpowers/plans/2026-11-15-m1-8-plan-a-per-file-gate.md`: the layer this plan builds on, and its Global
  Constraints;
- `docs/quality-gate/DEVIATIONS.md`: the differences recorded so far;
- plan A's final review, as recorded in its handoff message. Two of its notes are carried here (B6): `GIT_INDEX_FILE`
  for `staged`, and the process group on a timeout.

## Decisions (recorded in `DEVIATIONS.md` by the task that implements each one)

Andrea delegated these ("You make the decisions"). Every value below was measured on 2026-11-16 with the pinned tools.

| # | Decision | Why |
|---|---|---|
| B1 | **`env_passthrough = ["XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"]`** (Task 8). | With only §7.3's variables, `systemd-run --user` fails: "$DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined". With these two added, the whole suite passes (1429 passed, 0 skipped). |
| B2 | **Tests make commits only in temporary repositories** under `tmp_path`, through `Runner.git` with `-c commit.gpgsign=false`. They never commit in the project's repository. | `changed` needs a `HEAD` and a merge-base. CLAUDE.md's rule guards the project's history, and a throwaway repository has none. The handoff asks Andrea to confirm. |
| B3 | **Until the switch, three integrity checks fail on this repository.**<ul><li>`shadow-config`: `pyrightconfig.json`, `quality_gate/ruff.toml` and `[tool.pytest.ini_options]`.</li><li>`hook-integrity`: no `.claude/settings.json`, `core.hooksPath` set, no pre-commit hook.</li><li>`config-lock`: no lock yet.</li></ul> | All are plan C's work. `changed` is not wired into `make check` before the switch, so nothing is blocked. |
| B4 | **deptry gets `known_first_party = ["agency"]`.** The gate also drops two kinds of finding: DEP004 in a test file (a file under a `tests/` folder, or a `conftest.py`), and any finding outside the discovered files, except in `pyproject.toml`. | Without the key, deptry reports `agency` itself as a transitive dependency 408 times: it misreads the `src` layout. The key excludes nothing. deptry's own default excludes only the root `tests/`, so pytest in `quality_gate/tests` gives 11 DEP004. `legacy/` (D4) gives 49 findings. |
| B5 | **The coverage check judges from coverage's JSON, not from its exit code.** It checks that the sets of files agree in `changed` and `full`, and asks for 100% of lines and branches only in `full`. | `coverage json`, `xml` and `report` all exit 2 below `fail_under = 100`, yet §7.5 asks `changed` only for the file sets to agree. |
| B6 | **`Runner.git` passes the gate's own `GIT_INDEX_FILE` to git, and to no other tool.** A timeout kills the whole process group (`start_new_session=True`). | Inside a commit hook, git may point at a temporary index; `staged` must read that one. basedpyright's node outlived a timeout (plan A's review). |
| B7 | **`hook-integrity` also fails when `core.hooksPath` is set.** | git would then never run `.git/hooks/pre-commit`. This is stricter than §8.4. |
| B8 | **A locked file that is missing hashes as `"absent"`**, like a missing table (§8.3). The quality group is locked under the key `dependency-groups.quality`. | A file added or removed is a difference, as §8.3 asks. |
| B9 | **pylint runs with `--persistent n`** (no stats cache, §7.3). Its duplicate blocks name modules; the gate maps each one to a discovered file the way pylint names modules, as the dotted path from the first folder without `__init__.py`. | pylint's own `path` field names whichever file it read last, not the duplicated ones (measured: `tests/test_vocabulary.py` for a block in two other files). |
| B10 | **diff-cover runs with `--format json:<tmp>` and `--branch-coverage`.** | diff-cover 10.6.0 has no `--json-report`, and `--branch-coverage` is the flag §13.6 looks for. |
| B11 | **`BASELINE.md` comes from a `full` run of this plan.** Its Ruff counts are taken with §6.1's rules (`--config quality_gate/ruff.toml`), because the root table is still today's. Plan C refreshes it after the switch. | A9 asks for the counts of `full`, and today's Ruff table would understate them. |

## Target tree after this plan

```
quality_gate/
  changes.py          changed_paths, staged_paths (git's view of what changed)
  modes.py            run_file_mode (plan A), run_staged, run_changed, run_full
  checks/
    verdict.py        + run_once (a tool run with no file arguments)
    scope.py          keep_in (the ratchet's filter)
    contracts.py      import-contracts
    dead_code.py      dead-code
    dependencies.py   dependencies
    duplication.py    duplication
    suite.py          tests
    covered.py        coverage
    diff_coverage.py  diff-coverage
  integrity/
    __init__.py
    tool_versions.py  shadow_config.py  config_lock.py  locking.py  lock_staged.py  hook_integrity.py
```

`execution.py` gains `Runner.with_environment`, the git index variable and the process group. `command.py` and
`cli.py` learn the new modes. `pyproject.toml` gains `known_first_party` and `env_passthrough`. The documents are
`docs/quality-gate/BASELINE.md` (new), `DEVIATIONS.md`, the roadmap and `01-ARCHITECTURE.md`.

## Global Constraints

- **Plan A's Global Constraints hold unchanged**:
  - English code, Italian documents; no git writes in the project;
  - the READY FOR COMMIT handoff after every task;
  - standard library only at run time, and only `execution.py` launches processes;
  - no `Any`, no `cast`, no suppression text, no print;
  - exit codes 0, 1 and 2.
- **Plan A's rulings are the house style**:
  - a call expected to raise is written `with pytest.raises(E, match=...): pytest.fail(repr(call()))`;
  - files are written with `writelines`;
  - a suppression directive in a test is written masked (`'no~qa'.replace('~', '')`);
  - test names stay within 45 characters (WPS118);
  - JSON is read through `jsonvalue`, and TOML into an `object`, then narrowed with the guards.
- **The strict self-check closes every task**, beside `make check`. It is plan A's, with coverage data kept outside the
  repository:

  ```bash
  export COVERAGE_FILE="$PWD/.superpowers/sdd/<this plan>/.coverage"
  uv run ruff check --ignore-noqa quality_gate
  uv run ruff format --check quality_gate
  uv run flake8 --config .flake8 --disable-noqa --format default quality_gate
  uv run pydoclint --config pyproject.toml --quiet quality_gate
  uv run basedpyright --project pyproject.toml --pythonpath .venv/bin/python quality_gate
  uv run coverage erase
  uv run coverage run -m pytest -W error --strict-markers --strict-config quality_gate/tests
  uv run coverage report --include='quality_gate/*'
  ```

- **Temporary files of a run live in one `tempfile.TemporaryDirectory`**, created by the mode and removed at its end
  (§7.3). Nothing a check writes stays in the repository.
- **A real-tool test runs in a temporary repository** with its own small config, as in plan A. A commit there is made
  only through `Runner.git` (B2).
- **Every check of §7.4 keeps its name and its place in the order**: `ruff-lint`, `ruff-format`, `wps`, `pydoclint`,
  `basedpyright`, `suppressions`, `import-contracts`, `dead-code`, `dependencies`, `duplication`, `tests`, `coverage`,
  `diff-coverage`, `shadow-config`, `config-lock`, `hook-integrity`, `tool-versions`, `lock-staged`.

## Review Focus

These are the conditions a reasonable person expects to hold, and the tests that pin them.

- **A check whose tool ran but left no data never passes.** Pytest that wrote no JUnit file, coverage with no data, and
  deptry with no JSON report all give ERROR. Pinned by `test_missing_junit_is_an_error` (Task 8),
  `test_no_coverage_data_is_an_error` (Task 9) and `test_missing_deptry_report_is_an_error` (Task 7).
- **A test skipped at run time fails `tests`, even without a banned name** (A4's canary), and `PYTEST_ADDOPTS` has no
  effect. Pinned by `test_a_runtime_skip_fails_the_suite` and `test_pytest_addopts_does_not_reach_pytest` (Task 8).
- **`changed` sees what changed and nothing else.**
  - Staged, unstaged and untracked files all count.
  - A base that does not exist exits 2.
  - A repository with no commit counts everything.

  Pinned by `test_untracked_and_unstaged_files_count` and `test_an_unknown_base_is_a_gate_error` (Task 1), and
  `test_without_commits_everything_changed` (Task 1).
- **The ratchet filters results, not checks.** A finding outside the changed files does not fail `changed`; one inside
  does; a duplicate block that touches a changed file counts. Pinned by `test_keep_in_drops_findings_outside` (Task 1),
  `test_a_block_touching_a_changed_file_counts` (Task 7) and `test_changed_filters_project_findings` (Task 11).
- **No agent can write the lock.** Without a terminal, or with `CLAUDECODE` in the environment, the `lock` mode refuses
  with exit 2, and a staged lock without approval fails `lock-staged`. Pinned by `test_lock_refuses_without_a_terminal`,
  `test_lock_refuses_inside_claude_code` and `test_a_staged_lock_needs_approval` (Task 4).

---

## Phase 1: plumbing

### Task 1: git's view of change, the ratchet's filter, and three runner fixes

**Files:**
- Create: `quality_gate/changes.py`, `quality_gate/checks/scope.py`, `quality_gate/tests/test_changes.py`,
  `quality_gate/tests/test_scope.py`
- Modify: `quality_gate/execution.py`, `quality_gate/checks/verdict.py`, `quality_gate/tests/test_execution.py`,
  `quality_gate/tests/test_verdict.py`, `quality_gate/tests/conftest.py` (a helper `commit_all(runner: Runner) -> None`
  that runs `git add -A` and `git -c commit.gpgsign=false commit -q -m snapshot`, B2)

**Interfaces:**
- Produces:
  - `Runner.with_environment(extra: Mapping[str, str]) -> Runner`, a copy with the variables added.
  - `execution.GIT_ONLY_VARIABLES: Final = ('GIT_INDEX_FILE',)`. `Runner.git` adds them from `os.environ` when set;
    `Runner.tool` never does (B6).
  - Every process starts with `start_new_session=True`. On a timeout the gate kills its process group, then raises
    `ToolError('timeout after Ns')` (B6).
  - `changes.changed_paths(runner: Runner, base: str) -> tuple[str, ...] | None`: the sorted root-relative paths of
    every file, Python or not, that differs between the merge-base of `base` and `HEAD` and the working tree (staged
    and unstaged, `--diff-filter=ACMR`), plus the untracked ones that are not ignored. It returns `None` in a
    repository with no commit, where everything counts (§7.2). A base git cannot resolve raises
    `GateError('unknown base: <base>')`.
  - `changes.staged_paths(runner: Runner) -> tuple[str, ...]`: `git diff --cached --name-only -z --diff-filter=ACMR`.
  - `scope.keep_in(result: CheckResult, paths: Collection[str]) -> CheckResult`: keeps the violations whose path is in
    `paths`. A FAIL with nothing left becomes PASS, and an ERROR stays an ERROR.
  - `verdict.run_once(check: ToolCheck, runner: Runner) -> CheckResult`: runs the tool with its options only (no
    files), then judges it with `judge`. A `ToolError` becomes an ERROR, as in `run_tool_check`.

- [ ] **Step 1:** write the failing tests.
  - `test_with_environment_adds_variables`: the copy keeps the old variables and adds the new.
  - `test_git_sees_the_index_variable` and `test_tools_never_see_the_index_variable`: with `GIT_INDEX_FILE` set
    through monkeypatch, `git rev-parse --git-path index`, run with a temporary index, answers that index; a fake tool
    that dumps its environment does not see the variable.
  - `test_a_timeout_kills_the_process_group`: a fake tool starts a child that writes a file after 2 s, then sleeps.
    With a timeout of 0.5 s, the file is still absent 3 s later.
  - `test_untracked_and_unstaged_files_count`: after `commit_all`, a modified tracked file, a staged new file, an
    untracked file and a changed `README.md` are all in `changed_paths(runner, 'HEAD')`; a deleted file is not.
  - `test_the_merge_base_is_the_reference`: on a branch two commits past `main`, `changed_paths(runner, 'main')`
    holds the files of both commits.
  - `test_an_unknown_base_is_a_gate_error`.
  - `test_without_commits_everything_changed`: a fresh repository gives `None`.
  - `test_staged_paths_are_the_index`.
  - `test_keep_in_drops_findings_outside`: a FAIL with violations in `a.py` and `b.py`, kept in `{'a.py'}`, is a FAIL
    with only `a.py`'s; kept in `{'c.py'}` it is PASS; an ERROR stays an ERROR.
  - `test_run_once_passes_no_files`: a fake tool echoes its argv; the result's raw output holds only the options.
- [ ] **Step 2:** implement. `changed_paths` runs:
  1. `git rev-parse --verify --quiet HEAD`; a nonzero exit means no commit, so return `None`;
  2. `git merge-base <base> HEAD`; a nonzero exit is the GateError;
  3. `git diff --name-only -z --diff-filter=ACMR <sha>`;
  4. `git ls-files -z --others --exclude-standard`.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Record B2 and B6 in `DEVIATIONS.md`. Handoff
  with `feat(quality): read what changed, filter by it, and run tools once`.

## Phase 2: integrity

### Task 2: `tool-versions` and `shadow-config`

**Files:**
- Create: `quality_gate/integrity/__init__.py`, `quality_gate/integrity/tool_versions.py`,
  `quality_gate/integrity/shadow_config.py`, `quality_gate/tests/test_tool_versions.py`,
  `quality_gate/tests/test_shadow_config.py`

**Interfaces:**
- Produces:
  - `tool_versions.run(root: Path) -> CheckResult` (name `tool-versions`, §8.5). There is one violation per broken pin,
    at `pyproject.toml:1:1`, coded `pin-not-exact`, `not-installed` or `version-differs`. Names are compared in their
    PEP 503 form.
  - `shadow_config.run(root: Path, venv: Path) -> CheckResult` (name `shadow-config`, §8.2). It walks the
    filesystem below `root`, skips `.git/` and `venv`, and follows no link. There is one violation per finding, coded
    `shadow-file`, `shadow-folder` or `shadow-section`:
    - **forbidden files anywhere:** `ruff.toml`, `.ruff.toml`, `pyrightconfig.json`, `basedpyrightconfig.json`,
      `pytest.ini`, `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `.coveragerc`, `pylintrc`, `.pylintrc`,
      `pylintrc.toml`, `.pylintrc.toml`, `.importlinter`;
    - **forbidden away from the root:** `.flake8`;
    - **forbidden folders:** `.basedpyright/`;
    - **forbidden sections:**
      - `[tool.ruff]` in a `pyproject.toml` that is not the root's;
      - `[tool.pyright]` and `[tool.pytest.ini_options]` in any `pyproject.toml`;
      - in `setup.cfg` and `tox.ini`: `[flake8]`, `[pytest]`, `[tool:pytest]`, `[coverage:*]`, `[pylint*]`,
        `[importlinter*]` and `[mutmut]`;
    - **a TOML or INI file that cannot be read** is a finding too: its sections cannot be checked.

- [ ] **Step 1:** write the failing tests.
  - `test_matching_pins_pass`: a temporary `pyproject.toml` pins `pytest==<installed version>`.
  - `test_a_loose_pin_fails` (`>=`), `test_a_missing_package_fails`, `test_a_different_version_fails`.
  - `test_the_repository_pins_pass`, on this repository.
  - Shadow config:
    - `test_each_shadow_file_is_found`, parametrized over the forbidden file names, each in a subfolder;
    - `test_a_root_flake8_is_allowed`, and `test_a_nested_flake8_is_found`;
    - `test_a_nested_tool_ruff_table_is_found`;
    - `test_pyright_and_ini_options_tables_are_found`, in the root `pyproject.toml`;
    - `test_setup_cfg_sections_are_found`, parametrized over the INI sections;
    - `test_git_and_venv_are_skipped`;
    - `test_an_unreadable_config_file_is_found`;
    - `test_a_clean_tree_passes`.
- [ ] **Step 2:** implement. Reading INI files uses `configparser`, with interpolation off.
- [ ] **Step 3:** run both checks on this repository and record the result.
  - Expected: `tool-versions` PASS.
  - Expected: `shadow-config` FAIL with exactly three findings: `pyrightconfig.json`, `quality_gate/ruff.toml`, and
    `[tool.pytest.ini_options]` in `pyproject.toml` (B3).
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): check tool versions and look for shadow configs`.

### Task 3: `config-lock`

**Files:**
- Create: `quality_gate/integrity/config_lock.py`, `quality_gate/tests/test_config_lock.py`

**Interfaces:**
- Produces:
  - `LOCK_PATH: Final = 'quality_gate/config.lock'`.
  - `LOCKED_TABLES: Final`, the tables of §8.3 in order: `tool.ruff`, `tool.basedpyright`, `tool.pyright`,
    `tool.pydoclint`, `tool.importlinter`, `tool.vulture`, `tool.deptry`, `tool.pylint`, `tool.pytest`, `tool.coverage`,
    `tool.mutmut`, `tool.diff_cover`, `tool.quality_gate`, `dependency-groups.quality`.
  - `LOCKED_FILES: Final`: `.flake8`, `.pre-commit-config.yaml`, `.claude/settings.json`, `AGENTS.md`, `CLAUDE.md`.
  - `compute_lock(root: Path, gate_files: Sequence[str]) -> dict[str, object]`. It returns
    `{'schema': 1, 'tables': {...}, 'files': {...}}`:
    - a table is hashed as the SHA-256 of `json.dumps(value, sort_keys=True, separators=(',', ':'),
      ensure_ascii=False)`, and an absent one is `"absent"`;
    - a file is hashed as the SHA-256 of its bytes, and an absent one is `"absent"` (B8);
    - `gate_files` are the discovered files under `quality_gate/`, which the caller passes;
    - `config.lock` itself is never in it.
  - `render_lock(lock: dict[str, object]) -> str`: JSON with sorted keys, an indent of 2 and a final newline.
  - `differences(old: dict[str, object] | None, new: dict[str, object]) -> tuple[str, ...]`: one line per entry
    added, removed or changed, as `tables tool.ruff changed`, `files quality_gate/x.py added`, or `lock missing`.
  - `run(root: Path, gate_files: Sequence[str]) -> CheckResult` (name `config-lock`). There is one violation per
    difference, at `quality_gate/config.lock:1:1`, coded `lock-differs`. A lock file that is not JSON is one
    `lock-unreadable` violation.

- [ ] **Step 1:** write the failing tests.
  - `test_a_table_hashes_by_its_value`: two `pyproject.toml` files, same `[tool.ruff]` but different spacing, comments
    and key order, give the same hash.
  - `test_absent_tables_and_files_are_marked`.
  - `test_the_lock_renders_sorted_with_a_newline`.
  - `test_a_matching_lock_passes`.
  - `test_a_changed_threshold_fails`: A4's canary, a changed `max-args` in `[tool.ruff.lint.pylint]`.
  - `test_a_file_added_to_the_gate_fails`: A4's canary.
  - `test_a_missing_lock_fails` and `test_an_unreadable_lock_fails`.
  - `test_a_normal_dependency_change_passes`: a new entry in `[project].dependencies` changes nothing.
- [ ] **Step 2:** implement.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Record B8 in `DEVIATIONS.md`. Handoff with
  `feat(quality): lock the gate's configuration by hash`.

### Task 4: the `lock` mode and `lock-staged`

**Files:**
- Create: `quality_gate/integrity/locking.py`, `quality_gate/integrity/lock_staged.py`,
  `quality_gate/tests/test_locking.py`, `quality_gate/tests/test_lock_staged.py`

**Interfaces:**
- Consumes: `compute_lock`, `render_lock`, `differences`, `LOCK_PATH` (Task 3); `shadow_config.run` and
  `tool_versions.run` (Task 2); `hook_integrity.run` (Task 5) through the `Guards` argument below, so this task does
  not wait on Task 5.
- Produces:
  - `class Terminal(Protocol)`, with `interactive() -> bool`, `show(text: str) -> None` and `ask(prompt: str) -> str`.
    The real one wraps `sys.stdin` and `sys.stdout`, and is `interactive` only when both are terminals.
  - `type Guards = Callable[[], tuple[CheckResult, ...]]`: the integrity checks that must pass before a lock.
  - `lock(root: Path, gate_files: Sequence[str], terminal: Terminal, *, guards: Guards) -> int`. In order:
    1. without a terminal → the refusal `quality-gate: lock needs a terminal`, and 2;
    2. `CLAUDECODE` in `os.environ` → the refusal `quality-gate: lock cannot run inside Claude Code`, and 2;
    3. any guard that does not pass → its name and violations shown, and 2;
    4. otherwise it shows the differences against the current lock and asks `Type LOCK to write the new lock: `;
       exactly `LOCK` writes `render_lock(...)` to `LOCK_PATH` and returns 0, and anything else aborts with 2.
  - `lock_staged.run(runner: Runner, environment: Mapping[str, str]) -> CheckResult` (name `lock-staged`): FAIL when
    `LOCK_PATH` is among `staged_paths(runner)` and `environment.get('QUALITY_GATE_LOCK_CHANGE_OK') != '1'`. Its one
    violation is coded `lock-unapproved`, with the message
    `commit a new lock with QUALITY_GATE_LOCK_CHANGE_OK=1 git commit`.

- [ ] **Step 1:** write the failing tests, with a fake `Terminal`.
  - `test_lock_refuses_without_a_terminal`, and `test_lock_refuses_inside_claude_code` (monkeypatch `CLAUDECODE`).
  - `test_lock_refuses_when_a_guard_fails`.
  - `test_lock_shows_changes_and_writes_on_lock`: the shown text holds `tables tool.ruff changed`, and the file
    equals `render_lock(compute_lock(...))`.
  - `test_any_other_answer_aborts`: `lock`, `y` and an empty answer leave the file untouched and return 2.
  - `test_the_real_terminal_needs_two_ttys`: a test of the real terminal's `interactive`, monkeypatching
    `sys.stdin.isatty` and `sys.stdout.isatty`.
  - `test_a_staged_lock_needs_approval`, `test_an_approved_lock_passes` and `test_an_unstaged_lock_passes`, in a
    temporary repository.
- [ ] **Step 2:** implement. `CLAUDECODE` is read from `os.environ` on purpose: it is the gate's own environment, not
  a tool's.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): let only a person at a terminal write the lock`.

### Task 5: `hook-integrity`

**Files:**
- Create: `quality_gate/integrity/hook_integrity.py`, `quality_gate/tests/test_hook_integrity.py`

**Interfaces:**
- Produces:
  - `STOP_TIMEOUT: Final = 334`, which is 2 × `<T_SUITE>` (107 s) + 120.
  - `EXPECTED_HOOKS: Final[dict[str, object]]`: the `hooks` object of §9.1, with `<ENV_PY>` = `.venv/bin/python`
    and the timeouts 10, 120, `STOP_TIMEOUT` and 10. Plan C writes `.claude/settings.json` from this value.
  - `PRE_COMMIT_MARKER: Final = '# ID: 138fd403232d2ddd5efb44317e38bf03'`: the line pre-commit 4.7.0 writes in every
    hook it installs.
  - `run(root: Path, home: Path, runner: Runner, *, environment: Mapping[str, str]) -> CheckResult` (name
    `hook-integrity`). There is one violation per condition that is false, coded `hooks`:
    1. `.claude/settings.json` holds `"disableAllHooks": false` and `"hooks"` equal to `EXPECTED_HOOKS`;
    2. `.claude/settings.local.json`, if it exists, is JSON; it has no `disableAllHooks: true` and no `hooks` key, and
       its `env` defines no variable starting with `QUALITY_GATE_` and no `CLAUDECODE`;
    3. `home / '.claude/settings.json'`, if it exists, defines in its `env` no `QUALITY_GATE_*` and no `CLAUDECODE`;
    4. outside CI (`environment.get('CI')` empty): `.git/hooks/pre-commit` exists and holds `PRE_COMMIT_MARKER`, and
       `git config --get core.hooksPath` exits nonzero (B7).

- [ ] **Step 1:** write the failing tests. Each starts from a temporary repository that satisfies all four conditions,
  then breaks one.
  - `test_a_complete_setup_passes`.
  - `test_missing_or_disabled_settings_fail`, parametrized over: no file, `disableAllHooks: true`, a hook removed, a
    timeout changed.
  - `test_local_settings_cannot_disable_hooks`: A4's canary.
  - `test_local_settings_cannot_set_gate_variables`: A4's canary, `env.QUALITY_GATE_MAINTENANCE`.
  - `test_user_settings_cannot_set_gate_variables`.
  - `test_a_foreign_pre_commit_hook_fails`.
  - `test_a_hooks_path_fails`.
  - `test_ci_skips_the_commit_hook`.
- [ ] **Step 2:** implement.
- [ ] **Step 3:** run the check on this repository. Expected: FAIL, with no settings file, `core.hooksPath` set and no
  pre-commit hook (B3). Record B7 in `DEVIATIONS.md`.
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): check that the hooks are in place and nobody turned them off`.

## Phase 3: project checks

### Task 6: `import-contracts` and `dead-code`

**Files:**
- Create: `quality_gate/checks/contracts.py`, `quality_gate/checks/dead_code.py`, `quality_gate/tests/test_contracts.py`,
  `quality_gate/tests/test_dead_code.py`

**Interfaces:**
- Consumes: `ToolCheck`, `run_once`, `run_tool_check`, `relative_path` (plan A, Task 1).
- Produces:

  | Check | Tool | Options | Failing exit codes | Files |
  |---|---|---|---|---|
  | `import-contracts` | `lint-imports` | `--no-cache --config pyproject.toml` | `{1}` | none (`run_once`) |
  | `dead-code` | `vulture` | `--config pyproject.toml` | `{3}` | every discovered file |

  - `parse_lint_imports`: one violation per `<name> BROKEN` line, at `pyproject.toml:1:1`, coded `broken-contract`,
    whose message is the contract's name. Other lines are ignored. import-linter prints a long name over two lines,
    so the parser joins a line that ends with a space to the next one.
  - `parse_vulture`: `path:line: message (N% confidence)` becomes a violation coded `dead-code`, at column 1, with the
    message and its confidence.

- [ ] **Step 1:** write the failing tests.
  - Parsers, on samples captured from the pinned tools:
    - `test_broken_contracts_become_violations`, including a wrapped name;
    - `test_vulture_lines_become_violations`.
  - Real tools, in a temporary repository:
    - `test_an_import_cycle_breaks_a_contract`: A4's canary, with an `acyclic_siblings` contract;
    - `test_kept_contracts_pass`;
    - `test_an_unused_function_is_dead_code`: A4's canary;
    - `test_used_code_passes`.
- [ ] **Step 2:** implement.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): check import contracts and dead code`.

### Task 7: `dependencies` and `duplication`

**Files:**
- Create: `quality_gate/checks/dependencies.py`, `quality_gate/checks/duplication.py`,
  `quality_gate/tests/test_dependencies_check.py`, `quality_gate/tests/test_duplication.py`
- Modify: `pyproject.toml` (`[tool.deptry]` gains `known_first_party = ["agency"]`, with a one-line comment, B4)

**Interfaces:**
- Produces:
  - `dependencies.run(given: CheckInput, workspace: Path) -> CheckResult` (name `dependencies`).
    - deptry runs once, through `run_once`, with `. --config pyproject.toml --no-ansi --json-output
      <workspace>/deptry.json`. The failing exit code is `{1}`.
    - The parser reads that JSON file. A file that is missing or unreadable is an ERROR.
    - Each finding becomes a violation at its location, coded `DEP00N`, with deptry's message.
    - The B4 filter applies: a finding is kept only if its path is in `given.files` or is `pyproject.toml`, and a
      DEP004 in a test file is dropped.
  - `duplication.run(given: CheckInput) -> CheckResult` (name `duplication`).
    - pylint runs on every discovered file, with `--rcfile pyproject.toml --output-format json --persistent n`. The
      failing exit code is `{8}`, so a fatal or usage bit is an ERROR.
    - Each `duplicate-code` message becomes one violation per block, coded `R0801`. The path is the first file of
      the block, and the line is its first line. The message lists every file of the block, with its line range.
  - `duplication.module_name(path: str, root: Path) -> str`: the dotted path from the first parent folder without
    `__init__.py` (B9).
  - `duplication.block_paths(violation: Violation) -> tuple[str, ...]`: every file a block touches, read back from
    the message. Task 11's filter uses it.

- [ ] **Step 1:** write the failing tests.
  - `test_deptry_findings_become_violations`: a JSON sample with DEP001, DEP002 at `pyproject.toml`, DEP003 and DEP004.
  - `test_findings_outside_discovery_are_dropped`, and `test_dep004_in_test_files_is_dropped`.
  - `test_missing_deptry_report_is_an_error`.
  - `test_an_undeclared_import_fails`: A4's canary, with the real deptry in a temporary repository.
  - `test_module_names_follow_packages`: `src/agency/studio/shared.py` gives `agency.studio.shared`,
    `tests/test_x.py` gives `test_x`, and `quality_gate/checks/verdict.py` gives `quality_gate.checks.verdict`.
  - `test_duplicate_blocks_become_violations`, on a captured JSON sample.
  - `test_a_copied_block_is_found`: A4's canary, four or more copied lines with the real pylint.
  - `test_a_block_touching_a_changed_file_counts`: `block_paths` names both files.
- [ ] **Step 2:** implement. Then run `dependencies` on this repository. Expected: PASS. The 408 DEP003, the 11
  DEP004 and the 49 findings in `legacy/` are all gone (B4). Record B4 and B9 in `DEVIATIONS.md`.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): check declared dependencies and duplicated code`.

### Task 8: `tests`, and `env_passthrough`

**Files:**
- Create: `quality_gate/checks/suite.py`, `quality_gate/tests/test_suite.py`
- Modify: `pyproject.toml` (`env_passthrough = ["XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"]`, B1),
  `quality_gate/tests/test_settings.py` (`test_repository_settings_are_decided` expects the two variables)

**Interfaces:**
- Produces:
  - `suite.run(runner: Runner, workspace: Path) -> CheckResult` (name `tests`).
    - The command is `coverage run --rcfile pyproject.toml -m pytest -p no:cacheprovider --junit-xml
      <workspace>/junit.xml`, through `run_once`.
    - It runs on a runner that has `COVERAGE_FILE=<workspace>/.coverage` added.
    - The failing exit code is `{1}`; 2, 3, 4 and 5 are ERRORs.
  - The JUnit parser reads `testsuites/testsuite`. It gives a violation for:
    - `tests == 0` (`no-tests`);
    - `skipped > 0`, which counts xfails too (`skipped`);
    - `errors > 0` (`collection-errors`);
    - each `testcase` with a `failure` or `error` child (`test-failed`, message `<classname>::<name>`).

    All of them sit at path `.`. A missing or unreadable JUnit file is an ERROR (§8.6).

- [ ] **Step 1:** write the failing tests, with the real tools, in a temporary repository holding a tiny package and
  its tests.
  - `test_a_passing_suite_passes`.
  - `test_a_failing_test_fails_with_its_name`.
  - `test_a_runtime_skip_fails_the_suite`: A4's canary. The test skips at run time by raising `SkipTest` imported
    under another name, which the suppression scan cannot see.
  - `test_an_empty_suite_fails`.
  - `test_missing_junit_is_an_error`: a fake `coverage` that exits 0 and writes nothing.
  - `test_pytest_addopts_does_not_reach_pytest`: A4's canary. `PYTEST_ADDOPTS="-k nothing"` is set through
    monkeypatch, and the suite still runs its test.
  - `test_coverage_data_lands_in_the_workspace`.
- [ ] **Step 2:** implement, and set `env_passthrough` (B1).
- [ ] **Step 3:** run `suite.run` on this repository with `runner_for(root, settings.env_passthrough, 600)`.
  Expected: PASS, with 0 skipped. Record B1 in `DEVIATIONS.md`, with the two measurements quoted in the Decisions
  table as proof.
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): run the suite under coverage and refuse skipped tests`.

### Task 9: `coverage` and `diff-coverage`

**Files:**
- Create: `quality_gate/checks/covered.py`, `quality_gate/checks/diff_coverage.py`,
  `quality_gate/tests/test_covered.py`, `quality_gate/tests/test_diff_coverage.py`

**Interfaces:**
- Consumes: the workspace `suite.run` filled (`.coverage`).
- Produces:
  - `covered.run(runner: Runner, workspace: Path, discovered: Sequence[str], *, whole: bool) -> CheckResult` (name
    `coverage`).
    - It runs `coverage json --rcfile pyproject.toml -o <workspace>/coverage.json`, then `coverage xml` the same way
      (`coverage.xml`), then `coverage report --rcfile pyproject.toml`, whose text becomes `raw`.
    - All three run with the workspace's `COVERAGE_FILE`, and exits 0 and 2 are both expected (B5).
    - Violations:
      - a measured file that is not a discovered file (`not-discovered`, §8.6);
      - with `whole`, a discovered file that is absent from the report (`never-imported`);
      - with `whole`, a file with missing lines, missing branches or partial branches (`not-covered`, message
        `lines <list>, branches <list>`).
    - No `.coverage` file, or no JSON, is an ERROR.
  - `diff_coverage.run(runner: Runner, workspace: Path, base: str) -> CheckResult` (name `diff-coverage`).
    - The command is `diff-cover <workspace>/coverage.xml --compare-branch <base> --fail-under 100
      --include-untracked --branch-coverage --format json:<workspace>/diff-cover.json`. The failing exit code is
      `{1}`.
    - Each uncovered line of `src_stats` becomes a violation, coded `diff-coverage`.
    - A missing JSON file is an ERROR.

- [ ] **Step 1:** write the failing tests, in temporary repositories, after a real `suite.run`.
  - `test_coherent_sets_pass_in_changed`, with partial coverage and `whole=False`.
  - `test_partial_coverage_fails_in_full`, with `whole=True`, naming the missing line and branch.
  - `test_an_ignored_module_fails_coherence`: A4's canary. A module in a folder `.gitignore` hides, imported by a
    test.
  - `test_a_never_imported_file_fails_in_full`.
  - `test_no_coverage_data_is_an_error`.
  - `test_an_untested_branch_fails_diff_coverage`: A4's canary. After `commit_all`, a new branch is added and not
    tested.
  - `test_tested_changes_pass_diff_coverage`.
- [ ] **Step 2:** implement. First confirm that diff-cover reads no other configuration file. If it accepts
  `-c pyproject.toml` with no `[tool.diff_cover]` table, add it. Record B5 and B10 in `DEVIATIONS.md`.
- [ ] **Step 3:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): check coverage, whole and on the changed lines`.

## Phase 4: the modes

### Task 10: `full`, `staged`, `lock` and the command line

**Files:**
- Modify: `quality_gate/command.py`, `quality_gate/cli.py`, `quality_gate/modes.py`, `quality_gate/tests/test_cli.py`
- Create: `quality_gate/tests/test_modes.py`

**Interfaces:**
- Produces:
  - `Command(mode: str, paths: tuple[str, ...], base: str | None, output: str)`. The grammar is
    `file PATH...`, `staged`, `changed [--base REF]`, `full` and `lock`; `--format text|json` goes on every mode but
    `lock`.
  - `USAGE` lists the five modes.
  - `modes.run_full(runner: Runner, settings: Settings) -> Report`: every check of §7.4 but `diff-coverage`,
    `lock-staged` and mutation. The per-file checks get every discovered file. `coverage` has `whole=True`.
  - `modes.run_staged(runner: Runner, settings: Settings) -> Report`: the per-file checks on `staged_paths` ∩
    discovered, then `shadow-config`, `config-lock`, `hook-integrity`, `tool-versions` and `lock-staged`.
  - In `cli.main`, `lock` runs `locking.lock` with the real terminal, and its guards are `shadow-config`,
    `hook-integrity` and `tool-versions`. The other modes print their report.
  - If `modes.py` would exceed WPS's limits, it is split into `modes/` (`file.py`, `whole.py`, `changed.py`), with the
    same public names.

- [ ] **Step 1:** write the failing tests.
  - The command line:
    - `test_each_mode_parses`;
    - `test_changed_takes_a_base`, which defaults to `HEAD`;
    - `test_lock_takes_no_format`;
    - `test_a_mode_with_stray_paths_is_refused`.
  - The modes, with fake tools for the speed of the per-file checks, and real git:
    - `test_full_runs_every_check_in_order`: the names equal §7.4's order without `diff-coverage` and `lock-staged`;
    - `test_staged_checks_only_the_index`: of two changed files, only the staged one is in `python_files`;
    - `test_staged_runs_lock_staged`.
- [ ] **Step 2:** implement. Each mode makes one `TemporaryDirectory` as its workspace.
- [ ] **Step 3:** run `uv run python -m quality_gate full` on this repository. Expected: exit 1. Every check gives a
  verdict, and none is ERROR apart from what the report explains. Save the report under the plan's workspace for
  Task 12.
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): add the full, staged and lock modes`.

### Task 11: `changed`, the ratchet

**Files:**
- Modify: `quality_gate/modes.py` (or `modes/changed.py`), `quality_gate/tests/test_modes.py`

**Interfaces:**
- Produces: `modes.run_changed(runner: Runner, settings: Settings, base: str) -> Report`. Its header has
  `base=<base>`. With `changed = changed_paths(runner, base)`, where `None` means every discovered file and every
  path:
  - **nothing changed:** only `shadow-config`, `config-lock`, `hook-integrity` and `tool-versions` run;
  - **otherwise:**
    - the per-file checks run on the changed Python files (changed ∩ discovered);
    - `import-contracts` runs on everything;
    - `dead-code` and `dependencies` run on everything, and `keep_in(changed)` filters their results;
    - `duplication` keeps the blocks whose `block_paths` touch a changed file;
    - `tests`, `coverage` (`whole=False`) and `diff-coverage` (base) run; they do not run when every changed path is
      a `.md` file or sits under `docs/`;
    - then the four integrity checks.

- [ ] **Step 1:** write the failing tests, with fake tools for the per-file checks and real git.
  - `test_nothing_changed_runs_integrity_only`.
  - `test_docs_only_skips_the_suite`: only a `README.md` and a `docs/x.md` changed; `tests`, `coverage` and
    `diff-coverage` do not appear.
  - `test_changed_filters_project_findings`: a fake vulture that reports `old.py` and `new.py`; only `new.py` changed;
    `dead-code` shows only `new.py`.
  - `test_a_new_top_level_folder_is_seen`: A4's canary. A `.py` file in a new folder is in `python_files`.
  - `test_the_header_names_the_base`.
- [ ] **Step 2:** implement.
- [ ] **Step 3:** run `uv run python -m quality_gate changed` on a clean tree of this repository. Expected: exit 1,
  with only `shadow-config`, `config-lock` and `hook-integrity` failing (B3). A2's "changed on a clean tree exits 0"
  waits for plan C.
- [ ] **Step 4:** the strict self-check passes and `make check` exits 0. Handoff with
  `feat(quality): add the changed mode, the ratchet`.

### Task 12: `BASELINE.md`, and plan B closes

**Files:**
- Create: `docs/quality-gate/BASELINE.md`
- Modify: `docs/02-ROADMAP.md`, `docs/quality-gate/DEVIATIONS.md`, `docs/01-ARCHITECTURE.md`

- [ ] **Step 1:** from Task 10's `full` report, write `BASELINE.md` in Italian (A9):
  - for each check, its count and duration;
  - the ten most frequent rules for Ruff, WPS and basedpyright. Ruff's are measured with §6.1's rules, through
    `uv run ruff check --config quality_gate/ruff.toml --ignore-noqa --output-format json` on every discovered file
    (B11);
  - today's coverage, lines and branches;
  - the active contracts: today's 13, and the two of §6.5 that wait for the switch;
  - the pending contracts: the indirect versions of the four direct-import ones (ADR-0060, D2);
  - every exception of §6.10, with its reason;
  - vulture's likely false positives (methods that frameworks call by name, such as pydantic validators and Django's
    `settings_customise_sources`);
  - the 120 suppression directives counted in plan A, now by `full`'s `suppressions` check.
- [ ] **Step 2:** update the documents.
  - **Roadmap.** Items 5 and 6 are ticked as far as plan B goes: the hook and lock parts that plan C finishes are
    named, and item 7 is ticked. Items 3 and 4 say what is left for plan C. The status row and "Primo passo
    concreto" point to plan B's final review, then plan C.
  - **`DEVIATIONS.md`.** It is complete for plan B.
  - **`01-ARCHITECTURE.md`.** The paragraph on `quality_gate/` lists the modes and the `integrity/` package.
- [ ] **Step 3:** `make check` exits 0. Handoff with `docs: record the gate's baseline and close plan B of M1.8`.

---

## After this plan

Plan C (items 8–12) starts with the switch:
- the shared tables become §6, with the two fixed contracts;
- `quality_gate/ruff.toml` and `pyrightconfig.json` are deleted;
- `.editorconfig` goes to 80 columns;
- pyright and the dev tool entries go, together with `tests/test_dependencies.py`;
- `task check` runs through the gate, `check:clean` becomes a clone, and pre-commit replaces `.githooks/`.

Then come:
- `.claude/settings.json` from `EXPECTED_HOOKS`, the hooks with their truncated output, and `AGENTS.md`;
- mutation and P5;
- the proofs A4–A7, with the plan B canaries reused;
- `BASELINE.md` refreshed;
- Andrea's lock.

From the switch on, `changed` on a clean tree must exit 0.
