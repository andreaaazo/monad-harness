# M1.7 slice architecture, plan A (roadmap items 1–3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** split the engine into the package tree ADR-0021 describes, without changing one byte of what the model
receives. This plan covers roadmap M1.7 items 1–3: the cycles, `tools/surface.py` and `graph/workflow.py`.

**Architecture:** the work happens in three steps.
- Break the last import cycle, `tools → qa`, and pin acyclicity with an import-linter contract.
- Split the agent tools by owner. The shared kit goes to `agency.toolkit`, the phase tools go to the slices of
  `agency.studio`, and the catalogue and `Toolbox` go to `agency.agents.toolbox`.
- Move the graph nodes into the slices. `agency.process` composes the graph and runs sessions.

Each task does one kind of change: a move, a refactor, or a build/DX change. Moves change imports only.

**Tech Stack:** Python 3.13, uv, pytest, ruff, pyright, import-linter 2.15 (it has `acyclic_siblings`, `layers` and
`independence`), LangGraph, grimp.

**Spec:**
- `docs/02-ROADMAP.md`, section M1.7;
- `docs/adr/0021-monolite-modulare-a-slice.md`;
- `docs/adr/0055-il-quality-gate-prima-di-merlo4.md` and `docs/adr/0056-m1-7-senza-prova-dal-vivo.md`;
- the deferred findings STR-003, STR-004, STR-007, STR-013, SIM-004 and SIM-012 in `docs/audit/SUMMARY.md`. Their
  detail is in `docs/audit/50-structure.md` and `70-simplification.md`.

## Decisions for Andrea (before Task 0)

Each one is recorded in ADR-0057 (Task 0), with the answer Andrea gives.

| # | Decision | Recommended | Why |
|---|---|---|---|
| D1 | Rename `agency.tools` to `agency.workshop` once the agent tools have left it (Task 4) | Yes | After the split, "tools" would mean three things: the sandbox and Craft machinery, the kit agent tools are made of, and the tools the model calls. If no, skip Task 4 and read `workshop` as `tools` below. |
| D2 | The slices live under one parent package, `agency.studio`: `exploration`, `selection`, `proposal`, `presentation`, `refinement`, `delivery` | Yes | ADR-0021's six capabilities, in English. One new top-level package instead of six, so the five hand-kept import-linter lists (see Global Constraints) grow by one entry, not six. |
| D3 | The layers, bottom to top: `contracts` → platform (`config`, `registry`, `ledger`, `gateway`, `telemetry`, `artifacts`, `workshop`) → `qa` → `toolkit` → `studio` → `agents` → `process` → entry points. `evaluation` and `insights` stay on `contracts` only | Yes | `agents` sits above `studio`, because the catalogue in `agents.toolbox` imports the slices' tools. Nodes reach the runner through the `Runner` protocol in `studio.shared`. This keeps the default `Toolbox(context)` and the eight `AgentRunner(...)` constructions in the tests unchanged. |
| D4 | The QA scripts are mounted only when a check runs, not in every sandboxed command (Task 1) | Yes | It narrows the sandbox. Today every `compute`, `craft_run` and `render` sees `/opt/agency-qa`. No prompt or registry entry mentions it (`grep -rn agency-qa prompts registry` finds nothing). |

## Target tree after this plan

| Package | Holds | From |
|---|---|---|
| `agency.workshop` | `sandbox.py` (with `Sandbox.with_mount`), `files.py`, `craft.py`, `master.py`, `render.py` (`proof_stem`), `board.py` | `agency.tools` minus `surface` and `presentation`. `board.py` stays shared: `submit_concept` (exploration) calls `board.mark_problem`, and `make_board` (selection) calls `board.build` |
| `agency.qa` | `checks.py` (owns `QA_MOUNT`, `SCRIPTS`), `delivery.py`, `evidence.py`, `scripts/` (unchanged path) | unchanged |
| `agency.toolkit` | `base.py`: `Refused`, `ToolContext`, `Strict`, `Tool`, `definition`, `result_text`, `viewed`, `replayed`, `tracer`. `files.py`, `craft.py`, `review.py`, `closing.py`: the shared agent tools, each module with `TOOLS: tuple[Tool, ...]` | `tools/surface.py` |
| `agency.studio` | `shared.py`: `ProjectState`, `Runner`, `Crew`, `Node`, `Router`, `attempt`, `rework_note`, `copy_capped`. One subpackage per slice with `tools.py` and `nodes.py`; `presentation/document.py` | `tools/surface.py`, `graph/workflow.py`, `tools/presentation.py` |
| `agency.agents` | `loop.py`, `prompts.py`, `transcript.py`, and `toolbox.py`: `TOOLS`, `BASE`, `AUTHOR`, `REVIEWER`, `DIRECTOR`, `KIND_TOOLS`, `role_tools`, `tools_for`, `Toolbox` | `tools/surface.py` |
| `agency.process` | `graph.py`: `build`, `Graph`, the routers. `session.py`: `Session`, `open_session`, `ProjectLock`, the errors | `graph/workflow.py`, `runtime.py` |

