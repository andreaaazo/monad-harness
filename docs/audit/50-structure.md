Module boundaries are mostly sound: grimp finds no module-level import cycle, import-linter keeps 4/4 contracts, the insights slice and the Django server follow ADR-0019/0021/0031, and `web/` follows the Next.js App Router layout.
The engine still carries what ADR-0021 defers to M1.7 (the `agents`↔`tools`↔`qa` package cycle, a 968-line `tools/surface.py`), and several documented boundaries are not enforced: three hand-kept contract lists, `anthropic` in `cli.py`, SQLModel rows outside the ledger.
The defects to fix now are single-owner breaks: the data root has three sources and two env names (engine and dashboard can read different registries), `registry/` JSON is parsed twice with no schema, and paths, ports and key names are copied across files.
Critical 0 · High 0 · Medium 1 · Low 13 · Nit 3

Audit of HEAD `86f51a1` (branch `audit/deep-review`), read-only. Throwaway scripts lived in `/tmp/audit-str/`; the
commands below recreate what they did. Sizes and the module map are in `00-baseline.md` §1 and are not repeated.

## Findings

### STR-001 · Medium · Confirmed
- Where: src/agency/config.py:16, src/agency/config.py:18, src/agency/entrypoints/server/settings.py:31, .env.example:4, Taskfile.yml:95-98, Taskfile.yml:124, docker/compose.yaml:32
- Problem: The data root (registry, traces, transcripts) has no single owner. The engine reads `AGENCY_DATA_DIR`
  from the process environment or from `.env`, the dashboard server only from the process environment, and
  `task docker:up` from a third variable, `AGENCY_DATA`, that defaults to `<root>/.data`. With `AGENCY_DATA_DIR` set
  in `.env`, as `.env.example:4` invites, `agency run` and `agency report` use that folder while `task dashboard` and
  `task docker:up` read `./.data`, so the dashboard shows another registry (or a 503) and nothing says so.
- Evidence: `Settings` has `env_file=".env"` and `env_prefix="AGENCY_"` (config.py:16), so `data_dir` (config.py:18)
  comes from `.env`. The server never reads `.env` by design (settings.py:3-4, ADR-0031) and resolves
  `os.environ.get("AGENCY_DATA_DIR", ".data")` (settings.py:31). `task dashboard:api` runs `uv run agency-server` with
  no variables (Taskfile.yml:95-98), and the Taskfile has no dotenv on purpose (ADR-0039). `task docker:up` builds
  `AGENCY_DATA` from `.ROOT_DIR/.data` (Taskfile.yml:124), which Compose mounts at `/data` (compose.yaml:32, :25).
  `DataLayout` (contracts/layout.py) owns only the sub-paths below the root, never the root itself.
- Reproduce: run from the worktree with `PYTHONDONTWRITEBYTECODE=1 mise exec -- uv run python <file>`. It printed
  `engine: /tmp/audit-str/envcase/elsewhere/ledger.sqlite` and `server: /tmp/audit-str/envcase/.data`.

  ```python
  import os
  import pathlib

  case = pathlib.Path("/tmp/audit-str/envcase")
  case.mkdir(parents=True, exist_ok=True)
  (case / ".env").write_text(f"AGENCY_DATA_DIR={case}/elsewhere\n", encoding="utf-8")
  os.chdir(case)
  os.environ.pop("AGENCY_DATA_DIR", None)
  os.environ["DJANGO_SETTINGS_MODULE"] = "agency.entrypoints.server.settings"

  from agency.config import Settings  # noqa: E402
  from agency.entrypoints.server import settings  # noqa: E402

  print("engine:", Settings().ledger_path)  # /tmp/audit-str/envcase/elsewhere/ledger.sqlite
  print("server:", settings.AGENCY_DATA_DIR)  # /tmp/audit-str/envcase/.data
  ```

- Fix: Give the root one source and one name. Either `.env` keeps only the API key (the engine stops reading
  `AGENCY_DATA_DIR` from it and `.env.example` drops the line), or the dashboard tasks receive the root the engine
  resolved. The choice belongs to the owner, and renaming `AGENCY_DATA` contradicts ADR-0040, so it needs a new ADR.
  Fix risk: Med.

### STR-002 · Low · Confirmed
- Where: pyproject.toml:74-95, pyproject.toml:121-143, pyproject.toml:145-169, tests/test_server.py:417-427
- Problem: Three of the four import-linter contracts (insights, server, evaluation) forbid the engine through
  hand-written package lists, and no check keeps those lists complete: the only completeness test covers the Django
  contract. Insights, the server and the evaluation slice can import a new engine package (M1.7 adds `shared/`,
  `platform/`, `studio/`, `process/`) while all four contracts are still kept.
- Evidence: `test_every_engine_package_is_forbidden_to_import_django` picks the contract whose forbidden list
  contains `django` (test_server.py:421) and compares only its `source_modules` with the packages on disk. The other
  three lists already differ from one another: insights leaves out `agency.config`, `agency.doctor` and
  `agency.context` (pyproject.toml:78-95), and the server leaves out `agency.doctor` and `agency.context` (:125-143).
  Today those gaps are closed only indirectly: server → insights → config is caught by the server contract.
