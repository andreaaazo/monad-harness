# M1.7 slice architecture, plan B (roadmap items 4–7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** finish M1.7. When this plan is done, the engine follows ADR-0021 principle by principle, and each principle
has the command that checks it.

**Architecture:** five phases, in order.
1. **Entry points and boundaries.** The CLI moves to `entrypoints/cli/`. Blocking import-linter contracts enforce the
   layers of ADR-0057 and the library rules of ADR-0021.
2. **Explicit types.** Director phases and graph routes become `Literal` types, node updates become a `TypedDict`,
   and the role registry becomes typed models that are passed to whoever needs them.
3. **Ports.** The ledger moves behind ports in `agency.contracts`. Those ports carry plain records, not SQLModel
   rows. The sandbox gets a port as well.
4. **Domain and application.** Each slice gets a `domain.py` of pure rules with unit tests. Each slice with nodes
   also gets an `application.py`, which holds its node logic without LangGraph. A contract keeps both free of
   frameworks.
5. **Tests and close.** The large test files and `globals.css` are split, the docs are aligned, and the exit
   criteria are checked.

**Tech Stack:** Python 3.13, uv, pytest, ruff, pyright, import-linter 2.15 (`layers`, `forbidden`, `independence`,
`acyclic_siblings`), LangGraph 1.2, pydantic 2, Next.js (CSS only).

**Spec:**
- `docs/02-ROADMAP.md`, section M1.7: items 4–7 and the exit criteria;
- `docs/adr/0021-monolite-modulare-a-slice.md`;
- `docs/adr/0057-l-albero-dei-pacchetti-del-motore.md`;
- the "Plan B" section of `docs/superpowers/plans/2026-11-14-m1-7-slice-architecture.md`;
- the deferred findings STR-003, STR-007 and STR-013 in `docs/audit/SUMMARY.md`, with their detail in
  `docs/audit/50-structure.md`;
- the plan A final review's notes, as recorded in the M1.7 handoff messages: the `Send` import in
  `studio.shared`, where `agency.context` sits, where cross-slice queries live, and the deferred minors.

## Decisions (recorded in ADR-0058 by Task 0)

Andrea delegated these ("Sei tu che fai decisioni"). Each one is decided here, and ADR-0058 records it.

| # | Decision | Why |
|---|---|---|
| D5 | **The ports live in `agency.contracts`**, as `Protocol`s, together with the records they carry. That covers `contracts.ledger` (new), `contracts.sandbox` (new) and the existing `contracts.artifact.ArtifactStore`. The model's port stays `gateway.transport.Transport`. | `ArtifactStore` already set the pattern. `contracts` is the lowest layer, so every layer can depend on a port without depending on the adapter behind it. |
| D6 | **The ledger port is split by concern:** `Tickets`, `Operations`, `Concepts`, `Gates`, `Proofs`, `Usage`, `KeptArtifacts`, `Runs`. `LedgerPort` composes them. Each consumer is typed by the narrowest one it needs, for example the gateway by `Usage`. The records are frozen pydantic models named `<Kind>Entry`, with the same fields as the row. | ADR-0021 lists the registry as an outer boundary. `*Entry` avoids a clash with `insights.domain`'s `*Record` and with `contracts.gate.Gate`. |
| D7 | **Only the composition roots import `agency.ledger`:** `agency.process.session` and `agency.entrypoints.cli`. A forbidden contract enforces it. | That is how "il registro solo dietro la sua porta" (item 5) becomes checkable. |
| D8 | **Phases and routes are `Literal` types, not `StrEnum`.** `DirectorMode = Literal["plan", "select", "present"]` goes in `contracts.phase`. `Route` goes in `studio.shared`, with `END_ROUTE: Final = "__end__"` beside it. | A checkpoint keeps today's strings, so paused projects resume. LangGraph's serializer can record an enum's module and class. |
| D9 | **The two nodes reached by `Send` take `TicketTask = Mapping[str, str]`, not a `TypedDict`.** | LangGraph turns a `TypedDict` annotation into an input schema, which adds a channel to the checkpoint. A `Mapping` alias is not a class, so LangGraph ignores it. Task 5's graph-shape test proves this. |
| D10 | **The studio rules are a typed value, passed to their users.** `contracts.registry.StudioRules` is loaded by `agency.registry.load_rules()` in the composition roots and passed to `AgentRunner`, `ToolContext` and `qa.delivery`. The prompt-library lookups stay functions in `agency.registry`, because they read files at call time. | Explicit over implicit (ADR-0021 principle 2). The flow tests receive the rules through `tests/support/rules.py`. |
| D11 | **The CLI moves to `agency.entrypoints.cli`** (`__init__.py` from `cli.py`), with `render.py` (from `telemetry/report.py`) and `doctor.py` (from `agency/doctor.py`). The run fingerprint moves to `agency.process.fingerprint`. After that, `agency.telemetry` holds only OpenTelemetry. | STR-007. The fingerprint's only caller is the session. |
| D12 | **Inside a slice**, there are up to four kinds of module: <ul><li>`domain.py`: pure rules, which import only `agency.contracts`;</li><li>`application.py`: the node logic without LangGraph, which may import `contracts`, `studio.shared`, its own `domain`, `toolkit.base` and `workshop.files`;</li><li>`tools.py` and `nodes.py`: the adapters.</li></ul>A query that two slices use lives in `studio.shared`. A rule that one slice uses lives in that slice's `domain`. The LangGraph-facing types (`Node`, `TaskNode`, `Router`) live in `agency.studio.graph`. | ADR-0021 principle 3, made concrete without a port around code that has no boundary. The final review asked where cross-slice queries live. |
| D13 | **`agency.context`**, empty until M3, sits in the platform layer. | The layers contract has to place it, and the final review noted that ADR-0057 does not. |
| D14 | **In this plan the flow tests may also change the constructor arguments that make a dependency explicit**: `rules=`, and ports in place of concrete classes. They never change an assertion, a recorded answer or a scripted turn. The roadmap's exit criterion says so. | Plan A's constraint was written for moves. D10 legitimately changes constructors. |