Removed by the end: `agency.tools`, `agency.graph` and `agency.runtime`.

## Global Constraints

- **The request snapshots stay byte-identical.** `tests/test_request_snapshots.py` must pass with
  `tests/snapshots/requests/*.json` untouched. So these never change:
  - the tool names and descriptions;
  - the schema class names. `Application`, `BoardRating`, `Lever`, `ProposalText`, `Medium`, `TicketType` and
    `Verdict` appear in the snapshots as `$defs`;
  - the field names and their order, and the `strict` and `eager_input_streaming` flags.
- **Move units are byte-identical apart from imports.** In a move task every moved or split file differs from
  its source only in `import`/`from` lines. Check with `diff <(git show HEAD:<old>) <new>` and read the result.
- **The flow tests change only their imports.** `tests/test_agent_flow.py`, `tests/test_sketch_flow.py` and
  `tests/test_recording.py` may change import lines and string targets of `monkeypatch.setattr` only, and must
  pass. Read the `git diff` of these three files.
- **These names stay as they are:** the graph node names and the `ProjectState` fields; the span names
  (`tool.call`), the span attributes (`agency.tool`, `agency.instance`) and the tracer scopes (`"agency.tools"`,
  `"agency.agents"`, `"agency.gateway"`), even when the module that holds them moves.
- **Some paths are frozen.** `src/agency/qa/scripts/` is fixed by its bytes (`tests/fixtures/qa_scripts.json`,
  `tests/test_language.py` `FROZEN`). `src/agency/ledger/migrations/` and `legacy/` are not touched.
- **The import-linter lists are kept by hand.** Every top-level package of `src/agency` must appear in five lists
  of `pyproject.toml`:
  - the engine-imports-no-Django `source_modules`;
  - the `forbidden_modules` of the insights, server and evaluation contracts;
  - the anthropic contract's `source_modules`.

  `tests/test_server.py` fails when a package is missing. Every task that adds, renames or removes a top-level
  package updates all five lists.
- **Git.**
  - Never run a git command that writes. Move files with plain `mv`.
  - Every task ends with `make check` exiting 0, then this block, and waits for Andrea's "committed":
    ```text
    READY FOR COMMIT
    Message: <the task's message>
    Files: <every file changed>
    Verification: <commands run and their results>
    ```
- **Docs follow the code in the same task.** A task that moves a module fixes every reference to its old path
  under `docs/` (not `docs/audit/`, not `docs/adr/`, which are historical) and in `docs/PARITY.md`. Find them with
  `git grep -n "<old dotted path>\|<old file path>" -- docs ':!docs/audit' ':!docs/adr'`.
- **Language.** Code, comments and docstrings in English. Documents and user-facing strings in Italian.
- **One kind of change per task:** move, refactor, or build/DX. A new decision goes in an ADR (Task 0).

## Review Focus

These are the conditions most likely to break silently. Each line names the test that pins it and the task that
owns it.

- **A closing tool replayed after a crash must close again with the same outcome.** A tool re-run on resume is
  replayed from the ledger, not run again. The mapping moves from `CLOSE_ALWAYS` and `_restore` onto each `Tool`.
  Pinned by `tests/test_toolbox.py` (Task 5) and by the existing
  `test_interruption_resumes_without_repeating_effects` and `test_interrupted_exploration_resumes_without_repeating_work`.
- **A check must still find its script after the mount moves.** That holds both in an instance's sandbox and in
  the sandbox the final gate builds for acceptance. Pinned by the Task 1 tests and by the existing sandboxed
  `test_author_cannot_deliver_without_master_then_can`, which runs `svg_audit` for real.
- **A copied sandbox must keep everything it had.** `with_mount` must keep `ops`, `toolchain` and `read_only`.
  Without them, `craft_run` inside a check would lose `/ops`. Pinned by the Task 1 argv equality test.