- Reproduce: a mutation in a scratch copy. It gave 4 kept before the mutation, 4 kept after it, and the guard test
  failed only until `agency.studio` was added to the Django list.

  ```sh
  mkdir -p /tmp/audit-str/mut && cp -r src pyproject.toml /tmp/audit-str/mut/
  export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/audit-str/mut/src
  mise exec -- uv run lint-imports --config /tmp/audit-str/mut/pyproject.toml        # 4 kept
  mkdir /tmp/audit-str/mut/src/agency/studio
  echo '"""New slice."""' > /tmp/audit-str/mut/src/agency/studio/__init__.py
  echo 'from agency.contracts import phase' > /tmp/audit-str/mut/src/agency/studio/exploration.py
  for f in insights/domain.py entrypoints/server/api.py evaluation/blind.py; do
    echo 'import agency.studio.exploration  # noqa' >> "/tmp/audit-str/mut/src/agency/$f"
  done
  mise exec -- uv run lint-imports --config /tmp/audit-str/mut/pyproject.toml        # still 4 kept
  mise exec -- uv run pytest -p no:cacheprovider \
    tests/test_server.py::test_every_engine_package_is_forbidden_to_import_django     # fails: 'studio'
  # add "agency.studio" to the Django contract's source_modules only: the test passes, 4 kept
  ```

- Fix: Extend the test at tests/test_server.py:417 so that the insights, server and evaluation contracts each forbid
  every package on disk except an explicit allow-list (`agency.contracts`, plus `agency.insights` for the server).
  Fix risk: Low.

### STR-003 · Low · Confirmed
- Where: src/agency/cli.py:15, src/agency/cli.py:112, src/agency/runtime.py:11-13, src/agency/runtime.py:126-127, src/agency/ledger/__init__.py:6, docs/adr/0021-monolite-modulare-a-slice.md:22, docs/01-ARCHITECTURE.md:97, docs/01-ARCHITECTURE.md:228-233
- Problem: ADR-0021:22 says import-linter "impone" `anthropic` only in the gateway, `langgraph` only in the process
  and `sqlmodel` only in the ledger, and 01-ARCHITECTURE.md:97 calls the gateway the only module that imports
  `anthropic` and knows the key. None of these rules has a contract, and three are already broken.
- Evidence:
  - `cli.py:15` imports `anthropic` only to catch `anthropic.APIError` (cli.py:112).
  - `runtime.py:11-13` imports `langgraph` and `langchain_core` outside `graph/`.
  - The key is unwrapped outside the gateway: `runtime.py:126-127` calls `get_secret_value()` on `config.Settings`.
  - SQLModel table classes leave the ledger. `agency.ledger.models` rows are imported by artifacts/keeping.py:18,
    gateway/client.py:15, graph/workflow.py:29, qa/evidence.py:12, telemetry/report.py:11, tools/master.py:10 and
    tools/surface.py:27. The `ledger.store` internals `now` and `BUSY_SECONDS` are imported by
    artifacts/keeping.py:19, cli.py:33, gateway/client.py:16, graph/workflow.py:30, qa/evidence.py:13, runtime.py:24
    and tools/master.py:11, although `agency.ledger.__all__` exports four names (ledger/__init__.py:6).
  - pyproject.toml:74-169 forbids `anthropic` and `langgraph` only to insights, the server and evaluation. Only
    01-ARCHITECTURE.md:226 says "le altre regole della tabella entrano con M1.7"; the ADR's present tense does not.
- Reproduce: `rg -n "^\s*(import|from) (anthropic|langgraph|langchain_core)\b" src/agency` lists cli.py:15 and
  runtime.py:11-13 next to the gateway and graph files; `mise exec -- uv run lint-imports` still reports 4 kept.
- Fix: Have `agency.gateway` export the error the CLI catches (a re-export or a wrapper of `APIError`), then add a
  forbidden contract on `anthropic` for every package except the gateway, with `allow_indirect_imports = true`.
  Leave `langgraph` and a port in front of the ledger to M1.7 item 5 (02-ROADMAP.md:411). Fix risk: Low.

### STR-004 · Low · Confirmed
- Where: src/agency/tools/surface.py:19, src/agency/tools/surface.py:28-29, src/agency/agents/loop.py:18-20, src/agency/qa/checks.py:10-12, src/agency/qa/delivery.py:20-22, src/agency/qa/evidence.py:14, src/agency/tools/sandbox.py:63
- Problem: `agents`, `tools` and `qa` form one strongly connected component at package level. This is the cycle
  ADR-0021 names and M1.7 item 1 plans to break (02-ROADMAP.md:407). It is not an import-time cycle, but it blocks
  the slice split, and one of the tools→qa edges is a filesystem path that no import tool sees.
- Evidence: grimp finds no module-level cycle. The only `agency` imports inside functions are cli.py:133, :156, :166
  and entrypoints/server/schema.py:24, and the only `TYPE_CHECKING` import is cli.py:37; none of them closes a cycle.
  The two mutual package edges are:
  - agents→tools (loop.py:18-20) against tools→agents (surface.py:19). The latter is used only for registry and
    prompt lookups: `prompts.skill_names`, `PROMPTS`, `can_open`, `ROLES` and `has_prompt` (surface.py:309-311,
    :481-485).
  - qa→tools (`files`, `sandbox`, `master`, `render`: checks.py:10-12, delivery.py:20-22, evidence.py:14) against
    tools→qa (surface.py:28-29).

  On top of that, `Sandbox.argv` mounts `Path(__file__).resolve().parents[1] / "qa/scripts"` (sandbox.py:63), a
  tools→qa dependency outside the import graph.
