SIM at 86f51a1: the code is lean for its scope; complexity sits in graph/workflow.py and tools/surface.py, which ADR-0021 already schedules for M1.7, and no TypeScript function is complex.
Dead code is a handful of bootstrap leftovers and five never-supplied parameters; removing the leftovers and four of the parameters in a scratch copy kept ruff, pyright and pytest green. One runtime dependency, the three extras and three undeclared transitive imports need an owner decision.
One duplication has already diverged into a crash path (SIM-001). The 23-commit, 53-hour history has no fix commits, so no complexity is shown to be producing bugs.
Critical 0 · High 0 · Medium 1 · Low 12 · Nit 4
After review (SUMMARY.md): Critical 0 · High 0 · Medium 0 · Low 12 · Nit 4 (SIM-013 merged into STR-006)

# 70 — Simplification (SIM)

Scope: dead code, unused dependencies, duplication, needless abstraction, the most complex functions and churn. Read-only:
every script ran from `/tmp/audit-sim/`, and the only file written in the repository is this report. Findings marked
"preference" are style choices, not defects.

## Findings

### SIM-001 · Medium · Confirmed
- Where: src/agency/telemetry/report.py:108, src/agency/telemetry/report.py:112, src/agency/telemetry/report.py:132, src/agency/insights/compare.py:132, src/agency/cli.py:361
- Problem: The run fingerprint is parsed by two copies of the same helper, and they already disagree. The dashboard copy treats a fingerprint of an unknown shape as "not readable"; the CLI copy raises, so `agency runs` and `agency compare` would end in a pydantic traceback on a registry the dashboard renders fine.
- Evidence: insights/compare.py:132-136 wraps `Fingerprint.model_validate_json` in `except ValidationError: return None`, and tests/test_compare_view.py:240 covers exactly this case ("un'impronta di una forma che il contratto non conosce più"). telemetry/report.py:108-109 calls `Fingerprint.model_validate_json` bare, from `render_runs` (:119) and `render_comparison` (:133). `Fingerprint` (contracts/run.py:20-36) is `extra="forbid"` with every field required, so any change to the contract makes rows of the other shape fail. `cli.main` (cli.py:359-363) catches only `LedgerOutdated`, `LedgerMismatch`, `ChainBroken` and `RegistryNotReadable`. ADR-0030 moved `agency report` onto insights to avoid parallel calculations; `runs` and `compare` stayed on `Ledger` with their own parser.
- Reproduce: from the repo root, `PYTHONDONTWRITEBYTECODE=1 mise exec -- uv run python /tmp/audit-sim/repro_runs.py`, which prints `render_runs raised ValidationError: 9 validation errors for Fingerprint`. The script writes only to a temporary folder:

  ```text
  import json, tempfile
  from pathlib import Path
  from sqlmodel import Session
  from agency.ledger import Ledger
  from agency.ledger.models import RunRow
  from agency.telemetry import report

  with tempfile.TemporaryDirectory(dir="/tmp/audit-sim") as scratch:
      ledger = Ledger(Path(scratch) / "ledger.sqlite")
      old_form = {"model": "", "effort": "", "explorer_effort": "high"}  # a shape this version does not know
      with Session(ledger.engine) as session:
          session.add(RunRow(at="2026-11-01T00:00:00+00:00", project="p", command="run",
                             digest="0" * 64, fingerprint_json=json.dumps(old_form)))
          session.commit()
      try:
          print(report.render_runs(ledger, "p"))
      except Exception as exc:
          print(f"render_runs raised {type(exc).__name__}: {str(exc).splitlines()[0]}")
  ```

  Today every stored fingerprint has the same shape (contracts/run.py has a single commit, b0dad7f), so this fires the first time the contract changes.
- Fix: Keep one tolerant reader next to `Fingerprint` in contracts/run.py (returns `None` on `ValidationError`) and use it from both places, with the CLI renderers labelling or skipping an unreadable run instead of raising; or route `agency runs`/`agency compare` through insights, as ADR-0030 did for `report`. Fix risk: Low.
- Review (SUMMARY.md): Downgraded to Low. Latent: `contracts/run.py` has one commit, so every stored fingerprint has the current shape. Effort: S.