- **A new top-level package must not slip past the forbidden lists.** Pinned by
  `test_every_slice_contract_forbids_every_engine_package` and the two sibling tests in `tests/test_server.py`,
  which run in every task's `make check`.
- **The fingerprint's code map changes with every move.** `agency compare` across this plan shows every file as
  changed. That is expected and needs no fix. `tests/test_runs.py:213` asserts
  `src/agency/telemetry/fingerprint.py` is in the map, and that file does not move in plan A.

---

### Task 0: ADR-0057, the package tree

**Files:**
- Create: `docs/adr/0057-l-albero-dei-pacchetti-del-motore.md`, in Italian.
- Modify: `docs/adr/README.md` (one row); `docs/02-ROADMAP.md`. M1.7's intro links ADR-0057 and this plan.

- [ ] **Step 1:** write the ADR with Contesto, Decisione and Conseguenze, in the form of the existing ADRs. It
  covers:
  - D1–D4 as Andrea answered them;
  - the target tree table;
  - the constraint that request snapshots and node names stay the same.
- [ ] **Step 2:** check the links: every relative link in the three files resolves.
- [ ] **Step 3:** `make check` exits 0. Handoff with
  `docs(adr): record the engine's package tree for M1.7 (ADR-0057)`.

### Task 1: qa owns the QA scripts mount, and uses only public workshop names

Kind: refactor. It closes the mount half of STR-004.

**Files:**
- Modify:
  - `src/agency/tools/sandbox.py`: drop `QA_MOUNT` and the `qa/scripts` bind (lines 17 and 156–157 today). Add
    `with_mount`.
  - `src/agency/tools/render.py`: rename `_stem` to `proof_stem`, with its two call sites.
  - `src/agency/qa/checks.py`: add `QA_MOUNT` and `SCRIPTS`, use `with_mount` in `_script`, import `proof_stem`.
- Test: `tests/test_qa_gates.py`.

**Interfaces:**
- Produces:
  - `Sandbox.with_mount(self, source: Path, target: str) -> Sandbox`: a new `Sandbox` with the same `work`,
    `toolchain`, `read_only` and `ops`, whose `argv` adds `["--ro-bind", str(source), target]` after the
    `read_only` binds. It keeps the scope check already done.
  - `agency.qa.checks.QA_MOUNT = "/opt/agency-qa"`.
  - `agency.qa.checks.SCRIPTS = Path(__file__).resolve().parent / "scripts"`.
  - `agency.tools.render.proof_stem(relative: str) -> str`, with the old `_stem`'s body.

- [ ] **Step 1: write the failing tests**

```python
def test_a_plain_sandbox_does_not_mount_the_qa_scripts(tmp_path: Path) -> None:
    assert checks.QA_MOUNT not in Sandbox(tmp_path).argv(["true"])


def test_a_check_mounts_the_qa_scripts_and_keeps_everything_else(tmp_path: Path) -> None:
    ops = tmp_path / "ops"
    plain = Sandbox(tmp_path / "w", toolchain=tmp_path / "t", read_only=(tmp_path,), ops=ops).argv(["true"])
    mounted = (
        Sandbox(tmp_path / "w", toolchain=tmp_path / "t", read_only=(tmp_path,), ops=ops)
        .with_mount(checks.SCRIPTS, checks.QA_MOUNT)
        .argv(["true"])
    )
    at = mounted.index(checks.QA_MOUNT)
    assert mounted[at - 2 : at + 1] == ["--ro-bind", str(checks.SCRIPTS), checks.QA_MOUNT]
    assert mounted[: at - 2] + mounted[at + 1 :] == plain


def test_the_qa_scripts_are_the_frozen_folder() -> None:
    assert checks.SCRIPTS == REPO_ROOT / "src/agency/qa/scripts"
```

- [ ] **Step 2:** `uv run pytest tests/test_qa_gates.py -q -k "qa_scripts or mounts"` fails. The reason is
  `AttributeError` on `checks.QA_MOUNT` or `with_mount`.
- [ ] **Step 3:** make the changes in Files.
- [ ] **Step 4:** the new tests pass. `uv run pytest tests/test_agent_flow.py -q -k
  author_cannot_deliver_without_master` passes too: it runs `svg_audit` in a real sandbox.
- [ ] **Step 5:** `git grep -n "_stem\|QA_MOUNT\|qa/scripts" src` shows `proof_stem`, `QA_MOUNT` and `SCRIPTS`
  only where the Interfaces say. `make check` exits 0. Handoff with
  `refactor(qa): mount the QA scripts only for a check, and name the proof stem in public`.