- Reproduce: from the worktree, `mise exec -- uv run python <file>` printed `module cycles: []` and
  `mutual package edges: [('agency.agents', 'agency.tools'), ('agency.qa', 'agency.tools')]`.

  ```python
  import grimp

  graph = grimp.build_graph("agency")
  mods = graph.modules
  cycles = [
      (a, b)
      for a in mods
      for b in graph.find_modules_directly_imported_by(a)
      if graph.chain_exists(importer=b, imported=a)
  ]
  print("module cycles:", cycles)
  top = {m: ".".join(m.split(".")[:2]) for m in mods}
  edges = {
      (top[a], top[b]) for a in mods for b in graph.find_modules_directly_imported_by(a) if top[a] != top[b]
  }
  print("mutual package edges:", sorted((a, b) for a, b in edges if (b, a) in edges and a < b))
  ```

- Fix: In the sanity refactor, remove only the tools→agents edge by moving the registry and prompt lookups into one
  module that both packages import (STR-005). Leave qa↔tools and the sandbox mount to M1.7 item 1; there, the owner of
  the QA scripts should pass their directory into `Sandbox`. Fix risk: Med.

### STR-005 · Low · Confirmed
- Where: src/agency/agents/prompts.py:10-14, src/agency/qa/evidence.py:16-20, src/agency/tools/surface.py:427, src/agency/tools/surface.py:437, src/agency/tools/surface.py:465-466, src/agency/qa/delivery.py:26, src/agency/tools/surface.py:862-869, src/agency/contracts/ticket.py:78
- Problem: The studio rules in `registry/` have no single owner and no schema. Two modules parse the JSON at import
  into `dict[str, dict]`, one of the two copies is dead, and code rebuilds the rule vocabulary (check kinds, which
  roles direct) from string literals and name suffixes. That goes against ADR-0021's "explicit over implicit" and
  CLAUDE.md's "le regole dello studio stanno in dati".
- Evidence:
  - `registry/roles.json` is loaded twice, at agents/prompts.py:11 and qa/evidence.py:19. Nothing reads
    `evidence.ROLES`: every reader uses `prompts.ROLES` (agents/loop.py:107, tools/surface.py:483).
  - Check kinds are bare strings compared in three modules: `"observation"` (surface.py:427), `"judgement"`
    (surface.py:437, delivery.py:26) and `"measure"` (evidence.py:20, :85), with the full set at surface.py:466.
    Nothing validates `kind` in `registry/checks.json`: tests/test_registry.py:26-30 checks only `roles`. A misspelt
    kind (`judgment` is the spelling used everywhere else, as in contracts/judgment.py) would silently drop the check
    from the "looked at" rules.
  - Role capabilities live in four places: model, effort and craft in roles.json, `can_open` in org.json,
    `REVIEWERS` in contracts/ticket.py:78, and the tool set chosen by name suffix with
    `role.endswith("-director") or role == "router"` (surface.py:863). `art-director` counts as a director by its
    suffix and gets `open_ticket`, but org.json has no `can_open` row for it, so every ticket it opened would be
    refused. This stays latent only because `prompts/roles/art-director.md` does not exist (`has_prompt`,
    prompts.py:25-27).
- Reproduce: `rg -n "\bROLES\b" src/agency`; `jq '.can_open | keys' registry/org.json` (no `art-director`);
  `jq '[.checks[].kind] | unique' registry/checks.json`.
- Fix: Add one module, proposed as `src/agency/registry.py`, that loads `registry/*.json` once into Pydantic models
  (with a `CheckKind` enum) and owns the prompt-library lookups now at agents/prompts.py:10-27 and :75-77, then delete
  the dead copy. Moving the suffix rule into roles.json changes data and therefore behaviour, so that is the owner's
  decision. Fix risk: Med (the request snapshots must stay byte-identical, and they would catch a drift).

### STR-006 · Low · Confirmed
- Where: src/agency/cli.py:227, src/agency/runtime.py:129, src/agency/runtime.py:76, src/agency/cli.py:90, src/agency/agents/loop.py:67, src/agency/graph/workflow.py:68, src/agency/evaluation/blind.py:60, src/agency/contracts/layout.py:1
- Problem: `DataLayout` presents itself as the single owner of where data sits in `.data/` (layout.py:1, pinned by
  tests/test_server.py:446), yet two `.data/` folders and the project's `work/` folder are built ad hoc. Any change to
  the layout must be repeated by hand at each site.
- Evidence: `settings.data_dir / "blind" / comparison` (cli.py:227) and `settings.data_dir / "craft-index"`
  (runtime.py:129) bypass `DataLayout`. `settings.project_dir(project) / "work"` is written four times (runtime.py:76,
  cli.py:90, agents/loop.py:67, graph/workflow.py:68), and blind.py:60 parses the same `work` segment back out of a
  path.