## Target tree after this plan

| Package | Holds | Change |
|---|---|---|
| `agency.contracts` | today's contracts, plus `clock.py` (`now`), `ledger.py` (the entries, the concern ports, `LedgerPort`, `IllegalTransition`, `ForbiddenAction`), `sandbox.py` (`SandboxPort`, `Completed`) and, in `registry.py`, `StudioRules` | new modules |
| `agency.ledger` | the SQLite adapter, which implements `LedgerPort` and maps entries to rows | its rows no longer leave the package |
| `agency.studio` | `shared.py` (state, `ProjectUpdate`, `Route`, `END_ROUTE`, `Crew`, `Runner`, the cross-slice helpers); `graph.py` (`Node`, `TaskNode`, `Router`); and per slice `domain.py`, `application.py` (if the slice has nodes), `tools.py`, `nodes.py` | `graph.py`, `domain.py` and `application.py` are new |
| `agency.process` | `graph.py`, `session.py`, `fingerprint.py` | `fingerprint.py` comes from `telemetry` |
| `agency.entrypoints.cli` | `__init__.py` (`main`), `render.py`, `doctor.py` | moved from `cli.py`, `telemetry/report.py` and `doctor.py` |
| `agency.telemetry` | `setup.py` (OpenTelemetry) | `report.py` and `fingerprint.py` leave |

Removed by the end: `agency.cli`, `agency.doctor`, `agency.telemetry.report` and `agency.telemetry.fingerprint`.

## Global Constraints

- **Plan A's constraints still hold**, with D14 added. They are in `docs/superpowers/plans/2026-11-14-m1-7-slice-architecture.md`:
  - the request snapshots stay byte-identical: tool names, descriptions, schemas and `$defs` class names, and system
    prompts;
  - move units are byte-identical apart from imports;
  - graph node names, `ProjectState` field names, span names and tracer scopes stay as they are;
  - frozen paths are not touched;
  - the five hand-kept import-linter lists stay complete;
  - no git writes; every task ends with `make check` exiting 0, then the READY FOR COMMIT block;
  - English code, Italian documents;
  - one kind of change per task.
- **User-facing strings move verbatim.** A refusal or a note that moves into a `domain.py` keeps its exact Italian
  text, and its unit test asserts that text.
- **A checkpoint written before this plan must resume after it.** Route values, mode values, node names and the
  graph's channels do not change. Task 5's shape test pins the channels.
- **No new `Any`, and no `cast`.** M1.8 bans both, so every type this plan adds is precise.
- **Docs follow the code in the same task, folder names included.** Plan A's Tasks 4–7 missed the folder names in
  the tree of `docs/01-ARCHITECTURE.md`. Find stale paths with
  `git grep -n "<old dotted path>\|<old file path>\|<old folder>/" -- docs README.md ':!docs/audit' ':!docs/adr' ':!docs/superpowers'`.
- **M1.8 is next.** This plan adds no lint configuration and does not pre-empt M1.8's gate (complexity 8, the
  `Any` ban). The `select` factory stays at McCabe 11 until M1.8.

## Review Focus

These are the conditions most likely to break silently. Each line names the test that pins it and the task that
owns it.

- **A project paused before this plan resumes after it.** Every change to state types, routes or node signatures
  must leave the checkpoint shape alone. Pinned by `test_the_graph_keeps_its_channels_and_branches` (Task 5) and by
  the existing resume tests in `test_agent_flow.py`.
- **The hash chain binds the same bytes when a row is written through an entry.** `agency verify` on an existing
  registry must keep passing. Pinned by one `test_<kind>_written_through_an_entry_chains_like_the_row` per entry
  family (Tasks 8–10), and by the existing chain tests in `test_ledger.py`.
- **The typed rules say exactly what `roles.json`, `org.json` and `checks.json` say.** A role without a prompt is
  still refused, and so is a sender `org.json` does not allow. Pinned by
  `test_the_typed_rules_match_the_registry_files` and `test_opening_refusal_*` (Tasks 6 and 18).
- **The `agency` command still starts after the CLI moves.** Pinned by `test_the_agency_script_is_the_cli_main`
  (Task 1) and by `uv run agency --help` exiting 0.
- **The model still receives the same requests.** Typed rules, moved handlers and ports must not change one
  byte of a tool definition or a system prompt. Pinned by `tests/test_request_snapshots.py`, which runs in every
  task's `make check`.

---

## Phase 1: entry points and boundaries

### Task 0: ADR-0058, the decisions of plan B

Kind: docs.

**Files:**
- Create: `docs/adr/0058-porte-tipi-e-livelli-del-motore.md`, in Italian. It records the context (M1.7 items 4–7,
  and ADR-0021 principle 2 only partly covered), D5–D14 with their reasons, and the consequences. The
  consequences are:
  - the flow tests change constructors (D14);
  - checkpoints are unchanged (D8, D9);
  - the select factory waits for M1.8.