### Task 2: the agent tools leave `tools`, which breaks the last cycle

Kind: move.

**Files:**
- Move: `mv src/agency/tools/surface.py src/agency/agents/toolbox.py`.
- Modify:
  - imports in `src/agency/agents/loop.py` and `src/agency/graph/workflow.py`;
  - imports in the tests that import `agency.tools.surface` or `from agency.tools import surface`:
    `test_agent_flow`, `test_artifacts`, `test_explicit_types`, `test_hardening`, `test_ledger`, `test_media`,
    `test_qa_gates`, `test_registry`, `test_safe_files`, `test_sketch_flow`;
  - `docs/04-TOOLS.md`: "definito in `agency.tools`" becomes `agency.agents.toolbox`;
  - `docs/PARITY.md`: the destinations that name `agency.tools.surface`.

- [ ] **Step 1:** move the file and update the imports.
- [ ] **Step 2:** check the move. `diff <(git show HEAD:src/agency/tools/surface.py) src/agency/agents/toolbox.py`
  shows import lines only. Here it shows none, because the module's own imports are absolute.
- [ ] **Step 3:** check the cycle. Write `<scratch>/acyclic.toml` with `[tool.importlinter]`
  `root_package = "agency"` and the contract of Task 3. Then `uv run lint-imports --config <scratch>/acyclic.toml
  --no-cache` reports it KEPT. Before this task it reported `.tools -> .qa (3 imports)` as the only cycle in
  `agency`.
- [ ] **Step 4:** the snapshot and flow tests pass unchanged. `make check` exits 0. Handoff with
  `refactor(agents): move the agent tools out of tools, breaking the tools-qa cycle`.

### Task 3: acyclicity becomes a contract

Kind: build/DX.

**Files:**
- Modify: `pyproject.toml`, adding the contract below.
- Modify: `docs/02-ROADMAP.md`. Tick M1.7 item 1, with the way to reproduce it: `uv run lint-imports`.

```toml
[[tool.importlinter.contracts]]
name = "no import cycles between sibling modules, at any depth (STR-004)"
type = "acyclic_siblings"
ancestors = ["agency"]
```

- [ ] **Step 1:** add the contract. `uv run lint-imports` reports it KEPT.
- [ ] **Step 2:** prove the contract bites.
  - Copy `src/` and `pyproject.toml` into `<scratch>/bite/`.
  - Add `from agency.qa import evidence` at the top of `<scratch>/bite/src/agency/tools/files.py`.
  - Run `PYTHONPATH=<scratch>/bite/src uv run --no-sync lint-imports --config <scratch>/bite/pyproject.toml
    --no-cache`. It reports this contract BROKEN.
  - Delete `<scratch>/bite/`.
- [ ] **Step 3:** `make check` exits 0. Handoff with `build(imports): forbid import cycles between sibling modules`.
  This is also the first contract of the M1.8 spec (§6.5) for `agency`, active from day one.

### Task 4: `tools` becomes `workshop` (only if D1 is yes)

Kind: move.

**Files:**
- Move: `mv src/agency/tools src/agency/workshop`.
- Modify:
  - every `agency.tools` import in `src/` and `tests/`, with `git grep -n "agency.tools\b"` finding them;
  - `pyproject.toml`: the five lists;
  - the docs that name `agency.tools.*` or `src/agency/tools/`: `docs/04-TOOLS.md`, `docs/06-SECURITY.md`,
    `docs/PARITY.md` and `docs/solutions/**`.

- [ ] **Step 1:** move and update. The tracer in `agents/toolbox.py` keeps the literal `"agency.tools"`.
- [ ] **Step 2:** check the move with `git grep -n "agency\.tools\b\|src/agency/tools/" -- src tests docs
  ':!docs/audit' ':!docs/adr'`. It finds only the tracer literal.
- [ ] **Step 3:** `make check` exits 0. Handoff with
  `refactor(workshop): rename tools to workshop now that the agent tools have left it`.

### Task 5: each tool says how it closes on replay; shared helpers become public

Kind: refactor, all inside `src/agency/agents/toolbox.py`.