- Reproduce: `rg -n '"work"|"blind"|"craft-index"' src/agency`.
- Fix: Add `blind` and `craft_index` to `DataLayout`, one `Settings.work_dir(project)`, and a `WORK` constant in
  `contracts/layout.py` for blind.py (evaluation may not import config); then use them at the seven sites. Fix risk:
  Low.

### STR-007 · Low · Confirmed
- Where: src/agency/telemetry/__init__.py:1, src/agency/telemetry/report.py:1, src/agency/telemetry/report.py:8-11, src/agency/telemetry/fingerprint.py:1, src/agency/cli.py:34
- Problem: `agency.telemetry` describes itself as OpenTelemetry traces (`__init__.py:1`), but two of its three
  modules are not telemetry. `report.py` is the CLI's text renderer for the insights read models, and `fingerprint.py`
  computes a run's fingerprint. The renderer alone gives telemetry its dependency on insights.
- Evidence: report.py has no OpenTelemetry import, only `render*` functions over `ProjectReport`, `Provenance`,
  `RunRow`, `JudgmentRow` and `ArtifactRow` (report.py:8-11, :21-190). Its only caller in `src/` is cli.py:34; in
  tests, test_judgments.py:21 and test_hardening.py:29. The grimp package edge `agency.telemetry → agency.insights`
  comes only from report.py:8-9. fingerprint.py's only caller is runtime.py:26 and :60.
- Reproduce: `rg -n "opentelemetry" src/agency/telemetry` (only setup.py); `rg -n "telemetry import" src tests`.
- Fix: Move `telemetry/report.py` next to its only caller as `src/agency/cli/render.py`, turning `cli.py` into
  `src/agency/cli/__init__.py`; `agency.cli:main` and `from agency import cli` keep working. Alternatively, defer the
  move to M1.7, when the CLI goes to `entrypoints/cli/`. `fingerprint.py` waits for M1.7's `platform/`. Fix risk: Low.

### STR-008 · Low · Likely
- Where: src/agency/config.py:12, src/agency/agents/prompts.py:10-14, src/agency/qa/evidence.py:16-19, src/agency/telemetry/fingerprint.py:59, src/agency/telemetry/fingerprint.py:70-73, pyproject.toml:45-46, docker/server.Dockerfile:18
- Problem: The engine finds `prompts/`, `registry/`, `src/agency` and `uv.lock` through
  `REPO_ROOT = Path(__file__).resolve().parents[2]`. That is the repo root only for an editable install from a
  checkout. The wheel holds only `src/agency`, so a non-editable install computes a wrong root and the engine fails
  at import.
- Evidence: hatch packages only `src/agency` (pyproject.toml:45-46). The API image already installs non-editable
  (`uv sync --no-editable`, server.Dockerfile:18). There, `config.py` sits in
  `/app/.venv/lib/python3.13/site-packages/agency/`, so `parents[2]` is `/app/.venv/lib/python3.13`, which has no
  `registry/roles.json`. Yet `agency.agents.prompts` and `agency.qa.evidence` read that file at module import
  (prompts.py:11, evidence.py:16-19). The server survives only because import-linter forbids it `agency.config` and
  the engine (pyproject.toml:121-143).
- Reproduce: a non-editable install was not run. `python3 -c "from pathlib import Path;
  print(Path('/app/.venv/lib/python3.13/site-packages/agency/config.py').resolve().parents[2])"` prints
  `/app/.venv/lib/python3.13`, the root the image would compute.
- Fix: Keep the engine checkout-only, as ADR-0040 already keeps it on the host, but say so in code: the registry
  module of STR-005 resolves the root once and fails with a clear message when `registry/` is missing. Shipping
  prompts and registry as package data would change the `Fingerprint` keys (`prompts/…`, `registry/…`) and break
  comparisons with earlier runs. Fix risk: Low.

### STR-009 · Low · Confirmed
- Where: src/agency/insights/adapters/registry.py:1, src/agency/insights/ports.py:30, src/agency/insights/ports.py:77, src/agency/insights/application.py:33, src/agency/contracts/run.py:32, src/agency/telemetry/fingerprint.py:71
- Problem: In code, "registry" names two different things, and the ledger has two names. The engine calls the SQLite
  log `Ledger` (`agency.ledger`). Insights calls the same file `Registry` (`RegistryReader`, `RegistrySnapshot`,
  `ReadOnlyRegistry`, `RegistryNotReadable`, `adapters/registry.py`). Meanwhile `Fingerprint.registry` and the
  `registry/` folder mean the studio rules JSON. A reader of insights cannot tell which one is meant, and the module
  proposed in STR-005 would collide.
- Evidence: adapters/registry.py:1 ("Il registro in sola lettura… mai `Ledger()`") reads `ledger.sqlite` through
  `DataLayout.ledger`. contracts/run.py:32 describes `registry` as the "sha256 di ogni file in registry/", and
  fingerprint.py:71 hashes `_hashes(root, "registry")`. The OpenAPI exposes `Provenance.from_registry` and
  `Provenance.registry_revision` (schemas/openapi.json).
- Reproduce: `rg -n -i "registry" src/agency --glob '!**/qa/scripts/**'`.
- Fix: Rename the insights-side identifiers and the module to `Ledger*` and `adapters/ledger.py` before adding a
  `registry` module. Keep the two OpenAPI field names, since renaming them is a schema change that regenerates
  `schemas/openapi.json` and `web/src/api/schema.ts` (ADR-0032), and keep `Fingerprint.registry`, which historical
  `runs` rows store. Fix risk: Med.