- Modify:
  - `docs/adr/README.md`: add the row;
  - `docs/02-ROADMAP.md`, M1.7: exit criterion 3 adds "e gli argomenti dei costruttori che rendono esplicita una
    dipendenza (ADR-0058)". The roadmap already links this plan.

- [ ] **Step 1:** write the ADR and the two edits. Check them with
  `uv run ruff format --check docs/adr/0058-*.md docs/02-ROADMAP.md`.
- [ ] **Step 2:** `make check` exits 0. Handoff with `docs(adr): record ports, types and layers for M1.7 plan B (ADR-0058)`.

### Task 1: the CLI moves to `entrypoints/cli`, the fingerprint to `process`

Kind: move. It closes STR-007.

**Files:**
- Move:
  - `mkdir -p src/agency/entrypoints/cli`;
  - `mv src/agency/cli.py src/agency/entrypoints/cli/__init__.py`;
  - `mv src/agency/telemetry/report.py src/agency/entrypoints/cli/render.py`;
  - `mv src/agency/doctor.py src/agency/entrypoints/cli/doctor.py`;
  - `mv src/agency/telemetry/fingerprint.py src/agency/process/fingerprint.py`.
- Modify:
  - `pyproject.toml`:
    - `agency = "agency.entrypoints.cli:main"`;
    - the five lists drop `agency.cli` and `agency.doctor`;
    - every forbidden list that named `agency.cli` names `agency.entrypoints.cli` instead;
    - the engine-no-Django contract (ADR-0020) adds `agency.entrypoints.cli` to `source_modules`, and its
      `forbidden_modules` entry `agency.entrypoints` becomes `agency.entrypoints.server`;
  - `tests/test_server.py`: `test_every_engine_package_is_forbidden_to_import_django` expects
    `agency.entrypoints.cli` in the source list as well;
  - the imports, and the `monkeypatch` string targets `"agency.cli.` and `"agency.doctor.`, in `src/` and `tests/`;
  - `tests/test_runs.py`: the code-map path of the fingerprint;
  - the `agency.telemetry` package docstring;
  - the docs that name the old paths: `docs/01-ARCHITECTURE.md` (tree and text), `docs/PARITY.md`, `README.md` and
    `Taskfile.yml` if it names a module.
- Test: `tests/test_layout.py` gets `test_the_agency_script_is_the_cli_main`.

- [ ] **Step 1: write the failing test**

```python
def test_the_agency_script_is_the_cli_main() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["scripts"]["agency"] == "agency.entrypoints.cli:main"
    assert callable(importlib.import_module("agency.entrypoints.cli").main)
```

Run `uv run pytest tests/test_layout.py::test_the_agency_script_is_the_cli_main`. Expected: FAIL on the script
value.
- [ ] **Step 2:** move and update. Run `uv sync` so the console script points at the new module, then
  `uv run agency --help`. Expected: exit 0.
- [ ] **Step 3:** check the moves. `diff <(git show HEAD:<old>) <new>` for each of the four files shows only import
  lines. `git grep -n "agency\.cli\b\|agency\.doctor\|telemetry\.report\|telemetry\.fingerprint\|telemetry/report\|telemetry/fingerprint" -- src tests docs README.md ':!docs/audit' ':!docs/adr' ':!docs/superpowers'`
  finds nothing.
- [ ] **Step 4:** `make check` exits 0. Handoff with `refactor(entrypoints): move the CLI with its renderer and doctor, and the fingerprint to process`.

### Task 2: tidy what plan A's split scripts left

Kind: style. These are the plan A final review's minor 5 items.

**Files:**
- Modify:
  - `src/agency/studio/{exploration,proposal,presentation}/tools.py`: each `X = [...]` sits right above its `X += [...]`;
  - `src/agency/toolkit/base.py` and `src/agency/agents/toolbox.py`: imports of one or two names fit on one line;
  - `src/agency/workshop/render.py`: add `proof_stem` to `__all__`, if the module has one.

- [ ] **Step 1:** edit. `git diff --stat` touches only these files, and `git diff -w` shows no change to any statement.
- [ ] **Step 2:** `make check` exits 0. Handoff with `style(studio): tidy the leftovers of the tool split`.

### Task 3: the LangGraph-facing types leave `studio.shared`

Kind: refactor (a move of definitions).

**Interfaces:**
- Produces: `agency.studio.graph`, holding `Node` (the Protocol, moved verbatim) and
  `type Router = Callable[[ProjectState], list[Send] | str]`. `studio.shared` no longer imports `langgraph`.

- [ ] **Step 1:** move the two definitions. Every `nodes.py` and `process/graph.py` imports them from
  `agency.studio.graph`. Check with `git grep -n "langgraph" src/agency/studio/shared.py`: nothing.
- [ ] **Step 2:** `make check` exits 0. Handoff with `refactor(studio): keep the LangGraph-facing types in studio.graph`.

### Task 4: the layers and the library rules become contracts

Kind: build/DX. It closes the library part of STR-003.

**Files:**
- Modify: `pyproject.toml`, adding three contracts:

```toml
[[tool.importlinter.contracts]]
name = "the engine's layers: each imports only from the layers below (ADR-0057)"
type = "layers"
layers = [
  "agency.entrypoints",
  "agency.process",
  "agency.agents",
  "agency.studio",
  "agency.toolkit",
  "agency.qa",
  "agency.config : agency.registry : agency.ledger : agency.gateway : agency.telemetry : agency.artifacts : agency.workshop : agency.context",
  "agency.contracts",
]

[[tool.importlinter.contracts]]
name = "langgraph only in the process and the studio's graph adapters (ADR-0021)"
type = "forbidden"
source_modules = [ "...every top-level package but agency.process and agency.studio, plus agency.studio.shared and each agency.studio.<slice>.tools..." ]
forbidden_modules = ["langgraph", "langchain_core"]
allow_indirect_imports = true

[[tool.importlinter.contracts]]
name = "sqlmodel, sqlalchemy and alembic only in the ledger (ADR-0021)"
type = "forbidden"
source_modules = [ "...every top-level package but agency.ledger..." ]
forbidden_modules = ["sqlmodel", "sqlalchemy", "alembic"]
allow_indirect_imports = true
```

  Each `source_modules` list is written out in full. A list that names packages by hand gets a guard test.
- Test: `tests/test_server.py`, beside the other list guards:
  - `test_every_package_but_the_process_and_the_studio_is_forbidden_langgraph`;
  - `test_every_studio_module_but_the_graph_adapters_is_forbidden_langgraph`. It reads the `studio` folder, and
    `nodes.py` and `graph.py` are exempt;
  - `test_every_package_but_the_ledger_is_forbidden_the_orm`.

- [ ] **Step 1:** write the three guard tests. Run them. Expected: FAIL (`assert 0 == 1`, no such contract).
- [ ] **Step 2:** add the contracts. `uv run lint-imports` reports 10 kept. The guard tests pass.
- [ ] **Step 3:** prove that each new contract bites, on a scratch copy run with `PYTHONDONTWRITEBYTECODE=1` and
  `PYTHONPATH=<copy>/src`, after checking that the copy starts from 10 kept:
  - `from agency.process import graph` in `toolkit/base.py` → the layers contract is BROKEN;
  - `from langgraph.graph import END` in `studio/exploration/tools.py` → the langgraph contract is BROKEN;
  - `import sqlmodel` in `qa/checks.py` → the ORM contract is BROKEN.
- [ ] **Step 4:** in `docs/01-ARCHITECTURE.md`, the contract list goes to ten, and the library table says which
  rows are now enforced. `make check` exits 0. Handoff with `build(imports): enforce the engine's layers and the library rules of ADR-0021`.

## Phase 2: explicit types (item 7)

### Task 5: phases, routes, node updates and Send payloads are types

Kind: refactor.

**Interfaces:**
- Produces:
  - in `agency.contracts.phase`: `type DirectorMode = Literal["plan", "select", "present"]`. `MODES` becomes
    `dict[DirectorMode, str]`. `instance(ticket_id, attempt, mode: DirectorMode | None = None)` and
    `of(role, prompt="", mode: DirectorMode | None = None)` return the same strings as today for the same values.
    `mode_of(name) -> DirectorMode | None`;
  - `AgentRunner.run(..., mode: DirectorMode | None = None, ...)`, `Runner.run` likewise,
    `tools_for(role, spec, mode: DirectorMode | None = None)` and `ToolContext.mode: DirectorMode | None = None`;
  - in `agency.studio.shared`:
    - `type Route = Literal[...]`, holding the 13 node names, `"rejected"`, `"__end__"` and `""`. That is every
      value a router returns and every value `ProjectState.route` holds;
    - `END_ROUTE: Final = "__end__"`;
    - `ProjectState.route: Route`;
    - `class ProjectUpdate(TypedDict, total=False)`, with the fields of `ProjectState`;
    - `type TicketTask = Mapping[str, str]`;
  - in `agency.studio.graph`:
    - `Node.__call__(self, state: ProjectState) -> ProjectUpdate`;
    - a new `class TaskNode(Protocol)` with `def __call__(self, state: TicketTask) -> ProjectUpdate: ...`;
    - `type Router = Callable[[ProjectState], list[Send] | Route]`.

    `explore` and `proposal` return `TaskNode`. Every other node factory returns `Node`. Every router, the plain ones
    in `process/graph.py` included, returns `Route` or, for the two fan-outs, `list[Send] | Route`.
    `process/graph.py`'s node tuple is typed `tuple[tuple[str, Node | TaskNode], ...]`.

- [ ] **Step 1: pin the graph's shape first.** This is a characterization test, and it passes on today's code.

```python
def test_the_graph_keeps_its_channels_and_branches(tmp_path: Path) -> None:
    graph = workflow.build(MagicMock(), Ledger(tmp_path / "l.sqlite"), settings(tmp_path), InMemorySaver())
    assert sorted(graph.channels) == CHANNELS
    assert {name: spec.input_schema for name, spec in graph.builder.nodes.items()} == dict.fromkeys(
        NODES, ProjectState
    )
```

  It goes in `tests/test_gate_sandbox.py`, beside the graph build. `CHANNELS` is copied from printing it on today's
  code, and `NODES` lists the 13 node names. The second assertion is the one D9 protects: a `TypedDict` on `explore`
  would change that node's `input_schema` and add a channel.
- [ ] **Step 2:** a test that `END_ROUTE == langgraph.graph.END`, and one that every `DirectorMode` round-trips
  through `instance` and `mode_of`. Run them. Expected: FAIL on the import.
- [ ] **Step 3:** change the types. No runtime value changes: every route and mode is the same string as before.
- [ ] **Step 4:** `uv run pyright` reports 0 errors, the shape test still passes unchanged, and
  `git grep -n "Any" src/agency/studio src/agency/process` finds no `Any` this task left. `make check` exits 0.
  Handoff with `refactor(studio): type the director phases, the routes and the node updates`.