**Interfaces:**
- Produces:
  - `Tool` gains two fields, `closes: OutcomeState | None = None` and
    `on_replay: Callable[[str], Outcome | None] | None = None`.
  - `Toolbox._restore(name, stored)` sets `finished` in one of two ways:
    - to `Outcome(state=tool.closes, note="ripreso dopo un'interruzione")` when `closes` is set;
    - to `tool.on_replay(stored)`, when that is not `None`, otherwise.
  - `CLOSE_ALWAYS` is deleted, and its six pairs become `closes=` on those tools.
  - `_closed_by_selection(stored: str) -> Outcome`, `_closed_by_draft(stored: str) -> Outcome | None` and
    `_closed_by_presentation(stored: str) -> Outcome` take the three branches of today's `_restore`.
  - `_viewed` becomes `viewed`, and `_replayed` becomes `replayed`. Tools that will live in different modules
    share them (the helper table in Task 6).
- Test: `tests/test_toolbox.py` (new).

- [ ] **Step 1: write the failing tests**

```python
CLOSING = {
    "deliver": OutcomeState.DELIVERED,
    "block": OutcomeState.BLOCKED,
    "hand_off": OutcomeState.HANDED_OFF,
    "plan_exploration": OutcomeState.HANDED_OFF,
    "submit_concept": OutcomeState.DELIVERED,
    "reject_concept": OutcomeState.CONCEPT_REJECTED,
}
REPLAYED = {"select_concepts", "draft_presentation", "present_concepts"}


def test_the_closing_tools_keep_their_outcomes() -> None:
    assert {n: t.closes for n, t in TOOLS.items() if t.closes is not None} == CLOSING


def test_only_the_three_choice_tools_derive_their_outcome_from_the_stored_result() -> None:
    assert {n for n, t in TOOLS.items() if t.on_replay is not None} == REPLAYED


def test_a_replayed_selection_closes_by_what_it_chose() -> None:
    chose = SelectConcepts(chosen=["A"], reasons="r").model_dump_json()
    none = SelectConcepts(chosen=[], reasons="r").model_dump_json()
    assert TOOLS["select_concepts"].on_replay(chose).state is OutcomeState.SELECTED
    assert TOOLS["select_concepts"].on_replay(none).state is OutcomeState.NO_CONCEPT


def test_a_replayed_draft_closes_only_when_no_proposal_holds_up() -> None:
    assert TOOLS["draft_presentation"].on_replay('{"pagine": ["p.png"]}') is None
    assert TOOLS["draft_presentation"].on_replay('{"ok": true}').state is OutcomeState.NO_CONCEPT


def test_a_replayed_presentation_closes_by_its_proposals() -> None:
    empty = PresentConcepts(proposals=[], recommended=None, reasons="r").model_dump_json()
    one = PresentConcepts(
        proposals=[ProposalText(letter="A", title="t", idea="i", why="w", risk="r")],
        recommended="A",
        reasons="r",
    ).model_dump_json()
    assert TOOLS["present_concepts"].on_replay(empty).state is OutcomeState.NO_CONCEPT
    assert TOOLS["present_concepts"].on_replay(one).state is OutcomeState.PRESENTED
```

- [ ] **Step 2:** `uv run pytest tests/test_toolbox.py -q` fails with `AttributeError: 'Tool' object has no
  attribute 'closes'`.
- [ ] **Step 3:** make the changes in Interfaces.
- [ ] **Step 4:** the tests pass. So do `test_interruption_resumes_without_repeating_effects`,
  `test_interrupted_exploration_resumes_without_repeating_work` and
  `test_empty_draft_goes_back_to_exploration_and_survives_a_resume`.
- [ ] **Step 5:** `make check` exits 0. Handoff with
  `refactor(agents): let each tool say how it closes when replayed`.

### Task 6: the shared agent tools move to `agency.toolkit`

Kind: move. Each symbol moves unchanged. Each new tool module (`files`, `craft`, `review`, `closing`) ends with
`TOOLS: tuple[Tool, ...]`, listing its `Tool(...)` entries cut from the `TOOLS` dict of `agents/toolbox.py`. That dict
is then built from those tuples and from the `Tool(...)` entries still in `agents/toolbox.py`, keeping the same 28
names.

| Destination | Symbols |
|---|---|
| `src/agency/toolkit/base.py` | `tracer`, `Refused`, `ToolContext`, `Strict`, `Tool`, `definition`, `result_text`, `viewed`, `replayed` |
| `src/agency/toolkit/files.py` | `TEXT_FILES`, `IMAGE_SIDE`, `IMAGE_BYTES`, `IMAGE_MEDIA`, `HIDDEN`, `_text_only`, `ReadFile`, `ListFiles`, `WriteFile`, `ReadSkill`, `ViewImage`, `read_file`, `list_files`, `write_file`, `read_skill`, `view_image` |
| `src/agency/toolkit/craft.py` | `EXPORT_OPTIONS`, `NO_OPS`, `CRAFT_APP`, `require_craft_app`, `Render`, `CraftSearch`, `CraftDescribe`, `CraftRun`, `Compute`, `ExportMaster`, `render_tool`, `craft_search`, `craft_describe`, `craft_run`, `compute`, `export_master` |
| `src/agency/toolkit/review.py` | `RunCheck`, `Observe`, `Judge`, `RecordRequirement`, `_recorded`, `_check_result`, `_seen_proof`, `run_check`, `observe`, `judge`, `record_requirement` |
| `src/agency/toolkit/closing.py` | `Deliver`, `Block`, `deliver`, `block` |

