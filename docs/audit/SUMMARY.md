# Audit summary

The seven area reports (`10`–`70`) were written by auditors briefed to find problems. A separate reviewer, who wrote
none of them, then tried to disprove every Critical, High and Medium finding: it reread the code, checked callers,
guards and tests, reproduced each finding with new scripts, and ran 38 one-line mutants on a throwaway copy. This file
is the result. It is the input for planning the sanity refactor.

- **Code audited:** identical to `8d99a5c`. The audit branch adds only `docs/audit/` on top of it. The reports cite
  `86f51a1`, the first ID of the baseline commit, which differs from `8d99a5c` only by `docs/audit/00-baseline.md`.
- **Reviewed:** 30 findings (Critical, High and Medium). **21 Confirmed, 9 Downgraded, 0 Rejected.** No finding was
  rated too low.
- **Not reviewed:** the 79 Low and Nit findings. They are carried over as their auditors reported them.
- **Duplicates:** 1 finding is merged in full (SIM-013 into STR-006). 11 more share part of their defect with another
  finding: the shared part is tracked under one canonical ID, and each alias keeps only the part that is its own.
- **Surviving:** 108 findings: Critical 1 · High 5 · Medium 17 · Low 71 · Nit 14. As reported, the 109 findings were
  Critical 1 · High 8 · Medium 21 · Low 65 · Nit 14.
- **Per-finding detail:** each reviewed finding in its area report now ends with a `Review` line. Each alias ends with
  a `Duplicate` line.
- **Reproductions:** the reviewer's scripts lived in `/tmp/audit-review/` and do not survive a reboot. Each review line
  says enough to rebuild them.

Effort: **S** is a few lines plus a test, under about an hour. **M** is several files, or about half a day. **L** is
more than that, or needs a design decision or a new ADR. Confidence is the auditor's label. For reviewed findings, it is
raised to Confirmed where the reviewer reproduced the finding or killed it with a mutant.

## Surviving findings