### Task 6: the studio rules are typed and passed

Kind: refactor.

**Interfaces:**
- Produces:
  - in `agency.contracts.registry`, a frozen `class StudioRules(BaseModel)`, with fields:
    - `roles: dict[str, RoleSpec]`;
    - `org: dict[str, list[str]]`;
    - `checks: dict[str, CheckSpec]`;
    - `active: frozenset[str]`: the roles with a prompt;

    and methods:
    - `can_open(sender, assignee) -> bool`;
    - `reviewers() -> frozenset[str]`;
    - `directions() -> dict[str, str]`.

    The methods and the field `active` give the same answers as today's `registry` functions and constants.
  - `read_roles` and `read_checks` return the typed models;
  - `agency.registry.load_rules(root: Path = REPO_ROOT) -> StudioRules`. The module-level `ROLES`, `ORG`,
    `CHECKS`, `REVIEWERS` and `DIRECTIONS` are removed. The prompt-library functions stay;
  - a `rules: StudioRules` parameter on:
    - `AgentRunner` (no default);
    - `ToolContext` (no default);
    - `qa.delivery.delivery_problems` and `qa.delivery.acceptance_problems`;
  - `Crew` gains `rules: StudioRules`, because `client_gate` passes it to acceptance;
  - `process.session.open_session` and `entrypoints.cli` call `load_rules()` once and pass the result;
  - `tests/support/rules.py` with `RULES = load_rules()`. Tests pass `rules=RULES`, as D14 allows.

- [ ] **Step 1: write the failing tests.**
  - `test_the_typed_rules_match_the_registry_files` builds the old answers with `json.loads` of the three files and
    compares them with `StudioRules`:
    - every role's fields;
    - `can_open` for every pair in `org.json`, plus one forbidden pair;
    - `reviewers()`;
    - `directions()` in file order;
    - `active` against the prompt files.
  - `test_no_module_reads_the_role_registry_as_a_global` runs
    `git grep -n "registry\.\(ROLES\|ORG\|CHECKS\|REVIEWERS\|DIRECTIONS\)" src` and expects nothing.

  Run them. Expected: FAIL.
- [ ] **Step 2:** implement and thread the value through. Each of today's `registry.X[...]` reads becomes a read
  from `ctx.rules`, from the runner's `rules` or from `crew.rules`.
- [ ] **Step 3:** the request snapshots pass unchanged. The flow-test diffs show only `rules=RULES` arguments and
  imports. `make check` exits 0. Handoff with `refactor(registry): type the studio rules and pass them to their users`.

## Phase 3: ports (items 4 and 5)

### Task 7: the clock and the ledger's errors move to the contracts

Kind: refactor (a move of definitions).

**Interfaces:**
- Produces:
  - `agency.contracts.clock.now() -> str`, verbatim from `ledger.store`;
  - `IllegalTransition` and `ForbiddenAction`, verbatim, in `agency.contracts.ledger`.

  `ledger.store` imports them from there. `agency.ledger.__all__` drops the two errors. Every caller imports from
  the contracts.

- [ ] **Step 1:** move. Check with `git grep -n "ledger.store import now\|ledger import .*\(IllegalTransition\|ForbiddenAction\)" src tests`: nothing.
- [ ] **Step 2:** `make check` exits 0. Handoff with `refactor(contracts): own the registry clock and the ledger's errors`.

### Task 8: concepts and gates cross the boundary as entries

Kind: refactor. Tasks 9 and 10 repeat the same pattern for the other row families.

**Interfaces:**
- Produces, in `agency.contracts.ledger`:
  - `ConceptEntry` and `GateEntry`: `BaseModel`s with `ConfigDict(frozen=True, from_attributes=True)`, holding
    exactly the fields, types and defaults of `ConceptRow` and `GateRow`;
  - the concern ports:
    - `class Concepts(Protocol)`, with `concepts(...) -> list[ConceptEntry]` and `update_concept(...)`;
    - `class Gates(Protocol)`, with `gates(...) -> list[GateEntry]` and `add_gate(gate: GateEntry) -> None`.

    The parameters are copied from `Ledger`'s methods.
  - `Ledger.open(..., concept: ConceptEntry | None = None)`. Inside `ledger.store`, rows are built with
    `Row(**entry.model_dump())`, and entries are returned with `Entry.model_validate(row)`.
  - `studio/exploration/tools.py` builds a `ConceptEntry`, and `studio/presentation/nodes.py` builds a `GateEntry`.

- [ ] **Step 1: pin the chain before changing the API.** In `tests/test_ledger.py`, write
  `test_a_concept_written_through_an_entry_chains_like_the_row` and
  `test_a_gate_written_through_an_entry_chains_like_the_row`. Each one:
  - fixes the clock with `monkeypatch.setattr("agency.ledger.store.now", lambda: "2026-01-01T00:00:00+00:00")`;
  - writes one fixed concept (through `open(..., concept=...)`) or one fixed gate, through today's row API;
  - asserts `verify_chain()` passes;
  - asserts that the newest event's hash, read the way `verify_chain` reads it, equals a constant.

  Copy the constant from the first run on today's code. The test passes on `HEAD`.
- [ ] **Step 2:** switch both tests to build a `ConceptEntry` and a `GateEntry`, with the same values. Run them.
  Expected: FAIL on the import of `ConceptEntry`.
- [ ] **Step 3:** implement. The two tests pass with the constants unchanged.
  `git grep -n "ConceptRow\|GateRow" src --exclude-dir=ledger` finds nothing.