- [ ] **Step 1:** create the package: an `__init__.py` with a one-line docstring, plus the five modules. Update
  imports in `src/` and `tests/`. Add `agency.toolkit` to the five lists in `pyproject.toml`.
- [ ] **Step 2:** prove every moved symbol is unchanged. For each destination, the lines of the moved definitions
  match the old `surface.py` text byte for byte. A script in the scratchpad can slice both files by top-level
  definition and compare them.
- [ ] **Step 3:** the snapshot, flow and `test_toolbox.py` tests pass, and `lint-imports` reports every contract
  KEPT. `make check` exits 0. Handoff with
  `refactor(toolkit): move the shared agent tools out of the toolbox`.

### Task 7: the phase tools move to their slices

Kind: move. Each slice module ends with `TOOLS: tuple[Tool, ...]`, plus its tool-set name lists, moved unchanged.

| Destination | Symbols |
|---|---|
| `src/agency/studio/exploration/tools.py` | `Lever`, `Application`, `PlanExploration`, `plan_exploration`, `submit_concept`, `PLAN`, `EXPLORE` |
| `src/agency/studio/selection/tools.py` | `BoardRating`, `RateBoard`, `SelectConcepts`, `rate_board`, `select_concepts`, `_closed_by_selection`, `BOARD`, `SELECT` |
| `src/agency/studio/proposal/tools.py` | `PROPOSAL` |
| `src/agency/studio/presentation/tools.py` | `ProposalText`, `PresentConcepts`, `ConfirmPresentation`, `_delivered_proposal`, `draft_presentation`, `_drafted_pages`, `present_concepts`, `_closed_by_draft`, `_closed_by_presentation`, `PRESENT` |
| `src/agency/studio/refinement/tools.py` | `OpenTicket`, `TicketRef`, `HandOff`, `RejectConcept`, `_coming`, `open_ticket`, `_own_child`, `accept_ticket`, `rework_ticket`, `hand_off`, `reject_concept` |

What stays in `src/agency/agents/toolbox.py`: `TOOLS`, built from every `TOOLS` tuple; `BASE`, `AUTHOR`, `REVIEWER`,
`DIRECTOR`, `KIND_TOOLS`, `_without_craft`, `role_tools`, `tools_for`, which reads the slices' name lists; and
`Toolbox`.

- [ ] **Step 1:** create `src/agency/studio/__init__.py` and one `__init__.py` per slice, each with a one-line
  docstring. Move the symbols. `graph/workflow.py` imports `PresentConcepts` and `SelectConcepts` from their
  slices. Add `agency.studio` to the five lists. Update `docs/04-TOOLS.md` ("Set fisso per ruolo…") to point at
  `agency.agents.toolbox`, with the tools in `agency.toolkit` and `agency.studio`.
- [ ] **Step 2:** prove the moved symbols are byte-identical, as in Task 6 Step 2. The snapshot tests pass, which
  proves the schemas, names and order are unchanged.
- [ ] **Step 3:** `wc -l src/agency/agents/toolbox.py` is under 250. `make check` exits 0. Tick M1.7 item 2 in
  `docs/02-ROADMAP.md`. The criterion «`tools/surface.py` non esiste più» holds since Task 2, and now nothing of it
  remains in one file. Handoff with `refactor(studio): move each phase's tools into its slice`.

### Task 8: the graph nodes become factories over a crew

Kind: refactor, all inside `src/agency/graph/workflow.py`. No move yet.