### STR-010 · Low · Confirmed
- Where: .gitignore:10-11, web/src/app/projects/[name]/page.tsx:1, tests/test_repository.py:3-5
- Problem: The dashboard route folder `web/src/app/projects/` has the same name as the client-materials folder,
  which `.gitignore` excludes at any depth. The collision already hid the dashboard pages from a commit on
  2026-11-03, and the fix now depends on a negation rule that some tools do not honour.
- Evidence: the unanchored `projects/` (.gitignore:10) is reopened only by `!/web/src/app/projects/` (.gitignore:11).
  tests/test_repository.py:3-5 records the incident, and :33-56 now guard both directions. tokei 13 still skips the
  six route files (965 lines) when it follows `.gitignore` (00-baseline.md §4).
- Reproduce: `git check-ignore -v --no-index "web/src/app/projects/[name]/page.tsx" projects/x web/projects/x`
  reports only the last two as ignored, by `.gitignore:10`.
- Fix: No move. Renaming the route would change URLs fixed in ADR-0038:26 and needs a new ADR, and anchoring the
  rule would drop the "ovunque stiano" protection that test_repository.py:43-56 asserts. Keep the guard and count
  sizes with `--no-ignore`. Fix risk: Low.

### STR-011 · Low · Confirmed
- Where: src/agency/config.py:26, src/agency/entrypoints/server/serve.py:18-20, web/package.json:11-14, web/playwright.config.ts:10-15, web/next.config.mjs:7, web/src/api/client.ts:13, docker/web.Dockerfile:17, docker/web.Dockerfile:25, .python-version:1, pyproject.toml:6, docker/server.Dockerfile:4, src/agency/doctor.py:12-25, src/agency/telemetry/fingerprint.py:20
- Problem: The 19 tool-config files are each the idiomatic one for their tool, with no redundant configs. Several
  values, though, are copied between them with no single owner and no guard, so a change in one place silently
  leaves the others behind.
- Evidence: these copies are not tied by any test:
  - API key variable names: config.py:26, serve.py:19, web/package.json:11, :12, :13, :17,
    web/playwright.config.ts:13, :15 and web/scripts/check-defenses.mjs:43 (doctor.py:55 checks only the first
    name). A third alias added to config.py would be accepted by the engine, but neither scrubbed by the server nor
    removed by `env -u` in the web scripts.
  - e2e Django port 18765: web/package.json:14 (baked into the rewrites at build time, next.config.mjs:6-7) and
    web/playwright.config.ts:10, :31. e2e build folder `.next-e2e`: package.json:14, playwright.config.ts:41, :50,
    tsconfig.json:40-41 and .gitignore:23.
  - Django origin `http://127.0.0.1:8000`: next.config.mjs:7, client.ts:13 and web.Dockerfile:17, :25, plus the
    port in serve.py:20, server.Dockerfile:26 and compose.yaml:43. Next.js port 3000: package.json:11, :13,
    web.Dockerfile:25 and compose.yaml:41.
  - Python: `>=3.13` (pyproject.toml:6), `3.13` (.python-version:1), `3.13.15` (server.Dockerfile:4).
    test_docker.py:116-119 compares only the major and minor version. mise.toml:2 and test_toolchain.py:35 say
    pyproject.toml chooses Python (as does ADR-0034:12), but uv reads `.python-version` first when it exists.
  - Machine CLIs are listed in doctor.py:12-25 and fingerprint.py:20 (and docs/04-TOOLS.md).
    `SETTINGS = "agency.entrypoints.server.settings"` appears in serve.py:18 and schema.py:14, and the lint
    exclusions in pyproject.toml:55 and :63.
  - Already guarded, and healthy: the node, pnpm and uv pins (test_toolchain.py:25-31, test_docker.py:113-124) and
    the two host allow-lists (test_server.py:314, web/src/loopback.test.ts:6).
- Reproduce: `rg -n "AGENCY_ANTHROPIC_API_KEY|18765|\.next-e2e|127\.0\.0\.1:8000" --glob '!legacy/**' --glob '!docs/**'`.
- Fix: Put the key names in `agency.contracts`, which the server may import, use them in config.py and serve.py, and
  add one check that the web copies and the e2e port and folder agree. Correct the Python-owner sentence in
  mise.toml:2 and the test docstring; the ADR stays as written. Fix risk: Low.

### STR-012 · Low · Likely
- Where: spikes/sandbox_craft.sh:9-11, src/agency/tools/sandbox.py:11, src/agency/tools/sandbox.py:32-69, docs/04-TOOLS.md:17, docs/adr/0005-sandbox-bwrap.md:9
- Problem: The only check that the five Craft tools run under bwrap builds its own bwrap command, and that command
  differs from the sandbox the engine uses. ADR-0005's verification therefore no longer covers the real `Sandbox`.
- Evidence: the spike binds all of `/etc` and has no `--clearenv`, `--unshare-ipc`, `--tmpfs /home`, `HOME`/`PATH`
  settings or QA mount (sandbox_craft.sh:9-11). `Sandbox.argv` binds only `ETC_ALLOWED` and clears the environment
  (sandbox.py:11, :32-69). pytest runs the real `Sandbox` only with `python3` (tests/test_agent_flow.py:441-455), and
  figcraft, photocraft, effectcraft and Blender never run in it in any test. docs/04-TOOLS.md:17 cites the spike in
  the present tense.