- [ ] **Step 4:** `make check` exits 0. Handoff with `refactor(ledger): let concepts and gates cross the boundary as entries`.

### Task 9: proofs cross the boundary as entries

Kind: refactor. Same pattern as Task 8: pin the chain with a fixed clock on today's code, switch the tests to
entries, then implement.

- Covers `EvidenceEntry`, `RenderEntry` and `DerivationEntry`, under `class Proofs(Protocol)`. Its methods are
  `add_evidence`, `evidence`, `add_render`, `renders_of`, `add_derivation` and `derivations`.
- Callers: `qa/evidence.py`, `workshop/render.py` and `workshop/master.py`.
- Tests:
  - `test_evidence_written_through_an_entry_chains_like_the_row`;
  - `test_a_render_written_through_an_entry_chains_like_the_row`;
  - `test_a_derivation_written_through_an_entry_chains_like_the_row`.
- Handoff with `refactor(ledger): let proofs cross the boundary as entries`.

### Task 10: usage, kept artifacts, runs and events cross the boundary as entries

Kind: refactor. Same pattern as Task 8.

- Covers:
  - `UsageEntry`, under `Usage(Protocol)`: `record_usage`, `spent`, `usage`;
  - `ArtifactEntry`, under `KeptArtifacts(Protocol)`: `record_artifacts`, `artifacts`, `artifacts_with`,
    `all_artifacts`;
  - `RunEntry` and `JudgmentEntry`, under `Runs(Protocol)`: `record_run`, `runs`, `run`, `record_judgment`,
    `judgments`, `comparison`;
  - `EventEntry`, returned by `history`;
  - `OperationEntry`, returned by `operations`.
- Callers: `gateway/client.py`, `artifacts/keeping.py`, `entrypoints/cli/render.py` and the agents and toolkit
  modules that read `history`.
- Tests: one `..._chains_like_the_row` for each written family.
- Final check: `git grep -n "from agency.ledger.models" src --exclude-dir=ledger` finds nothing.
- Handoff with `refactor(ledger): let usage, artifacts, runs and events cross the boundary as entries`.

### Task 11: the engine depends on ledger ports, not on the SQLite ledger

Kind: refactor, plus one contract. It closes STR-003.

**Interfaces:**
- Produces, in `agency.contracts.ledger`:
  - `class Tickets(Protocol)`, with `open`, `apply`, `spec`, `status`, `children`, `history`, `delivered`,
    `tickets`, `project_of`, `inputs` and `project`;
  - `class Operations(Protocol)`, with `operation`, `operations` and `record_operation`;
  - `class LedgerPort(Tickets, Operations, Concepts, Gates, Proofs, Usage, KeptArtifacts, Runs, Protocol)`.
- Consumes the concern ports of Tasks 8–10. Every annotation `Ledger` outside the composition roots becomes the
  narrowest port the code uses:
  - `gateway.client`: `Usage`;
  - `artifacts.keeping`: `KeptArtifacts`;
  - `qa.evidence`: `Proofs`;
  - `ToolContext`, `Crew`, `AgentRunner` and `agents.prompts`: `LedgerPort`.

- [ ] **Step 1: write the failing tests.**
  - In `tests/test_ledger.py`, a pyright-checked conformance test:

```python
def test_the_sqlite_ledger_is_a_ledger_port(tmp_path: Path) -> None:
    port: LedgerPort = Ledger(tmp_path / "l.sqlite")  # pyright checks every method of the port here
    assert port is not None
```

  - In `tests/test_server.py`, a guard test `test_only_the_composition_roots_import_the_sqlite_ledger` for the new
    contract below.

  Run them. Expected: FAIL on the import of `LedgerPort`.
- [ ] **Step 2:** add the ports, switch the annotations and imports, and add the contract:

```toml
[[tool.importlinter.contracts]]
name = "only the composition roots reach the SQLite ledger (ADR-0058)"
type = "forbidden"
source_modules = [ "...every top-level package but agency.ledger, agency.process and agency.entrypoints, plus agency.process.graph..." ]
forbidden_modules = ["agency.ledger"]
```

- [ ] **Step 3:** prove the contract bites on a scratch copy: `from agency.ledger import Ledger` in
  `studio/shared.py` → BROKEN. `make check` exits 0. Handoff with
  `refactor(contracts): put the ledger behind its ports`.

### Task 12: the sandbox gets a port

Kind: refactor.

**Interfaces:**
- Produces, in `agency.contracts.sandbox`:
  - `Completed`, moved verbatim from `workshop.sandbox`;
  - `class SandboxPort(Protocol)`, whose members are those that `toolkit`, `qa` and `studio` use: `work`, `run`,
    `with_mount` and `python`, copied from `Sandbox`.
- Every annotation `Sandbox` outside `workshop` and the composition roots becomes `SandboxPort`. `ToolContext` is
  included.
- `Crew` gains `sandbox_for: Callable[[str], SandboxPort]`, which `process.graph.build` constructs.
  `studio/delivery/nodes.py` no longer imports `workshop.sandbox`.

- [ ] **Step 1:** `test_the_bwrap_sandbox_is_a_sandbox_port`, in the same style as Task 11's conformance test,
  in `tests/test_qa_gates.py`. Run it. Expected: FAIL on the import.
- [ ] **Step 2:** implement. Check with `git grep -n "workshop.sandbox import\|workshop import.*sandbox" src/agency/studio src/agency/toolkit src/agency/qa`:
  it finds nothing.