**Interfaces:**
- Produces, at module level in `workflow.py`:
  - `class Runner(Protocol)`, with
    `def run(self, ticket_id: str, attempt: int = 1, rework_note: str = "", mode: str = "", exploration: int = 0) -> Outcome: ...`.
    `AgentRunner` satisfies it without importing it.
  - `@dataclass(frozen=True) class Crew`, with fields `runner: Runner`, `ledger: Ledger` and `settings: Settings`,
    and the method `work_dir(self, project: str) -> Path`, which is today's `work_dir` closure.
  - `class Node(Protocol)`, with `def __call__(self, state: Any) -> dict: ...`, for a node. LangGraph's `add_node`
    takes a callable whose parameter is named `state`, which `Callable[[Any], dict]` does not promise, and pyright
    refuses it.
  - `Router = Callable[[ProjectState], list[Send] | str]` for a router that needs the crew: `send_explorers`,
    `send_proposals` and `after_lead`.
  - `attempt(ledger, ticket) -> int`, `rework_note(ledger, ticket) -> str` and
    `copy_capped(work, source, target, limit) -> None`: today's `_attempt`, `_rework_note` and `_copy`, now public
    because several slices will use them.
  - One factory per node and per router that needs the crew, each `name(crew: Crew) -> Node`, or `-> Router` for
    the three routers:
    - `plan`, `send_explorers`, `explore`;
    - `make_board`, `board_review`, `select`;
    - `prepare_proposals`, `send_proposals`, `proposal`;
    - `present`, `concept_gate`;
    - `start_production`, `lead`, `team`, `after_lead`;
    - `client_gate`.

    `_proposal_tickets(crew, state)` becomes a module-level helper.
  - `build(runner, ledger, settings, checkpointer)` keeps its signature. It builds `Crew` and wires the nodes, by
    their current names, and the routers. `begin`, `after_board`, `follow_route` and `after_gate` stay plain
    functions, because they read only the state. `after_lead` reads the root ticket's status from the ledger, so it
    is a factory.

- [ ] **Step 1:** check the baseline. `uv run ruff check --select C901 --config "lint.mccabe.max-complexity = 10"
  src/agency/graph/workflow.py` reports `build` at 65. SIM-012 measured 63 before the audit's last fixes.
- [ ] **Step 2:** refactor. Each closure body moves unchanged into its factory's inner function, and the captured
  `runner`, `ledger`, `settings` and `work_dir` become `crew.<name>`.
- [ ] **Step 3:** the same ruff command no longer reports `build` (it drops to 2). It still reports the `select`
  factory at 11: its node body is 10, unchanged, and ruff counts one more for a nested `def`. Splitting `select`
  would change a body this task only lifts. M1.8 sets `max-complexity = 8` and splits it, with `present` (8). The
  flow, snapshot and recording tests pass unchanged. `make check` exits 0. Handoff with
  `refactor(graph): turn the graph nodes into factories over a crew`.

### Task 9: the nodes move to their slices

Kind: move.

| Destination | From `graph/workflow.py` | Other moves |
|---|---|---|
| `src/agency/studio/shared.py` | `ProjectState`, `Runner`, `Crew`, `Node`, `Router`, `attempt`, `rework_note`, `copy_capped` | |
| `src/agency/studio/exploration/nodes.py` | `plan`, `send_explorers`, `explore` | |
| `src/agency/studio/selection/nodes.py` | `make_board`, `board_review`, `select` | `board.py` stays in `workshop` (Target tree) |
| `src/agency/studio/proposal/nodes.py` | `prepare_proposals`, `send_proposals`, `proposal`, `_proposal_tickets` | |
| `src/agency/studio/presentation/nodes.py` | `present`, `concept_gate` | `mv src/agency/workshop/presentation.py src/agency/studio/presentation/document.py` |
| `src/agency/studio/refinement/nodes.py` | `start_production`, `lead`, `team` | |
| `src/agency/studio/delivery/nodes.py` | `client_gate` | `__init__.py` for the new slice |

`graph/workflow.py` keeps `build`, `Graph`, the four plain routers and the `after_lead` factory, and imports the other
factories.

- [ ] **Step 1:** move. Update the imports of `presentation` in `src/` and `tests/`, found by
  `git grep -n "workshop import presentation\|workshop.presentation"`. Update `docs/PARITY.md` if it names it.
- [ ] **Step 2:** check the moves with Task 6 Step 2's comparison, against `HEAD`'s `workflow.py` and
  `presentation.py`.
- [ ] **Step 3:** `make check` exits 0. Handoff with `refactor(studio): move the graph nodes into their slices`.

### Task 10: the process composes the graph and runs sessions

Kind: move. It also closes SIM-004: `langchain_core` is imported only by `process.session`.

**Files:**
- Move:
  - `mv src/agency/graph/workflow.py src/agency/process/graph.py`, then `rm -r src/agency/graph`.
  - `mv src/agency/runtime.py src/agency/process/session.py`, and create `src/agency/process/__init__.py`.