| ID | Area | Severity | Confidence | File:line | Description | Effort |
|---|---|---|---|---|---|---|
| SEC-001 | SEC | Critical | Confirmed | src/agency/tools/surface.py:388 | `compute` writes through a `.ops` symlink planted by the sandbox; Alembic then runs the model's code on the host (related: SEC-003) | M |
| COR-001 | COR | High | Confirmed | src/agency/tools/surface.py:417 | `observe` and `judge` accept a render the instance viewed for an older version of the file | S |
| TST-001 | TST | High | Confirmed | src/agency/qa/checks.py:36 | No test sees a QA check fail and stop a delivery | S |
| TST-002 | TST | High | Confirmed | src/agency/graph/workflow.py:398 | No test sees acceptance refuse; the client gate is the only place `critique` is enforced | S |
| TST-003 | TST | High | Confirmed | src/agency/qa/evidence.py:128 | The refusals for a stale proof, a stale input, a missing master and a non-derived export are untested | S |
| TST-005 | TST | High | Confirmed | src/agency/cli.py:148 | No test checks that `--budget`, `--model` and `agency budget` reach the ledger | S |
| COR-002 | COR | Medium | Confirmed | src/agency/gateway/client.py:132 | Parallel calls all pass the budget check before any records usage (2× the cap in the repro) | S |
| COR-004 | COR | Medium | Confirmed | src/agency/runtime.py:79 | A brief that isn't UTF-8 crashes after the project row is saved, and the name stays unusable | S |
| COR-005 | COR | Medium | Confirmed | src/agency/runtime.py:121 | There is no per-project lock, so two processes run the same instances and pay twice | S |
| COR-006 | COR | Medium | Confirmed | src/agency/insights/adapters/transcripts.py:90 | A transcript line cut inside a UTF-8 character takes down report, insights and the dashboard | S |
| COR-007 | COR | Medium | Confirmed | src/agency/tools/render.py:105 | Proof names drop the extension, so sources with the same stem share one proof | S |
| COR-008 | COR | Medium | Likely | src/agency/gateway/client.py:172 | After a server-side fallback, the declined attempt's billed usage is not recorded | S |
| SEC-002 | SEC | Medium (↓ High) | Confirmed | src/agency/tools/render.py:46 | A bare `Image.open` on sandbox-written files lets Pillow run Ghostscript on the host (contained by `-dSAFER`) | S |
| SEC-003 | SEC | Medium | Confirmed | src/agency/tools/presentation.py:221 | The presentation re-globs proposal folders and picks up hidden symlinked host images | S |
| SEC-004 | SEC | Medium | Confirmed | src/agency/tools/surface.py:300 | The reviewer write rule checks the raw path, so `reviews/../brief.md` passes | S |
| SEC-005 | SEC | Medium | Confirmed | src/agency/tools/sandbox.py:42 | The sandbox has no memory, file-size, process or tmpfs limits | M |
| TST-004 | TST | Medium (↓ High) | Confirmed | src/agency/qa/evidence.py:108 | ADR-0018's "own proofs" and "a FAIL persists" rules are untested | S |
| TST-007 | TST | Medium | Confirmed | src/agency/tools/surface.py:945 | Replay protection on resume is tested only for `open_ticket` | S |
| TST-008 | TST | Medium | Confirmed | src/agency/qa/evidence.py:62 | The rules on who may sign an independent check (the author excluded, allowed roles only) are untested | S |
| TST-011 | TST | Medium | Confirmed | src/agency/qa/delivery.py:63 | The contract and verdict rules that keep tickets deliverable are untested | S |
| TST-012 | TST | Medium | Confirmed | src/agency/agents/loop.py:135 | The per-role model and effort from `roles.json` never reach a tested request | S |
| STR-001 | STR | Medium | Confirmed | src/agency/config.py:16 | The data root has three sources and two env names, so the engine and the dashboard can read different registries (alias: DX-003, part) | L |
| DX-003 | DX | Medium | Confirmed | src/agency/ledger/store.py:62 | Read-only commands create an empty registry, and `verify` reports it intact | S |
| COR-003 | COR | Low (↓ Medium) | Confirmed | src/agency/tools/surface.py:618 | An effect and its resume record are committed separately (a window of microseconds) | M |
| COR-009 | COR | Low | Suspected | src/agency/agents/loop.py:152 | Tool calls from a declined attempt before a `fallback` block would be executed | M |
| COR-010 | COR | Low | Likely | src/agency/gateway/client.py:160 | Retries after malformed tool JSON are neither re-authorized nor recorded | M |
| COR-011 | COR | Low | Likely | src/agency/agents/loop.py:164 | `model_context_window_exceeded` is handled as a finished answer | S |
| COR-012 | COR | Low | Confirmed | src/agency/tools/render.py:150 | Two zooms with the same corner overwrite each other | S |
| COR-013 | COR | Low | Confirmed | src/agency/config.py:53 | Project names are never validated (`../x` escapes `projects/`) | S |
| COR-014 | COR | Low | Likely | src/agency/ledger/store.py:139 | Ticket ids sort as text, so the order breaks after T-9999 (latent) | S |
| COR-015 | COR | Low | Suspected | src/agency/tools/surface.py:330 | `view_image` takes the media type from the file suffix (alias: SEC-002, part) | S |
| COR-016 | COR | Low | Suspected | src/agency/qa/scripts/svg_audit.py:144 | The vendored `svg_audit` misses strokes inherited from a `<g>` | S |
| SEC-006 | SEC | Low | Confirmed | src/agency/evaluation/board.py:50 | `agency judge` renders model SVGs outside bwrap, and a local `<image href>` gets drawn | S |
| SEC-007 | SEC | Low | Confirmed | src/agency/qa/delivery.py:98 | Ticket paths accept absolute paths and `..`, so the review glob reveals whether host files exist | S |
| SEC-008 | SEC | Low | Likely | src/agency/tools/sandbox.py:33 | bwrap runs without `--new-session` (TIOCSTI class; blocked on this host) | S |
| SEC-009 | SEC | Low | Likely | src/agency/cli.py:96 | Model text is printed to the terminal without stripping control sequences | S |
| TST-006 | TST | Low (↓ Medium) | Confirmed | tests/test_agent_flow.py:448 | The isolation probes pass for unrelated reasons when the host is offline; the e2e loopback test skips offline (baseline F1) | S |
| TST-009 | TST | Low (↓ Medium) | Confirmed | src/agency/gateway/transport.py:37 | The live transport is tested only with a hand-made request (the cassette half is under SIM-006) | S |
| TST-010 | TST | Low (↓ Medium) | Confirmed | src/agency/gateway/client.py:121 | The input part of the cost estimate after the first call is untested | S |
| TST-013 | TST | Low | Confirmed | src/agency/cli.py:58 | The exit code of `agency verify` on a broken chain is untested | S |
| TST-014 | TST | Low | Confirmed | src/agency/ledger/store.py:238 | Rework clearing a review's verdict is untested | S |
| TST-015 | TST | Low | Confirmed | src/agency/graph/workflow.py:306 | Recording the concept gate only once on resume is untested | S |
| TST-016 | TST | Low | Confirmed | src/agency/tools/surface.py:669 | Three tool refusals are untested: more than 3 ideas, judging a file against itself, unknown export options | S |
| TST-017 | TST | Low | Likely | tests/test_insights.py:578 | The reader test ignores the result of the writer's `wait` (the key-leak half is under DX-001) | S |
| TST-018 | TST | Low | Confirmed | tests/test_doctor.py:5 | The two slowest tests spend their time on `nvidia-smi` and a `uv run` subprocess | S |
| CMT-001 | CMT | Low | Confirmed | src/agency/insights/views.py:31 | Some docstrings are runtime data: OpenAPI text, CLI help, tool schemas | M |
| CMT-002 | CMT | Low | Confirmed | web/scripts/check-defenses.mjs:17 | The `code()` JSDoc says comments are ignored, but most checks read them | S |
| CMT-003 | CMT | Low | Confirmed | web/next.config.mjs:3 | A comment claims every defense is checked, but the headers and rewrites are not | S |
| CMT-004 | CMT | Low | Confirmed | src/agency/tools/board.py:23 | The `MAIN_SHARE` comment names the wrong quantity | S |
| CMT-005 | CMT | Low | Confirmed | src/agency/insights/__init__.py:1 | The insights docstrings predate transcripts and the view use cases | S |
| CMT-006 | CMT | Low | Confirmed | src/agency/ledger/schema.py:1 | It cites ADR-0022 for a rule that is ADR-0025 | S |
| CMT-007 | CMT | Low | Likely | src/agency/ledger/__init__.py:1 | It says ticket state derives from events, but verdicts live only in `tickets` | S |
| CMT-008 | CMT | Low | Suspected | src/agency/contracts/ticket.py:12 | Italian stored and wire values: changing them is a data migration, not a translation | S |
| CMT-009 | CMT | Low | Confirmed | src/agency/** (40-comments-language.md A1–A3) | 126 comment lines, 299 docstrings and 15 field descriptions in Italian | L |
| CMT-010 | CMT | Low | Confirmed | tests/** (A1, A2) | 110 comment lines and 134 docstrings in Italian | M |
| CMT-011 | CMT | Low | Confirmed | src/agency/gateway/transport.py:70 (A4) | 25 developer-facing messages in Italian | S |
| CMT-012 | CMT | Low | Confirmed | web/** (A5) | 114 comment blocks and 14 CSS comments in Italian | M |
| CMT-013 | CMT | Low | Confirmed | web/e2e/run.spec.ts:173 (A6) | 40 web test titles and 30 build-check messages in Italian | S |
| CMT-014 | CMT | Low | Confirmed | src/agency/ledger/store.py:61 (A10) | 228 of 378 public functions and classes have no docstring | L |
| STR-002 | STR | Low | Confirmed | pyproject.toml:74 | Three import-linter contract lists are kept by hand, with no completeness check | S |
| STR-003 | STR | Low | Confirmed | src/agency/cli.py:15 | ADR-0021's library boundaries are not enforced, and are already broken (alias: SIM-004, part) | M |
| STR-004 | STR | Low | Confirmed | src/agency/tools/surface.py:19 | `agents`, `tools` and `qa` import each other at package level (planned for M1.7) | M |
| STR-005 | STR | Low | Confirmed | src/agency/qa/evidence.py:19 | `registry/` has no single owner and no schema (aliases: SIM-005 and SIM-008, part) | M |
| STR-006 | STR | Low | Confirmed | src/agency/cli.py:227 | The `blind/`, `craft-index` and `work/` paths bypass `DataLayout` (alias: SIM-013) | S |
| STR-007 | STR | Low | Confirmed | src/agency/telemetry/report.py:1 | `telemetry` holds the CLI renderer and the run fingerprint, neither of which is telemetry | S |
| STR-008 | STR | Low | Likely | src/agency/config.py:12 | `REPO_ROOT = parents[2]` works only from a source checkout | S |
| STR-009 | STR | Low | Confirmed | src/agency/insights/adapters/registry.py:1 | "registry" names both the ledger and the studio-rules folder | M |
| STR-010 | STR | Low | Confirmed | .gitignore:10 | The route folder `projects/` collides with the ignored client folder (already guarded) | S |
| STR-011 | STR | Low | Confirmed | src/agency/entrypoints/server/serve.py:19 | Key names, ports and the e2e folder are copied across files with no owner (the Python pin is under DX-011) | M |
| STR-012 | STR | Low | Likely | spikes/sandbox_craft.sh:9 | The ADR-0005 spike builds its own bwrap profile, not the real `Sandbox` | S |
| STR-013 | STR | Low | Confirmed | tests/test_sketch_flow.py:1 | Four test files and `globals.css` are over 500 lines (`surface.py` is under SIM-012) | L |
| STR-014 | STR | Low | Likely | src/agency/qa/scripts/logo_proof.py:1 | No test keeps the vendored QA scripts identical to legacy | S |
| DX-001 | DX | Low (↓ High) | Confirmed | tests/test_agent_flow.py:60 | Without VectorCraft or bwrap, 11 tests crash instead of skipping (alias: TST-017, part) | S |
| DX-002 | DX | Low (↓ Medium) | Confirmed | README.md:22 | The README omits activating mise, installing bwrap and VectorCraft, and Playwright's Chromium | S |
| DX-004 | DX | Low | Confirmed | Taskfile.yml:21 | `task setup` silently rewrites a stale `uv.lock` | S |
| DX-005 | DX | Low | Confirmed | tests/test_taskfile.py:107 | The `git check-ignore` test fails with an opaque message outside a git checkout | S |
| DX-006 | DX | Low | Confirmed | src/agency/doctor.py:23 | Doctor requires Docker "for Langfuse and ComfyUI" and does not check Chromium | S |
| DX-007 | DX | Low | Confirmed | spikes/sandbox_craft.sh:24 | The spike prints `ok` for two probes when bwrap is missing (same pattern as TST-006) | S |
| DX-008 | DX | Low | Confirmed | Taskfile.yml:34 | No write-mode formatter, no web linter, no editor config | S |
| DX-009 | DX | Low | Suspected | Makefile:1 | No CI and no git hooks, so the gate runs only by hand | M |
| DX-010 | DX | Low | Likely | Taskfile.yml:124 | On a fresh clone, `task docker:up` builds both images and then fails on a missing `.data` | S |
| DX-011 | DX | Low | Likely | .python-version:1 | Python is pinned only to `3.13`, while Docker pins 3.13.15 (alias: STR-011, part) | S |
| SIM-001 | SIM | Low (↓ Medium) | Confirmed | src/agency/telemetry/report.py:108 | The two fingerprint parsers disagree; the CLI one would raise on an older shape (latent) | S |
| SIM-002 | SIM | Low | Confirmed | pyproject.toml:15 | The runtime dependency `opentelemetry-exporter-otlp-proto-http` is never imported | S |
| SIM-003 | SIM | Low | Confirmed | pyproject.toml:23 | The unused extras add 56 locked packages, and `pillow` is listed twice | S |
| SIM-004 | SIM | Low | Confirmed | src/agency/runtime.py:11 | `langchain_core`, `sqlalchemy` and `httpx2` are imported but not declared | S |
| SIM-005 | SIM | Low | Confirmed | src/agency/graph/workflow.py:38 | Three definitions dead since bootstrap (the `evidence.ROLES` part is under STR-005) | S |
| SIM-006 | SIM | Low | Confirmed | src/agency/gateway/transport.py:79 | The record/replay transport was never wired, and `ScriptedTransport` is test-only code in `src/` (alias: TST-009, part) | S |
| SIM-007 | SIM | Low | Confirmed | src/agency/tools/sandbox.py:27 | Five parameters are never passed by any caller | S |
| SIM-008 | SIM | Low | Confirmed | registry/roles.json:8 | The `craft` and `department` fields are never read (the suffix rule is under STR-005) | S |
| SIM-009 | SIM | Low | Likely | src/agency/graph/workflow.py:197 | Concept status is six string literals, not a type | S |
| SIM-010 | SIM | Low | Likely | src/agency/agents/loop.py:25 | The closing-tool lists disagree: `reject_concept` is missing from the reminder | S |
| SIM-011 | SIM | Low | Confirmed | src/agency/tools/files.py:21 | The sha256, clip and `BUSY_SECONDS` helpers are copied across the import boundaries | S |
| SIM-012 | SIM | Low | Confirmed | src/agency/graph/workflow.py:64 | `build` (McCabe 63) and the 968-line `surface.py`, both deferred to M1.7 (alias: STR-013, part) | L |
| CMT-015 | CMT | Nit | Confirmed | web/src (A11) | 20 exported TypeScript functions have no JSDoc | S |
| CMT-016 | CMT | Nit | Confirmed | pyproject.toml:49 (A7) | Italian comments in config and infra files | S |
| CMT-017 | CMT | Nit | Confirmed | web/e2e/project.ts:2 (A9) | Italian fixture identifiers (recommendation: leave them) | M |
| CMT-018 | CMT | Nit | Likely | src/agency/contracts/__init__.py:1 | "Everything that crosses a boundary is Pydantic" is false for two types | S |
| CMT-019 | CMT | Nit | Likely | src/agency/insights/domain.py:147 | A comment that only restates the line below it | S |
| STR-015 | STR | Nit | Confirmed | web/src/components/project-header.tsx:6 | Each dashboard view has up to four names | S |
| STR-016 | STR | Nit | Confirmed | tests/test_board.py:18 | The test helpers rely on pytest's default import mode | S |
| STR-017 | STR | Nit | Confirmed | src/agency/context/__init__.py:1 | Layout leftovers: an empty package, a non-ASCII ADR file name, phase prompts in `roles/` (the README tree is under DX-013) | S |
| DX-012 | DX | Nit | Confirmed | Makefile:7 | A bare `make` runs setup, while a bare `task` lists the commands | S |
| DX-013 | DX | Nit | Confirmed | README.md:69 | The README omits `agency verify` and five folders (alias: STR-017, part) | S |
| SIM-014 | SIM | Nit | Confirmed | src/agency/ledger/models.py:133 | `ConceptRow.sketch_ticket` is never written or read | S |
| SIM-015 | SIM | Nit | Likely | tests/test_hardening.py:35 | The test helpers `settings()` and `turn()` are copied between files (preference) | S |
| SIM-016 | SIM | Nit | Likely | web/src/app/compare/page.tsx:99 | The scroll-region wrapper is written out 14 times (preference) | S |
| SIM-017 | SIM | Nit | Likely | src/agency/config.py:29 | `Settings` gives every data path two names (preference) | S |

## Final status (2026-11-13)

Each finding above, after the sanity refactor and its final review (`99-result.md`). **Fixed** names the commits on
`audit/deep-review` that close the finding. A finding fixed in part names its remainder, which is Deferred or
Rejected with its reason. Every Deferred and Rejected item is a decision recorded in `PLAN.md` ("Not planned in
this refactor") or in the answers to Q1-Q22 below.

- **Fixed:** 101, of which 8 leave a remainder that is deferred or rejected (STR-003, STR-005, STR-017, DX-008,
  DX-009, SIM-004, SIM-010 and SIM-011). SIM-007 keeps two of its five parameters on purpose: both have callers.
- **Deferred:** 5. STR-004, STR-007, STR-013 and SIM-012 go to M1.7; SIM-014 goes to the next migration that has a
  reason of its own.
- **Rejected:** 3, all by decision: CMT-014, CMT-017, STR-010.
- **Since then (M1.7, 2026-11-15):** STR-004 and SIM-012 are fixed, and so is SIM-004's remainder; their rows name the
  commits. SIM-012 leaves the `select` node factory to M1.8. STR-007 and STR-013 stay with M1.7 items 4 and 6.

The final review found and fixed eleven more issues (R1-R11). They have no ID in this table; `PLAN.md` ("Final
review" and the review rounds after it) and `99-result.md` list them.

| ID | Severity | Final status | Commits, or the reason |
|---|---|---|---|
| SEC-001 | Critical | Fixed | 480f688, 74c2a96, 5413af5, fe50543; the same class closed in 8b558fc, 642ee28, 3976aa8, 9fb7bf1 |
| COR-001 | High | Fixed | affdad2 |
| TST-001 | High | Fixed | d76b4f5 |
| TST-002 | High | Fixed | d76b4f5 |
| TST-003 | High | Fixed | d76b4f5 |
| TST-005 | High | Fixed | b9e3617 |
| COR-002 | Medium | Fixed | 75ddfb1 |
| COR-004 | Medium | Fixed | e8fe18c |
| COR-005 | Medium | Fixed | 17ee240 |
| COR-006 | Medium | Fixed | da8556e |
| COR-007 | Medium | Fixed | af41782 |
| COR-008 | Medium | Fixed | bb68b65 |
| SEC-002 | Medium | Fixed | 17cdbdc |
| SEC-003 | Medium | Fixed | 74c2a96, b50c32f |
| SEC-004 | Medium | Fixed | 74c2a96, as a side effect of the no-follow helpers; every route pinned in 0631cb9 (Task 2.7) |
| SEC-005 | Medium | Fixed | 449690c, 55a2f49; /dev/shm and output caps in b26910f |
| TST-004 | Medium | Fixed | d76b4f5 |
| TST-007 | Medium | Fixed | 3dcf60f |
| TST-008 | Medium | Fixed | d76b4f5 |
| TST-011 | Medium | Fixed | d76b4f5 |
| TST-012 | Medium | Fixed | 21e057d |
| STR-001 | Medium | Fixed | 0b2f5dd, 004e066, b453b9e; the docker guards in 01329dc |
| DX-003 | Medium | Fixed | 0898e4d, 0b2f5dd |
| COR-003 | Low | Fixed | 55039eb; every replayed tool in 84aa208 |
| COR-009 | Low | Fixed | d8552e8 |
| COR-010 | Low | Fixed | 0f4abbf |
| COR-011 | Low | Fixed | 9fb4739 |
| COR-012 | Low | Fixed | af41782 |
| COR-013 | Low | Fixed | 45180f1; typed layout paths in 3884586 |
| COR-014 | Low | Fixed | afaf26c; insights order in ff187e6 |
| COR-015 | Low | Fixed | 17cdbdc |
| COR-016 | Low | Fixed | cb3f724; inline style in cd50917 |
| SEC-006 | Low | Fixed | a636634 |
| SEC-007 | Low | Fixed | a339160 |
| SEC-008 | Low | Fixed | 8cef9ed (engine), 362b53a (spike) |
| SEC-009 | Low | Fixed | a90f568; API error text in 01329dc, one-line text in 3884586 |
| TST-006 | Low | Fixed | c2c6e75 |
| TST-009 | Low | Fixed | 376138f, dd756d6 |
| TST-010 | Low | Fixed | 376138f |
| TST-013 | Low | Fixed | b9e3617 |
| TST-014 | Low | Fixed | b9e3617 |
| TST-015 | Low | Fixed | 3dcf60f |
| TST-016 | Low | Fixed | fb88e54 |
| TST-017 | Low | Fixed | f1af1e3 (the wait), 56cae12 (the key) |
| TST-018 | Low | Fixed | 149300c |
| CMT-001 | Low | Fixed | 93e9dd4 (CLI help), f0d0f3d and 1853844 (OpenAPI) |
| CMT-002 | Low | Fixed | 1a14ea5 |
| CMT-003 | Low | Fixed | 1a14ea5 |
| CMT-004 | Low | Fixed | fdd58bc, fbce501 |
| CMT-005 | Low | Fixed | 962bafc |
| CMT-006 | Low | Fixed | a1cacc1 |
| CMT-007 | Low | Fixed | ee366ad (the invariant), a1cacc1 (the comment) |
| CMT-008 | Low | Fixed | 72b7a4e, 92bdc11 |
| CMT-009 | Low | Fixed | 0f3c3cb, fb8f368, ea356fe, 357a8c7, 07a76b0, 64dbbae, d1e0369, 962bafc, a1cacc1, 01f7362, affe8a5, fdd58bc, 9d804e9 |
| CMT-010 | Low | Fixed | 1a49f13, 35c97e9, cb4fb3c |
| CMT-011 | Low | Fixed | 64dbbae, d1e0369, a1cacc1, 1853844, 1a49f13, 35c97e9, cb4fb3c |
| CMT-012 | Low | Fixed | 1a14ea5 |
| CMT-013 | Low | Fixed | de2cbfd |
| CMT-014 | Low | Rejected | by decision (Q14): no docstring campaign and no ruff D1; ports, contracts and platform modules got docstrings in their Phase 3 units |
| STR-002 | Low | Fixed | 53eadda (the guard), 740e88e (the lists) |
| STR-003 | Low | Fixed | 23b89e1 for `anthropic`; the `langgraph` and ledger-port rules are Deferred to M1.7 (Q19) |
| STR-004 | Low | Fixed | M1.7: 1754438 (the QA mount only for a check), 8953e00 (the qa<->tools cycle), 2f3ad00 (the acyclic contract); the tools->agents edge went in 73881ee |
| STR-005 | Low | Fixed | 85cb4fb, b990dc9, 73881ee, 8a4edc1, a1c882e, 2b19b9f, 7948aed; typing ROLES and CHECKS as RoleSpec and CheckSpec is Deferred (PLAN Task 6.9) |
| STR-006 | Low | Fixed | 272e68e |
| STR-007 | Low | Deferred | M1.7 (Q18): the CLI moves to entrypoints/cli/ then, so moving report.py now would move it twice |
| STR-008 | Low | Fixed | 0b2f5dd |
| STR-009 | Low | Fixed | 08bfd10, 300e30c |
| STR-010 | Low | Rejected | by decision: renaming the route breaks ADR-0038's URLs; the guard in tests/test_repository.py holds |
| STR-011 | Low | Fixed | e8a4531, e001621, ce1a5a5, af0b406 |
| STR-012 | Low | Fixed | 362b53a |
| STR-013 | Low | Deferred | M1.7 (Q19): the large test files and globals.css split with surface.py |
| STR-014 | Low | Fixed | 928598d |
| DX-001 | Low | Fixed | 56cae12 |
| DX-002 | Low | Fixed | 3967e55, 8a644d1 |
| DX-004 | Low | Fixed | d93cc4e |
| DX-005 | Low | Fixed | 131a770 |
| DX-006 | Low | Fixed | 399fe2d |
| DX-007 | Low | Fixed | 362b53a |
| DX-008 | Low | Fixed | f4f5a1e, 3e91d64; a web formatter and linter is Deferred (a new dependency under the quarantine needs its own ADR) |
| DX-009 | Low | Fixed | 526957b for the hook and the clean-checkout gate; CI is Deferred until a Git remote exists, before M6 (ADR-0051) |
| DX-010 | Low | Fixed | a1179b4 |
| DX-011 | Low | Fixed | e001621 |
| SIM-001 | Low | Fixed | 2fb371e, be01c80 |
| SIM-002 | Low | Fixed | 9da57c3 |
| SIM-003 | Low | Fixed | 4ab753b |
| SIM-004 | Low | Fixed | ab7d394 (declared and tested); the langchain_core import moved to the process layer in M1.7, 1b466f2 |
| SIM-005 | Low | Fixed | 8a4edc1 |
| SIM-006 | Low | Fixed | dd756d6, cc70e8b |
| SIM-007 | Low | Fixed | 5a8173f for three parameters; Sandbox(read_only=...) stays because the spike uses it (5.10), and CommandIndex.load(app) stays |
| SIM-008 | Low | Fixed | 85cb4fb |
| SIM-009 | Low | Fixed | f917fd8 |
| SIM-010 | Low | Fixed | a770286, 6005cec; the `closes`/`conditional` tool fields were Rejected (they move facts without removing any) |
| SIM-011 | Low | Fixed | fed289d for the hash; one `clip` and one BUSY_SECONDS were Rejected (merging changes output; two independent waits) |
| SIM-012 | Low | Fixed | M1.7: 890fd06 and 386914d (surface.py split), 42ffc0e and 1a3d49e (workflow.build: McCabe 65 to 2); the `select` node factory, at 11, is Deferred to M1.8's gate (max-complexity 8) |
| CMT-015 | Nit | Fixed | 1a14ea5, for the helpers the finding named; the framework entry points (Layout, NotFound, Projects, generateMetadata) stay as its own fix allowed |
| CMT-016 | Nit | Fixed | e8a4531, 740e88e |
| CMT-017 | Nit | Rejected | by decision (Q14): the fixture identifiers stay |
| CMT-018 | Nit | Fixed | ea356fe |
| CMT-019 | Nit | Fixed | 962bafc |
| STR-015 | Nit | Fixed | 5a11385 |
| STR-016 | Nit | Fixed | a92e02b, fbaf53c, cc70e8b |
| STR-017 | Nit | Fixed | 3967e55 for the README tree; the empty package, the ADR file name and prompts/roles/ are Rejected by decision (fingerprint keys and frozen files) |
| DX-012 | Nit | Fixed | 6a5e2fa |
| DX-013 | Nit | Fixed | 3967e55 |
| SIM-014 | Nit | Deferred | drop ConceptRow.sketch_ticket in a migration needed for its own sake; 0009 did not, because concept rows are bound whole in the chain and dropping a column needs those rows re-bound |
| SIM-015 | Nit | Fixed | 5ca5335 |
| SIM-016 | Nit | Fixed | 08f125c |
| SIM-017 | Nit | Fixed | 1f4b7cf |
| SIM-013 | Low (merged) | Fixed | 272e68e (merged into STR-006) |

## Duplicates

**Merged in full** (the alias has no part of its own):

- STR-006 ← SIM-013: `settings.project_dir(project) / "work"` is built by hand in four modules and parsed back in a
  fifth, outside `DataLayout`.

**Merged in part.** The shared part is fixed under the canonical ID, and the alias keeps only its remainder.

| Canonical | Alias, and the part it shares | What the alias keeps |
|---|---|---|
| STR-005 | SIM-005: the second `roles.json` loader (`qa.evidence.ROLES`) | three other dead definitions |
| STR-005 | SIM-008: the director/reviewer split by name suffix | the unread `craft` and `department` fields |
| SIM-006 | TST-009: the unused cassette pair | the untested `count_tokens`/`fallbacks` request shape |
| SIM-012 | STR-013: the 968-line `tools/surface.py` | the other files over 500 lines |
| DX-011 | STR-011: the Python pin | the other copied values |
| DX-013 | STR-017: the README tree | the other layout leftovers |
| COR-015 | SEC-002: the media type taken from the suffix | Pillow choosing Ghostscript from the file's content |
| DX-001 | TST-017: the fake key left set after the bwrap-less crash | the ignored `Event.wait` result |
| STR-001 | DX-003: `.env` and `.data` resolved from the CWD | read-only commands creating an empty registry |
| STR-003 | SIM-004: `langchain_core` imported in `runtime.py` | `sqlalchemy` and `httpx2` undeclared |

**Related, fix together** (the same root cause or pattern, but different code, so no ID is merged):

- SEC-001 and SEC-003: the harness follows symlinks that sandboxed code can plant under `/job`. One rule fixes both.
- TST-006 and DX-007: an isolation probe counts an unrelated failure as success.
- STR-012 and DX-007: `spikes/sandbox_craft.sh` is not valid ADR-0005 evidence for the real `Sandbox`.
- COR-001, COR-007 and COR-012: a render proof is identified only by its path, not by its source's extension, version or
  zoom box.

## Rejected findings

None. Each of the 30 reviewed defects was reproduced, killed by a mutant, or read directly in the code. Nine were rated
too high; they are listed below with the reason, so they are not escalated again.

| ID | From → to | Why |
|---|---|---|
| SEC-002 | High → Medium | Reproduced, but gs 10.06 `-dSAFER` limits the PostScript to reading and writing `/tmp` and to terminal output: the repo, home and `/etc` are denied. It would become High with any SAFER bypass, so fix it with SEC-001. |
| TST-004 | High → Medium | The client gate's assignee-signature check (src/agency/qa/delivery.py:163) still stops the director overriding the critic. What could ship is narrower: a review delivered on someone else's proofs, or a child-ticket FAIL hidden by a non-assignee PASS. |
| DX-001 | High → Low | Reproduced (11 failures), but the only machine has both binaries, doctor marks them as required, and each failure names the missing binary. |
| COR-003 | Medium → Low | Reproduced only by injection. The gap between the two commits contains no I/O, while a Ctrl-C almost always lands in a model call or a sandbox run. |
| TST-006 | Medium → Low | Mutant X2 (`--unshare-net` removed) is killed on an online host, which is the normal state. The `/usr` regression it would miss has no effect for a non-root operator. |
| TST-009 | Medium → Low | Both missed regressions fail safe: a `count_tokens` `TypeError` stops the first live call before any spend, and a lost fallback blocks with "rifiuto del modello". |
| TST-010 | Medium → Low | The missed error is a few cents (cache-read price at merlo3's peak context). The dominant output term is guarded: mutant G0 was killed. |
| DX-002 | Medium → Low | A documentation gap on a single-operator project whose machine is already set up. |
| SIM-001 | Medium → Low | Latent: `contracts/run.py` has a single commit, so every stored fingerprint has the current shape. |

**Checked and found sound, so not to be rediscovered:**

- **Ledger:**
  - The hash chain, ticket ids and every write stay serialized under parallel threads and separate processes (`BEGIN IMMEDIATE` plus an `RLock`; tests/test_hardening.py:305, :343).
  - Migrations run in one transaction, with a backup and a chain check.
  - The artifact store fsyncs before its rename.
  - Timestamps are uniformly aware UTC.
- **Engine:**
  - When the budget runs out, LangGraph lets sibling explorers finish before it raises.
  - `craft_run` replays its stored result on resume.
  - The append-only history is enforced, and `stop_reason` is checked before `content`, apart from COR-009 and COR-011.
  - Budget input rejects 0, negatives, `nan`, `inf` and text.
- **Sandbox profile:**
  - `--clearenv` keeps the key out, there is no network (errno 101), and `/usr`, `/opt/agency-qa` and the toolchain are read-only.
    Corrected by the final review: `--clearenv` kept the key out of the command's environment only, and bwrap's own
    block stayed readable at `/proc/1/environ` (see `20-security.md`, "Checked, no finding").
  - `inside()` resolves symlinks for `read_file`, `write_file`, `view_image`, `render`, `judge`, `observe`, delivery and keep.
- **SQL:** every statement in `ledger/` and `insights/adapters/` is a constant or uses parameters.
- **Dashboard:**
  - Django answers only GET, checks `ALLOWED_HOSTS` first, reads with `mode=ro`/`query_only`, scrubs the key and refuses non-loopback binds.
  - The Next.js proxy rejects foreign Hosts, and every fetch uses `no-store`.
  - The Docker build contexts are allowlists, and the containers run read-only with `cap_drop: ALL`.
- **Secrets:** the git history (all refs, `legacy/` included) holds only fake canaries, and no `.env` was ever committed.
- **Dependencies:** `pnpm audit` finds one moderate advisory (minimatch, reachable only through the dev tool `openapi-typescript` on the project's own schema). Next.js 16.4.2 and Pillow 13.0.0 are past the 2026 advisories the auditors found.
- **Tests:**
  - Stable in reverse file and test order, and the thread-based tests passed 12 of 12 repeats under load.
  - Every test asserts something.
  - 50 of the auditors' 99 mutants were killed (ledger, chain, migrations, gateway ceiling, perimeter, gates, read-only server).
  - The one bug fixed inside a feature commit (678f94c) came with its regression test.
- **Structure:** grimp finds no module-level import cycle, import-linter keeps 4 of 4 contracts, and no config file is redundant.
- **DX:** Task is the single entry point, every Make alias works, the preconditions print one actionable line, the tool versions are pinned exactly, and pnpm installs with `--frozen-lockfile`.
- **SIM, leads dismissed:**
  - Django and Ninja reach their settings, URLconf and routes dynamically.
  - The Pydantic validators and `log_message` are framework hooks.
  - The two board composers are not duplicates.
  - The insights ports earn their keep (`FakeRegistry` in the tests).
  - Every web dependency is used.
- **CMT:**
  - No TODO/FIXME markers, no logging calls, no i18n resources.
  - No Python or TypeScript identifier is Italian.
  - The QA scripts are vendored, so they are not translation work.
- **Leads the reviewer did not merge:**
  - COR-001/COR-007 vs TST-003: different mechanisms; TST-003 is about freshness at delivery.
  - SEC-007 vs SEC-001: the ticket-spec paths are written by the director, not by the sandbox.
  - DX-006 vs SIM-003, and STR-016 vs SIM-015: different defects.

## The five changes with the most quality per unit of risk

Each is one unit in the sense of the audit rules, and the first should land before anything else moves.

1. **Lock the gates with tests first: TST-001, TST-002, TST-003, TST-005.** These are tests only, with no behaviour
   change. They guard QA failure, acceptance, freshness and the budget hand-off, which are the paths a refactor is most
   likely to disturb. Effort: S each.
2. **SEC-004: compare resolved paths in the reviewer write rule.** One line in `write_file` (src/agency/tools/surface.py:300) plus a test, closing a documented self-approval bypass. Risk: Low.
3. **SEC-002 (with COR-015): open sandbox-written images through one helper.** The helper takes a format allowlist
   (`Image.open(path, formats=[…])`) and derives the media type from `image.format`. It is used at the eight call
   sites. Ghostscript then never runs on the host. Risk: Low.
4. **COR-001 (with COR-007 and COR-012): make a render proof name exactly what it proves.** Keep the viewed hash in
   `_seen_proof`, the extension in the proof name, and the zoom box in the zoom name. This closes the stale-render
   PASS, the High bug on the main QA path. Risk: Low.
5. **SEC-001 (with SEC-003), minimal version: never follow a sandbox-planted symlink on the harness side.** Resolve
   `.ops` through `inside()`, refuse it if it is a symlink, and open with `O_NOFOLLOW`. Build the presentation's image
   list from the delivered files instead of re-globbing. This is the only Critical. The minimal version is Low risk;
   moving `.ops` out of `/job` (Q1) is the M-effort follow-up.

Close runners-up, each S with Low risk: COR-006 (decode transcripts line by line), COR-004 (read the brief before
`set_project`), DX-003 (refuse a missing ledger in read-only commands) and COR-005 (a per-project lock).

## Open questions for the owner

Answered on 2026-11-04. Andrea asked Claude to decide these as the owner would. Any answer can still be overturned
before the unit that depends on it starts. Each answer begins with the decision in bold, then gives the reasons and
the implementation. "New ADR" means CLAUDE.md's rule applies: the ADR is written in the same unit that implements the
decision.

1. SEC-001: is the minimal fix enough for now (refuse symlinks, `O_NOFOLLOW`)? Or should the harness-owned `.ops` move
   out of `/job` into a read-only bind, which changes how `craft_run` resumes? **Minimal / move.**

   **Answer: move, before `merlo4` starts. The safe-open helper from the minimal fix lands first, in a unit of its
   own. New ADR, extending ADR-0005's sandbox layout.**

   - _Why move._ The minimal fix patches one call site, but the bug is a class: the trusted harness keeps state in a
     tree the untrusted sandbox can write. `craft_run` has it twice. It writes its plan into `.ops`, and on resume it
     trusts `.ops/<op>.result.json` and `.ops/<op>.vectorcraft`, which sandboxed `compute` code in the same `/job`
     can rewrite. Only moving those files out of `/job` removes the class.
   - _Why now._ The move changes where `craft_run` resumes from, so it breaks the resume of any paused project. Today
     there is none to break: `merlo3` is closed and will not resume (ADR-0021), and `merlo4` has not started. Once
     `merlo4` starts, the same change also needs a migration of its `.ops`.
   - _Why the minimal fix is not enough alone._ `O_NOFOLLOW` checks only the last path component, so a symlinked
     `.ops` directory still redirects `open(".ops/x", O_NOFOLLOW)`. Resolving with `inside()` and then writing is a
     check-then-use race. The helper must walk the path with directory descriptors: open the trusted root, then call
     `os.open(part, O_DIRECTORY | O_NOFOLLOW, dir_fd=…)` for each component, and create the last one with
     `O_CREAT | O_EXCL | O_NOFOLLOW`. Every read or write the harness makes under `/job` goes through this helper:
     SEC-003's presentation images, delivery, `view_image` and keep. That makes the fix a rule, not a patch.
   - _Shape of the move._ Three kinds of file, each with its own place:
     - Inputs the harness writes (the `compute` script, the `craft_run` plan) go to
       `.data/ops/<project>/<instance>/in/`, which is bound read-only at `/ops`.
     - Outputs a tool produces (the partial export) stay in `/job`, writable by the sandbox.
     - The resume record (the result JSON and the built document) is copied by the harness, through the helper, into
       `.data/ops/<project>/<instance>/`. That copy is not bound into the sandbox, and resume reads only from there.

     The sandbox can still write garbage into its own outputs, but it can no longer write anything the harness later
     trusts.
   - _Check._ The request snapshots must stay byte-identical. `.ops` appears in no prompt and no tool definition
     (`rg '\.ops' prompts tests` finds nothing), so only command lines change. Rebuild the auditor's
     `ops_symlink_probe.py` as a regression test.

2. STR-001: how should the data root get a single owner? **(a)** `.env` keeps only the API key and `AGENCY_DATA_DIR`
   leaves `.env.example`. **(b)** The dashboard tasks receive the root the engine resolved, which needs a new ADR
   against ADR-0031, ADR-0039 and ADR-0040.

   **Answer: (a), widened into a rule: `.env` holds secrets only. Add one name and one resolver for the data root.
   New ADR, which also replaces ADR-0040's `AGENCY_DATA`.**

   - _Why not (b)._ To hand the dashboard "the root the engine resolved", the Taskfile would have to run the engine's
     config loader. That loader reads `.env`, and with it the key. ADR-0031 keeps the server away from `agency.config`
     for exactly this reason, and ADR-0039 keeps dotenv out of the Taskfile. Under (b), starting the dashboard would
     depend on the one file the dashboard must never read.
   - _Why widen it._ The defect is not specific to the data root. Only the engine reads `.env`, so any setting stored
     there is invisible to every other process. ADR-0043 already found a 40 $ budget that only the effective settings
     showed. Settings that more than one process needs (`AGENCY_DATA_DIR`, and `AGENCY_PROJECTS_DIR` wherever a
     second process reads `projects/`) come only from the process environment. Task and Compose give that environment
     to every process alike. The engine-only knobs in `.env.example` (`AGENCY_EXPLORERS`, the two efforts,
     `AGENCY_MAX_PARALLEL`) equal the code defaults, so removing those lines changes nothing. An experiment sets a
     knob on the command line, and the run fingerprint records it (ADR-0026).
   - _How._
     - `Settings` reads only the key from `.env`.
     - If `.env` still has a non-secret `AGENCY_*` line, the engine stops with one line that names the variable and
       says where it belongs. ADR-0043 let a leftover variable be ignored silently, and that is not safe here. A
       `.env` that points at the real registry would otherwise leave the engine quietly writing a new, empty one.
     - The root resolver moves next to `DataLayout` in `agency.contracts.layout`, which the server already imports.
       The engine and the server both call it.
     - `task docker:up` and `compose.yaml` use `AGENCY_DATA_DIR` for the host path too. The container keeps its own
       value, `/data`. The one name then always means "the data root as this process sees it".

3. STR-001 and DX-003: should `.env` and `.data` resolve from the repository root instead of the current directory?
   **Yes/no.**

   **Answer: yes. Use one anchor, and require any override to be absolute.**

   - The default root is the checkout the code runs from. That is the same `REPO_ROOT` that already locates `prompts/`
     and `registry/` (agents/prompts.py:10, qa/evidence.py:16), so code and data always come from one checkout. It
     also isolates worktrees: each one under `.worktrees/` gets its own `.data`, so an audit or refactor worktree can
     never write to the real registry. `.env` resolves from the same root.
   - When `AGENCY_DATA_DIR` is set, its value must be absolute. A relative value would bring back the dependence on
     the current directory, so the engine rejects it at start-up.
   - DX-003's other half: read-only commands never create a registry. `verify`, `runs`, `artifacts`, `compare`,
     `report` and `insights` stop with an error that names the absolute path, and only `run` creates a registry.
   - STR-008: the anchor gets one definition, shared by the resolver and `agency.config`. When the engine ships as an
     installed wheel in M7, `prompts/` and `registry/` become package data and `AGENCY_DATA_DIR` becomes mandatory.
     That is a decision for M7's ADR, not for this one.

4. COR-016 and STR-014: should the vendored QA scripts stay byte-identical to `legacy/`, pinned by a new test? Or may
   they be fixed, for example inherited strokes in `svg_audit`? **Keep identical / allow fixes.**

   **Answer: allow fixes, and pin every byte. Add the pin test now, and fix `svg_audit` in a separate bug-fix unit.**

   - _Why._ `legacy/` is the frozen reference for parity. The copies in `src/agency/qa/scripts/` are the studio's live
     QA. A check that lets un-expanded strokes pass breaks the core promise, "ogni affermazione di qualità legata a una
     prova". Keeping the copy byte-identical would keep that hole on purpose.
   - _How._ STR-014's test pins each copy against a manifest kept next to the scripts. The manifest records two hashes
     per file: the legacy original and the current copy. Today the two are equal. A fix updates the current hash in
     its own unit, adds a regression test (the stroked `<g>` case) and adds a line to a short `PATCHES` note that says
     what changed and why. Every divergence then shows up in review, which is the test's job. The scripts stay
     excluded from ruff and pyright, so their diff against legacy stays exactly the size of the fixes.
   - _Consequence._ A fixed check can turn an old PASS into a FAIL on the same file, and that is the correct result.
     Old `evidence` rows are not rewritten. The run fingerprint already hashes `src/agency/` (ADR-0026), so runs
     before and after the fix can be told apart.

5. SIM-002: remove the unused `opentelemetry-exporter-otlp-proto-http` dependency now? **Yes/no.**

   **Answer: yes.** Nothing imports it, and the only exporter is `JsonlExporter`. It still pulls seven packages into
   every environment, the dashboard image included, and each one is supply-chain surface the project chose to keep
   small (ADR-0006). If Langfuse arrives in M4 it brings the exporter back as its own dependency. The work is one
   dependency-change unit: `uv remove`, the lock diff and `make check`.

6. SIM-003: drop the `context`, `qa` and `telemetry` extras until the milestone that first imports them, or keep them
   and drop only the duplicate `pillow`? **Drop / keep.**

   **Answer: drop all three.**

   - _Why._ Together they lock 56 packages, among them torch, triton and 15 `nvidia-*` wheels. Nothing imports any
     of them, and no milestone before M3 needs them. Meanwhile every lock refresh under `exclude-newer` has to resolve
     them, and every lock review has to read them. Versions picked today will be months out of date by M3 or M4, and
     ADR-0009 asks for licences to be checked at the source when a model is adopted. The milestone that first imports
     a package declares it then. Dropping `context` also removes the duplicate `pillow`.
   - _Docs._ Update docs/04-TOOLS.md, where OpenImageIO still comes "dal gruppo `qa`". ADR-0010 says
     "`langfuse` … nel gruppo `telemetry`": record in the same unit that the package now arrives with M4. That changes
     when the package is declared, not ADR-0010's decision.

7. SIM-004: declare `sqlalchemy` and `langchain-core` (runtime) and `httpx2` (dev) with `uv add`? **Yes/no.**

   **Answer: yes, all three. Then add a test so this kind of finding cannot come back.**

   - _Declare._ `sqlalchemy` and `langchain-core` become runtime dependencies, and `httpx2` a dev dependency. Each gets
     a lower bound at its locked version and no upper bound, so the resolver stays free. Declaring `langchain-core`
     does not make its use in `runtime.py` legitimate: that import still moves to the process layer in M1.7
     (STR-003). The manifest should say what the code imports today.
   - _Guard._ A test next to the import-linter contracts, built from the auditor's `thirdparty.py`, maps every
     top-level import in `src/` and `tests/` to its distribution with `importlib.metadata.packages_distributions()`.
     It fails on an undeclared import. It also fails on a declared runtime dependency that nothing imports, with an
     explicit allowlist for the packages used without an import. It needs no new dependency. A tool such as deptry
     would do the same job, but it would be one more package under quarantine.

8. SIM-006: delete `RecordingTransport` and `from_cassette` and move `ScriptedTransport` into the tests, or wire
   recording behind an explicit `open_session` option? **Delete / wire.**

   **Answer: wire recording, but rebuild it first. Replay moves into the tests together with `ScriptedTransport`.
   Land it before `merlo4`. New ADR.**

   - _Why not delete._ Roadmap M1 item 2 is checked off ("Risposte registrate: registratore per ripetere nei test le
     chiamate senza spendere"), and CLAUDE.md says the tests use recorded responses. Neither is true today. A recording
     of `merlo4` is the most valuable test data the project can get for 0 $, for two reasons:
     - It holds the real response shapes that the audit could only take from the docs (COR-008 to COR-011).
     - It gives M1.7 a golden master. Replay `merlo4` against the split engine, and a request that differs by one byte
       misses the recording at the turn that changed. M1.7's exit criteria then cover the whole run, not just the first
       request of each phase. The criteria are "gli snapshot … identici" and "i test di flusso passano con le sole
       modifiche agli import".
   - _Why rebuild._ The current pair cannot replay a real run. It stores responses without their requests, and
     `from_cassette` hands them out in order. Five explorers working in parallel never call in the same order twice.
     Appends from parallel threads can also interleave lines.
   - _Shape._
     - Each record is keyed by the sha256 of the canonical request: model, system, tools, messages and output_config,
       as JSON with sorted keys. A list per key handles repeated requests.
     - `count_tokens` is recorded too, so budget authorization replays exactly.
     - Records are written under a lock to `.data/cassettes/<project>/<run>.jsonl`. That folder is not versioned,
       because a real client's run contains their materials, just like `.data/runs/`.
     - Recording is explicit: `agency run|resume|decide --record`. The `merlo4` start command in docs/02-ROADMAP.md
       gets the flag.
     - A run on an invented brief (E1 to E8) may be copied into `tests/` by hand, once a review confirms it holds no
       key. Responses carry no headers, but a test should still check for the key.
     - The replay transport and `ScriptedTransport` live in `tests/support/`, so no production path can build them.
     - Replay also needs the local tools to be deterministic. If one is not, the first miss names it, and that is
       worth knowing before M1.7.

9. COR-008 and COR-009: implement fallback accounting (`usage.iterations`) and drop the declined attempt's blocks from
   the docs alone, or first run one live check with a declared spend cap? **Docs only / capped live check (state the cap).**

   **Answer: docs only. No live check, so the declared cap is 0 $.**

   - _Why no live check._ A fallback fires only when a safety classifier declines a request, and nothing documented
     triggers one on demand. A prompt written to provoke a refusal would probe the safeguards instead of testing our
     code, and one passing sample would prove little. The code has to meet the documented contract, which the
     claude-api reference (refusal section) states precisely:
     - `usage.iterations` is the per-attempt source of truth. The top-level `usage` covers only the attempt that
       produced the returned message.
     - After a mid-output fallback, the `thinking`, `redacted_thinking` and `tool_use` blocks (and any unpaired
       `server_tool_use`) that come before the last `fallback` block are omitted. Text blocks are echoed as usual.
   - _COR-008._ When `iterations` is present, price each attempt at the rates of the model that ran it, and record
     the sum in the call's single `usage` row. One row per attempt would break ADR-0038's link of one row per
     `request_id`. If per-attempt detail is ever wanted, it gets a new nullable column, decided together with its
     migration. `price_of` already charges an unknown model at the highest rate (`UNKNOWN_MODEL`), so a fallback to a
     model missing from the table over-counts and never under-counts. That matters here: with `"default"`, the server
     chooses the fallback model, and `claude-opus-5` and `claude-opus-4-8` cost more per token than `claude-opus-5-5`.
   - _COR-009._ Filter out the declined partial once, before the assistant turn first enters the history. This does
     not edit a sent turn, because that turn has not been sent yet, so the append-only rule holds. Execute only the
     `tool_use` blocks after the last `fallback` block. The raw response, `fallback` block included, still goes to the
     transcript and the recording, so the first real case can be checked against this code.
   - _Fixtures._ Use responses shaped like the docs now. The first real fallback in any recorded run (Q8) becomes a
     cassette and replaces them.

10. DX-001: when bwrap or VectorCraft is missing, should the affected tests skip, or should the session fail once at
    start, naming the binary? **Skip / fail once.**

    **Answer: both, decided by what each test proves.**

    - _Craft CLIs: skip._ Add the `needs_craft` marker to the 8 `runner()` tests. The Craft CLIs are licensed tools
      that a newcomer's machine or a CI runner will not have, and on such a machine the suite already skips 59 of
      these tests.
    - _bwrap: fail once._ The session fails at start, with one line naming the binary. The sandbox tests prove the
      guarantees of no network, no key and one writable folder, so a green run without them is a false green. Mark
      those tests `sandbox`, and fail the session only when a selected test carries the marker. That makes
      `pytest -m "not sandbox"` the explicit, visible way to run without them.
    - _Probe that bwrap works, not just that it exists._ Run a trivial command such as `bwrap --unshare-net … true`
      once per session. Ubuntu's AppArmor restriction on unprivileged user namespaces makes an installed `bwrap` fail
      on many hosts, CI runners included. TST-006 already showed the cost of a probe that passes for the wrong reason.
    - _TST-017's half._ In the same unit, set the fake key with `monkeypatch`, so it is removed even after a crash.

11. DX-009: should the gate also run automatically? **None / pre-commit hook / CI / both.** Anything but "none" is a
    new ADR.

    **Answer: both, in two stages, under one new ADR. A pre-commit hook and a clean-checkout gate come now, and CI
    comes once a Git remote exists.**

    - _Why not CI now._ The repository has no remote (`git remote` prints nothing). Where the remote and the backups
      should live is still an open decision in docs/00-PROJECT.md, and CI needs that decision first.
    - _Pre-commit hook, now._ A plain, versioned script in `.githooks/pre-commit`, enabled once with
      `git config core.hooksPath .githooks`. Andrea runs that command: `task setup` may print it but does not run it.
      The hook runs the fast, deterministic part of the gate, about 10 s by the baseline timings: `uv lock --check`,
      `ruff check`, `ruff format --check`, `lint-imports`, `pyright`, `api:check`, the web typecheck and `defenses`.
      Two alternatives are rejected:
      - The pre-commit framework, because it fetches hook repositories from GitHub at arbitrary revisions, which
        defeats the two-week quarantine (ADR-0006).
      - The full gate, because a commit that takes 80 s gets skipped with `--no-verify`.
    - _Clean-checkout gate, now._ `task check:clean` exports `HEAD` (`git archive`) or the index
      (`git checkout-index -a --prefix=`) into a scratch folder. Neither command writes history or the index. It then
      runs `task setup` and `task check` there, and deletes the folder. This is the check that catches DX-009's own bug,
      files on disk but missing from the commit, and the auditor already used the same method for `make schemas`
      (baseline row 16). Once a remote exists, it becomes the `pre-push` hook.
    - _CI, when the remote exists._ That is before M6 at the latest, because M6 needs off-machine backups and so a
      remote anyway. CI runs `task check` on a clean checkout. The Craft tests skip, and the sandbox tests run where
      bwrap works or are deselected explicitly where it does not (Q10).

12. DX-004: should `task setup` use `uv sync --locked`, with `UV_LOCKED=1` set for every `uv run`? **Yes/no.**

    **Answer: yes, and one step further.**

    - `task setup` uses `uv sync --locked`.
    - `UV_LOCKED=1` goes in the Taskfile's `env`, so every task fails on a stale lock instead of rewriting it. It does
      not go in `mise.toml`'s `[env]`, which would reach Andrea's shell, where `uv add` and `uv lock` must keep
      working.
    - The API image changes from `uv sync --frozen --no-dev` to `--locked` (docker/server.Dockerfile:16, :18).
      `--frozen` installs a stale lock without a word.
    - `uv lock --check` becomes the first step of `task check`, so drift is reported in one plain line.

13. DX-006: should Docker become optional in `agency doctor`, with a check for Playwright's Chromium added? It changes
    user-facing strings. **Yes/no.**

    **Answer: yes.** Doctor is useful only while every ERR it prints is true. An error about Docker, which the code
    does not need, teaches the operator to read past red lines.

    - _Docker._ It becomes optional, with its real reason: the dashboard in Docker, `task docker:up`. It goes back to
      required in M4 if Langfuse or ComfyUI need it.
    - _Chromium._ It becomes required, because `task check` needs it. Doctor finds the revision Playwright expects in
      `web/node_modules/playwright-core/browsers.json` and checks that its folder exists in the browser cache. That
      reads a file and runs nothing, which keeps doctor's rule of querying only known CLIs. When it is missing, doctor
      prints the exact install command from docs/04-TOOLS.md.
    - _Rules._ Only required items set a non-zero exit code. The new strings are Italian, in doctor's current style.

14. CMT-009 to CMT-016: translate code comments, docstrings and developer-facing messages to English, one package per
    unit, as the audit rules require? **Yes/no.**

    **Answer: yes. CLAUDE.md already says code is in English, so this is compliance, not a new decision. Translate one
    package per unit, after the bug-fix and test units and before M1.7.**

    - _Order._ The translation comes after the fixes, so each fix is reviewed as a small diff. It comes before M1.7,
      so the M1.7 split is a pure move that git and the reviewer can follow.
    - _Never in these units._
      - Model-facing text: tool and field descriptions, prompts, contracts/concept.py:11-15.
      - User-facing strings (Q15).
      - Stored and wire values (Q16).
      - Migration files, docstrings included: ADR-0025 freezes them whole.
      - The vendored QA scripts (Q4).
      - The CMT-017 fixtures.

      The request snapshots must stay byte-identical in every unit. That is the check that model-facing text was not
      touched.
    - _CMT-014 and CMT-015, the missing docstrings._ No campaign and no ruff `D1` rule. Requiring a docstring
      everywhere produces docstrings that only repeat the name. Ports, contracts and platform modules (gateway,
      ledger, artifacts, sandbox) get a docstring when a unit touches them, and only where it says something the name
      does not. Tool-input models, `ConceptCard` and the three enums never get a class docstring, because it would
      reach the tool schema (CMT-001). They use `#` comments.
    - _Handoff._ Each finished package is listed in docs/audit/, so the next session knows what is done.

15. CMT-001: should the OpenAPI descriptions and the CLI help stay Italian as user-facing text, or be translated in
    their own schema-change unit? **Stay Italian / translate.**

    **Answer: split them by who reads them. The CLI help stays Italian, decoupled from the docstrings. The OpenAPI
    descriptions are translated in their own schema-change unit.**

    - _CLI help._ The operator reads it, so it is user-facing. It stays Italian and unchanged, byte for byte. Each
      `ArgumentParser` gets an explicit `description=` string instead of `__doc__` (cli.py:297, serve.py:58,
      schema.py:30). The module docstring can then be English like any other comment, and the help can no longer
      change by accident (ADR-0021, explicit over implicit).
    - _OpenAPI descriptions._ Developers read them, in `schemas/openapi.json` and as JSDoc in `web/src/api/schema.ts`.
      Ninja's docs are off, and no page shows them. Being developer-facing, they become English, in one unit that runs
      `uv run agency-schemas` and `pnpm --dir web run api:types` and reviews both generated diffs (ADR-0032). Only
      descriptions change. No field, enum or `operationId` does, so the dashboard is unaffected.

16. CMT-008: keep the Italian stored and wire values, and record them as domain vocabulary in docs/03-DATA-MODEL.md?
    **Yes/no.**

    **Answer: yes.** Stored and wire values are domain vocabulary, not prose. They sit in append-only ledger rows that
    are never rewritten (ADR-0022), in the request snapshots the model sees, and in OpenAPI enums the web keys on.
    Translating them would mean a dual read forever, a cache break and a contract change, with no gain in meaning.

    - _Record the rule in docs/03-DATA-MODEL.md, with a glossary of the current values._ Identifiers are English.
      Values that are stored or cross a boundary use the studio's Italian domain vocabulary, and new values follow
      the same rule.
    - _Pin it in code._ A test lists the exact value set of every stored or wire enum. Its failure message says that
      changing a value is a migration, not a rename.

17. CMT-007: which is right? **docs/03-DATA-MODEL.md ("events are the truth") / the code (`tickets` holds the verdict
    and the delivered hashes).**

    **Answer: the docs state the right invariant, and the code falls short of it. The code changes to meet it, with a
    new ADR and a migration. Until then, the comment and the doc describe the code as it is.**

    - _Why the docs are right._ The review verdict and the delivered hashes live only in `tickets` (`Ledger.apply`,
      store.py:235-241). The chain digest covers only `prev, ticket_id, at, actor, action, note` (chain.py:13-15), and
      `tickets` is mutable by design, with no append-only triggers. The two facts that decide what reaches the client
      are therefore outside the hash chain. `agency verify` reports "registro integro" for a ledger whose verdicts
      could have been changed. That is the wrong place for them in a studio whose product is proven quality, and in a
      future SaaS where a client can dispute what was approved and delivered.
    - _Now, as a comment-edit unit._ Reword `ledger/__init__.py` as CMT-007 proposes. Correct the sentence in
      docs/03-DATA-MODEL.md so it says what is true today, and point it to the new ADR.
    - _Then, in its own unit of this refactor (it does not block `merlo4`)._
      - DELIVER and REWORK events carry their payload (the verdict and the delivered hashes) in a new column, covered
        by a versioned digest (v2) that includes it. Old events keep the v1 formula, and verification picks the formula
        by each row's version, so no historical row is rewritten.
      - The migration appends one baseline event per existing ticket. Each one binds that ticket's current `tickets`
        state into the chain from then on, append-only and with its real timestamp.
      - `agency verify` replays the events and compares the result with `tickets`. A mismatch is reported like a
        broken chain.

      `tickets` then becomes what the docs always called it: a projection.

18. STR-005, STR-009 and STR-007: do these moves happen in this refactor or in M1.7? Each is **this refactor / M1.7**:
    a new `agency/registry.py`; insights `Registry*` → `Ledger*`; `telemetry/report.py` → `cli/render.py`.

    **Answer: STR-009, then STR-005, both in this refactor. STR-007 waits for M1.7.**

    - _STR-009 first._ Rename the internal insights names `Registry*` to `Ledger*`, and `adapters/registry.py` to
      `adapters/ledger.py`. "Registry" then means one thing, the rules in `registry/`, before a module with that name
      exists. Keep `Provenance.from_registry`, `Provenance.registry_revision` and `Fingerprint.registry`. Renaming them
      would be a schema change and would rewrite stored `runs` rows, for no gain.
    - _STR-005 now._ It is a fix more than a move:
      - It deletes a dead duplicate loader.
      - It fixes a latent bug: `art-director` gets `open_ticket` but has no `can_open` row.
      - It replaces string literals with a `CheckKind` enum.
      - It gives the rules a schema before M2 loads 25 roles onto them.
      - It removes STR-004's `tools → agents` edge as a side effect.

      Load every `registry/*.json` once, into Pydantic models with `extra="forbid"`, so an unknown or misspelt field
      fails at start-up. Today `checks.json` accepts any `kind`. The request snapshots must stay byte-identical. If
      M1.7 later wants the module under `shared/`, moving one file is an import change.
    - _STR-007 waits._ Its only gain is the name. The CLI moves to `entrypoints/cli/` in M1.7, so moving `report.py`
      to `cli/render.py` now would move it twice.

19. SIM-012, STR-013 and STR-004: confirm that splitting `surface.py` and `workflow.build`, and breaking the package
    cycle, stay deferred to M1.7? **Yes/no.**

    **Answer: yes, with the one exception covered in Q18.** M1.7 exists for this work. It comes after `merlo4`, so
    the engine's behaviour is measured before anything moves, and the snapshot rule is its safety net. The exception
    is the `tools → agents` edge, which STR-005 removes now. That leaves M1.7 item 1 with only `qa ↔ tools` and the
    sandbox's mount of the QA scripts. With Q8, M1.7 can also replay `merlo4` as a golden master.

20. SEC-005: add sandbox resource limits in this refactor, after measuring Blender's and the Craft CLIs' memory?
    **Yes/no.**

    **Answer: yes, in this refactor, in two units: first the limits that need no measurement, then the memory and
    process caps after measuring. New ADR, because it adds `systemd-run` to the sandbox's runtime (ADR-0005).**

    - _Unit 1, no measurement needed._
      - A `--size` on each `--tmpfs`.
      - `RLIMIT_FSIZE` on the child process.
      - Bounded reads on the harness side: `master.problem` reads 8 bytes, not the whole `.blend`, and `view_image`
        refuses files over a fixed size before decoding them.
    - _Unit 2, the memory and process caps._ Use cgroup v2, wrapping bwrap in
      `systemd-run --user --scope -p MemoryMax=… -p MemorySwapMax=0 -p TasksMax=…`. Rlimits are the wrong tool here.
      `RLIMIT_AS` breaks Blender, GPU drivers and JIT runtimes, which reserve far more address space than they use.
      `RLIMIT_NPROC` counts every process of the user, not just the sandbox's. A cgroup counts what is actually used,
      including the tmpfs pages that rlimits never see.
    - _Measure first, at 0 $._ Run each Craft CLI and Blender in the sandbox on a representative document, such as
      the `merlo3` masters and an E6-sized scene, inside a scope with accounting on, and read `memory.peak`. Set each
      cap at about twice the largest peak. The ADR records the number and how it was measured.
    - _Fail closed._ If the scope cannot be created (no user systemd, or the controller is not delegated), the
      harness refuses to run the sandbox and says why, as it does for every other sandbox guarantee. Doctor gets the
      same check.

21. COR-013: validate project names against `^[a-z0-9][a-z0-9-]{0,62}$`? **Yes/no.** If not, which pattern?

    **Answer: yes, with a slightly stricter pattern, enforced by a type rather than by checks spread through the
    code.**

    - _Pattern._ `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$`, the rule for a DNS label: 1 to 63 characters, lower case,
      no leading or trailing hyphen. Every name in use passes (`merlo` to `merlo4`, `officina-e2e`, the tests' `p`),
      and the name stays valid as a subdomain, bucket prefix or container name once M7 isolates clients.
    - _Matching._ Use `re.fullmatch`. With `re.match`, `$` also matches before a trailing newline, so `"merlo\n"`
      would pass.
    - _Type._ One type, `ProjectName`, in `agency.contracts`. It is validated wherever a name comes in: CLI arguments,
      `Session.start` and the API's `{name}` routes. It is the only type `project_dir`, `DataLayout.transcript` and
      the artifact paths accept, so pyright stops a plain `str` from reaching the filesystem.

22. SIM-008: enforce the `craft` field of `roles.json` in the tool sets, or drop `craft` and `department` and correct
    docs/04-TOOLS.md? **Enforce / drop.**

    **Answer: enforce `craft`, drop `department`, and move the director/reviewer split into data. Do all three with
    STR-005, while they change no tool set.**

    - _`craft`._ docs/04-TOOLS.md already promises it, and the roadmap lists it as M2 work ("Il campo `craft` … va
      applicato"). Today it is free to enforce: every active author lists `vectorcraft`, so no tool set and no
      snapshot changes. In M2 it is what stops `motion-designer` (EffectCraft, FigCraft, PhotoCraft) from driving
      VectorCraft. Enforce it in two places:
      - A role with an empty `craft` list gets no `craft_*` tools.
      - `craft_run` and `craft_search` refuse an app the role does not list.

      A per-role `enum` on `app` in the tool schema would be stricter, but it changes the tool definitions. That waits
      for M2, when the snapshots change anyway.
    - _`department`._ Nothing reads it, and the hierarchy it describes already has one owner: `can_open` in
      `org.json`. An unread second copy of the same structure will drift ("un solo proprietario di ogni dato"). If M2
      needs departments, they come back in the same change as the code that reads them.
    - _The suffix rule (`endswith("-director")`)._ Each role in `roles.json` declares its tool set explicitly:
      `director`, `author`, `reviewer` or `router`. A test checks the declarations against `org.json`: a `director`
      must have a `can_open` row, and only a director may have one. That turns the latent `art-director` bug into a
      failing test today. The request snapshots of the 11 phases must not change.

### What the answers add up to

- **New ADRs**, each written in the unit that implements it:
  - the sandbox profile: inputs and resume records outside `/job` (Q1), and resource limits (Q20);
  - configuration: `.env` holds only secrets, and the data root has one resolver and one name, replacing ADR-0040's
    `AGENCY_DATA` (Q2, Q3);
  - dependencies are declared by the code that imports them, with a test that enforces it (Q5 to Q7);
  - live runs can be recorded and replayed (Q8);
  - the hash chain covers verdicts and delivered hashes (Q17);
  - the gate runs automatically (Q11).
- **Must land before `merlo4` starts:** Q1's move and Q8's recorder. Everything else can land before or after it.
  Q17's baseline events cover `merlo4` either way.