- Reproduce: compare the two argument lists; `rg -n "figcraft-cli|photocraft-cli|effectcraft-cli|blender" tests` finds
  only the fingerprint test (tests/test_runs.py:208-211).
- Fix: Build the spike's bwrap prefix from `Sandbox(work).argv([])` through `uv run python -c …`, or turn the spike
  into a pytest that skips when the CLIs are missing. Keep it out of `make check` either way. Fix risk: Low.

### STR-013 · Low · Confirmed
- Where: src/agency/tools/surface.py:1, tests/test_sketch_flow.py:1, tests/test_insights.py:1, tests/test_agent_flow.py:1, tests/test_hardening.py:1, web/src/app/globals.css:1
- Problem: Six hand-written files are over ~500 lines. `tools/surface.py` is the one with a structural cost: it holds
  every phase's tools, the tool sets per role and the `Toolbox`, and it keeps growing although ADR-0021 marked it for
  splitting.
- Evidence (`wc -l`): surface.py 968 lines (940 at 51c511c, the ADR-0021 commit, with two commits since);
  test_sketch_flow.py 1,168 (56 tests); test_insights.py 880 (38); test_agent_flow.py 658 (25); test_hardening.py
  656 (36); globals.css 622 (the styles of every view in one sheet). The generated files over 500 lines (schema.ts
  1,415, tests/snapshots/requests/design-director.json 516) are out of scope. Next in size: ledger/store.py 472,
  graph/workflow.py 456, insights/domain.py 447.
- Reproduce: `git ls-files src tests web | grep -v pnpm-lock | xargs wc -l | sort -rn | head -12`.
- Fix: Nothing in the sanity refactor. surface.py is M1.7 item 2 (02-ROADMAP.md:408) and must keep the request
  snapshots byte-identical; split the flow tests by slice along with it (item 6). Fix risk: Med.

### STR-014 · Low · Likely
- Where: src/agency/qa/scripts/logo_proof.py:1, src/agency/qa/scripts/optical_check.py:1, src/agency/qa/scripts/svg_audit.py:1, src/agency/qa/scripts/svg_parity.py:1, pyproject.toml:55, pyproject.toml:63, src/agency/tools/sandbox.py:51
- Problem: The four QA scripts are byte-identical copies of the legacy originals and are treated as vendored (excluded
  from ruff and pyright), but no test keeps them identical. Unlike the legacy originals, whose hashes are pinned, an
  edit to these copies would pass `make check` unnoticed.
- Evidence: each copy's sha256 matches its legacy original (logo_proof `0d7fe4e5…`, optical_check `6340cbab…`,
  svg_audit `2fdbffa5…`, svg_parity `457a586c…`). `MANIFEST.sha256` covers only `legacy/` (tests/test_registry.py:10-15),
  and `rg -n "qa/scripts" tests` finds nothing. The engine depends on their legacy behaviour: the sandbox sets
  `CLAUDE_PROJECT_DIR=/tmp` (sandbox.py:51) for the legacy root lookup at logo_proof.py:109.
- Reproduce: `for f in logo_proof optical_check svg_audit svg_parity; do sha256sum src/agency/qa/scripts/$f.py
  legacy/claude-code-v1/src/.claude/skills/*/scripts/$f.py; done`.
- Fix: Add a test next to `test_legacy_backup_is_frozen` that compares each copy with its legacy original, so that
  any divergence becomes a visible decision. Fix risk: Low.

### STR-015 · Nit · Confirmed
- Where: web/src/components/project-header.tsx:6-7, src/agency/entrypoints/server/api.py:95-114, tests/test_report_views.py:1, docker/compose.yaml:16, docker/server.Dockerfile:1, registry/checks.json:17
- Problem: Each dashboard view carries up to four names, and a few component and module names collide, so finding the
  code behind a view or a container by name takes a lookup.
- Evidence:

  | View (label) | Page | e2e | API route · operationId | Read model · module | pytest |
  |---|---|---|---|---|---|
  | Run | `/projects/[name]` | `run.spec.ts` | `/report` · `projectReport` | `ProjectReport` · `views.py` | `test_report_views.py` |
  | Fasi | `/phases` | `phases.spec.ts` | `/flow` · `projectFlow` | `FlowReport` · `flow.py` | `test_flow_view.py` |
  | Modello | `/model` | `model.spec.ts` | `/behaviour` · `projectBehaviour` | `BehaviourReport` · `behaviour.py` | `test_behaviour_view.py` |

  The Django component is called `server` (`server.Dockerfile`, `agency-server`, `entrypoints/server`) and `api`
  (Compose service `api`, image `dashboard-api`, `task dashboard:api`). Two modules are called `board.py` (the
  critic's anonymous board in `tools/`, the blind-judgment board in `evaluation/`) and two `files.py` (`artifacts/`,
  `tools/`). The check kind is spelt `judgement` (registry/checks.json:17), while the blind judgment is `judgment`
  everywhere (contracts/judgment.py).