### SIM-002 · Low · Confirmed
- Where: pyproject.toml:15, src/agency/telemetry/setup.py:41, docker/server.Dockerfile:16, docker/server.Dockerfile:18
- Problem: `opentelemetry-exporter-otlp-proto-http` is a runtime dependency that no code imports. The only span exporter is the project's own `JsonlExporter`, yet the package adds seven installed packages to every environment, including the dashboard API image.
- Evidence: `rg -n -i 'otlp|exporter' --glob '!legacy/**' --glob '!uv.lock' .` finds only pyproject.toml:15, the baseline doc, and `JsonlExporter`/`SpanExporter` in telemetry/setup.py. `uv tree --frozen --no-dev --invert --package …` shows that, in the default install, these exist only because of it: googleapis-common-protos, protobuf, opentelemetry-proto, opentelemetry-exporter-otlp-proto-common, opentelemetry-exporter-otlp-common and opentelemetry-exporter-http-transport. All six, plus the exporter itself, are installed in `.venv`. server.Dockerfile:16 and :18 run `uv sync --frozen --no-dev`, so the image ships them too. The `telemetry` extra (`langfuse`, pyproject.toml:25) already depends on the exporter, so Langfuse in M4 brings it back by itself.
- Reproduce: `mise exec -- uv tree --frozen --package opentelemetry-exporter-otlp-proto-http`; `mise exec -- uv tree --frozen --no-dev --invert --package protobuf`; `ls .venv/lib/python3.13/site-packages | rg -i '^(googleapis|protobuf|opentelemetry_proto|opentelemetry_exporter)'`.
- Fix: `uv remove opentelemetry-exporter-otlp-proto-http`, once the owner confirms no OTLP export is wanted before M4. Fix risk: Low.

### SIM-003 · Low · Confirmed
- Where: pyproject.toml:23, pyproject.toml:24, pyproject.toml:25, src/agency/context/__init__.py:1
- Problem: The extras `context`, `qa` and `telemetry` are declared and locked, but nothing imports any of their packages, and `agency.context` is a one-line docstring. They add 56 packages to the lock that every `uv lock` must resolve under the `exclude-newer` quarantine: torch, triton, 15 `nvidia-*` wheels, transformers, lancedb, pyarrow, langfuse, trimesh, openimageio and others. `context` also repeats `pillow`, which is already a runtime dependency (pyproject.toml:16).
- Evidence: `rg -n -i 'lancedb|transformers|\btorch\b|trimesh|openimageio|langfuse' --glob '!legacy/**' --glob '!uv.lock' --glob '!docs/**' .` finds only pyproject.toml:23-25 and the doctor label "Langfuse e ComfyUI" (doctor.py:23). `uv export --frozen --no-hashes --no-dev` lists 68 packages, and 124 with `--all-extras`. Baseline §1.6: none of them is installed. docs/04-TOOLS.md places LanceDB, trimesh and OpenImageIO in M3 and Langfuse in M4.
- Reproduce: the `rg` above; `mise exec -- uv export --frozen --no-hashes --no-header --no-annotate --no-emit-project --no-dev -o /tmp/audit-sim/exp-runtime.txt`, then the same with `--all-extras`, then count the package lines in each.
- Fix: Owner decision. Either drop each extra until the milestone that first imports it (`uv remove --optional context lancedb transformers torch pillow`, and so on), or keep them and drop only the duplicate `pillow` from `context`. Fix risk: Low.

### SIM-004 · Low · Confirmed
- Where: src/agency/runtime.py:11, src/agency/ledger/store.py:14, src/agency/ledger/models.py:5, src/agency/ledger/schema.py:21, tests/test_ledger.py:5, tests/test_gateway.py:7, tests/test_hardening.py:13
- Problem: Code imports three packages that pyproject.toml does not declare: `langchain_core`, `sqlalchemy` and, in tests, `httpx2`. They resolve only through other packages' requirements, so an upstream release that drops or re-pins them would break these imports with no change here.
- Evidence: /tmp/audit-sim/thirdparty.py maps every top-level import in src/ and tests/ to its distribution through `importlib.metadata.packages_distributions()`; every other import maps to a declared dependency (the vendored qa/scripts run in the toolchain Python, not this venv). `uv tree --frozen --no-dev --invert --depth 1` shows sqlalchemy ← alembic, sqlmodel; langchain-core ← langgraph, langgraph-checkpoint, langgraph-prebuilt, langgraph-sdk; httpx2 ← anthropic. runtime.py uses `RunnableConfig` only as the return annotation of `Session._config` (runtime.py:49). The import-linter contracts already list `sqlalchemy` as a forbidden module, so the project treats it as a direct dependency.
- Reproduce: `rg -n 'httpx2|langchain_core|^from sqlalchemy' src tests`, then compare with `[project].dependencies` and `[dependency-groups].dev` in pyproject.toml.
- Fix: `uv add sqlalchemy langchain-core` and `uv add --dev httpx2`, with lower bounds at the locked versions. Fix risk: Low.
- Duplicate: the `langchain_core` import is also tracked under STR-003; removing it closes both.