- [ ] **Step 3:** `make check` exits 0. Handoff with `refactor(contracts): put the sandbox behind a port`.

### Task 13: a scope probe made on a copied sandbox counts for the original

Kind: bug fix. This is the plan A final review's deferred minor 3.

The bug: `with_mount` copies `_scope_checked`. A probe made on the copy never sets the original's flag, so every
check probes `systemd-run` again when a check is an instance's first sandbox command.

- [ ] **Step 1: write the failing test**, in `tests/test_qa_gates.py`:
  `test_a_probe_on_a_mounted_copy_counts_for_the_original`. It uses a counting stub for the probe, runs a command
  on `sandbox.with_mount(...)` and then one on `sandbox`, and asserts that the probe ran once. Run it. Expected:
  FAIL, 2 probes.
- [ ] **Step 2:** fix it by sharing the probe result between the original and its copies, in one mutable holder
  that `copy.copy` keeps by reference. Do not add a class-level cache: sandboxes with different toolchains must
  not share it.
- [ ] **Step 3:** `make check` exits 0. Handoff with `fix(workshop): probe the scope once for a sandbox and its mounted copies`.

## Phase 4: domain and application per slice (item 4)

Every task in this phase follows the same steps, and its brief adds the names below:
1. Write the domain unit tests in `tests/test_domain_<slice>.py`. Each refusal or note is asserted with its exact
   Italian text, copied from the tool or node that holds it today. Expected: FAIL on the import.
2. Move each rule into `domain.py`, verbatim. The tool or node calls it.
3. Move each node body into `application.py`, as a function of `(crew, state)` that returns `ProjectUpdate`,
   `Route` or ticket lists. `nodes.py` keeps only the LangGraph glue: `Send`, `interrupt` and the mapping of
   `END_ROUTE`. Prove the move with plan A's AST comparison (closure body against application body, after the
   documented renames).
4. The flow tests and the request snapshots pass unchanged. `make check` exits 0. The handoff message is
   `refactor(<slice>): split the slice into domain, application and adapters`.

The application functions have names that differ from the node factories, so `nodes.py` can import them by
name.

| Task | Slice | `domain.py` | `application.py` |
|---|---|---|---|
| 14 | exploration | <ul><li>`banned_exclusions(assets: list[str], excluded: list[str]) -> list[str]`</li><li>`explorer_assignments(directions: dict[str, str], levers: list[str], explorers: int) -> list[tuple[str, str, str]]`</li><li>`exploration_spec(...) -> TicketSpec`: today's spec in `plan_exploration`, with keyword parameters for every value it reads</li><li>`plan_note(explorers: int, client_note: str) -> str`</li></ul> | <ul><li>`start_round(crew, state) -> ProjectUpdate`</li><li>`explorers_to_run(crew, state) -> list[str] \| Route`</li><li>`explore_one(crew, ticket: str) -> None`</li></ul> |
| 15 | selection | <ul><li>`rating_refusal(rated: set[str], letters: set[str]) -> str \| None`</li><li>`selection_refusal(chosen: list[str], available: set[str]) -> str \| None`, with `MAX_DEVELOPED = 3`</li><li>`board_review_spec(turn: int, root: str) -> TicketSpec`</li><li>`concept_sheets(cards: list[tuple[str, ConceptCard]]) -> str`</li><li>`selection_note(folder: str) -> str`</li></ul> | <ul><li>`build_board(crew, state) -> ProjectUpdate`</li><li>`review_board(crew, state) -> ProjectUpdate`</li><li>`choose_concepts(crew, state) -> ProjectUpdate`</li></ul> |
| 16 | proposal | <ul><li>`proposal_title(anon: str, turn: int) -> str`</li><li>`proposal_spec(...) -> TicketSpec`</li></ul> | <ul><li>`open_proposals(crew, state) -> ProjectUpdate`</li><li>`proposals_to_run(crew, state) -> list[str] \| Route`</li><li>`develop(crew, ticket: str) -> None`</li></ul> |
| 17 | presentation | <ul><li>`draft_refusal(letters: list[str], available: set[str], recommended: str \| None) -> str \| None`</li><li>`proposals_digest(items: list[tuple[str, str, ConceptCard]]) -> str`</li><li>`concept_choice(decision: Decision, options: list[str]) -> tuple[bool, str]`</li></ul> | <ul><li>`present_proposals(crew, state) -> ProjectUpdate`</li><li>`concept_gate_request(crew, state) -> ConceptGate`</li><li>`record_concept_decision(crew, state, decision: Decision) -> ProjectUpdate`</li></ul>The `document as presentation` alias is dropped, both here and in the tests. |
| 18 | refinement | <ul><li>`opening_refusal(rules: StudioRules, actor: str, assignee: str) -> str \| None`</li><li>`rework_refusal(note: str) -> str \| None`</li><li>`rejection_refusal(reason: str) -> str \| None`</li><li>`production_title(anon: str, turn: int) -> str`</li><li>`production_spec(...) -> TicketSpec`</li></ul> | <ul><li>`open_production(crew, state) -> ProjectUpdate`</li><li>`direct(crew, state) -> ProjectUpdate`</li><li>`run_team(crew, state) -> ProjectUpdate`</li></ul> |
| 19 | delivery | `acceptance_refusal(problems: list[str]) -> str` | <ul><li>`final_gate_request(crew, state) -> FinalGate`</li><li>`record_final_decision(crew, state, decision: Decision) -> ProjectUpdate`</li></ul> |

A test that pins an exact value, for Task 14:

```python
def test_banned_exclusions_finds_an_asset_inside_an_exclusion() -> None:
    assert banned_exclusions(["Merlo"], ["merlo stilizzato", "gradienti", "3D"]) == ["merlo stilizzato"]
```

Each `opening_refusal` case gets its own test, named `test_opening_refusal_<case>`. The cases are: the sender
`org.json` does not allow, the unknown role, the role without a prompt, and the allowed role.

### Task 20: domain and application import no framework

Kind: build/DX. It closes M1.7's exit criterion 4.

**Files:**
- Modify: `pyproject.toml`, adding two contracts.
  - "a slice's domain depends only on the contracts (ADR-0021)". Its `source_modules` are every
    `agency.studio.<slice>.domain` and `agency.insights.domain`. Its `forbidden_modules` are every `agency`
    package but `agency.contracts`, plus the frameworks.
  - "domain and application import no framework (ADR-0021)". Its `source_modules` are every studio and insights
    `domain` and `application`. Its `forbidden_modules` are:
    - the frameworks: `anthropic`, `langgraph`, `langchain_core`, `sqlmodel`, `sqlalchemy`, `alembic`, `django`,
      `ninja`, `opentelemetry` and `PIL`;
    - the adapters: `agency.ledger`, `agency.gateway`, `agency.process`, `agency.agents` and
      `agency.workshop.sandbox`.

    It sets `allow_indirect_imports = true`, because `contracts.media` imports PIL for the adapters.
- Test: a guard in `tests/test_server.py` that every `domain.py` and `application.py` on disk is in both lists.

- [ ] **Step 1:** write the guard. Expected: FAIL. Add the contracts. `uv run lint-imports` reports them kept.
- [ ] **Step 2:** prove each contract bites on a scratch copy:
  - `from langgraph.graph import END` in `studio/selection/application.py` → BROKEN;
  - `from agency.studio import shared` in `studio/selection/domain.py` → BROKEN.
- [ ] **Step 3:** `make check` exits 0. Handoff with `build(imports): keep domain and application free of frameworks`.

## Phase 5: the test pyramid and the large files (item 6)

### Task 21: the flow tests split by slice

Kind: move. `tests/test_agent_flow.py` (2,228 lines) and `tests/test_sketch_flow.py` (1,340 lines) become one file
per subject:
- `test_flow_<slice>.py` for each slice the tests exercise;
- `test_flow_resume.py`;
- `test_flow_sandbox.py`;
- `test_flow_budget.py`.

The rule: a test goes to the slice whose node or tool it drives first. A helper that more than one new file uses
moves to `tests/support/flow.py`. The aliases `graph as workflow` and `session as runtime` are dropped.

- [ ] **Step 1:** record `uv run pytest --collect-only -q tests/test_agent_flow.py tests/test_sketch_flow.py | sort`
  into the scratchpad.
- [ ] **Step 2:** move. Each test function's body is byte-identical. Prove it with an AST comparison by name against
  `HEAD`.
- [ ] **Step 3:** the collected test names, without their file prefix, equal Step 1's list. No new file is over
  500 lines. `make check` exits 0. Handoff with `test(flow): split the flow tests by slice`.

### Task 22: the other large test files split by subject

Kind: move. Same steps as Task 21, for:
- `tests/test_hardening.py` (2,299 lines);
- `tests/test_safe_files.py` (1,299 lines);
- `tests/test_insights.py` (985 lines).

Each becomes files named after its subjects. The cut lines are the existing section comments. Where a file has
none, tests are grouped by the `agency` module they exercise first. No new file is over 500 lines.

Handoff with `test: split the hardening, safe-files and insights tests by subject`.

### Task 23: `globals.css` splits by view

Kind: move. `web/src/app/globals.css` (622 lines) keeps the base layer: tokens, layout and shared components. The
rules of each view move to `web/src/app/styles/<view>.css`, and `globals.css` imports them. The comment headers
(`/* The replay view…`, `/* Small multiples…` and the others) are the cut lines.

- [ ] **Step 1:** move. Each rule block is byte-identical.
- [ ] **Step 2:** `make check` (the Playwright suite included) exits 0. No CSS file is over 500 lines. Handoff with
  `style(web): split the global stylesheet by view`.

## Phase 6: close M1.7

### Task 24: ADR-0021, principle by principle

Kind: docs.

**Files:**
- Modify:
  - `docs/02-ROADMAP.md`:
    - items 4–7 are ticked, each with the command that reproduces it;
    - each exit criterion is ticked only after its command was run in this task;
    - a table "ADR-0021, principio per principio" gives each of the five principles and the import-linter rules
      with the command and the result that verify it.
  - `docs/01-ARCHITECTURE.md`: tree, layers and contracts, as the code is.
  - `docs/03-DATA-MODEL.md`: the owner of `.data/ops/` names `agency.toolkit.craft` too (plan A's deferred minor 1).
  - `docs/PARITY.md`:
    - the `craft-guard.py` row names `require_craft_app` in `agency.toolkit.craft` (deferred minor 2);
    - the ledger rows are updated.
  - `README.md`: the state.
  - `docs/audit/SUMMARY.md`: STR-003, STR-007 and STR-013 are marked fixed, with their commits.

- [ ] **Step 1:** run every command in the table, and copy each result in.
- [ ] **Step 2:** `make check` exits 0. Handoff with `docs: close M1.7 with ADR-0021 checked principle by principle`.

After Task 24 comes the whole-branch review by a fresh reviewer, as in plan A. Then M1.7 is closed in the roadmap,
and M1.8 is next.