- Modify:
  - imports in `src/agency/cli.py` and the tests;
  - every string target `"agency.runtime.open_session"` becomes `"agency.process.session.open_session"`, in
    `test_hardening.py` (8) and `test_recording.py` (2);
  - `pyproject.toml`: the five lists drop `agency.graph` and `agency.runtime` and add `agency.process`;
  - `docs/PARITY.md`: `agency.graph`, `agency.graph.gates`.

- [ ] **Step 1:** move and update.
- [ ] **Step 2:** check that `langchain_core` and `langgraph` are where they should be.
  - `git grep -n "langchain_core" src` finds only `src/agency/process/session.py`.
  - `git grep -n "^from langgraph\|^import langgraph" src` finds only `process/`, `studio/*/nodes.py` and
    `studio/shared.py`, which needs `Send` for the `Router` type. That is the rule ADR-0021 states, and Plan B makes
    it a contract.
- [ ] **Step 3:** `make check` exits 0. Tick M1.7 item 3 in `docs/02-ROADMAP.md`. Handoff with
  `refactor(process): compose the graph and run sessions from the process package`.

### Task 11: the slices do not import each other

Kind: build/DX.

**Files:**
- Modify: `pyproject.toml`.

```toml
[[tool.importlinter.contracts]]
name = "the slices do not import each other (ADR-0021)"
type = "independence"
modules = [
  "agency.studio.exploration",
  "agency.studio.selection",
  "agency.studio.proposal",
  "agency.studio.presentation",
  "agency.studio.refinement",
  "agency.studio.delivery",
]
```

- [ ] **Step 1:** add the contract. `uv run lint-imports` reports it KEPT.
- [ ] **Step 2:** prove it bites, the way Task 3 Step 2 does. In the copy, add
  `from agency.studio.selection import nodes` to `studio/exploration/nodes.py`: the contract reports BROKEN.
- [ ] **Step 3:** `make check` exits 0. Handoff with
  `build(imports): forbid the slices from importing each other`.

---

## Plan B (roadmap items 4–7), written after Task 11

Written on 2026-11-15: `docs/superpowers/plans/2026-11-15-m1-7-plan-b-domain-ports-types.md`. The outline below is
what it started from.

Plan B gets written once plan A has landed: which rules are pure becomes visible only when each slice's code sits
apart. It must decide and cover:
- **Item 4.** What moves to a `domain.py` per slice, and what becomes an application use case with ports at the
  outer boundaries (model, ledger, sandbox, artifacts, reading). It also moves the CLI to `entrypoints/cli/`
  together with the renderer in `telemetry/report.py` (STR-007), and decides where the run fingerprint lives.
- **Item 5.**
  - A `layers` contract with D3's order.
  - STR-003's rules: `langgraph` only in `process` and `studio.*.nodes`; `sqlmodel` and `sqlalchemy` only in
    `ledger`; the ledger behind its port.
  - "Domain and application import no framework".
- **Item 6.** Unit tests on the pure rules. The flow tests stay. The four test files over 500 lines and
  `web/app/globals.css` get split by slice (STR-013).
- **Item 7, explicit types (ADR-0021 principle 2).** Added on 2026-11-15: items 1–6 leave this principle only partly
  covered. It fits with item 4, where the pure rules leave their frameworks.
  - The director phases (`mode="plan"`, `"select"`, `"present"`) and the graph routes (`ProjectState.route`) become
    types. The checkpoint must keep today's strings, or paused projects stop resuming (ADR-0021). LangGraph's
    serializer can record an enum's module and class, so prefer `Literal` types, or a `StrEnum` turned into its value
    before it enters the state. Prove it with a resume from a checkpoint written before the change.
  - The nodes return a typed partial update (a `TypedDict` with `total=False`) instead of a bare `dict`. The two
    nodes reached by `Send`, `explore` and `proposal`, take a typed payload instead of `Any`. Check first how
    LangGraph treats a node input schema that differs from the state: it can add channels to the checkpoint.
  - The role registry (`ROLES: dict[str, dict]`, and `CHECKS`) becomes typed models, passed to whoever uses it
    instead of read as a module global. Today 5 reads sit outside `agency.registry`, in `agents.toolbox`,
    `agents.loop`, `studio.refinement.tools` and `toolkit.craft`.
- **Exit check.** M1.7 closes only after ADR-0021 is checked principle by principle, each with the command that
  reproduces it. The roadmap's exit criteria carry the list.