- Reproduce: `ls web/src/app/projects/[name] web/e2e src/agency/insights tests`.
- Fix: No renames: the routes and operationIds are fixed by ADR-0035–0038 and pinned by tests/test_schemas.py:172-185,
  so renaming them needs a new ADR. A single mapping table in docs/01-ARCHITECTURE.md ("Cruscotto e server") is
  enough. Fix risk: Low.

### STR-016 · Nit · Confirmed
- Where: tests/drawings.py:1, tests/test_board.py:18, tests/test_judgments.py:22, tests/dashboard_fixture.py:1, web/playwright.config.ts:30, tests/test_hardening.py:1, pyproject.toml:66-68
- Problem: Test helpers sit next to the test modules and are imported as top-level modules, which works only because
  of pytest's default `prepend` import mode. One 656-line file groups its tests by when the defects were found, not
  by slice.
- Evidence: `from drawings import …` (test_board.py:18, test_judgments.py:22), with no `pythonpath` or import mode set
  in pyproject.toml:66-68. `tests/dashboard_fixture.py` is not a test but a data generator that Playwright runs from
  `web/` as `../tests/dashboard_fixture.py` (playwright.config.ts:30). test_hardening.py:1 ("Difetti trovati
  rileggendo il sistema prima di M2") imports from nine packages (lines 16-32), so M1.7 cannot move its tests along
  with their slices.
- Reproduce: `PYTHONDONTWRITEBYTECODE=1 mise exec -- uv run pytest -p no:cacheprovider --import-mode=importlib
  --collect-only -q tests/test_board.py tests/test_judgments.py` fails with `ModuleNotFoundError: No module named
  'drawings'`.
- Fix: Optional: move the helpers to `tests/support/`, set `pythonpath = ["tests"]` and update
  playwright.config.ts:30; split test_hardening.py by slice in M1.7 item 6. Fix risk: Low.

### STR-017 · Nit · Confirmed
- Where: src/agency/context/__init__.py:1, pyproject.toml:106, pyproject.toml:154, README.md:69-76, docs/adr/README.md:24, prompts/roles/director-plan.md:1, src/agency/contracts/phase.py:1
- Problem: A few small layout leftovers: an empty placeholder package that two contracts must list, a README tree
  that leaves out half the top-level folders, a non-ASCII ADR file name, and `prompts/roles/` holding phase prompts.
- Evidence: `agency.context` is a one-line docstring package (context/__init__.py:1), yet it is listed at
  pyproject.toml:106 and :154 and required by tests/test_server.py:417. README.md:69-76 lists `src/agency`,
  `registry`, `docs`, `tests`, `spikes` and `legacy`, but not `web/`, `schemas/`, `prompts/`, `docker/` or `evals/`.
  `git ls-files` prints ADR-0017's name escaped (`ci\303\262`). `prompts/roles/` keeps phase prompts
  (`director-plan`, `director-select`, `director-present`, `critic-board`, `explorer`, `proposer`, `finisher`; see
  `phase.of`, contracts/phase.py:1, :27-29) next to the role prompts.
- Reproduce: `git ls-files prompts/roles docs/adr | head -20`.
- Fix: Update the README tree and leave the rest. ADR files are frozen. Renaming `prompts/roles/` would change every
  `Fingerprint.prompts` key, so every comparison with an earlier run would show all prompts as changed. `context/` can
  go when M3 decides where context packets live. Fix risk: Low.

## Current tree

Tracked files at `86f51a1`, collapsed (line counts in parentheses where they matter).

```text
.
├── .env.example  .gitignore  .python-version  CLAUDE.md  Makefile  README.md
├── Taskfile.yml  mise.toml  pyproject.toml  uv.lock
├── docker/        compose.yaml, server.Dockerfile (+ .dockerignore), web.Dockerfile (+ .dockerignore)
├── docs/          00-PROJECT … 07-EVALS, PARITY.md, audit/00-baseline.md, adr/ (43 ADRs + README)
├── evals/         briefs/E1.md
├── legacy/        frozen Claude Code v1 backup (151 files, never edited)
├── prompts/       common.md, org/ (4), roles/ (11 role and phase prompts), skills/ (3 skills, 5 files)
├── registry/      checks.json, org.json, roles.json
├── schemas/       openapi.json (generated)
├── spikes/        sandbox_craft.sh
├── src/agency/
│   ├── __init__.py  cli.py (367)  config.py  doctor.py  runtime.py
│   ├── agents/        loop.py, prompts.py, transcript.py
│   ├── artifacts/     files.py, keeping.py
│   ├── context/       __init__.py only (placeholder)
│   ├── contracts/     artifact, concept, gate, judgment, layout, outcome, phase, run, ticket
│   ├── entrypoints/
│   │   └── server/    __main__, api, middleware, schema, serve, settings, urls
│   ├── evaluation/    blind.py, board.py
│   ├── gateway/       client.py, pricing.py, transport.py
│   ├── graph/         workflow.py (456)
│   ├── insights/      domain (447), ports, application, views, flow, behaviour, quality, compare, replay, sums
│   │   └── adapters/  projection, registry, stamps, traces, transcripts
│   ├── ledger/        chain, models, schema, store (472), migrations/ (env.py, versions/0001…0005)
│   ├── qa/            checks, delivery, evidence, scripts/ (4 vendored)
│   ├── telemetry/     setup.py, fingerprint.py, report.py
│   └── tools/         board, craft, files, master, presentation, render, sandbox, surface (968)
├── tests/
│   ├── conftest.py  dashboard_fixture.py  drawings.py  test_*.py (27)
│   ├── fixtures/      ledger_schema_0001.sql
│   └── snapshots/     requests/*.json (11, generated)
└── web/
    ├── package.json  pnpm-lock.yaml  pnpm-workspace.yaml  tsconfig.json  next.config.mjs  playwright.config.ts
    ├── e2e/           canary.ts, project.ts, 6 *.spec.ts
    ├── scripts/       check-defenses.mjs, standalone.mjs
    └── src/
        ├── proxy.ts  loopback.ts  chart.ts  format.ts  labels.ts  timescale.ts  (+ 5 *.test.ts)
        ├── api/         client.ts, index.ts, read.ts, schema.ts (generated)
        ├── app/         layout.tsx, page.tsx, not-found.tsx, globals.css (622), compare/page.tsx (418),
        │                projects/[name]/{page.tsx, model/, phases/, quality/, replay/, replay/[instance]/}
        └── components/  context-chart, project-header, said, setbacks, timeline, unavailable
```

## Proposed target tree

The smallest change set that fixes the findings above. Everything not shown stays where it is. Most fixes (STR-001,
002, 003, 006, 011, 012, 014) are code, config or test changes and move no files.

```text
src/agency/
├── registry.py                 NEW: the only reader of registry/*.json and of the prompts/ library (STR-005, STR-004)
├── cli/                        was cli.py (optional, STR-007)
│   ├── __init__.py             main() and the 14 subcommands, unchanged
│   └── render.py               was telemetry/report.py
├── telemetry/                  setup.py, fingerprint.py
├── agents/prompts.py           keeps system_prompt() and packet(); its lookups come from agency.registry
├── qa/evidence.py              CHECKS come from agency.registry; the dead ROLES copy is gone
├── tools/surface.py            imports agency.registry, no longer agency.agents (tools→agents edge removed)
├── contracts/layout.py         gains blind, craft_index and WORK (STR-006)
├── insights/adapters/ledger.py was adapters/registry.py; Registry* → Ledger* (STR-009)
└── (everything else unchanged)
```

| From → to | Reason | Risk | ADR impact | When |
|---|---|---|---|---|
| `agents/prompts.py:10-27,75-77` + `qa/evidence.py:16-20` → new `src/agency/registry.py` | STR-005 (one owner, a schema, no dead copy); STR-004 (removes tools→agents) | Med: six import sites in `src/`; the request snapshots must stay byte-identical; `agency.registry` must join the four contract lists (the test at test_server.py:417 forces the Django one) | None. ADR-0021's target would place it in `shared/` at M1.7 | sanity, after the next row |
| `insights/adapters/registry.py` → `insights/adapters/ledger.py`, `Registry*` → `Ledger*` | STR-009 | Med: insights, cli.py:27, api.py:15, conftest.py:14 and about eight tests; `schemas/openapi.json` must stay byte-identical (`test_schemas.py`) | None if `from_registry` and `registry_revision` keep their names; renaming those follows ADR-0032 (schema and types regenerated in the same commit) | sanity, first |
| `cli.py` → `cli/__init__.py`; `telemetry/report.py` → `cli/render.py` | STR-007 | Low: the `agency.cli:main` entry point and `from agency import cli` are unchanged; two tests change one import | None. 01-ARCHITECTURE puts the CLI in `entrypoints/cli/` at M1.7 | sanity, optional |
| `tests/drawings.py`, `tests/dashboard_fixture.py` → `tests/support/`, plus `pythonpath = ["tests"]` | STR-016 | Low: two test imports and playwright.config.ts:30 | None | optional |

**Not moved, on purpose.**
- The never-edit paths of baseline §1.7: `legacy/`, `ledger/migrations/versions/`, `schemas/openapi.json`,
  `web/src/api/schema.ts`, `tests/snapshots/`, `tests/fixtures/`, `src/agency/qa/scripts/` and the lockfiles.
- The `registry/` and `prompts/` folder names: they are `Fingerprint` keys stored in historical `runs` rows.
- `web/src/app/projects/` and the API routes and operationIds: URLs and names fixed by ADR-0035–0038 and
  tests/test_schemas.py:172-185. Renaming them needs a new ADR.
- `docs/adr/` file names (frozen).

**Deferred to M1.7.** These are already planned in 02-ROADMAP.md:407-413 and ADR-0021, and the sanity refactor
should not start them:
- split `tools/surface.py`;
- move `graph/workflow.py` into `process/`;
- move `cli/` into `entrypoints/cli/`;
- move `tools/{files,sandbox}.py` and `telemetry/fingerprint.py` into `platform/`;
- put the ledger behind a port, so rows stop leaving `ledger/`;
- pass the QA scripts directory into `Sandbox` (this breaks qa↔tools);
- make `import-linter` blocking on the library table.

**Would need a new ADR.** Renaming `AGENCY_DATA` (ADR-0040) or letting the dashboard read `.env` (ADR-0031,
ADR-0039) while fixing STR-001; renaming any route, operationId or view (ADR-0035–0038).
