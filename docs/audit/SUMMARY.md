# Audit summary

The seven area reports (`10`–`70`) were written by auditors briefed to find problems. A separate reviewer, who wrote
none of them, then tried to disprove every Critical, High and Medium finding: it reread the code, checked callers,
guards and tests, reproduced each finding with new scripts, and ran 38 one-line mutants on a throwaway copy. This file
is the result. It is the input for planning the sanity refactor.

- **Code audited:** identical to `8d99a5c`. The audit branch adds only `docs/audit/`. The baseline commit, cited as
  `86f51a1` in the reports, is now `e44f09a` after a reword, and the reports are `b1b48b7`.
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

1. SEC-001: is the minimal fix enough for now (refuse symlinks, `O_NOFOLLOW`)? Or should the harness-owned `.ops` move
   out of `/job` into a read-only bind, which changes how `craft_run` resumes? **Minimal / move.**
2. STR-001: how should the data root get a single owner? **(a)** `.env` keeps only the API key and `AGENCY_DATA_DIR`
   leaves `.env.example`. **(b)** The dashboard tasks receive the root the engine resolved, which needs a new ADR
   against ADR-0031, ADR-0039 and ADR-0040.
3. STR-001 and DX-003: should `.env` and `.data` resolve from the repository root instead of the current directory?
   **Yes/no.**
4. COR-016 and STR-014: should the vendored QA scripts stay byte-identical to `legacy/`, pinned by a new test? Or may
   they be fixed, for example inherited strokes in `svg_audit`? **Keep identical / allow fixes.**
5. SIM-002: remove the unused `opentelemetry-exporter-otlp-proto-http` dependency now? **Yes/no.**
6. SIM-003: drop the `context`, `qa` and `telemetry` extras until the milestone that first imports them, or keep them
   and drop only the duplicate `pillow`? **Drop / keep.**
7. SIM-004: declare `sqlalchemy` and `langchain-core` (runtime) and `httpx2` (dev) with `uv add`? **Yes/no.**
8. SIM-006: delete `RecordingTransport` and `from_cassette` and move `ScriptedTransport` into the tests, or wire
   recording behind an explicit `open_session` option? **Delete / wire.**
9. COR-008 and COR-009: implement fallback accounting (`usage.iterations`) and drop the declined attempt's blocks from
   the docs alone, or first run one live check with a declared spend cap? **Docs only / capped live check (state the cap).**
10. DX-001: when bwrap or VectorCraft is missing, should the affected tests skip, or should the session fail once at
    start, naming the binary? **Skip / fail once.**
11. DX-009: should the gate also run automatically? **None / pre-commit hook / CI / both.** Anything but "none" is a
    new ADR.
12. DX-004: should `task setup` use `uv sync --locked`, with `UV_LOCKED=1` set for every `uv run`? **Yes/no.**
13. DX-006: should Docker become optional in `agency doctor`, with a check for Playwright's Chromium added? It changes
    user-facing strings. **Yes/no.**
14. CMT-009 to CMT-016: translate code comments, docstrings and developer-facing messages to English, one package per
    unit, as the audit rules require? **Yes/no.**
15. CMT-001: should the OpenAPI descriptions and the CLI help stay Italian as user-facing text, or be translated in
    their own schema-change unit? **Stay Italian / translate.**
16. CMT-008: keep the Italian stored and wire values, and record them as domain vocabulary in docs/03-DATA-MODEL.md?
    **Yes/no.**
17. CMT-007: which is right? **docs/03-DATA-MODEL.md ("events are the truth") / the code (`tickets` holds the verdict
    and the delivered hashes).**
18. STR-005, STR-009 and STR-007: do these moves happen in this refactor or in M1.7? Each is **this refactor / M1.7**:
    a new `agency/registry.py`; insights `Registry*` → `Ledger*`; `telemetry/report.py` → `cli/render.py`.
19. SIM-012, STR-013 and STR-004: confirm that splitting `surface.py` and `workflow.build`, and breaking the package
    cycle, stay deferred to M1.7? **Yes/no.**
20. SEC-005: add sandbox resource limits in this refactor, after measuring Blender's and the Craft CLIs' memory?
    **Yes/no.**
21. COR-013: validate project names against `^[a-z0-9][a-z0-9-]{0,62}$`? **Yes/no.** If not, which pattern?
22. SIM-008: enforce the `craft` field of `roles.json` in the tool sets, or drop `craft` and `department` and correct
    docs/04-TOOLS.md? **Enforce / drop.**