### SIM-005 · Low · Confirmed
- Where: src/agency/graph/workflow.py:38, src/agency/tools/render.py:74, src/agency/tools/render.py:92, src/agency/ledger/store.py:297, src/agency/qa/evidence.py:19
- Problem: Four module-level definitions have had no caller since the bootstrap commit 51c511c:
  - `SKETCH_CHECKS`. Its literal is retyped at tools/surface.py:610, so the dead constant also misleads about where the sketch checks are defined.
  - `contact_sheet`, which is also exported in `__all__`.
  - `Ledger.render_of`. Its live sibling is `renders_of` (store.py:311).
  - `qa.evidence.ROLES`, a second loader of registry/roles.json besides `agents.prompts.ROLES` (prompts.py:11). This is a second owner for the same data.
- Evidence: two AST scans over src/ and tests/ (/tmp/audit-sim/refs.py, then the import-aware /tmp/audit-sim/imports.py) followed by `rg -w`: each name appears only at its definition, plus `__all__` for `contact_sheet`. `git grep -n -e SKETCH_CHECKS -e render_of -e contact_sheet 51c511c -- src tests` shows the same state at bootstrap. Dynamic uses were ruled out: console scripts, Django settings and URLconf, Alembic, registry/*.json names, the tool table in surface.py, getattr and importlib, tests, and web/e2e.
  Scratch-copy check, shared with SIM-006 and SIM-007. The 427 tracked files were copied to /tmp/audit-sim/copy and run with the worktree's `.venv` and `PYTHONPATH=/tmp/audit-sim/copy/src` (`agency.__file__` resolved into the copy).
  - Before: ruff "All checks passed!", pyright "0 errors, 0 warnings", pytest "481 passed, 2 skipped". tests/test_docker.py and tests/test_taskfile.py were excluded because they need Docker and a git checkout.
  - After deleting every item of SIM-005, SIM-006 (`RecordingTransport`, `from_cassette`) and SIM-007 (`read_only`, `stdin`, `inputs_changed`, `ticket_id`): the same three results. `ruff format --check` only asked to re-join the shortened `subprocess.run(...)` call in sandbox.py.
- Reproduce: `rg -n -w -e SKETCH_CHECKS -e contact_sheet -e render_of --glob '!legacy/**' .` and `rg -n 'evidence\.ROLES' src tests` (no hits). Mutation script: /tmp/audit-sim/mutate.py; copy script: /tmp/audit-sim/make_copy.py.
- Fix: Delete the four definitions, `"contact_sheet"` in `__all__`, and the `ImageDraw` and `Path` imports in render.py that then become unused. Fix risk: Low.
- Duplicate: the `qa.evidence.ROLES` item is tracked under STR-005; the other three definitions stay here.

### SIM-006 · Low · Confirmed
- Where: src/agency/gateway/transport.py:56, src/agency/gateway/transport.py:74, src/agency/gateway/transport.py:79, src/agency/gateway/__init__.py:4
- Problem: The record-and-replay pair `RecordingTransport` and `ScriptedTransport.from_cassette` was never wired: no command records a cassette and no test replays one. `ScriptedTransport` is test-only code in src/ with no production caller; it is used by tests/test_agent_flow.py, tests/test_gateway.py and tests/test_hardening.py.
- Evidence: `RecordingTransport` appears only at its definition and in the `agency.gateway` re-export (`__init__.py:4`, `:13`). `from_cassette` appears only at its definition. In src/, `ScriptedTransport` appears only in transport.py and the re-export. `open_session` (runtime.py:121-127) either builds `AnthropicTransport` or takes the caller's transport, with no recording option. The tests script responses by hand with `turn(...)` builders, not cassettes. All of this is unchanged since 51c511c. Deleting the pair kept the scratch copy green (SIM-005).
- Reproduce: `rg -n -w 'RecordingTransport|from_cassette|ScriptedTransport' src tests`.
- Fix: Owner decision. If live runs should leave replayable recordings, wire `RecordingTransport` behind an explicit `open_session` option. Otherwise delete it and `from_cassette`, and move `ScriptedTransport` into a tests helper. Fix risk: Low.
- Aliases: TST-009 (part: the unused cassette pair).

### SIM-007 · Low · Confirmed
- Where: src/agency/tools/sandbox.py:27, src/agency/tools/sandbox.py:67, src/agency/tools/sandbox.py:78, src/agency/qa/delivery.py:211, src/agency/qa/delivery.py:223, src/agency/ledger/store.py:263, src/agency/ledger/store.py:266, src/agency/tools/craft.py:54
- Problem: Five defaulted parameters are never supplied by any caller, so their branches are dead:
  - `Sandbox(read_only=…)` and its bind loop (:67-68).
  - `Sandbox.run(stdin=…)`.
  - `delivery_problems(inputs_changed=…)`. The `if not inputs_changed` guard (:223) is always true.
  - `Ledger.spent(ticket_id=…)` and its filter (:266-267).
  - `CommandIndex.load(app=…)`. It is always `"vectorcraft"`; the tool schema `CraftSearch` has no app, and `craft_run` accepts only `.vectorcraft` (surface.py:376).
- Evidence: /tmp/audit-sim/params.py checks every defaulted parameter of src/agency, constructors included, against every call site in src/ and tests/ that has the same callee name. A parameter counts as supplied if a call passes it by keyword, positionally, or through `*`/`**`. The flagged ones were then confirmed by hand:
  - `rg -n 'read_only=|stdin=' src tests` finds only the definitions, and the 13 `sandbox.run(` / `box.run(` calls pass at most `timeout`.
  - `delivery_problems` is called at surface.py:551 and :634 without it.
  - `.spent(` is called at gateway/client.py:134, cli.py:190 and in two tests, each time with one argument.
  - `CommandIndex.load(` is called at runtime.py:129 and in two tests, never with `app`.
  - The first four were already dead at 51c511c. Removing them kept the scratch copy green (SIM-005).
- Reproduce: `mise exec -- uv run python /tmp/audit-sim/params.py` from the repo root, plus the `rg` above.
- Fix: Remove the parameters and their branches; keep `app` only if M3 adds a second Craft index. Fix risk: Low.

### SIM-008 · Low · Confirmed
- Where: registry/roles.json:5, registry/roles.json:8, src/agency/tools/surface.py:862, docs/04-TOOLS.md:34
- Problem: Two fields that every role in the studio registry carries, `department` and `craft`, are never read. docs/04-TOOLS.md:34 says the `craft_*` tools are given "secondo `craft` in `roles.json`". In fact `role_tools` gives the AUTHOR set, which includes all three `craft_*` tools, to every role that is not `*-director`, `router` or a reviewer, whatever its `craft` list says. The director split is a name-suffix rule in code (surface.py:863), not data. There is no effect today: every active author (identity-designer, direction-a to direction-e) lists vectorcraft, and only VectorCraft is wired.
- Evidence: `rg -n '"craft"|"department"' src tests` finds no reader. The only roles.json values the code reads are `model` and `effort` (agents/loop.py:107, :135-136). Work reaches only two kinds of role. The first is a role with its own prompt in prompts/roles/: critic, design-director, identity-designer and qa-inspector (`open_ticket` checks `has_prompt`, surface.py:485). The second is the explorers direction-a to direction-e, which `plan_exploration` opens with the `explorer` prompt (surface.py:603, :615).
- Reproduce: `jq -r '.roles | to_entries[] | "\(.key)\t\(.value.department)\t\(.value.craft)"' registry/roles.json`; `rg -n '"craft"|"department"' src tests`.
- Fix: Owner decision. Either enforce `craft` in `role_tools`/`tools_for` and move the director/reviewer split into roles.json, or drop both fields and correct 04-TOOLS.md. Fix risk: Low; the request snapshots catch any change to a tool set.
- Duplicate: the director/reviewer split by name suffix is tracked under STR-005; the unread fields stay here.

### SIM-009 · Low · Likely
- Where: src/agency/ledger/models.py:134, src/agency/tools/surface.py:644, src/agency/tools/surface.py:685, src/agency/tools/surface.py:693, src/agency/graph/workflow.py:197, src/agency/graph/workflow.py:237, src/agency/graph/workflow.py:260, src/agency/graph/workflow.py:272, src/agency/graph/workflow.py:332
- Problem: `ConceptRow.status` is a plain `str` whose six values are spelled as literals in two modules, and the graph branches on two of them. ADR-0021 principle 2 asks for phases and gates as types, not strings. A typo in one writer would silently empty a reader's list (for example `prepare_proposals` would find no chosen idea) with no type error.
- Evidence:
  - The six values are `"idea"`, `"schizzo"`, `"selezionata"`, `"in-sviluppo"`, `"proposta"` and `"scelta"`.
  - The default is set at models.py:134.
  - Writers: surface.py:644 and :685, workflow.py:237, :260 and :332.
  - Readers: workflow.py:197 and :272, surface.py:693.
  - insights passes the value through raw (insights/views.py:265).
  - The same words also name `TicketType.SKETCH` and `TicketType.PROPOSAL` (contracts/ticket.py:20-21), so a text search cannot tell the two apart.
- Reproduce: `rg -n '"selezionata"|"proposta"|"schizzo"|"in-sviluppo"|"scelta"' src`.
- Fix: A `ConceptStatus(StrEnum)` in agency.contracts with the same values, so stored data and the dashboard stay identical, used by both modules and by `ConceptRow.status`. Fix risk: Low.

### SIM-010 · Low · Likely
- Where: src/agency/agents/loop.py:25, src/agency/tools/surface.py:762, src/agency/tools/surface.py:948, src/agency/graph/workflow.py:37, src/agency/tools/surface.py:541, src/agency/agents/loop.py:192
- Problem: Which tools end an instance is written down in three places that do not agree:
  - `CLOSING` (loop.py:25), which only feeds the reminder text.
  - `CLOSE_ALWAYS` (surface.py:762).
  - The conditional branches of `Toolbox._restore` (surface.py:948-961).

  `reject_concept` closes an instance and is in the director's tool set, but it is missing from `CLOSING`, so the reminder never names it. That may be intentional, but nothing records it. The set of runnable statuses has the same problem: it is spelled three times (`RUNNABLE` at workflow.py:37, inline at surface.py:541 and loop.py:192) and equals the from-set of `Action.DELIVER` (contracts/ticket.py:61).
- Evidence: The three lists differ:
  - `CLOSING`: deliver, hand_off, plan_exploration, submit_concept, select_concepts, draft_presentation, present_concepts, block.
  - `CLOSE_ALWAYS`: deliver, block, hand_off, plan_exploration, submit_concept, reject_concept.
  - `_restore` adds select_concepts, draft_presentation and present_concepts.

  The director's tool list includes reject_concept (surface.py:832-833).
- Reproduce: read the three places listed above; `rg -n 'Status.OPEN, Status.REWORK|RUNNABLE' src`.
- Fix: Declare closing behaviour on the `Tool` record (for example a `closes` field, plus a flag for the conditional closers) and derive both lists from `TOOLS`, keeping `CLOSING`'s order so the reminder text stays byte-identical. Export one runnable set from contracts/ticket.py. Fix risk: Low.

### SIM-011 · Low · Confirmed
- Where: src/agency/tools/files.py:21, src/agency/artifacts/files.py:22, src/agency/evaluation/blind.py:51, src/agency/telemetry/fingerprint.py:51, src/agency/tools/files.py:29, src/agency/insights/adapters/transcripts.py:53, src/agency/ledger/schema.py:27, src/agency/insights/adapters/registry.py:32
- Problem: Small helpers exist in several copies:
  - Four "sha256 of a file" functions: two stream in 1 MiB chunks, two read the whole file.
  - Two head-and-tail text clippers, with different cut markers.
  - `BUSY_SECONDS = 30`, defined twice.

  The import-linter contracts stop evaluation and insights from importing tools, artifacts and the ledger, so copying was the only option without a shared module.
- Evidence: tools/files.py:21-26 and artifacts/files.py:22-27 are the same loop. evaluation/blind.py:51-52 and telemetry/fingerprint.py:51-52 are both `hashlib.sha256(path.read_bytes()).hexdigest()`. `clip` (tools/files.py:29-34) and `_clip` (insights/adapters/transcripts.py:53-56) implement the same truncation. The two `BUSY_SECONDS` are at ledger/schema.py:27 and insights/adapters/registry.py:32. The hash-while-copying loops in artifacts/files.py:54-59 and artifacts/keeping.py:102-106 are legitimate and not part of this finding.
- Reproduce: `rg -n 'def sha256|def _digest|def _sha256|def _?clip|BUSY_SECONDS\s*=' src/agency`.
- Fix: Put a `file_sha256` (and, if wanted, the clipper and the busy timeout) in agency.contracts, which every slice may import, or in the `shared/` package that docs/01-ARCHITECTURE.md plans, and replace the copies. Fix risk: Low.

### SIM-012 · Low · Confirmed
- Where: src/agency/graph/workflow.py:64, src/agency/tools/surface.py:771
- Problem: The two most complex units are ones ADR-0021 already names.
  - `build` is a 393-line function that holds the whole graph as 22 nested closures (13 nodes, 7 routers, 2 helpers). Ruff scores it 63 because McCabe adds nested functions to their parent; its own body is one loop plus edge wiring, and no single closure scores above 9.
  - tools/surface.py is 968 lines: 30 input schemas, 28 tools, 10 hand-assembled tool-set lists and the handlers of every phase.

  The graph nodes cannot be imported or unit-tested one by one: baseline §3.1 shows `graph.workflow` is reached only indirectly.
- Evidence: the C901 output below. The 13 closures that score above 1 add up to 52, the 9 that score 1 add 9, and `build`'s own loop and base add 2, which gives 63. ADR-0021's "Contesto" names both files. Its "Conseguenze" schedule the split for M1.7, require request snapshots to stay byte-identical at every step, and warn that renaming nodes or tools breaks the resume of paused projects.
- Reproduce: `mise exec -- uv run ruff check src/agency/graph/workflow.py --select C901 --config "lint.mccabe.max-complexity = 1" --output-format concise --exit-zero`.
- Fix: Leave to M1.7, which owns the slice split under the snapshot rule; the sanity refactor should not pre-empt it. If something must happen earlier, the smallest step is turning the closures into methods of a small class that holds runner, ledger and settings, with no node or tool renamed. Fix risk: Med.
- Aliases: STR-013 (part: `tools/surface.py`).

### SIM-013 · Low · Likely
- Where: src/agency/graph/workflow.py:68, src/agency/agents/loop.py:67, src/agency/runtime.py:76, src/agency/cli.py:90, src/agency/evaluation/blind.py:60
- Problem: The project layout `projects/<slug>/work` is built by hand in four modules and parsed back in a fifth. `DataLayout` (contracts/layout.py) owns every `.data/` path, but not this one.
- Evidence: each of the first four lines appends `/ "work"` to `settings.project_dir(project)`; workflow.py wraps it in a local `work_dir` closure that the other modules cannot use. blind.py:60 strips a leading `"work"` part to recover the path inside the project.
- Reproduce: `rg -n '"work"' src`.
- Fix: A `work_dir(project)` on `Settings`, or a project-layout type in agency.contracts that evaluation may import, used by all five places. Fix risk: Low.
- Duplicate: merged in full into STR-006; tracked there.

### SIM-014 · Nit · Confirmed
- Where: src/agency/ledger/models.py:133
- Problem: `ConceptRow.sketch_ticket` is never written or read; every row stores `""`.
- Evidence: /tmp/audit-sim/fields.py looks for attribute, keyword and string uses of every model field in src/, tests/ and web/; it reports only this one. `rg -n sketch_ticket --glob '!legacy/**' .` finds only the model, migrations/versions/0001_baseline.py:21 and tests/fixtures/ledger_schema_0001.sql:12.
- Reproduce: the `rg` above.
- Fix: Leave it until a schema migration is needed anyway, then drop the column in that new revision; applied revisions are frozen. Fix risk: Low.

### SIM-015 · Nit · Likely
- Where: tests/test_hardening.py:35, tests/test_agent_flow.py:43, tests/test_sketch_flow.py:122, tests/test_agent_flow.py:34, tests/test_sketch_flow.py:65
- Problem: Preference. `settings(tmp_path)` is defined three times with the same body and the same `# type: ignore[call-arg]`. The scripted-response builder `turn(*blocks)` is defined twice, and the two copies differ only in which field is a parameter.
- Evidence: compare the five definitions side by side; the bodies are identical apart from the parameter noted.
- Reproduce: `rg -n '^def (settings|turn)\(' tests`.
- Fix: Move the shared helpers into tests/conftest.py or a helper module like tests/drawings.py. Fix risk: Low.

### SIM-016 · Nit · Likely
- Where: web/src/app/compare/page.tsx:99, web/src/app/compare/page.tsx:183, web/src/app/projects/[name]/page.tsx:117, web/src/app/projects/[name]/quality/page.tsx:77, web/src/components/context-chart.tsx:43
- Problem: Preference. The scrolling-table wrapper `<div className="scroll" role="region" aria-label=… tabIndex={0}>` is written out 14 times in 7 files, always with the same three attributes. In compare/page.tsx, `rows()` (lines 99-175) spells out the same before/after/delta triple for eight measures.
- Evidence: `rg -c 'className="scroll" role="region"' web/src` reports 4 + 3 + 2 + 2 + 1 + 1 + 1 occurrences; every one carries `tabIndex={0}` and an `aria-label`.
- Reproduce: the `rg` above.
- Fix: A `<ScrollRegion label>` component, and a small helper for the metric rows, with every label string unchanged: the e2e specs select by them and they are user-facing. Fix risk: Low.

### SIM-017 · Nit · Likely
- Where: src/agency/config.py:29
- Problem: Preference. `Settings.layout` plus five one-line properties, each returning a field of `self.layout`, give every data path two names. Callers use both: `settings.ledger_path` six times and `settings.layout` three times.
- Evidence: config.py:29-51; `rg -n 'settings\.(ledger_path|layout)' src`.
- Reproduce: the `rg` above.
- Fix: Keep one spelling. Fix risk: Low.

## 15 most complex functions

Command: `mise exec -- uv run ruff check . --select C901 --config "lint.mccabe.max-complexity = 1" --output-format json --exit-zero`.
This covers 116 `.py` files; the vendored `qa/scripts` are excluded by `pyproject.toml`. Lines run from `def` to the last line of
the body, without decorators. Tests score at most 6, so none appears below. Rank 15 ties with `wrap`
(tools/presentation.py:68, 8, 24 lines).

| Rank | Function | File:line | McCabe | Lines |
|---:|---|---|---:|---:|
| 1 | `build` (22 nested node closures counted in) | src/agency/graph/workflow.py:64 | 63 | 393 |
| 2 | `JsonlTranscripts.transcript` | src/agency/insights/adapters/transcripts.py:152 | 16 | 87 |
| 3 | `AgentRunner._loop` | src/agency/agents/loop.py:97 | 14 | 73 |
| 4 | `master_problems` | src/agency/qa/delivery.py:172 | 12 | 31 |
| 5 | `render` | src/agency/telemetry/report.py:21 | 12 | 69 |
| 6 | `problem` | src/agency/tools/master.py:34 | 11 | 34 |
| 7 | `validate` | src/agency/qa/delivery.py:59 | 10 | 26 |
| 8 | `_judge` | src/agency/cli.py:216 | 9 | 50 |
| 9 | `TicketSpec._contract` | src/agency/contracts/ticket.py:109 | 9 | 16 |
| 10 | `select` (closure inside `build`) | src/agency/graph/workflow.py:146 | 9 | 33 |
| 11 | `Ledger.apply` | src/agency/ledger/store.py:206 | 9 | 40 |
| 12 | `evidence_problems` | src/agency/qa/delivery.py:140 | 9 | 30 |
| 13 | `Toolbox.call` | src/agency/tools/surface.py:906 | 9 | 41 |
| 14 | `JsonlTranscripts.read` | src/agency/insights/adapters/transcripts.py:112 | 8 | 39 |
| 15 | `run_steps` | src/agency/tools/craft.py:95 | 8 | 40 |

Only rank 1 is a real outlier, and most of its score is aggregation (SIM-012). Ranks 2 to 15 are flat branch lists: a
validator, a renderer, a stop-reason switch, or a per-extension `if` chain in `master.problem`. Each is short enough to read in
one screen. `transcript` builds string-keyed dicts and converts them to models at the end; building the models directly
would read better (preference). `_loop` has one branch per `stop_reason`, which CLAUDE.md requires.

**TypeScript/TSX.** No complexity tool is installed, so the largest files were read and their branches counted with `grep`.
web/src/app/compare/page.tsx (418 lines) has 28 functions and arrow functions with about 25 decision points between them (6
`if`, 19 ternaries). Its longest function, `rows()`, is data, not branching. The other pages (135–212 lines) have at most one
`if` and up to 12 ternaries each, mostly in JSX conditional rendering. The logic sits in small pure modules with unit tests
(`chart.ts`, `format.ts`, `labels.ts`, `timescale.ts`). No TS function needs simplifying for complexity; the only TS item is
the repetition in SIM-016.

## Churn hotspots

History: `git log --oneline | wc -l` gives 23 commits, none of them merges. The first is 51c511c (2026-11-01T19:05:11+01:00)
and the last 86f51a1 (2026-11-04T00:23:28+01:00), about 53 hours apart. They are 18 `feat`, 2 `docs`, 1 `refactor`, 1 `build`
and 1 `chore`, and **no `fix` commit**: the history is too short to show any complexity producing bugs. 8d99a5c reuses the
subject of 30d2c7e but touches only CLAUDE.md (the audit rules), so it does not count as a second change to the CLI.
Command: `git log --no-merges --format= --name-only | grep -v '^$' | grep -v '^docs/' | sort | uniq -c | sort -rn`.

| File | Commits touching it | Lines now | Note |
|---|---:|---:|---|
| README.md | 14 | 76 | Documentation outside `docs/` |
| src/agency/cli.py | 13 | 367 | The hottest code file: every feature adds a subcommand, and all 14 live in one module (the target layout has `entrypoints/cli/`). Max McCabe 9 (`_judge`) |
| tests/test_insights.py | 8 | 880 | Grows with every insights feature |
| src/agency/agents/loop.py | 7 | 195 | Hot and complex: `_loop` is rank 3 (14) |
| src/agency/telemetry/report.py | 7 | 201 | `render` is rank 5 (12). It holds the fingerprint parser that diverged (SIM-001) |
| src/agency/runtime.py | 7 | 133 | Session wiring; changes with every engine feature |
| src/agency/entrypoints/server/api.py | 7 | 189 | One endpoint per dashboard view |
| src/agency/insights/domain.py | 7 | 447 | Changed together with ports, application and api in each of the 4 dashboard-view commits |
| src/agency/insights/ports.py | 7 | 132 | As above |
| src/agency/insights/application.py | 7 | 160 | As above |
| src/agency/insights/adapters/registry.py | 7 | 175 | Raw SQL over ledger tables, by design (ADR-0019) |
| tests/test_sketch_flow.py | 7 | 1168 | The largest test file |
| tests/test_server.py | 7 | 453 | |
| src/agency/ledger/models.py | 6 | 218 | Schema changes, one Alembic revision each |
| schemas/openapi.json | 6 | 2894 | Generated; follows api.py |
| web/src/api/schema.ts | 5 | 1415 | Generated; follows openapi.json |
| src/agency/ledger/store.py | 5 | 472 | `Ledger.apply` is rank 11 (9) |
| src/agency/graph/workflow.py | 3 | 456 | For contrast: highest complexity (63), low churn |
| src/agency/tools/surface.py | 3 | 968 | For contrast: largest file, low churn |
| src/agency/qa/delivery.py | 1 | 242 | For contrast: 3 of the top 15, touched once since bootstrap |

Churn and complexity do not overlap: the complex engine core (workflow, surface, delivery) has barely moved since bootstrap,
while the churn comes from the read side, the dashboard and the CLI. Each of the four dashboard-view commits (e8a1c67,
dfa9d15, 974ac19, f7d3ee6) touched 41, 38, 28 and 29 files outside `docs/`. The same 13 files changed in all four: insights
`domain`, `ports` and `application`, `api.py`, `openapi.json`, `schema.ts`, `client.ts`, `globals.css`, `web/e2e/project.ts`,
`dashboard_fixture.py`, and the tests for insights, schemas and the server. That is the price of the layered, schema-first
design (ADR-0021, ADR-0022), not a defect. In `docs/`, the roadmap changed in 21 of 23 commits, the ADR index in 19,
03-DATA-MODEL.md in 14, and 04-TOOLS.md and 06-SECURITY.md in 9 each.

## Leads checked and not reported

- Django settings constants, `urlpatterns`, the Ninja route functions and their exception handler: Django and Ninja reach
  them through settings strings and decorators.
- `Judgment._coherent` and `TicketSpec._contract` are Pydantic validators, and `_Handler.log_message` is an override: the
  frameworks call them.
- The vendored `qa/scripts/*` are out of scope (byte-identical to `legacy/`). `optical_check.py:81` imports a module named
  `evidence` that is not shipped beside it, but only under `--record-by`, which `qa/checks.py` never passes.
- The two board composers, `tools/board.py:120` and `evaluation/board.py:158`, are not duplicates. The exploration board
  scales PNG sketches; the judgment board renders every size separately, as ADR-0041 requires; and evaluation may not import
  tools.
- The insights ports each have one adapter, but tests use `FakeRegistry` (tests/test_insights.py:616), so the boundary
  earns its keep. The four near-identical project endpoints in `api.py` are explicit by ADR-0021, and their operation ids
  feed the generated TypeScript.
- Web: the exports used only inside their own file are types (`JsonOperation`, `Point`, `View`, `Pause`). Every web
  dependency and devDependency has a use. In the Python dev group, pytest, ruff, pyright and import-linter are the CLIs of
  `make check`, and django-stubs gives pyright the Django types.
