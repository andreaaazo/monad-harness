# Sanity refactor: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Each task has one checkbox. Tick it in the same unit
> that completes the task.

**Goal:** close the findings that are in scope in `docs/audit/SUMMARY.md`, in the order the plan's phases set:
1. a safety net of characterization tests;
2. bug fixes, by severity;
3. comments and language;
4. file structure;
5. developer experience;
6. simplification.

Every task is a small unit that is reversible and ends in a commit handoff.

**Architecture:** the engine stays a modular monolith (ADR-0021). The plan changes three trust boundaries, each under
a new ADR:
- the sandbox: harness files leave `/job`, and memory and task caps are added;
- configuration: one data-root resolver, and `.env` holds secrets only;
- the ledger: the hash chain covers verdicts and delivered hashes.

It also adds a request-keyed recorder for live runs. Everything else is a fix, a translation, a move or a
simplification that keeps behaviour and every pinned artifact byte-identical.

**Tech stack:** Python 3.13 (uv, pytest, ruff, pyright, import-linter, Pydantic, SQLModel, Alembic, LangGraph, Django +
Ninja), TypeScript (Next.js 16, `node --test`, Playwright), bubblewrap, Task, mise.

**Spec:** `docs/audit/SUMMARY.md`: the surviving findings and Andrea's answers to Q1–Q22. The detail of every finding
is in `docs/audit/10-…70-*.md`, and the measured starting point is `docs/audit/00-baseline.md`. Executors read the
SUMMARY answer named in a task before starting it.

## Global constraints

- **Git.** Never run a git command that writes history, the index or a remote. Every task ends with this block, then
  waits for Andrea's "committed":

  ```text
  READY FOR COMMIT
  Message: <the task's commit message>
  Files: <every file changed in the task, including docs/audit/PLAN.md>
  Verification: <the task's commands and their results>
  ```

- **One kind of change per task.** The kinds are: test, fix, comment/docs, move/rename, refactor, build/DX, dependency.
  A task that changes behaviour never also moves, renames or restyles code.
- **Where to work.** The worktree `/home/andreaaazo/Dev/design-agency-harness/.worktrees/audit/deep-review`, on branch
  `audit/deep-review`, unless Andrea names another branch before Task 1.1.
- **Standard gate,** at the end of every task. Both checks must hold unless the task says otherwise:
  - `make check` exits 0 (ruff, import-linter, pyright, pytest, web unit tests, defenses and Playwright).
  - `git diff --exit-code -- tests/snapshots/requests schemas/openapi.json web/src/api/schema.ts` prints nothing.
- **Never edit:**
  - `legacy/`;
  - the applied migrations `0001`–`0005`;
  - lockfiles, except in dependency tasks;
  - model-facing text: prompts, tool and field descriptions, and `contracts/concept.py:11-15`;
  - user-facing strings, except where a task marked [APPROVAL] says so.
- **Never call the Anthropic API.** Tests use scripted or recorded responses. Before changing any code that builds or
  reads API requests (`gateway/`, `agents/loop.py`), load the `claude-api` skill.
- **Language.**
  - English: identifiers, comments, docstrings and developer-facing messages, in new code too.
  - Italian: new user-facing and model-facing strings, in the existing style.
  - Italian: documents, ADRs, the README and `docs/*.md`.
- **ADRs.** A new decision gets a new ADR, written in the unit that implements it. Take the next free number (the plan
  lists the expected one) and add it to `docs/adr/README.md`. ADR files themselves are never edited.
- **Bookkeeping.** Each task ticks its own checkbox below, in the same unit. `docs/audit/` is the handoff between
  sessions (CLAUDE.md).
- **Scratch work** (probes, mutation copies) goes outside the repository: the session scratchpad, or `/tmp`.
- **Before `merlo4` starts,** Tasks 2.3 (Q1) and 2.33 (Q8) must have landed.

**MUTATE recipe.** It proves that a new test really guards a line of code. Use a scratch directory `M` outside the repo.

```sh
rm -rf "$M" && mkdir -p "$M" && git archive HEAD | tar -x -C "$M"
python3 -I -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); s=p.read_text(); assert s.count(sys.argv[2])==1; p.write_text(s.replace(sys.argv[2], sys.argv[3]))" "$M/<file>" '<old>' '<new>'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$M/src" .venv/bin/python -m pytest -p no:cacheprovider -q <the task's tests>
```

Run the last line from the worktree root. A mutant is **killed** when that run fails. Before applying any mutant,
check that the unmutated copy passes the same tests. `agency.config.REPO_ROOT` then resolves to `$M`.

**LANG-CHECK.** This is the language check of Phase 3. Both commands must print nothing for the task's files. Since
D6 of the Phase 3 follow-up, `tests/test_language.py` runs the same word list in `make check`, reading comments with
`tokenize`, so a `#` inside a string no longer matches:

```sh
rg -n '#.*\b(che|non|della|delle|nella|perché|sono|questo|questa|degli|alla|senza|quando|viene)\b' <files>
python3 -I -c "import ast,re,sys;W=re.compile(r'\b(che|non|della|delle|nella|perché|sono|questo|questa|degli|alla|senza|quando|viene)\b');[print(f'{f}:{getattr(n,\"lineno\",1)}') for f in sys.argv[1:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and (d:=ast.get_docstring(n)) and W.search(d)]" <python files>
```

## Review focus

Five failure modes that no finding names but that are likely to hit Andrea. Each line has its test in the task that
owns the code.

1. A `.env` copied from the old `.env.example` (with `AGENCY_DATA_DIR=.data` and the effort knobs). It must stop the
   engine with one line that names the first offending variable, and never start a fresh, empty registry. The test is
   in Task 2.16.
2. A relative `AGENCY_DATA_DIR` in the shell, for example `AGENCY_DATA_DIR=.data task dashboard`. The engine and the
   server must refuse it the same way, with the same message. The test is in Task 2.15.
3. A project paused in the middle of a `craft_run` across the layout change. On resume, the steps run once more; a
   leftover in `/job` is never read as a record. The test is in Task 2.3.
4. A project name already stored that the new rule rejects. `agency report <name>` must refuse it with a message,
   `/api/projects/<name>` must answer 404, and `/api/projects` must still answer 200. The test is in Task 2.24.
5. Five explorers recording in parallel. The lines never interleave, and replay matches by request whatever the order.
   The test is in Task 2.33.

---

## Phase 1: characterization tests

These tasks add tests only, plus one lint-configuration completion (1.19). Each test is proven by the mutants it
kills. Unless a task says otherwise, the mutants come from `docs/audit/30-tests.md` and the reviewer's lines in
`SUMMARY.md`.

- [x] **Task 1.1: a QA failure stops a delivery, and proofs must be fresh.** Closes TST-001 and TST-003.
  - Files: create `tests/test_qa_gates.py`.
  - Tests:
    - `test_a_failed_svg_audit_refuses_delivery`: through `Toolbox` and the real `Sandbox`, `run_check svg_audit` on
      an SVG containing `<svg` returns `"FAIL"`, and `deliver` then returns `is_error` containing
      `"'svg_audit' è FAIL"`.
    - `test_evidence_problems_reports_a_fail_row`: `evidence_problems` on a FAIL row returns `[f"{file}: 'svg_audit' è FAIL"]`.
    - `test_a_proof_of_an_older_version_is_stale`: expect `"è STALE"`.
    - `test_a_changed_comparison_file_makes_a_judge_proof_stale`.
    - `test_a_changed_input_is_superseded`: expect `"input superato"`.
    - `test_a_vector_production_ticket_without_master_is_refused`: expect `"manca il master"`.
    - `test_an_svg_not_exported_from_the_master_is_refused`: expect `"non risulta esportato da un master del ticket"`.
    - `test_a_master_changed_after_export_asks_to_reexport`: expect `"riesporta"`.
  - Verify:
    - `mise exec -- uv run pytest tests/test_qa_gates.py -q` → all pass.
    - MUTATE: these mutants are killed:
      - E12: `qa/checks.py`, `"FAIL" if code else "PASS"` → `"PASS"`;
      - E13: `qa/delivery.py:167`, the FAIL branch → `elif False:`;
      - E5: `qa/evidence.py:128`, the hash comparison → `if False:`;
      - E4: `evidence.py:132` → `if False:`;
      - E8: `delivery.py:218` → `if False:`;
      - E18: `delivery.py:183` → `if False:`;
      - E9: `delivery.py:199` → `why = None`.
    - Standard gate.
  - Commit: `test(qa): pin that failed checks and stale proofs stop a delivery`.
- [x] **Task 1.2: the contract and verdict rules that keep tickets deliverable.** Closes TST-011.
  - Files: `tests/test_qa_gates.py`.
  - Tests:
    - `test_an_unknown_check_name_is_refused_at_opening`: expect `"controllo sconosciuto"`.
    - `test_an_output_without_a_check_is_refused_at_opening`.
    - `test_every_file_under_a_glob_output_needs_its_checks`.
    - `test_a_review_delivered_not_verified_needs_no_proofs`.
    - `test_a_review_may_deliver_revise_on_a_fail`.
  - Verify:
    - `mise exec -- uv run pytest tests/test_qa_gates.py -q` → all pass.
    - MUTATE kills:
      - D4: `delivery.py:63` → `why = None`;
      - E10: `delivery.py:81` → `if False:`;
      - E16: `delivery.py:226` → `pass`;
      - D3: `delivery.py:155` → `if False:`;
      - D6: the REVISE exemption at `delivery.py:167`, removed.
    - Standard gate.
  - Commit: `test(qa): pin the contract and verdict rules of delivery`.
- [x] **Task 1.3: acceptance refuses at the client gate and in `accept_ticket`.** Closes TST-002.
  - Files: `tests/test_qa_gates.py`, `tests/test_sketch_flow.py`.
  - Tests:
    - `test_acceptance_requires_the_independent_check`: expect `"manca la prova 'critique'"`.
    - `test_acceptance_refuses_an_independent_check_signed_by_the_assignee`: expect
      `"firmata dall'autore, serve un revisore"`.
    - `test_acceptance_refuses_a_file_changed_after_delivery`: expect `"modificato dopo la consegna"`.
    - `test_client_approval_of_a_root_without_critique_goes_back_to_rework`: a flow test where the root ends in
      `Status.REWORK` and its note contains `"Accettazione rifiutata dal sistema"`.
  - Verify:
    - MUTATE kills:
      - W2: `workflow.py:398` → `problems = []`;
      - T9: `surface.py:523` → `if False:`;
      - D1: `delivery.py:241`, `True` → `False`;
      - E6: `delivery.py:163` → `elif False:`;
      - E7: `delivery.py:239` → `if False:`;
      - E14: `delivery.py:158` ignores `include_independent`.
    - Standard gate.
  - Commit: `test(qa): pin that acceptance refuses missing, self-signed and changed work`.
- [x] **Task 1.4: who may sign, and a FAIL persists (ADR-0018).** Closes TST-004 and TST-008.
  - Files: `tests/test_qa_gates.py`.
  - Tests:
    - `test_a_reviewer_cannot_deliver_on_the_authors_proofs`: expect `"manca la prova"`.
    - `test_a_fail_stays_until_its_signer_changes_it`: after a critic FAIL and then a director PASS on the same hash,
      the result is still `"è FAIL"`. A critic PASS clears it, and so does a changed file.
    - `test_an_author_cannot_sign_an_independent_check`: expect `"è indipendente"`.
    - `test_a_role_outside_the_check_roles_cannot_sign_it`: `qa-inspector` signing `critique` gets `"lo firma"`.
    - `test_the_critic_signs_critique`.
  - Verify:
    - MUTATE kills:
      - D2: `evidence.py:108` → `if False:`;
      - E3: `evidence.py:120` → `table[key] = ordered[-1]`;
      - E1: `evidence.py:62` → `if False:`;
      - E2: `evidence.py:64` → `if False:`.
    - Standard gate.
  - Commit: `test(qa): pin the signer rules of independent checks`.
- [x] **Task 1.5: rework clears a verdict, and `verify` exits 1 on a broken chain.** Closes TST-013 and TST-014.
  - Files: `tests/test_ledger.py`.
  - Tests:
    - `test_rework_clears_a_review_verdict`: expect `status() == (Status.REWORK, None)`.
    - `test_verify_exits_1_on_a_broken_chain`: drop `events_no_update`, update one event, then
      `cli.main(["verify"]) == 1`, with output containing `"REGISTRO ALTERATO"`.
  - Verify:
    - MUTATE kills:
      - L2: `store.py:238`, `elif action is Action.REWORK:` → `elif False:`;
      - L5: `cli.py:58` → `return 0 if not broken else 1`.
    - Standard gate.
  - Commit: `test(ledger): pin rework verdicts and the verify exit code`.
- [x] **Task 1.6: the budget and the model reach the ledger from the CLI.** Closes TST-005.
  - Files: `tests/test_hardening.py`.
  - Tests:
    - `test_run_hands_budget_and_model_to_the_ledger`: patch `agency.runtime.open_session` so it builds the real
      session over a `ScriptedTransport`, scripted so that the director blocks at once. Run
      `cli.main(["run","p",brief,"--budget","12","--model","claude-sonnet-5-5"])`, then expect
      `ledger.project("p").budget_usd == 12.0` and `.model == "claude-sonnet-5-5"`.
    - `test_budget_command_changes_the_cap`: `cli.main(["budget","p","40"]) == 0`, and the stored cap is `40.0`.
  - Verify:
    - MUTATE kills:
      - B2: `cli.py:148` → `budget=1000.0,`;
      - B3: `cli.py:149` → `model="",`;
      - B1: `cli.py:189` → `pass`.
    - Standard gate.
  - Commit: `test(cli): pin that run and budget hand their values to the ledger`.
- [x] **Task 1.7: resume repeats no effect and records a gate only once.** Closes TST-007 and TST-015.
  - Files: `tests/test_agent_flow.py`, `tests/test_sketch_flow.py`.
  - Tests:
    - `test_an_effect_tool_records_its_result_for_resume`: one turn holding `run_check` and `deliver`. Make
      `Transcript.append` raise once, on the tool-result append, then resume. Expect one evidence row,
      `ledger.operation(id) is not None`, and an instance that closes `DELIVERED`.
    - `test_resuming_the_same_concept_decision_records_one_gate`: exactly one `gates` row.
  - Verify:
    - MUTATE kills:
      - H1: `surface.py:945`, `record_operation(...)` → `pass`;
      - W3: `workflow.py:306` → `if True:`.
    - Standard gate.
  - Commit: `test(engine): pin that resume repeats no effect and records the gate once`.
- [x] **Task 1.8: the live request shape and the estimate after the first call.** Closes TST-009 (its remainder) and
  TST-010.
  - Files: `tests/test_gateway.py`. Load the `claude-api` skill first.
  - Tests:
    - `test_live_transport_sends_the_gateway_params_through_the_sdk`: run `AnthropicTransport` over
      `httpx2.MockTransport`, as `tests/test_gateway.py:157` does. Expect:
      - the `count_tokens` body has exactly `{"model","system","messages"}`, plus `tools` when present;
      - the `messages` body carries `thinking={"type":"adaptive"}`, `output_config.effort`, `cache_control`, and
        `fallbacks="default"`;
      - the beta header contains `server-side-fallback-2026-07-01`.
    - `test_estimate_after_the_first_call_prices_context_and_new_tokens`. With a previous context of 100,000 tokens
      and a last message of 3,000 characters plus one image, expect
      `(100_000*cache_read + (1_000+2_500)*cache_write_5m + 4_000*output)/1e6` at the `claude-opus-5-5` prices in
      `pricing.PRICES`.
    - `test_a_cap_crossed_only_by_the_input_part_stops_the_call`.
  - Verify:
    - MUTATE kills:
      - P1: `transport.py:37` → `fields = params`;
      - P2: `fallbacks="default"` removed;
      - G2: `client.py:76` → `total += 0`;
      - G4: `client.py:122` → `input_cost = 0.0`;
      - G6: `client.py:121` → `fresh = 0`.
    - Standard gate.
  - Commit: `test(gateway): pin the live request shape and the follow-up estimate`.
- [x] **Task 1.9: each role sends its registry model and effort.** Closes TST-012.
  - Files: `tests/test_agent_flow.py`.
  - Tests:
    - `test_each_role_sends_its_registry_model_and_effort`: for `critic`, `design-director`, `identity-designer` and
      `qa-inspector`, with no client choice, the first request's `model` and `output_config.effort` equal
      `registry/roles.json`. For example, `qa-inspector` sends `claude-sonnet-5-5` / `medium`.
  - Verify:
    - MUTATE kills:
      - A1: `loop.py:135` → `"claude-opus-5-5"`;
      - A2: `loop.py:136` → `"high"`;
      - A3: `loop.py:135` → `"claude-sonnet-5-5"`.
    - Standard gate.
  - Commit: `test(agents): pin the per-role model and effort`.
- [x] **Task 1.10: three tool refusals.** Closes TST-016.
  - Files: `tests/test_sketch_flow.py`.
  - Tests: one `Toolbox.call` test per refusal. Each asserts `is_error` and the message currently in
    `surface.py:669`, `:444-445` and `:399`.
    - `test_select_concepts_refuses_more_than_three`;
    - `test_judge_refuses_a_file_against_itself`;
    - `test_export_master_refuses_unknown_options`.
  - Verify:
    - MUTATE kills:
      - T13: `len(a.chosen) > 3` → `False`;
      - T15: the self-comparison refusal → `pass`;
      - T18: `flags - EXPORT_OPTIONS` → `False`.
    - Standard gate.
  - Commit: `test(tools): pin three tool refusals`.
- [x] **Task 1.11: isolation probes that cannot pass by accident.** Closes TST-006.
  - Files: `tests/test_agent_flow.py:441-456`, `web/e2e/run.spec.ts:173-184`.
  - Change the probes:
    - Inside the sandbox, print `socket.if_nameindex()` names and `os.statvfs("/usr").f_flag & os.ST_RDONLY`. Assert
      the names are `["lo"]` and the flag is set.
    - In e2e, read the listening sockets of ports 13765, 13766 and 18765 from `/proc/net/tcp` and `/proc/net/tcp6`.
      Assert each is bound to `127.0.0.1` or `::1`, and remove `test.skip`.
  - Verify:
    - MUTATE kills these even with networking disabled:
      - X2: `--unshare-net` removed;
      - X3: `--ro-bind /usr` → `--bind /usr`.
    - `make e2e` → 22 passed, 0 skipped.
    - Standard gate.
  - Commit: `test(sandbox): prove isolation by what the sandbox sees, not by a failed probe`.
- [x] **Task 1.12: the reader test checks that the writer started.** Closes TST-017 (the `wait` half).
  - Files: `tests/test_insights.py:578`.
  - Change: `assert writing.wait(timeout=10)`.
  - Verify: `mise exec -- uv run pytest tests/test_insights.py -q`; standard gate.
  - Commit: `test(insights): fail when the concurrent writer never started`.
- [x] **Task 1.13: what `compute` and `craft_run` do, as a safety net for 2.1–2.3.**
  - Files: `tests/test_agent_flow.py`.
  - Tests:
    - `test_compute_runs_the_script_and_returns_exit_and_output`: expect `{"exit": 0, "output": "42\n"}`.
    - `test_craft_run_replays_its_stored_result_on_resume`: with a fake `Sandbox` that counts `run()` calls, a second
      call with the same operation id makes no new `run()`, returns the same `results`, and the document is copied
      again.

    Assert behaviour only, no paths: Task 2.3 moves the files.
  - Verify: `mise exec -- uv run pytest tests/test_agent_flow.py -k "compute or replays" -q`; standard gate.
  - Commit: `test(tools): pin compute output and craft_run replay`.
- [x] **Task 1.14: the reminder texts and the closing tools, as a safety net for 6.8.**
  - Files: `tests/test_agent_flow.py`.
  - Tests:
    - `test_the_reminder_names_each_phase_closing_tools`: for each tool set, assert the exact current
      `AgentRunner._reminder` string. The sets are `role_tools("identity-designer")`, `role_tools("design-director")`,
      and the `EXPLORE`, `PROPOSAL`, `PLAN`, `SELECT`, `PRESENT` and `BOARD` sets.
    - `test_restore_closes_each_closing_tool_with_its_state`: covers every `CLOSE_ALWAYS` name, plus
      `select_concepts`, `draft_presentation` and `present_concepts`, each with a sample stored value.
  - Verify: `mise exec -- uv run pytest tests/test_agent_flow.py -k "reminder or restore" -q`; standard gate.
  - Commit: `test(agents): pin the reminder text and the closing outcomes`.
- [x] **Task 1.15: the data paths, as a safety net for 2.15, 6.11 and 6.12.**
  - Files: create `tests/test_layout.py`.
  - Tests:
    - `test_data_paths_under_a_root`. `DataLayout(Path("/r"))` gives `/r/ledger.sqlite`,
      `/r/checkpoints.sqlite`, `/r/artifacts`, `/r/traces.jsonl`, `/r/insights.sqlite`, `/r/runs`, and
      `transcript("p","i") == Path("/r/runs/p/i.jsonl")`.
      `Settings(data_dir=Path("/r"), projects_dir=Path("/q"), _env_file=None)` gives the same paths, and
      `project_dir("p") == Path("/q/p")`.
  - Verify: `mise exec -- uv run pytest tests/test_layout.py -q`; standard gate.
  - Commit: `test(config): pin where the data lives`.
- [x] **Task 1.16: the CLI help, byte for byte, as a safety net for 3.1, 3.7 and 3.16.**
  - Files: create `tests/test_cli_help.py` and `tests/snapshots/cli/*.txt`. The snapshots are one for `agency`, one
    per subcommand (14), `agency-server` and `agency-schemas`.
  - Tests:
    - `test_cli_help_is_unchanged`: set `COLUMNS=100` with `monkeypatch`, then capture `--help` from `cli.main`,
      `serve.main` and `schema.main` under `pytest.raises(SystemExit)` and `capsys`.
    - `UPDATE_SNAPSHOTS=1` rewrites the files, as in `tests/test_request_snapshots.py:27`.
  - Verify:
    - The tests pass.
    - Mutant: changing one word of `cli.py`'s module docstring is killed.
    - Standard gate.
  - Commit: `test(cli): pin the help text of every command`.
- [x] **Task 1.17: the stored and wire values, as a safety net for Phase 3 and for 6.7.** Closes CMT-008 (its "pin it
  in code" part, Q16).
  - Files: create `tests/test_vocabulary.py`.
  - Tests:
    - `test_stored_and_wire_values_are_fixed`: the exact value sets of `TicketType`, `Medium`, `Verdict`, `Status`,
      `Action`, `Level`, `RunCommand`, `OutcomeState`, and the OpenAPI enums `Compared` and `Alignment`.
    - The failure message reads: "a stored or wire value changes only through a migration, never a rename".
  - Verify:
    - Mutant: renaming one `TicketType` value is killed.
    - Standard gate.
  - Commit: `test(contracts): pin every stored and wire value`.
- [x] **Task 1.18: the vendored QA scripts are pinned.** Closes STR-014 (Q4).
  - Files:
    - create `src/agency/qa/scripts/MANIFEST.json`, holding per script its `legacy` path, its `legacy_sha256` and
      its current `sha256` (equal today);
    - `tests/test_registry.py`.
  - Tests:
    - `test_vendored_qa_scripts_match_their_manifest`. Each copy and each legacy original match the manifest. Where
      `sha256 != legacy_sha256`, `src/agency/qa/scripts/PATCHES.md` must name the file.
  - Verify:
    - Mutant: one byte appended to a script in the copy is killed.
    - Standard gate.
  - Commit: `test(qa): pin the vendored QA scripts against a manifest`.
- [x] **Task 1.19: the import-linter contract lists stay complete.** Closes STR-002.
  - Files: `tests/test_server.py:417`, and `pyproject.toml`: the forbidden lists of the insights, server and evaluation
    contracts gain the packages that are missing today.
  - Tests:
    - `test_every_slice_contract_forbids_every_engine_package`: each contract forbids all the packages on disk,
      except an allow-list. The allow-lists are insights `{agency.contracts}`, server
      `{agency.contracts, agency.insights}` and evaluation `{agency.contracts}`.
  - Verify:
    - `mise exec -- uv run lint-imports` → "4 kept, 0 broken".
    - The STR-002 mutation (a new package that insights, the server and evaluation all import) makes the test fail.
    - Standard gate.
  - Commit: `test(structure): keep every slice contract complete`.

### Phase 1 status (2026-11-05)

Done in twelve commits, `d76b4f5` to `53eadda`. No file under `src/`, `legacy/` or `pyproject.toml` changed:
`git diff --stat f7a3221 HEAD -- src pyproject.toml legacy` is empty. The Python suite went from 496 tests to 597, and
`make check` is green, with 22 Playwright tests and none skipped. Mutants were run per module on a scratch copy of the
repository, and the new tests killed every one. Each commit handoff lists them. For comparison, Task 1.11's mutant X3
was also run against the old probe, and it survived there, as TST-006 says.

Deviations from the tasks above:
- Task 1.11: the e2e test keeps its title, and its new assertion messages are in English.
- Task 1.14 calls `AgentRunner._reminder` directly, as the task says. It takes each tool set from `tools_for`, and it
  restores through `Toolbox.call`.
- Task 1.17 also pins `Lifecycle`, the third enum in `schemas/openapi.json`.
- Task 1.18: the manifest is `tests/fixtures/qa_scripts.json`, not `src/agency/qa/scripts/MANIFEST.json`, because
  Phase 1 changes no production file. `PATCHES.md` keeps its planned path: the unit that first patches a script
  creates it.
- Task 1.19 is half done, so its box stays empty. Its test exists and pins today's gaps as STR-002: `SLICE_GAPS` in
  `tests/test_server.py` lists `config`, `context` and `doctor` for insights, and `context` and `doctor` for the
  server. The `pyproject.toml` half is not done, and no other task closes STR-002. Andrea decides where it goes. When
  it lands, `SLICE_GAPS` empties. Done in D8 of the Phase 3 follow-up: the lists are complete and `SLICE_GAPS` is gone.

Known bugs pinned as they behave today. Each pin has a comment that names the task that flips it:

| Finding | Test | Flipped by |
|---|---|---|
| SEC-001 | `tests/test_hardening.py::test_compute_writes_through_a_planted_ops_symlink` | 2.1 |
| COR-001 | `tests/test_agent_flow.py::test_observe_accepts_a_render_viewed_for_an_older_version` | 2.4 |
| SEC-003 | `tests/test_sketch_flow.py::test_a_hidden_image_never_reaches_the_presentation` | 2.6 |
| SEC-004 | `tests/test_hardening.py::test_a_reviewer_leaves_reviews_with_dotdot` | 2.7 |
| COR-007 | `tests/test_agent_flow.py::test_sources_with_one_stem_share_one_proof` | 2.8 |
| COR-012 | `tests/test_agent_flow.py::test_two_zooms_with_one_corner_share_one_file` | 2.8 |
| COR-006 | `tests/test_insights.py::test_a_line_torn_inside_a_utf8_character_breaks_the_whole_read` | 2.9 |
| COR-004 | `tests/test_hardening.py::test_a_brief_that_is_not_utf8_leaves_the_project_name_stuck` | 2.10 |
| COR-002 | `tests/test_gateway.py::test_parallel_calls_overspend_the_cap` | 2.11 |
| COR-008 | `tests/test_gateway.py::test_a_fallback_call_is_charged_only_for_the_serving_attempt` | 2.13 |
| DX-003 | `tests/test_ledger.py::test_verify_on_a_missing_registry_creates_one_and_calls_it_intact` | 2.14 |
| STR-001 | `tests/test_layout.py::test_engine_and_server_take_the_data_root_from_different_places` | 2.15–2.16 |
| COR-013 | `tests/test_layout.py::test_project_names_become_folders_unchecked` | 2.24 |
| STR-002 | `tests/test_server.py::test_every_slice_contract_forbids_every_engine_package` | D8 (Phase 3 follow-up) |

Coverage, measured as in `00-baseline.md` §3: the static scan of `tests/*.py`, the `sys.modules` recorder of §5,
and the same nine other-path modules. The scan gives the baseline's by-name count for all 90 modules when it runs on
the tests of `8d99a5c`.

| Status | Baseline | Now |
|---|---:|---:|
| direct | 60 | 61 |
| indirect | 18 | 17 |
| other path | 9 | 9 |
| none | 3 | 3 |
| `agency.*` modules loaded in a full session | 78 | 78 |

Only `agency.ledger.store` changed status: it went from indirect to direct, because `tests/test_qa_gates.py` imports
it. The three modules with no tests stay that way:
- `agency.context` is a placeholder.
- `logo_proof` and `optical_check` are pinned by their bytes (Task 1.18), but no test runs them.

Phase 1 added assertions on modules the suite already loaded, and a module count cannot show that. The repository
still has no line-coverage tool.

## Phase 2: bug fixes

The order is Critical, then High, then Medium, then Low. Low comes last but still precedes Phases 3–6, because those
must not change behaviour. Every task starts with its failing test.

### Critical

- [x] **Task 2.1: a no-follow helper for the files the harness writes.** Closes SEC-001, part 1 of 3 (Q1).
  - Files:
    - `src/agency/tools/files.py`;
    - `src/agency/tools/surface.py` (`compute`, :388-394);
    - `src/agency/tools/craft.py` (`run_steps`, :95-134);
    - create `tests/test_safe_files.py`;
    - `tests/test_hardening.py`.
  - Interfaces produced, in `agency.tools.files`. Each one walks the path with directory descriptors, opening every
    component with `O_DIRECTORY | O_NOFOLLOW` from the trusted root. A symlinked component, `..` or an absolute path
    raises `OutsidePerimeter`.
    - `open_under(root: Path, relative: str, flags: int, mode: int = 0o600) -> int`;
    - `ensure_dir_under(root: Path, relative: str) -> None`;
    - `read_under(root: Path, relative: str) -> bytes`;
    - `write_new_under(root: Path, relative: str, data: bytes) -> None`, using `O_CREAT | O_EXCL | O_NOFOLLOW`;
    - `replace_under(root: Path, relative: str, data: bytes) -> None`, which writes a temporary file and calls
      `os.replace` with `src_dir_fd`/`dst_dir_fd`;
    - `sha256_under(root: Path, relative: str) -> str`.
  - Tests:
    - `test_a_symlinked_directory_component_is_refused`;
    - `test_dotdot_and_absolute_paths_are_refused`;
    - `test_write_new_under_refuses_an_existing_file`;
    - `test_compute_never_writes_through_a_planted_ops_symlink`. This is the auditor's `ops_symlink_probe` as a
      regression test: plant `.ops -> <tmp target>`, then `compute` returns `is_error`, and the target folder stays
      empty.
  - Verify: `mise exec -- uv run pytest tests/test_safe_files.py tests/test_hardening.py -q`; standard gate.
  - Commit: `fix(tools): write harness files under /job without following symlinks`.
- [x] **Task 2.2: every harness read and write under `/job` goes through the helper.** Closes SEC-001 part 2 of 3, and
  SEC-003's symlink half.
  - Files:
    - `src/agency/tools/surface.py` (`read_file`, `write_file`, `view_image`);
    - `src/agency/tools/render.py`, `src/agency/tools/presentation.py` (`_fit`, `build`), `src/agency/tools/board.py`,
      `src/agency/tools/master.py`;
    - `src/agency/qa/evidence.py` and `src/agency/qa/delivery.py` (hashing of work files);
    - `src/agency/artifacts/keeping.py`;
    - `tests/test_safe_files.py`.
  - Tests:
    - `test_harness_readers_refuse_a_planted_symlink`, parametrized over `render_one`, `view_image`, the presentation
      image reader, delivery hashing, `keeping` and `board.build`. Each one refuses, and the sentinel file outside the
      work folder is never read.
  - Verify: the tests pass; `rg -n 'inside\(ctx\.work|inside\(sandbox\.work|inside\(work' src/agency` shows only path
    computations, with no direct `open`, `read_*` or `write_*` on their result; standard gate.
  - Commit: `fix(tools): read and write the work folder only through the no-follow helper`.
  - As built: `artifacts/keeping.py` and the `keeping` case of the test moved to Task 2.2a, by the owner's decision.
    Found entry 2.F19 stays open.
- [x] **Task 2.2a [APPROVAL]: keep reads delivered files through the no-follow helper.** Closes SEC-001 part 2 for `keep` (the reader the owner's Q1 answer names). Approved by Andrea on 2026-11-06 as its own unit after Task 2.2. `ArtifactStore.put` takes an opened binary file instead of a path; `ToolContext.keep` and `keeping.keep` open each delivered file with `open_under`. Test: `keep` refuses a planted symlink and never reads the sentinel outside the work folder.
- [x] **Task 2.3 [APPROVAL]: harness inputs and resume records leave `/job`.** Closes SEC-001 (Q1). New ADR, expected
  ADR-0044 ("I file dell'harness fuori dalla sandbox").
  - Files:
    - `src/agency/contracts/layout.py`;
    - `src/agency/tools/sandbox.py` (the new `ops: Path | None` argument, bound read-only at `OPS = "/ops"`);
    - `src/agency/tools/surface.py` (`compute`), `src/agency/tools/craft.py` (`run_steps`);
    - the `Sandbox(...)` construction sites (find them with `rg -n "Sandbox\(" src/agency`);
    - `docs/adr/0044-*.md`, `docs/adr/README.md`, `docs/06-SECURITY.md`, `docs/03-DATA-MODEL.md`;
    - `tests/test_agent_flow.py`.
  - Interfaces: `DataLayout.ops_inputs(project: str, instance: str) -> Path` resolves to
    `<root>/ops/<project>/<instance>/in`, and `DataLayout.ops_records(project: str, instance: str) -> Path` to
    `<root>/ops/<project>/<instance>`.
  - Where things go:
    - `compute` writes its script into `ops_inputs` and runs `/ops/compute_<id>.py`.
    - `craft_run` writes its plan into `ops_inputs` and exports to `/job/.partial/<op>.vectorcraft`. The harness then
      copies the result JSON and the built document into `ops_records`, through the helper. Resume reads only
      `ops_records`.
    - `list_files` keeps hiding the dot-folders.
  - Tests:
    - `test_compute_script_lives_outside_the_work_folder`: `/job` has no `.ops`, and sandbox code that opens
      `/ops/x` for writing fails.
    - `test_craft_run_resume_reads_only_the_harness_record`: anything written into `/job` is ignored on resume.
    - `test_resume_with_a_record_only_in_the_old_place_reruns_once` (Review focus 3).
    - Task 1.13's tests still pass. Only their call to `run_steps` may change, to pass the new directories; their
      assertions stay as they are. The request snapshots are byte-identical.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(sandbox): keep harness inputs and resume records outside the writable work folder`.
  - As built:
    - ADR-0044 is `docs/adr/0044-i-file-dell-harness-fuori-dalla-sandbox.md`.
    - `run_steps` gains `records: Path` and takes the plan folder from `sandbox.ops`. `craft_run` passes
      `ctx.settings.layout.ops_records(project, instance)`. Without `sandbox.ops` (and, for `craft_run`, without
      settings), both tools refuse with `"<tool> non è disponibile in questa sandbox: manca la cartella /ops"`. They
      never fall back to `/job`.
    - The copy of the built document into its target goes through `ensure_dir_under` and `replace_under`.
    - `list_files` hides `.ops` (left in older work folders) and `.partial`. A fourth test pins it:
      `test_list_files_hides_the_partial_exports`.
    - Construction sites: `agents/loop.py` creates `ops_inputs` beside the work folder and passes it as `ops`.
      `graph/workflow.py:397` (`client_gate`) keeps `ops=None`, because `acceptance_problems` only hashes delivered
      files and checks evidence: it runs nothing in the sandbox.
    - Tests changed only in construction: `bare_context` and `CountingSandbox` (test_agent_flow.py), `context`
      (test_hardening.py) and `test_finisher_cannot_explore` (test_sketch_flow.py) pass the new folders. The two
      Task 2.1 tests keep their names and their core assertion (the host folder stays empty), but compute and
      `run_steps` no longer touch `/job/.ops`. So the planted-link compute now succeeds, and `run_steps` returns the
      idle sandbox's failure instead of raising `OutsidePerimeter`.

### High

- [x] **Task 2.4: a render proof counts only for the version that was viewed.** Closes COR-001.
  - Files: `src/agency/tools/surface.py` (`_seen_proof`, :410-419), `tests/test_agent_flow.py`.
  - Tests:
    - `test_observe_refuses_a_render_viewed_for_an_older_version`. Render a red `a.png` and view the proof. Turn the
      file black and render it again, without viewing. `observe` must then be refused with
      `"non hai guardato un render della versione attuale"`.
  - Implementation: accept a proof only if `f"{proof}:{sha256_under(ctx.work, proof)}"` is in `_viewed(ctx)`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(tools): accept a render proof only for the version that was viewed`.

### Medium

- [x] **Task 2.5: open sandbox-written images only in safe formats.** Closes SEC-002 and COR-015.
  - Files:
    - create `src/agency/contracts/media.py`;
    - `src/agency/tools/render.py`, `src/agency/tools/surface.py` (`view_image`), `src/agency/tools/board.py`,
      `src/agency/tools/presentation.py`, `src/agency/evaluation/board.py`;
    - create `tests/test_media.py`.
  - Interfaces:
    - `IMAGE_MEDIA_TYPES: dict[str, str]` = `{"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}`;
    - `open_image(data: bytes) -> Image.Image`, which calls `Image.open(BytesIO(data), formats=list(IMAGE_MEDIA_TYPES))`;
    - `media_type(image: Image.Image) -> str`.

    These live in `contracts`, because `evaluation` may not import `tools`.
  - Tests:
    - `test_an_eps_file_named_png_is_refused`: raises `UnidentifiedImageError`.
    - `test_view_image_takes_the_media_type_from_the_content`: JPEG bytes in `x.png` are sent as `image/jpeg`.
  - Verify: the tests pass; `rg -n "Image\.open\(" src/agency --glob '!**/qa/scripts/**'` finds only
    `contracts/media.py`; standard gate.
  - Commit: `fix(tools): open sandbox-written images only as PNG, JPEG, WebP or GIF`.
- [x] **Task 2.6: the presentation shows only delivered images.** Closes SEC-003.
  - Files: `src/agency/tools/presentation.py` (`proposal_files`), `src/agency/graph/workflow.py` (`present`, :255-263),
    `src/agency/tools/surface.py` (`draft_presentation`), `tests/test_sketch_flow.py`.
  - Interface: `proposal_files(work: Path, turn: int, anon: str, delivered: Iterable[str]) -> tuple[Path, tuple[Path, ...]]`.
  - Tests:
    - `test_a_hidden_image_never_reaches_the_presentation`: a real `applicazioni-v/.zz.png` that was not delivered
      appears in no page.
  - Verify: the test passes; standard gate.
  - Commit: `fix(presentation): show only the images the proposal delivered`.
- [x] **Task 2.7: the reviewer write rule checks the resolved path.** Closes SEC-004.
  - Closed as not reproduced (2026-11-13), with the probe's routes pinned as tests instead of the planned change.
    The planned `inside(ctx.work, a.path)` resolves symlinks. On the work folder, which the sandbox can write, that
    is the very pattern Task 2.2 replaced with the no-follow helpers, so adding it would weaken the rule. The rule
    holds through two layers: the lexical `startswith("reviews/")` and the no-follow helpers, which refuse `..` and
    never follow a link.
  - New tests in tests/test_hardening.py, beside `test_a_reviewer_cannot_leave_reviews_with_dotdot`:
    - five other spellings are refused and write nothing: `reviews/./..`, `reviews//..`, an absolute path,
      `Reviews/` and backslashes;
    - `reviews` as a link to the work folder and `reviews/up -> ..` are refused;
    - a review written over a planted `reviews/x.md -> ../brief.md` replaces the link, not its target.
  - On a scratch copy, letting `_parts` accept `..` fails 3 of them, and dropping `O_NOFOLLOW` from `_enter`
    fails 10.
  - Files: `src/agency/tools/surface.py` (`write_file`, :298-305), `tests/test_hardening.py`.
  - Tests:
    - `test_a_reviewer_cannot_leave_reviews_with_dotdot`: `reviews/../brief.md` is refused with
      `"un revisore scrive solo in reviews/"`, and `brief.md` stays unchanged.
  - Implementation: compare `inside(ctx.work, a.path)` with `inside(ctx.work, "reviews")` using `is_relative_to`.
    Since Task 2.2, the no-follow helper refuses `..` first; this task still adds the resolved-path rule, and its test
    then expects the reviewer message.
  - Verify: the test passes; standard gate.
  - Commit: `fix(tools): check the reviewer write rule on the resolved path`.
  - **Not reproduced (2026-11-06).** Tried on a pristine `git archive HEAD` copy, as `critic` (and `qa-inspector`,
    `legal-reviewer` for the first): `reviews/../brief.md`, `reviews/./../brief.md`, `reviews//../brief.md`,
    trailing/doubled slash, absolute paths (also `/reviews/../brief.md`), `reviews` as a symlink to the work folder,
    `reviews/x.md -> ../brief.md`, `reviews/d -> ../secret`, `reviews/up -> ..`, full-width slash, backslashes, NUL
    byte, `Reviews/` case. No file outside `reviews/` changed in any attempt. Why each fails: the three `..` routes
    (`PurePosixPath` drops `.` and `//` but keeps `..`) are refused by `_parts` (`files.py:25-29`); absolute, backslash,
    full-width slash and case variants fail the prefix check at `surface.py:315`, and absolute paths also at
    `files.py:28`; a trailing or doubled slash on a text name fails `_text_only` (`surface.py:288-290`); the symlinked
    `reviews`, `reviews/d` and `reviews/up` are refused by `O_NOFOLLOW` in `_enter` (`files.py:41-47`,
    `_refuse_a_link` `:33-38`); the NUL byte is rejected by `os.mkdir`; `reviews/x.md -> ../brief.md` is accepted but
    `replace_under` renames over the link itself (`files.py:95-107`), so `brief.md` stays unchanged. The regression test
    `tests/test_hardening.py::test_a_reviewer_cannot_leave_reviews_with_dotdot` already guards the `..` route.
    Probe: `/tmp/claude-1000/-home-andreaaazo-Dev-design-agency-harness/9e06fba2-14d0-4eec-bfc3-a96db23a2412/scratchpad/task-2.7/probe.py`.
- [x] **Task 2.8: each proof is named after its source file and its zoom box.** Closes COR-007 and COR-012, which share
  one root cause. The real lines are `render.py:20-21`, `:36` and `:65`; the report cites :105 and :150.
  - Files: `src/agency/tools/render.py`, plus any test that asserts a proof path.
  - Implementation:
    - `_stem` keeps the extension: `relative.replace("/", "_")`, so `exports_segno.svg.png`.
    - The zoom name adds `w` and `h`: `_zoom_{x:.2f}_{y:.2f}_{w:.2f}_{h:.2f}`.
  - Tests:
    - `test_same_stem_sources_get_distinct_proofs`: renders of `x.png` and `x.jpg` give two paths.
    - `test_two_zooms_with_one_corner_get_two_files`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(render): name each proof after its source file and zoom box`.
- [x] **Task 2.9: transcripts are decoded line by line.** Closes COR-006.
  - Files: `src/agency/insights/adapters/transcripts.py` (`_entries`, :88-100), `tests/test_insights.py`.
  - Tests:
    - `test_a_line_torn_inside_a_utf8_character_counts_as_unreadable`: a file holding one whole line plus `b'{"a":"\xc3'`
      reads as 1 entry and 1 unreadable line.
  - Implementation: read the file as bytes, and decode each line inside the per-line `try`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(insights): skip a torn transcript line instead of failing the whole read`.
- [x] **Task 2.10: the brief is validated before the project exists, and resume says when there is nothing to
  resume.** Closes COR-004.
  - Files: `src/agency/runtime.py` (`Session.start` :67-104, `resume`), `src/agency/cli.py` (`_run`, `_resume`),
    `tests/test_hardening.py`.
  - Tests:
    - `test_a_brief_that_is_not_utf8_leaves_no_project`: exit 1, a message saying the brief is not UTF-8, and
      `ledger.project("p") is None`.
    - `test_resume_without_saved_work_says_so`: exit 1 with one line, and no `runs` row.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(runtime): validate the brief before the project exists, and say when there is nothing to resume`.
- [x] **Task 2.11: parallel calls cannot overspend the cap.** Closes COR-002.
  - Files: `src/agency/gateway/client.py` (`authorize`, `call`), `tests/test_gateway.py`.
  - Implementation: a `threading.Lock` plus `_reserved: dict[str, float]`. Authorize against
    `spent + reserved + estimate`, and release the reservation in `finally`, after `_record` or on error.
  - Tests:
    - `test_parallel_calls_cannot_overspend_the_cap`. Five threads wait at a barrier, against a 0.20 $ cap and a cost
      equal to the 0.085 $ estimate. Expect 2 calls streamed, 3 refused, and spend ≤ 0.20.
    - `test_a_call_that_fails_while_streaming_releases_its_reservation`: a dropped connection frees its estimate, so
      two later calls still fit a 0.20 $ cap.
  - Verify: the test passes; standard gate.
  - Commit: `fix(gateway): reserve each call's estimate until its usage is recorded`.
- [x] **Task 2.12 [APPROVAL]: one process at a time works on a project.** Closes COR-005.
  - Files: `src/agency/contracts/layout.py`, `src/agency/runtime.py`, `src/agency/cli.py` (`_run`, `_resume`,
    `_decide`), `tests/test_hardening.py`.
  - Interfaces:
    - `DataLayout.lock(project: str) -> Path` resolves to `<root>/locks/<project>.lock`.
    - `ProjectLock(path)` is a context manager using `fcntl.flock(LOCK_EX | LOCK_NB)`, and raises `ProjectBusy`.
  - The CLI then prints one Italian line saying that another process is already working on the project, and exits 1.
  - Tests:
    - `test_a_second_process_cannot_work_on_the_same_project`: the second process is refused before any model call,
      and the transport sees the calls of one worker only.
  - Verify: the test passes; standard gate.
  - Commit: `fix(runtime): let only one process work on a project at a time`.
- [x] **Task 2.13: a call that fell back to another model is charged for every attempt.** Closes COR-008 (Q9). Load
  the `claude-api` skill first.
  - Files: `src/agency/gateway/pricing.py`, `src/agency/gateway/client.py` (`_record`), `tests/test_gateway.py`.
  - Implementation: when `usage.iterations` is present, price each attempt at its own model's rates and store the sum
    in the call's single `usage` row. An unknown model keeps `UNKNOWN_MODEL`'s highest rate.
  - Tests:
    - `test_a_fallback_call_is_charged_for_both_attempts`. Use a response shaped like the docs: a declined attempt on
      `claude-opus-5-5` with 50k in and 6k out, and a fallback on `claude-opus-5` with 50k in and 3k out. Expect a
      recorded cost of `0.645` at the current table.
  - Verify: the test passes; standard gate.
  - Commit: `fix(gateway): charge every attempt of a call that fell back to another model`.
- [x] **Task 2.14 [APPROVAL]: read-only commands never create a registry.** Closes DX-003 (its own half; Q3).
  - Files: `src/agency/ledger/store.py`, `src/agency/cli.py`, `tests/test_hardening.py`.
  - Interfaces: `Ledger.existing(path: Path) -> Ledger` raises `LedgerMissing(path)`, which `cli.main` prints as
    `REGISTRO: nessun registro in <absolute path>`.
  - Only `run` creates a registry. `verify`, `runs`, `artifacts`, `compare`, `report`, `insights`, `budget`, `resume`
    and `decide` use `Ledger.existing`.
  - Tests:
    - `test_read_only_commands_never_create_a_registry`: run each command on an empty data directory. Each exits 1
      with the absolute path, and no `ledger.sqlite` appears.
    - Task 1.5's `verify` test adapts its setup if it needs to.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(cli): refuse a missing registry instead of creating an empty one`.
- [x] **Task 2.15 [APPROVAL]: one resolver for the data root, anchored at the checkout.** Closes STR-001 part 1 of 3,
  STR-008, and DX-003 (the alias part) (Q2, Q3). New ADR, expected ADR-0045 ("Una radice dei dati, e `.env` solo per i
  segreti"). It describes Tasks 2.15–2.17.
  - Files:
    - `src/agency/contracts/layout.py`, `src/agency/config.py`, `src/agency/entrypoints/server/settings.py`;
    - `docs/adr/0045-*.md`, `docs/adr/README.md`, `docs/03-DATA-MODEL.md`;
    - `tests/test_layout.py`, `tests/test_server.py`.
  - Interfaces:
    - `CHECKOUT: Path` is the repository root. `agency.config.REPO_ROOT = CHECKOUT`.
    - `data_root(environ: Mapping[str, str] = os.environ) -> Path` returns `CHECKOUT / ".data"`, or the value of
      `AGENCY_DATA_DIR`, which must be absolute. Otherwise it raises `RelativeDataRoot`.
    - `projects_dir` follows the same rule, through `AGENCY_PROJECTS_DIR`.
    - `env_file` becomes `CHECKOUT / ".env"`.
  - Tests:
    - `test_the_default_data_root_is_the_checkout_from_any_directory`;
    - `test_a_relative_data_root_is_refused_by_engine_and_server` (Review focus 2);
    - `test_engine_and_server_resolve_the_same_root`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(config): resolve the data root from the checkout, the same way in the engine and the server`.
  - As built:
    - ADR-0045 is `docs/adr/0045-una-radice-dei-dati-e-env-solo-per-i-segreti.md`.
    - The projects rule is `projects_root(environ)`. `RelativeDataRoot(name, value)` is not a `ValueError`, so it
      leaves pydantic unwrapped. `Settings` checks a `data_dir` or `projects_dir` from any source (environment, `.env`
      or the caller) through the same two functions. The server's root is `data_root()`, without `.resolve()`.
    - The refusal is one line, printed as is: `AGENCY_DATA_DIR deve essere un percorso assoluto, non '.data': uno
      relativo dipende dalla cartella da cui parte il comando`. `cli.main` prints it on stdout and `agency-server` on
      stderr; both exit 1. So two more files: `src/agency/cli.py` and `src/agency/entrypoints/server/serve.py`.
    - `tests/conftest.py` gains an autouse fixture that sets `Settings.model_config["env_file"]` to None, so no test
      reads the checkout's `.env`.
    - `web/playwright.config.ts` gives the e2e server an absolute `AGENCY_DATA_DIR`; the relative `e2e/.data` is now
      refused.
    - The phase 1 pin `test_engine_and_server_take_the_data_root_from_different_places` became
      `test_engine_and_server_resolve_the_same_root`.
- [x] **Task 2.16 [APPROVAL]: `.env` holds the API key only.** Closes STR-001, part 2 of 3 (Q2).
  - Files: `src/agency/config.py`, `src/agency/cli.py` (`main` catches the new error), `.env.example`,
    `tests/test_layout.py`.
  - Behaviour:
    - Settings read only `ANTHROPIC_API_KEY` / `AGENCY_ANTHROPIC_API_KEY` from `.env`.
    - Any other `AGENCY_*` line makes the engine stop with one Italian line. The line names the variable and says it
      belongs in the process environment.
    - `.env.example` keeps only the key.
  - Tests:
    - `test_dotenv_provides_only_the_key`;
    - `test_an_old_env_example_copy_stops_with_one_line` (Review focus 1).
  - Note for Andrea: before using this build, remove the non-secret lines from the main checkout's `.env`. The error
    message says which ones.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(config): read only the API key from .env`.
- [x] **Task 2.17 [APPROVAL]: `task docker:up` uses `AGENCY_DATA_DIR`.** Closes STR-001 (Q2).
  - Files: `Taskfile.yml` (`docker:up`, `docker:down`), `docker/compose.yaml` (the host side; the container keeps
    `/data`), `tests/test_docker.py`, `README.md` (the `docker:up` line), `docs/adr/README.md` (mark ADR-0040 as
    partly superseded by ADR-0045).
  - Tests:
    - `test_compose_mounts_agency_data_dir`;
    - `test_compose_names_agency_data_dir_when_missing`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(docker): name the host data root AGENCY_DATA_DIR, like every other process`.
- [x] **Task 2.18: sandbox limits that need no measurement.** Closes SEC-005, part 1 of 2 (Q20).
  - Files: `src/agency/tools/sandbox.py`, `src/agency/tools/master.py` (`problem`), `src/agency/tools/surface.py`
    (`view_image`), `tests/test_agent_flow.py`.
  - Values:
    - `--size` of 2 GiB on `/tmp` and 256 MiB on `/home`;
    - each command runs as `prlimit --fsize=2147483648 -- <command>` inside bwrap. `prlimit` comes from util-linux
      under `/usr`, and avoids `preexec_fn`, which is unsafe with threads;
    - `master.problem` reads 8 bytes;
    - `view_image` refuses files over `MAX_IMAGE_FILE_BYTES = 64 * 2**20` before decoding.
  - Tests:
    - `test_sandbox_tmp_is_size_limited`: `fallocate -l 3G /tmp/x` fails.
    - `test_sandbox_file_size_is_limited`: `truncate -s 3G /job/x` fails.
    - `test_master_problem_reads_only_the_header`.
    - `test_view_image_refuses_a_huge_file`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(sandbox): bound tmpfs, file sizes and harness-side reads`.
- [x] **Task 2.19 [APPROVAL]: memory and task caps in a cgroup scope.** Closes SEC-005 (Q20). New ADR, expected
  ADR-0046 ("I limiti della sandbox").
  - Files: `src/agency/tools/sandbox.py`, `src/agency/doctor.py`, `docs/adr/0046-*.md`, `docs/adr/README.md`,
    `docs/06-SECURITY.md`, `docs/04-TOOLS.md`, `tests/test_agent_flow.py`, `tests/test_doctor.py`.
  - Steps:
    1. Measure, at 0 $:
       - Run each Craft CLI and Blender inside
         `systemd-run --user --scope -p MemoryAccounting=yes` on the `merlo3` masters (copied read-only into scratch)
         and on an E6-sized scene.
       - Read `memory.peak` for each run.
       - Record the numbers in the ADR.
    2. Wrap bwrap in `systemd-run --user --scope --quiet -p MemoryMax=<about 2× the peak> -p MemorySwapMax=0 -p TasksMax=512 --`.
    3. If the scope cannot be created, raise `SandboxUnavailable` with the reason.
    4. Doctor gets the same check, as an Italian line.
  - Tests:
    - `test_sandbox_runs_in_its_own_capped_scope`: inside, `/proc/self/cgroup` differs from the caller's, and
      `memory.max` holds the value.
    - `test_sandbox_refuses_to_run_without_a_scope`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(sandbox): cap memory and tasks of every sandboxed run`.

### Low (behaviour changes; they precede Phases 3–6)

- [x] **Task 2.20: an effect and its resume record are committed together.** Closes COR-003.
  - Files: `src/agency/ledger/store.py` (`open`), `src/agency/tools/surface.py` (`plan_exploration` :587-624, and the
    closing handlers), `tests/test_agent_flow.py`.
  - Interface: `Ledger.open(..., concept: ConceptRow | None = None)` writes the concept row in the same transaction as
    the ticket.
  - Behaviour: `deliver`, `block` and `submit_concept` replayed on a ticket already in their target state, by the same
    actor, return their result instead of raising `IllegalTransition`.
  - Tests:
    - `test_an_interrupted_plan_never_loses_a_direction`;
    - `test_a_replayed_deliver_closes_as_delivered`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(tools): commit an effect together with its resume record`.
- [x] **Task 2.21: a declined attempt's tool calls are dropped after a fallback.** Closes COR-009 (Q9). Load the
  `claude-api` skill first.
  - Files: `src/agency/agents/loop.py`, `src/agency/agents/transcript.py` (a `raw` field kept for audit),
    `tests/test_agent_flow.py`.
  - Interface: `_after_fallback(content: list[dict]) -> list[dict]` drops the `thinking`, `redacted_thinking`,
    `tool_use` and unpaired `server_tool_use` blocks that come before the last `fallback` block, as the skill's
    refusal section specifies.
  - The filtered turn enters the history. The raw content is kept in the transcript line as `raw`.
  - Tests:
    - `test_tool_calls_before_a_fallback_are_not_executed`: with content `[tool_use A, fallback, text, tool_use B]`,
      only B runs, A is missing from the history, and `raw` holds A.
  - Verify: the test passes; standard gate.
  - Commit: `fix(agents): drop a declined attempt's tool calls after a server-side fallback`.
- [x] **Task 2.22: every attempt of a retried call is authorized and recorded.** Closes COR-010.
  - Files: `src/agency/gateway/client.py` (`_stream`, `call`), `tests/test_gateway.py`.
  - Behaviour: authorize before each attempt. A failed attempt writes a usage row with `stop_reason="malformed_stream"`,
    its estimate as the cost, and zero tokens.
  - Tests:
    - `test_a_malformed_stream_retry_is_authorized_and_recorded`: with two `ValueError`s before success, expect 3
      usage rows and 3 authorizations. Under a cap that allows one call, the retry raises `BudgetExceeded`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(gateway): authorize and record every attempt of a retried call`.
- [x] **Task 2.23: a turn cut off by the context window blocks.** Closes COR-011. Load the `claude-api` skill first.
  - Files: `src/agency/agents/loop.py` (:144-169), `tests/test_agent_flow.py`.
  - Behaviour: on `model_context_window_exceeded`, block with an Italian reason, as for a second `max_tokens`, without
    appending the turn. A content holding a `tool_use` with no result is never appended.
  - Tests:
    - `test_a_context_window_cut_blocks_without_appending`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(agents): block instead of appending a turn cut off by the context window`.
- [x] **Task 2.24 [APPROVAL]: project names follow the DNS-label rule.** Closes COR-013 (Q21).
  - Files:
    - create `src/agency/contracts/project.py`;
    - `src/agency/config.py` (`project_dir`), `src/agency/contracts/layout.py` (`transcript`);
    - `src/agency/cli.py` (argparse `type=`), `src/agency/runtime.py`, `src/agency/entrypoints/server/api.py`;
    - `tests/test_hardening.py`, `tests/test_server.py`.
  - Interfaces:
    - `PROJECT_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")`, always used with `fullmatch`;
    - `ProjectName = NewType("ProjectName", str)`;
    - `parse_project_name(text: str) -> ProjectName`, which raises `ValueError` with an Italian message.

    `project_dir` and `transcript` accept only `ProjectName`.
  - Tests:
    - `test_project_names`:
      - valid: `merlo`, `merlo4`, `officina-e2e`, `p`, and 63 characters;
      - invalid: `../x`, `a/b`, `""`, `Merlo`, `-a`, `a-`, `"merlo\n"`, and 64 characters.
    - `test_an_invalid_stored_name_is_reported_not_crashed` (Review focus 4).
  - Verify: the tests pass; pyright passes; standard gate.
  - Commit: `fix(contracts): accept only DNS-label project names`.
- [x] **Task 2.25: tickets are listed in creation order.** Closes COR-014.
  - Files:
    - `src/agency/ledger/store.py` (:139-140, :177, :203);
    - `src/agency/insights/adapters/registry.py:35`, `src/agency/insights/adapters/projection.py:90`;
    - `tests/test_ledger.py`.
  - Implementation: order by SQLite `rowid`, not by the text id.
  - Tests:
    - `test_ticket_10000_sorts_after_ticket_9999`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(ledger): list tickets in creation order`.
- [x] **Task 2.26 [APPROVAL]: `svg_audit` flags strokes inherited from a group.** Closes COR-016 (Q4). This task
  changes QA outcomes.
  - Files: `src/agency/qa/scripts/svg_audit.py`, `src/agency/qa/scripts/MANIFEST.json` (the current hash),
    create `src/agency/qa/scripts/PATCHES.md`, create `tests/test_qa_scripts.py`.
  - Tests:
    - `test_svg_audit_flags_a_stroke_inherited_from_a_group`: `<g stroke="#000" stroke-width="8">` around a path
      exits 1 with a warning.
    - `test_svg_audit_flags_a_style_element`.
  - Verify: the tests pass, Task 1.18's manifest test passes, and the standard gate holds.
  - Commit: `fix(qa): flag strokes inherited from a group in svg_audit`.
- [x] **Task 2.27: blind-judgment boards are rendered inside the sandbox.** Closes SEC-006.
  - Files: `src/agency/evaluation/board.py`, `src/agency/cli.py` (`_judge`), `tests/test_board.py`.
  - Interface: `board.lay_board(copies, folder, render)` already takes the renderer. `cli._board_renderer()` supplies
    one backed by `Sandbox`, because `evaluation` may not import `tools`; `board.vectorcraft()` is deleted.
  - Tests:
    - `test_judge_board_cannot_draw_host_files`: an SVG holding `<image href="/tmp/…/secret.png">` renders without
      red.
  - Verify: the test passes; lint-imports passes; standard gate.
  - Commit: `fix(evaluation): render blind-judgment boards inside the sandbox`.
- [x] **Task 2.28: ticket paths cannot be absolute or contain `..`.** Closes SEC-007.
  - Files: `src/agency/contracts/ticket.py` (a `TicketSpec` validator over outputs, inputs and the check patterns),
    `tests/test_hardening.py`.
  - First check whether stored specs are re-validated on load (`rg -n "TicketSpec.model_validate" src`). If they are,
    confirm that no spec in a read-only copy of the real registry would fail.
  - Tests:
    - `test_ticket_paths_must_stay_inside_the_work_folder`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(contracts): refuse absolute and parent paths in ticket specs`.
- [x] **Task 2.29: every sandbox starts in a new session.** Closes SEC-008, for the engine. The spike follows in 5.10.
  - Files: `src/agency/tools/sandbox.py` (`--new-session`), `tests/test_agent_flow.py`.
  - Tests:
    - `test_sandbox_runs_in_a_new_session`: `os.getsid(0)` inside differs from the test process's.
  - Verify: the test passes; standard gate.
  - Commit: `fix(sandbox): start every sandbox in a new terminal session`.
- [x] **Task 2.30: model text is printed without control sequences.** Closes SEC-009.
  - Files: `src/agency/cli.py`, `src/agency/telemetry/report.py` (every field that comes from the model),
    `tests/test_hardening.py`.
  - Interface: `plain(text: str) -> str` drops C0 and C1 control characters, except `\n` and `\t`.
  - Tests:
    - `test_cli_strips_control_sequences_from_model_text`: reasons containing `"\x1b]52;c;…\x07"` are printed without
      ESC or BEL.
  - Verify: the test passes; standard gate.
  - Commit: `fix(cli): strip control sequences from model text before printing it`.
- [x] **Task 2.31 [APPROVAL]: the hash chain covers verdicts and delivered hashes.** Closes CMT-007's invariant (Q17;
  the comment follows in 3.12). New ADR, expected ADR-0047 ("La catena copre verdetti e consegne").
  - Files:
    - `src/agency/ledger/models.py` (`EventRow.version: int = 1`, `payload_json: str = ""`);
    - create `src/agency/ledger/migrations/versions/0006_event_payload.py`, which adds the columns and appends one
      baseline event per ticket binding its current status, verdict and delivered hashes;
    - `src/agency/ledger/chain.py`, `src/agency/ledger/store.py`, `src/agency/cli.py` (`_verify`);
    - `docs/adr/0047-*.md`, `docs/adr/README.md`, `docs/03-DATA-MODEL.md`;
    - `tests/test_ledger.py`, `tests/test_migrations.py`.
  - Interfaces:
    - `chain.digest_v2(prev, ticket_id, at, actor, action, note, payload_json) -> str`;
    - `chain.intact` picks the formula by each row's `version`;
    - `Ledger.replay_mismatches() -> list[str]`.
  - Tests:
    - `test_changing_a_verdict_in_tickets_breaks_verify`;
    - `test_migration_binds_every_ticket_state_into_the_chain`;
    - `test_v1_events_still_verify`.
  - Verify: the tests pass; `agency migrate` on a copy of the real registry succeeds (read-only source); standard
    gate.
  - Commit: `fix(ledger): bind verdicts and delivered hashes into the hash chain`.
- [x] **Task 2.32: an unreadable fingerprint no longer crashes `agency runs`.** Closes SIM-001's behaviour half.
  - Files: `src/agency/contracts/run.py`, `src/agency/telemetry/report.py` (:108-133), `tests/test_runs.py`.
  - Interface: `read_fingerprint(text: str) -> Fingerprint | None`.
  - Behaviour: an unreadable run is listed with an Italian label instead of raising.
  - Tests:
    - `test_runs_lists_an_unreadable_fingerprint`.
  - Verify: the test passes; standard gate.
  - Commit: `fix(cli): show an unreadable fingerprint instead of crashing agency runs`.
- [x] **Task 2.33 [APPROVAL]: live runs are recorded, keyed by request, and replayed in tests.** Closes SIM-006 and
  TST-009's cassette part (Q8). New ADR, expected ADR-0048 ("Le esecuzioni si registrano e si ripetono"). Load the
  `claude-api` skill first.
  - Files:
    - create `src/agency/gateway/recording.py`;
    - `src/agency/gateway/transport.py` (delete the old `RecordingTransport` and `from_cassette`),
      `src/agency/gateway/__init__.py`;
    - `src/agency/runtime.py` (`open_session(..., record: bool = False)`; recording starts when the run id is known);
    - `src/agency/cli.py` (`--record` on `run`, `resume` and `decide`), `src/agency/contracts/layout.py`
      (`cassette(project: str, run: int) -> Path` → `<root>/cassettes/<project>/<run>.jsonl`);
    - create `tests/support/__init__.py` and `tests/support/replay.py`, create `tests/test_recording.py`;
    - `docs/adr/0048-*.md`, `docs/adr/README.md`, `docs/02-ROADMAP.md` (the `merlo4` command gets `--record`),
      `docs/03-DATA-MODEL.md`.
  - Interfaces:
    - `request_key(params: dict) -> str`: the sha256 of the canonical JSON of model, system, tools, messages and
      output_config, with sorted keys;
    - `RecordingTransport(inner: Transport, path: Path)` records `count_tokens` and `stream` under one lock;
    - `ReplayTransport(path: Path)` serves by key, with a list per key, and raises `MissingRecording(key, summary)`.
  - Tests:
    - `test_a_recorded_run_replays_to_the_same_ledger`;
    - `test_parallel_recording_replays_in_any_order` (Review focus 5);
    - `test_count_tokens_is_replayed`;
    - `test_a_recording_never_contains_the_key`.
  - Verify: the tests pass; standard gate.
  - Commit: `feat(gateway): record live runs keyed by request and replay them in tests`.
- [x] **Task 2.34: each role declares its tool set and Craft apps in `roles.json`.** Closes SIM-008 and STR-005 (the
  name-suffix part) (Q22). It changes no active tool set.
  - Files: `registry/roles.json`, `src/agency/tools/surface.py` (`role_tools` :862-869, `craft_run`, `craft_search`),
    `tests/test_registry.py`, `tests/test_sketch_flow.py`.
  - Data changes:
    - Every role gains `"tools": "director" | "author" | "reviewer" | "router"`, and `department` is removed.
    - `art-director` becomes `author` with `craft: []`. The evidence: `legacy/…/ORG.md:23,72` makes it a level-2 role
      that opens nothing, and its agent file bars the Craft tools.
  - Behaviour:
    - An empty `craft` list means no `craft_*` tools.
    - `craft_run` and `craft_search` refuse an app the role does not list.
  - Tests:
    - `test_tool_declarations_match_the_org_chart`: a `director` has a `can_open` row, and only a director has one.
      The `reviewer` roles equal `contracts.ticket.REVIEWERS`.
    - `test_craft_tools_follow_the_role_craft_list`.
    - The request snapshots of the 11 phases are byte-identical.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(registry): declare each role's tool set and Craft apps in roles.json`.
- [x] **Task 2.35: `registry/*.json` is validated against typed contracts at load.** Closes STR-005 (the schema part)
  (Q18).
  - Files: create `src/agency/contracts/registry.py`; `src/agency/agents/prompts.py` and `src/agency/qa/evidence.py`
    (their loaders validate first, and callers are unchanged); `tests/test_registry.py`.
  - Interfaces, all with `extra="forbid"`, and with `$comment` allowed:
    - `CheckKind(StrEnum)` with `observation`, `judgement`, `measure`, `reading` and `requirement`;
    - `RoleSpec`, `RolesFile`, `CheckSpec`, `ChecksFile` and `OrgFile`.
  - Tests:
    - `test_a_misspelt_registry_field_fails_at_load`: the error names the field.
    - `test_an_unknown_check_kind_fails_at_load`.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(registry): validate the studio rules against typed contracts at load`.

### Found during Phase 2

Task 2.1 searched `src/agency` for the same bug as SEC-001: the harness writes, creates, replaces, copies or reads a
file under a project's `work/` folder without the no-follow helpers of `agency.tools.files`. Any sandbox with
`compute` can plant a symlink there. An author ticket opened with `open_ticket` has `workspace=""`, so its `/job` is
the whole `work/`. Line numbers are as of Task 2.1. "Task 2.2's rule" means its title: every harness read and write
under `/job` goes through the helper. Its file list is narrower, and each entry says whether the file is on it.

- [x] **Task 2.F1: the workspace folder is created and bound through a planted link.** agents/loop.py:67-68 and
  tools/sandbox.py:27. `work.mkdir(parents=True, exist_ok=True)` runs on the raw `project_dir / "work" / workspace`,
  then `Sandbox(work)` calls `work.resolve()`. A link at any component, for example `work/proposals -> <host folder>`
  left by a whole-work sandbox, makes the harness create the folders on the host and bind the link's target
  read-write at `/job`. The next sandbox then writes a host folder. Reproduced on the bwrap argv alone (Task 2.1
  report). No planned task closes it: loop.py and sandbox.py are not on Task 2.2's list, and Task 2.3 only adds
  `/ops` to sandbox.py.
- [x] **Task 2.F2: `start` copies the brief through a planted `brief.md`.** runtime.py:77-78, and the hash at :92.
  `shutil.copyfile(brief, work / "brief.md")` follows a link left in an existing project's `work/`. Task 2.2's rule;
  runtime.py is not on its list.
- [x] **Task 2.F3: the board node writes with raw `work / …` joins.** graph/workflow.py:113-114. `board.build` writes
  `board/r<n>/tavola.png`, and `shutil.copyfile` reads `brief.md` and writes `board/r<n>/brief.md`, all following
  links. Task 2.2's rule; workflow.py is not on its list (board.py is). Since Task 2.2, `board.build` reads the
  sketches and writes `tavola.png` through the helper. The `brief.md` copy at :114 is still open.
- [x] **Task 2.F4: the select node copies the explorers' sheets through links.** graph/workflow.py:157-162. It writes
  `schede.md`, creates `fogli/`, and copies each `explorations/r<n>/<x>/foglio-<x>.png`, a file an explorer sandbox
  wrote and can make a link to a host image. Task 2.2's rule; workflow.py is not on its list.
- [x] **Task 2.F5: the proposals node reads and copies explorer files through links.** graph/workflow.py:195,
  :203-209 and :235. It reads `applicazioni.json`, creates the proposal folder with `mkdir(parents=True)`, copies
  `brief.md`, `scheda.json` and the sketch, then hashes the inputs, all on raw joins. Task 2.2's rule; workflow.py is
  not on its list.
- [x] **Task 2.F6: the present node builds each proposal sheet from raw paths.** graph/workflow.py:261-263 and
  tools/presentation.py:152-159 (`sheet`). The glob in `proposal_files` is SEC-003, closed by Task 2.6. `sheet` reads
  the images and writes `proposals/r<n>/insieme-<x>.png` with `mkdir` and `save`. Task 2.2's rule; its list names
  `_fit` and `build` in presentation.py, not `sheet`. Since Task 2.2, `sheet` reads the images through `_fit`, which
  goes through the helper. Its `mkdir` and `save` are still open. Since Task 2.6, `proposal_files` takes the proposal
  ticket's delivered paths (workflow.py:261 passes `ledger.delivered(ticket)`), so the glob is gone.
- [x] **Task 2.F7: the production node copies the chosen proposal through links.** graph/workflow.py:340-341 and
  :360. It copies `proposals/r<n>/<x>/proposta-<x>.vectorcraft`, written by a proposer sandbox, into the root ticket's
  target, then hashes the inputs. Task 2.2's rule; workflow.py is not on its list.
- [x] **Task 2.F8: `write_file` writes after `inside()`.** tools/surface.py:302-304. A check, then a use: a link
  swapped in between, or one that points elsewhere inside the work folder, is followed. Closed by Task 2.2 (named).
- [x] **Task 2.F9: `plan_exploration` writes the plan and the explorer folders after `inside()`.**
  tools/surface.py:582-584 and :593-595. Task 2.2's rule; only `read_file`, `write_file` and `view_image` of
  surface.py are on its list.
- [x] **Task 2.F10: the closing tools write their records after `inside()`.** tools/surface.py:630-631
  (`submit_concept`, `scheda.json`), :655-657 (`rate_board`, `reviews/valutazione.json`) and :715
  (`draft_presentation`, `testi.json`). Their readers follow links too: :636, :670 and :724-730. Task 2.2's rule;
  these surface.py functions are not on its list.
- [x] **Task 2.F11: the hash and existence checks in the tools follow links.** tools/surface.py:413 (`_seen_proof`),
  :440-443 (`judge`), :486 and :509 (`open_ticket`), :560 (`deliver`), and :78 (`ToolContext.keep`), whose open is
  artifacts/files.py:55 (`FileStore.put`, `source.open("rb")`). Task 2.2's rule; keeping.py is on its list, but these
  surface.py functions and artifacts/files.py are not. Its `FileStore.put` part is closed by Task 2.2a.
- [x] **Task 2.F12: `run_steps` copies the built document through links and trusts `.ops` on resume.**
  tools/craft.py:137-138: `target.parent.mkdir(parents=True)` and `shutil.copy2(built, target)` follow a link at the
  target or at `built`. tools/craft.py:112, :117 and :139: the resume checks and the result read. Task 2.3 closes the
  resume reads (resume reads only `ops_records`). The copy into the document is Task 2.2's rule; craft.py is on Task
  2.3's list, not Task 2.2's. Since Task 2.3, the resume checks and reads use `ops_records` only, and the copy goes
  through `ensure_dir_under` and `replace_under`. Still open: `target.exists()` (craft.py:124 as of Task 2.3), which
  decides whether the CLI gets `--in`. It runs after `inside()`, so a link that leaves the work folder is refused
  first. It reads nothing, but it still stats through a link that stays inside.
- [x] **Task 2.F13: render proofs are written after `inside()`.** tools/render.py:31-37, :46, :66, :69, :79 and
  :86-88. Closed by Task 2.2 (named).
- [x] **Task 2.F14: master export and hashing follow links.** tools/master.py:36, :79-80, :89, :101 and :110. Closed
  by Task 2.2 (named).
- [x] **Task 2.F15: the board image is written through links.** tools/board.py:145-146. Closed by Task 2.2 (named).
- [x] **Task 2.F16: the presentation pages are written, and old ones deleted, through links.**
  tools/presentation.py:229-238 (`build`: `mkdir`, `glob` and `unlink` of old pages, `save` of the pages and the PDF).
  Closed by Task 2.2 (named).
- [x] **Task 2.F17: the QA proof folders are created after `inside()`.** qa/checks.py:40 and :48; the proof glob at :53
  and the hash at :66-70 follow links too. Task 2.2's rule; qa/checks.py is not on its list.
- [x] **Task 2.F18: evidence and delivery hash work files through links.** qa/evidence.py:82, :98, :125 and :131;
  qa/delivery.py:103, :121, :198, :219-225 and :239. Closed by Task 2.2 (named), except the globs. Task 2.2 moved
  every hash onto `sha256_under`: evidence.py :91, :98, :128 and :132, delivery.py :219 and :239. Still open: the
  globs in `validate_review` (:103) and `expected` (:121) list a linked host folder, and its file names reach the
  delivery messages. The `exists()` and `is_file()` checks (:82, :125, :131, :198, :222, :225) stat through links but
  read nothing, and every open after them goes through the helper.
- [x] **Task 2.F19: `restore` creates the destination's folders through links.** artifacts/keeping.py:96-99.
  `open("xb")` refuses a link as the last component, but `destination.parent.mkdir(parents=True)` follows one higher
  up when the operator restores into a work folder. Closed by Task 2.2 (named).
- [x] **Task 2.F20: `agency judge` copies work files through links.** evaluation/blind.py:84. `shutil.copyfile` of each
  candidate reads through a link a sandbox left. Task 2.2's rule; evaluation/ is not on its list.
- [x] **Task 2.F21: a FIFO planted where the harness reads blocks the harness.** tools/files.py (`read_under`,
  `sha256_under`) and every plain read above. `os.open(..., O_RDONLY)` on a FIFO waits for a writer that never comes:
  a probe on `read_under` was still blocked when `timeout 3` killed it (exit 124). Not the same bug, but the readers
  Task 2.2 routes through the helper should refuse anything that is not a regular file (`O_NONBLOCK`, then `fstat`).
- [x] **Task 2.F22: the concept gate hashes the presentation PDF through links.** graph/workflow.py:302 (as of Task
  2.2). `sha256(work_dir(project) / file)` reads `presentation/r<n>/presentazione.pdf` on a raw join, so a link left
  at `presentation/` or at the PDF makes the gate record the hash of a host file. Found by Task 2.2. Task 2.2's rule;
  workflow.py is not on its list.
- [x] **Task 2.F23: `agency judge` resolves and hashes each candidate through links.** evaluation/blind.py:44 and :52
  (as of Task 2.2). `path.resolve()` follows a link a sandbox left in the work folder the operator names, so the
  comparison hashes, copies (Task 2.F20) and keeps the file the link points to. Found by Task 2.2. Task 2.2's rule;
  evaluation/ is not on its list, and it may not import `agency.tools` (ADR-0027), so the helper must be reachable
  from `contracts` first.
- [x] **Task 2.F24: the critic's first look is a file in the work folder, and `select_concepts` trusts it.**
  tools/surface.py:673 (`rate_board` writes `reviews/valutazione.json`) and :688-694 (`select_concepts` reads
  `board/r<n>/reviews/valutazione.json` and lets only the letters marked `passes` through). Line numbers are as of
  Task 2.3. This is SEC-001's class, not its links: the harness keeps a record it later trusts in a folder the agent
  can write. The ledger keeps no copy. The critic-board tool set has `write_file`, and a reviewer may write
  `reviews/*.json`. So the critic can replace the file without `rate_board`'s checks (every board letter and only
  those, and the `first_look` field). A probe on Task 2.3's code: `rate_board` refused a rating of a letter `Z` that
  is not on the board, then `write_file` stored the same rating, and that file is what `select_concepts` would
  read. The ticket lists `reviews/valutazione.json` as an output exempt from checks, so a planted file also satisfies
  delivery when `rate_board` never ran. Two records have the same shape, but no writer runs between their write and
  their read today. `presentation/r<n>/testi.json` is written by `draft_presentation` (:733) and sent to the client
  by `present_concepts` (:743-753), and the present tool set has neither `write_file` nor `compute`.
  `explorations/r<n>/applicazioni.json` is written by `plan_exploration` (:600-602) and read by the proposals node
  (graph/workflow.py:195). Explorers cannot reach it, and since Task 2.2 the helper refuses SEC-004's
  `reviews/../` route to it. Found by Task 2.3. No
  planned task closes it. The fix would record the ratings where only the harness writes, the ledger or
  `ops_records`, and have `select_concepts` read them from there.
- [x] **Task 2.F25: `agency judge` feeds a sandbox-written vector file to `vectorcraft-cli` on the host.**
  evaluation/board.py:62-66 (`render` runs `vectorcraft-cli convert <copy> <target>` with `subprocess.run`, outside
  bwrap) and :115-121 (`_raster`). Found by Task 2.5, which closed the Pillow side of SEC-002 only (every image is now
  opened through `contracts/media.open_image`, restricted to PNG, JPEG, WebP and GIF). The converter still parses a
  file the model wrote, in the harness's process tree and with the operator's `HOME`. `tools/craft.py` and
  `tools/render.py` run it through `Sandbox`, so only this path is unconfined. Closed by Task 2.27 (SEC-006), which
  adds a `render` callable backed by `Sandbox` that `cli.py` supplies.
- [x] **Task 2.F26: `present_concepts` lists the pages to check by globbing the folder.** tools/surface.py:765
  (`folder.glob("pagina-*.png")`). The pages the director must have viewed are whatever `pagina-*.png` files sit in
  `presentation/r<n>/`, not the list `draft_presentation` returned, so a page planted there is checked and kept as if
  it were part of the draft, and a page missing from the draft is not noticed. Only the PDF is sent, and `build`
  deletes old pages, so the exposure is small. Found by Task 2.6. Same shape as SEC-003; the fix is to read the page
  list from `testi.json` or from the draft result. Not covered by a planned task.

- [x] **Task 2.F27: the QA proof names drop the source extension.** qa/checks.py:38-39 (`proofs/optical/{stem}.png`)
  and :47 (`proofs/logo/{stem}`), with `Path(file).stem`. Two files with one stem in one folder, or under two
  folders, such as `a/mark.svg` and `b/mark.svg` or `mark.svg` and `mark.png`, share one proof file or folder, and
  the second run replaces the first. Same shape as COR-007. Found by Task 2.8. Not covered by a planned task.

- [x] **Task 2.F28: the trace reader decodes in text mode, so one undecodable byte fails the whole read.**
  insights/adapters/traces.py:51. `self.path.open(encoding="utf-8")` is iterated line by line, but the decode error
  is raised by the `for` and not inside the per-line `try` (:55-58, which catches `ValueError` and `TypeError` only
  around `json.loads`). The exporter (telemetry/setup.py:25) writes `json.dumps(record, default=str)` with
  `ensure_ascii` on, so a torn multibyte character cannot come from the exporter itself; a stray non-UTF-8 byte
  (damaged file) still would. Nothing repairs a torn tail of `traces.jsonl` (no `_repair` as in
  agents/transcript.py:17). Same shape as COR-006. Found by Task 2.9. Not covered by a planned task. The engine's
  own reader (agents/transcript.py:35, `read_text` plus `json.loads` per line) is not listed: `Transcript.__init__`
  repairs a torn tail first, and a mid-file bad line is outside COR-006.
- [x] **Task 2.F29: `agency budget` changes a project's cap with no claim on the project.** cli.py:216-222
  (`_budget`, `ledger.set_budget`). Task 2.12 locks `run`, `resume` and `decide` only, so a cap can change under a
  worker that is running (the gateway reads it per call). Whether that is wanted is a decision: raising the cap of a
  stopped project is the documented use, and refusing it while a worker runs may be right or may be too strict.
  Found by Task 2.12. Not covered by a planned task.
  - Decided (2026-11-10): by design. Raising the cap of a running project is the way to let it finish, and the gateway reads the cap per call, so `agency budget` takes no claim on the project; a test pins it and `docs/05-COSTS.md` says it.
- [x] **Task 2.F30: `agency migrate` rewrites the registry while a worker may be using it.** cli.py:61-70 and
  ledger/schema.py `migrate`. It takes no claim on any project, and the per-project lock of Task 2.12 cannot cover it
  (it is a whole-registry operation). It needs its own exclusive claim. Found by Task 2.12. Not covered by a planned
  task.
- [x] **Task 2.F31: the usage row's token columns still count only the serving attempt of a fallback call.**
  gateway/client.py:199-205 (`_record`) and insights/sums.py:18 (`context`), insights/behaviour.py:110 and :126
  (output tokens). After Task 2.13 the recorded `cost_usd` is the sum over `usage.iterations`, but `input_tokens`,
  `output_tokens` and the cache columns stay the top-level `usage`, so for a fallback call the cost no longer matches
  the tokens beside it, and insights' context and output-token figures leave out the declined attempt. Insights does
  not recompute cost from tokens (`sums.cost` sums the stored column), so no cost figure is wrong. Changing the
  columns needs a decision on one row versus a nullable per-attempt column (SUMMARY.md, COR-008). Found by Task 2.13.
  Not covered by a planned task.
  - Decided (2026-11-10): one row per call. The token columns stay the serving attempt's usage, the context the run actually used; `cost_usd` covers every attempt, as Task 2.13 made it. `docs/03-DATA-MODEL.md` says so beside the `usage` table.

- [x] **Task 2.F32: `agency restore` creates an empty registry when run from the wrong folder.** cli.py:310
  (`_restore`: `Ledger(settings.ledger_path)`). It only reads a kept version out of the registry, yet on a missing
  registry it creates an empty one and then says no version has that hash. Task 2.14 left it out because its list
  (SUMMARY.md, Q3) does not name it. The fix is `Ledger.existing`, the same message. Found by Task 2.14.
- [x] **Task 2.F33: `agency judge` creates a registry on a missing data root.** cli.py:252 (`_judge`:
  `Ledger(settings.ledger_path)`). It writes judgments, so creating the registry may be intended, but a wrong data
  root makes a fresh one that holds only that judgment. Needs the owner to say whether `judge` may create it. Found
  by Task 2.14.
  - Decided (2026-11-10): `agency judge` never creates a registry, like every command but `agency run` (DX-003): `Ledger.existing`, the same message.

- [x] **Task 2.F34: `agency-schemas` writes and checks the schema relative to the current folder.**
  entrypoints/server/schema.py:15 (`OUTPUT = Path("schemas/openapi.json")`). `task schemas` runs it from the root,
  but `uv run agency-schemas` from `web/` writes `web/schemas/openapi.json`, and `--check` from there reports a
  missing file as "non allineato". The anchor is `CHECKOUT / "schemas/openapi.json"`. Also, since Task 2.15
  `render()` loads the server settings, so a relative `AGENCY_DATA_DIR` in the shell stops `agency-schemas` with a
  traceback that ends in the refusal line: `main` does not catch `RelativeDataRoot`. Found by Task 2.15. Not covered
  by a planned task.
- [x] **Task 2.F35: a relative `AGENCY_PROJECTION_DIR` follows the server's current folder.**
  entrypoints/server/settings.py:37-38 (as of Task 2.15). `Path(_PROJECTION).resolve()` accepts a relative value and
  resolves it against the folder the server starts from, the case of Review focus 2. Only Compose sets it today, to
  `/projection`. The fix is the rule of `data_root`: absolute, or refused with the same kind of line. Found by Task
  2.15. Not covered by a planned task.
- [x] **Task 2.F36: a relative `AGENCY_TOOLCHAIN_DIR` follows the engine's current folder.** config.py:24
  (`toolchain_dir`; its default under `~/.local/share` is absolute) takes any value from the environment or `.env`,
  and tools/sandbox.py:77-78 binds it as given (`--ro-bind <value> <value>`), so a relative value names a different
  folder from each current folder. Task 2.16 stops it in `.env`, not in the process environment. The fix is the
  rule of `data_root`. Found by Task 2.15. Not covered by a planned task.
- [x] **Task 2.F37: an old `AGENCY_DATA` in the operator's shell is now ignored silently.** Taskfile.yml:124 and
  docker/compose.yaml:32 (as of Task 2.17). Until Task 2.17 `task docker:up` read `AGENCY_DATA`; now it reads only
  `AGENCY_DATA_DIR`, so an operator who still exports the old name gets the default `<root>/.data` with no message,
  and the dashboard can show a registry other than the one intended. Needs the owner's decision (a refusal when the
  old name is set, a note in the Taskfile, or nothing). Found by Task 2.17. Not covered by a planned task.
  - Decided (2026-11-10): refuse. `task docker:up` stops when `AGENCY_DATA` is set, with one line naming `AGENCY_DATA_DIR`.
- [x] **Task 2.F38: a relative `AGENCY_DATA_DIR` given to `task docker:up` is resolved against `docker/`.**
  Taskfile.yml:124 and docker/compose.yaml:32 (as of Task 2.17). Compose resolves a relative bind source against the
  folder of the Compose file, not the folder the operator is in, whereas the engine and the server refuse a relative
  data root (ADR-0045). Needs the owner's decision (refuse it in the Taskfile like the others, or accept it). Found by
  Task 2.17. Not covered by a planned task.
  - Decided (2026-11-10): refuse, as the engine and the server do (ADR-0045): `task docker:up` stops on a relative `AGENCY_DATA_DIR`.
- [x] **Task 2.F39: `/dev/shm` in the sandbox has no size bound of its own.** tools/sandbox.py:55 (`--dev /dev`; as of
  Task 2.18, re-checked as of Task 2.19). bwrap's `--size` applies only to the next `--tmpfs`, not to `--dev`, so the
  `/dev/shm` it mounts still reports the host's free RAM (30.5 GiB in the SEC-005 probe) while `/tmp` and `/home` are
  now 2 GiB and 256 MiB. Task 2.19 measured it: with the real Sandbox argv and `MemoryMax` set to 64 MiB in a scratch
  run only, `dd` of 128 MiB into `/dev/shm` was killed (`Killed`, exit -15 for the sandbox command), the same as
  128 MiB into `/tmp` and 128 MiB of heap. So it is bounded by the scope at `MEMORY_MAX_BYTES` (8 GiB), not by a
  size of its own. No test was added for it. A smaller bound would be `--tmpfs /dev/shm` with `--size` after
  `--dev /dev`. Found by Task 2.18. Covered by Task 2.19 as far as the host is concerned (the cap is 8 GiB, not a
  small `/dev/shm`); the direct fix is not covered by a planned task.
- [x] **Task 2.F40: `Sandbox.run` collects stdout and stderr of any size in memory.** tools/sandbox.py:96-98 (as of
  Task 2.18). `subprocess.run(..., capture_output=True, text=True)` holds everything the command prints until it exits
  or the timeout fires, so a command that prints at full speed for 120 s fills the harness's RAM; the cgroup of Task
  2.19 wraps bwrap, but the pipes are read by the harness outside it. Fix: read the pipes with a byte cap and kill the
  command past it. Found by Task 2.18. Not covered by a planned task.
- [x] **Task 2.F41: the harness reads whole sandbox-written text and JSON files with no size bound.**
  tools/surface.py:300 (`read_file`), :706 (`valutazione.json`), :776 (`draft`), tools/craft.py:138,143-144 (the
  partial document, the stored document and the result record) (as of Task 2.18). The sandbox can now write a file of up
  to 2 GiB, and each of these reads it whole into memory (`read_under`, `read_text`) and, for `read_file` and the
  JSON ones, decodes and parses it. Fix: a limit in `read_under` for these callers, or a refusal by size before the
  read. Found by Task 2.18. Not covered by a planned task.
- [x] **Task 2.F42: the harness reads whole image files before decoding in the render and board paths.**
  tools/render.py:27, tools/board.py:43, tools/presentation.py:71 (as of Task 2.18). `view_image` now refuses a file
  over `MAX_IMAGE_FILE_BYTES`, but these three call `read_under` on a proof or a page the sandbox wrote and decode it,
  with no size check. Fix: share the bounded read of `view_image` (a helper beside `read_under`), after the owner decides
  where that helper lives (see Task 4.F1). Found by Task 2.18. Not covered by a planned task.
- [x] **Task 2.F43: when the sandbox cannot get its scope, nothing decides whether the project stops or goes on.**
  tools/sandbox.py:138-143 (`Sandbox.run`), tools/surface.py:966-978 (`Toolbox.call`) and graph/workflow.py:399-402
  (`client_gate`) (as of Task 2.19). `SandboxUnavailable` is a `RuntimeError`, so inside `Toolbox.call` it reaches the
  model as a refused tool call with the reason (the `Refused/.../RuntimeError` branch, `is_error`, no traceback). The
  model can then retry or close with `block`, and every retry fails the same way, so a project on a machine
  without a user systemd session spends model turns on refusals. Outside `Toolbox.call` there is no catch site:
  `client_gate` builds a `Sandbox` and calls `delivery.acceptance_problems` after the client has approved, so the
  exception would leave that graph node. Needs the owner's decision: stop the project at the start with
  `agency doctor`'s message (a check in `agency run`), or let each tool refuse (today), or catch it at the gate and send
  the work back with the reason. Found by Task 2.19. Not covered by a planned task.
  - Decided (2026-11-10): fail fast. `agency run`, `resume` and `decide` check the sandbox scope (`scope_problem`) before the session opens and stop with the reason and `agency doctor`, before any model call; `client_gate` turns `SandboxUnavailable` into a stop with the reason instead of a traceback; each tool keeps refusing as today, as a second line of defence.
- [x] **Task 2.F44: `accept_ticket` and `rework_ticket` replayed after a crash raise `IllegalTransition`.**
  tools/surface.py:550-564 (as of Task 2.20). Each calls `ledger.apply` (one transaction) and `Toolbox.call` writes the
  resume record afterwards (another). Killed between the two, the ticket is already `accepted` (or `rework`); the
  replay with the same tool_use id runs the handler again and `apply` refuses (`accept non è ammesso da accepted`), so
  the director gets an error for a call that worked and may repeat it or give up. Same shape as COR-003, but nothing
  closes the instance, so it costs a turn, not the project. Fix: the replay check of Task 2.20 (`_replayed`) with the
  target status and the last event, or record the operation in the `apply` transaction. Found by Task 2.20. Not covered
  by a planned task.
- [x] **Task 2.F45: `run_check`, `observe`, `judge` and `record_requirement` double-apply on a replay.**
  tools/surface.py:437-500 and qa/evidence.py:100 (as of Task 2.20). `evidence.record` commits the evidence row and its
  hash-chain event (`add_evidence`), then `Toolbox.call` records the operation in a second transaction. A replay after
  a crash between them appends a second evidence row and a second chain event for the same call, and `run_check`
  also runs the check again. `evidence.latest` takes the newest row per file and check, so verdicts do not change; the
  ledger shows the same proof twice. Fix: write the operation record inside the `add_evidence` transaction, or key
  the evidence row by the operation id. Found by Task 2.20. Not covered by a planned task.
- [x] **Task 2.F46: `export_master`, `render` and the renders of `run_check` duplicate their rows on a replay.**
  tools/master.py:89 (`add_derivation`), tools/render.py:82 and qa/checks.py:70 (`add_render`) (as of Task 2.20). Each
  writes a row with no conflict rule, then `Toolbox.call` records the operation separately. A replay after a crash
  between them redoes the export or render and adds a second identical derivation or render row (`renders_of` then
  lists a proof twice). `record_artifacts` already uses `on_conflict_do_nothing`; these two tables do not. Found by Task
  2.20. Not covered by a planned task.
- [x] **Task 2.F47: the proposals node can lose the `in-sviluppo` status of a concept.** graph/workflow.py:236-237
  (as of Task 2.20). `ledger.open(spec, ...)` for the proposal ticket and `ledger.update_concept(..., status=
  "in-sviluppo")` are two transactions. If the process dies between them, the replayed node finds the ticket by its
  title (line 200-201), `continue`s, and never sets the status. Nothing reads `in-sviluppo` today (only `proposta`
  and `scelta` are read), so the effect is a wrong status shown in the concept table. Fix: pass the status through
  `Ledger.open(..., concept=...)`-style atomic write, or set it for the existing ticket too. Found by Task 2.20.
  Not covered by a planned task.
- [x] **Task 2.F48: the behaviour view shows a `malformed_stream` call as a complete answer.**
  insights/behaviour.py:21 and :89, gateway/client.py:202 (as of Task 2.23). The gateway records a usage row with
  `stop_reason="malformed_stream"` when a stream breaks, and `INCOMPLETE` lists only `max_tokens`, `refusal` and
  `model_context_window_exceeded`, so `StopCount.complete` is true for it and the Model page does not mark it as cut.
  Fix: add `malformed_stream` to `INCOMPLETE` (and its comment). Related finding: COR-011. Found by Task 2.23. Not
  covered by a planned task.
- [x] **Task 2.F49: `DataLayout.lock`, `ops_inputs` and `ops_records` still take a plain `str` project.**
  contracts/layout.py:86, :93 and :97, called from cli.py:147, agents/loop.py:96 and tools/surface.py:411 (as of Task
  2.24). They build paths from the project name exactly as `transcript` does (`locks/{project}.lock`, `ops/{project}/
  {instance}`), so a `str` that did not go through `parse_project_name` can still reach the filesystem. Task 2.24
  validates every name at the CLI, `Session.start` and the API, but these three methods do not carry the type. Fix: take
  `ProjectName` and parse at the three call sites (`ToolContext.project` is a `str`). Related finding: COR-013. Found
  by Task 2.24. Not covered by a planned task.
- [x] **Task 2.F50: `agency judge` records the folder name under `projects/` as the project without the name rule.**
  evaluation/blind.py:55-61 (as of Task 2.24). `_judged` takes `project` from the first path part below the projects
  folder, and `keeping.keep(..., project=judged.project)` stores it. A folder such as `projects/Merlo` is therefore
  written into the registry as a project name that `parse_project_name` rejects, and the dashboard then answers 404 for
  it. Fix: treat a first path part that fails `parse_project_name` like a file outside the projects (`project=""`), or
  refuse the comparison with a message. Related finding: COR-013. Found by Task 2.24. Not covered by a planned task.
- [x] **Task 2.F51: the insights flow report sorts tickets by their text id.**
  insights/flow.py:204 (as of Task 2.25). `flow_report` builds the ticket list with
  `sorted(data.tickets, key=lambda ticket: ticket.id)`, and `_outcome` at insights/flow.py:186 sorts the unfinished
  ids with `sorted(ticket.id ...)`. Both compare `T-{n:04d}` as text, so from the 10,000th ticket `T-10000` is listed
  before `T-9999`, the same defect as COR-014 (the registry and projection now read in creation order, and this sort
  discards it). Fix: keep the incoming order (rowid order from the registry) for the ticket list, and order
  `unfinished` by the numeric part of the id or by the incoming order. Found in Task 2.25. Not covered by a planned
  task.
- [x] **Task 2.F52: `svg_audit` ignores `opacity`, `filter`, `mask`, `clip-path` and `transform` written in the inline
  `style`.** src/agency/qa/scripts/svg_audit.py:164-167 (as of Task 2.26). The loop reads those five properties only as
  attributes (`el.get(attr)`), while it reads `stroke` from both the attribute and `style`. `<path style="opacity:.5">`
  or `style="filter:url(#f)"` passes. Fix: read them from the `style` declaration too, as `own_stroke` does for
  `stroke`, and record the change in PATCHES.md and the manifest. Found in Task 2.26. Not covered by a planned task.
- [x] **Task 2.F53: `svg_audit` gives the `stroke` attribute precedence over the `stroke:` of the inline `style`.**
  src/agency/qa/scripts/svg_audit.py:108-109 (`own_stroke`; the `el.get("stroke") or ...` expression, as of Task 2.26). In CSS
  the `style` declaration wins over the presentation attribute, so `<path stroke="none" style="stroke:#000">` is drawn
  stroked but audited as unstroked (and the reverse). Fix: read `style` first, then the attribute. Found in Task 2.26.
  Not covered by a planned task.
- [x] **Task 2.F54: the dashboard server logs the raw HTTP request line to stderr.** entrypoints/server/serve.py:30-31
  (`_Handler.log_message`: `format % args` carries the request line and path). The text is written by the HTTP client,
  not the model, and no control characters are removed, so a request with ESC or OSC bytes in its path forges lines of
  the operator's terminal (Task 2.30's bug, on the server side). Fix: pass the line through `report.plain` (or an
  equivalent shared helper that the server may import) before writing it. Found in Task 2.30. Not covered by a planned task.
- [x] **Task 2.F55: the API error text is printed raw.** cli.py:121 (`API NON DISPONIBILE: {exc}`; `BUDGET FINITO: {exc}`
  at :117 carries harness text only). `anthropic.APIError` messages include the response body from the API or from a
  proxy in between, which the harness does not control. Fix: wrap the line with `report.plain`. Found in Task 2.30. Not
  covered by a planned task.
- [x] **Task 2.F56: a ticket's contract and opening hashes are outside the hash chain.** ledger/store.py:206-230
  (`inputs`, `spec`) and :266 (`apply` takes the parties and the type from `spec_json`), tools/surface.py:592-600 and
  qa/delivery.py:205-229 (as of Task 2.31). `tickets.spec_json` decides who may deliver and accept, whether a delivery
  needs a verdict, and which outputs and checks `delivery_problems` requires; `tickets.inputs_json` holds the hashes its
  staleness check compares. `tickets` has no triggers, and since Task 2.31 the chain binds only the status, the verdict
  and the delivered hashes of a ticket (the `open` event's note is the title). A direct `UPDATE tickets SET spec_json =
  …` that drops a check or an output lets the next delivery pass without it, and `agency verify` still prints
  `registro integro`. No code changes either column after `open`. Fix: bind the sha256 of both columns into the chain
  (a new field of the version-2 payload, which needs its own ADR) and compare them in `replay_mismatches`. Same bug as
  CMT-007 (Q17). Found in Task 2.31. Not covered by a planned task.
  - Decided (2026-11-10): with 2.F57 and 2.F58, one ADR (expected ADR-0049, «La catena copre ciò che decide la consegna») and one migration 0007. The version-2 ticket payload gains the sha256 of the ticket's contract (`spec_json`, `inputs_json`), and `agency verify` compares it.
- [x] **Task 2.F57: the concept rows that decide what is developed and presented are outside the hash chain.**
  ledger/store.py:416-422 (`update_concept`), graph/workflow.py:109, :198, :261 and :275, tools/surface.py:730 and :748
  (as of Task 2.31). `concepts` is updated in place by design and has no triggers. Its `status` decides which ideas are
  developed into proposals (`selezionata`, workflow.py:198) and which proposals the director may put in the client
  presentation (`proposta`, surface.py:748 and workflow.py:275); `anon`, `card_json` and `sketch_file` decide what the
  presentation and the sheets show. None of it is chained, so a direct `UPDATE concepts SET status = …` changes what
  reaches the client with no trace, and `agency verify` stays `registro integro`. Fix: record each concept change as a
  chain event that binds the concept row, as Task 2.31 does for tickets, and replay it in `agency verify`. Same bug as
  CMT-007 (Q17). Found in Task 2.31. Not covered by a planned task.
  - Decided (2026-11-10): with 2.F56 (ADR-0049, migration 0007). Every concept write appends a version-2 event that binds the concept row; the migration binds today's rows; `agency verify` replays them.
- [x] **Task 2.F58: the append-only tables other than `events` rely on triggers alone, and `agency verify` cannot see
  a bypass.** migrations/versions/0001_baseline.py:222-236 (the `*_no_update` triggers), ledger/store.py:346-350
  (`add_evidence`) and qa/delivery.py:151 (as of Task 2.31). `gates` holds the client's decisions with the hashes of
  the files they were taken on, and `evidence` the QA results that decide whether a delivery passes
  (`evidence_problems` reads `evidence.latest`). Both refuse UPDATE and DELETE through triggers, but `DROP TRIGGER` is
  one statement for anyone who can write the file, and only `events` has a chain that detects it
  (`test_chain_detects_tampering_that_bypasses_the_triggers`). Each evidence row has a chain event whose note is
  `file:check:result:sha256[:16]`, but `agency verify` never compares the two; a gate has no event at all, so a dispute
  over what the client approved (Q17) has nothing chained to point at. Fix: needs the owner's decision on scope: replay
  `evidence` against its events and add a chained event per gate, or chain every append-only table. Same family as
  CMT-007 (Q17). Found in Task 2.31. Not covered by a planned task.
  - Decided (2026-11-10): with 2.F56 (ADR-0049, migration 0007). Every gate decision appends a version-2 event that binds the gate row, the migration binds today's rows, and `agency verify` compares gates and every evidence row with their chain events.
- [x] **Task 2.F59: `write_new_under` has no production caller.** tools/files.py:89 (as of Task 2.33). Task 2.2a added
  it with the other `*_under` helpers, but no harness write goes through it: `rg -n -w write_new_under src` finds only
  the definition, and tests/test_safe_files.py is its only caller. Same shape as SIM-006: code in `src/` that only the
  tests keep alive. Fix: delete it and its test uses, unless a harness write should refuse an existing file; then route
  that write through it. Found in Task 2.33. Not covered by a planned task (Task 4.3 moves only `ScriptedTransport`).
  - Moved to Phase 4 (2026-11-10), with Task 4.3: not a bug, code that only tests use.
  - Still open after Phase 4 (2026-11-12): Phase 4 only moves code, and this fix deletes code. It goes to the
    simplification phase.
  - Done after Phase 6 (2026-11-13): deleted, with its re-export in tools/files.py and its test uses. No harness
    write should refuse an existing file. All 21 go through `replace_under`, and each regenerates its file on
    purpose. Production calls `open_under` only to read, so the O_EXCL guarantee its own test checked protected no
    production path. The shared `..` and no-follow guarantees stay covered by the other rows of the same tables.
    test_safe_files.py goes from 126 to 119 cases. /ce-simplify-code (quality, test value) agreed.
- [x] **Task 2.F60: `Ledger.add_concept` is a seeding helper that only tests call.** ledger/store.py:404 (as of Task
  2.33). Since COR-003 (55039eb) the concept row is written by `Ledger.open(..., concept=...)` in the ticket's own
  transaction (tools/surface.py:660-665), and `rg -n -w add_concept src` finds only the definition. The tests
  (test_sketch_flow.py, test_agent_flow.py, test_report_views.py) and the e2e fixture tests/dashboard_fixture.py still
  seed concept rows through it, outside the transaction production uses. Same shape as SIM-006. Fix: seed through
  `Ledger.open(..., concept=...)` or a `tests/support/` helper, then delete the method; it fits Task 4.3. Found in
  Task 2.33. Not covered by a planned task.
  - Moved to Phase 4 (2026-11-10), with Task 4.3: not a bug, code that only tests use.
  - Still open after Phase 4 (2026-11-12): Phase 4 only moves code, and this fix deletes code. It goes to the
    simplification phase.
  - Done after Phase 6 (2026-11-13): deleted. The tests now seed concepts the way production writes them,
    through `Ledger.open(spec, project, concept=row)`, in the idea ticket's own transaction (COR-003).
    - A new `open_idea(ledger, row)` in tests/support/concepts.py opens the sketch ticket of the row's letter
      with plan_exploration's spec. The tests that seeded concepts pointing at idea tickets that did not
      exist ("T-1", "T-a") now get a real one.
    - The tests that already opened the idea ticket pass `concept=` to it: test_agent_flow's `closing_box`,
      test_sketch_flow and the e2e fixture's T-0002.
    - test_ledger's chain test binds its second concept through `Ledger.open`.
    - No test was dropped: the suite keeps 1165 tests, and Playwright keeps 24, the compare and scroll-region
      characterization included.
- [x] **Task 2.F61: `REVIEWERS` is a second list of the reviewer roles.** contracts/ticket.py:79 (as of Task 2.34).
  Task 2.34 made `roles.json` declare `"tools": "reviewer"` for `qa-inspector`, `critic` and `legal-reviewer`, but
  `REVIEWERS` still hard-codes the same three names and is read by tools/surface.py:318 and :518 and qa/delivery.py:96.
  Only `test_tool_declarations_match_the_org_chart` keeps the two equal. Fix: derive the set from the registry (after
  Task 2.35 types it), or give the contract a single owner. Found in Task 2.34. Not covered by a planned task.
  - Moved to Phase 6 (2026-11-10): a second owner of a rule, refactor rather than bug.
  - Done after Phase 6 (2026-11-13): `roles.json` is the only owner. `agency.registry.REVIEWERS` is derived from
    the roles whose `tools` is `"reviewer"`, and the hard-coded set left `contracts/ticket.py`, which never used
    it. tools/surface.py (2 uses) and qa/delivery.py (1 use) read `registry.REVIEWERS`, which they already imported.
    - `test_tool_declarations_match_the_org_chart` now pins the three names, so a role joins the reviewers only
      by a deliberate edit of the test, and checks the derived set against them.
    - Mutation check in a scratch copy, baseline 379 passed: an empty set fails 9 tests (the write refusal, the
      review validation, the registry), and a set without `legal-reviewer` fails the registry test.
- [x] **Task 2.F62: `plan_exploration` builds the direction role names from a letter.** tools/surface.py:640-645
  (`f"direction-{letter}"` over `"abcde"`, as of Task 2.34). The five direction roles are listed in `roles.json`, but
  the code derives them from the position in a string, so a renamed or added direction in the registry is not seen.
  Fix: read the direction roles from the registry, in order. The fixed pipeline roles named in graph/workflow.py
  (`design-director`, `identity-designer`, `critic`) are the graph's own structure and are not flagged. Found in Task
  2.34. Not covered by a planned task.
  - Moved to Phase 6 (2026-11-10): a rule rebuilt from names, refactor rather than bug.
  - Characterization first (2026-11-13): no test tied each lever to its direction.
    `test_five_directions_run_together_and_reach_the_board` compares the assignees as a set, and the scripted
    flows tie only ticket order to letters. `test_each_lever_goes_to_its_own_direction_in_order`
    (test_sketch_flow.py) pins, for five levers, each row's letter and lever and each ticket's assignee, title,
    workspace and outputs. Mutation check in a scratch copy, baseline 1 passed: reversed levers, reversed letters
    and roles swapped against letters each fail it.
  - Done after Phase 6 (2026-11-13): `roles.json` owns the directions and their order.
    - `agency.registry.DIRECTIONS` maps each direction's letter to its role, in the order roles.json lists them.
      It is the only place that knows the `direction-` prefix.
    - `plan_exploration` zips the levers with it instead of with `"abcde"`, and assigns the role it gives.
    - `test_tool_declarations_match_the_org_chart` pins the five pairs in order (ADR-0013).
    - Mutation check in a scratch copy, baseline 84 passed (test_registry.py, test_sketch_flow.py): the
      directions reversed, or without `direction-c`, fail 34 tests each, the characterization and the registry
      test included.
- [x] **Task 2.F63: `agency migrate` claims only the project locks that exist.** cli.py `_migrate` (as of the B6 batch:
  it globs `locks/*.lock`). A project's lock file is created by its first `run`, so a first `run` of a new project
  started during a migration takes no claim the migration holds; it then waits on the registry's write lock (busy
  timeout 30 s) or finds the registry outdated. Fix: a registry-wide claim that every `run`, `resume` and `decide`
  takes shared and `migrate` takes exclusive. Found in the B6 batch. Not covered by a planned task.
- [x] **Task 2.F64: `plain` keeps newlines in one-line messages.** contracts/text.py (`plain`) used by cli.py for
  `API NON DISPONIBILE`, `SANDBOX NON DISPONIBILE` and `Confronto non possibile`. A newline inside the exception
  text (an API or proxy body, systemd's output) still starts a new terminal line that can look like the CLI's own.
  Fix: a `one_line` variant that also folds `\n` and `\t` to a space, for messages that are one line by design.
  Found in the B6 batch. Not covered by a planned task.
- [x] **Task 2.F65: the tables that do not decide a delivery are outside the hash chain, some without triggers.**
  As of the B10 batch (ADR-0049): `projects` (budget, model, effort) and `operations` (the resume records of the
  tools) have neither triggers nor chain; `usage` (which feeds `spent()` and the budget), `renders`, `derivations`,
  `runs`, `judgments` and `artifacts` rely on their `*_no_update`/`*_no_delete` triggers alone, which one `DROP
  TRIGGER` removes, and `agency verify` cannot see a bypass. ADR-0049 chained what decides a delivery; these decide
  money, resumption and records. Fix: needs the owner's call on scope (chain `usage` and `projects`, the two that
  change money, like ADR-0049; triggers for `operations`). Found in the B10 batch. Not covered by a planned task.
- [x] **Task 2.F66: `renders`, `derivations` and the `view_image` records feed delivery checks but are not chained.**
  Found in the B11 batch: `_seen_proof` and `derivation_problem` read them, comparing their hashes with the current
  file's. After ADR-0050 they are append-only (`renders`, `derivations` by their triggers, `operations` by the new
  ones) but not bound by the chain, so a row INSERTed by hand with the right hash would pass. Decided (2026-11-10):
  accepted and recorded in ADR-0050. Forging one needs write access to the registry file on the operator's machine,
  and each row must still match the current file's hash; these rows guard what the agent looked at, not what the
  client approved, which ADR-0049/0050 chain. Revisit if the registry ever leaves the operator's machine (M7).

## Phase 3: comments and language (Q14–Q16)

Every task edits comments and docstrings only, plus developer-facing messages where it says so.
- **Never touched in these tasks:** model-facing text, user-facing strings, stored and wire values, migration files,
  the vendored scripts, and the CMT-017 fixtures.
- **Verify, besides the standard gate:**
  - LANG-CHECK prints nothing for the task's files;
  - the help snapshots of Task 1.16 are unchanged;
  - `uv run agency-schemas && git diff --exit-code schemas/openapi.json` prints nothing (except in 3.2).
- **Inventory:** the per-file lines are in `docs/audit/40-comments-language.md`, appendices A1–A11.
- **Docstrings (CMT-014, by the Q14 rule):** the package tasks for `artifacts`, `contracts`, `gateway`, `ledger` and
  `tools/sandbox` add docstrings to their A10 items, only where a docstring says something the name does not. They
  never add one to [T], [O] or [M] items.

- [x] **Task 3.1: argparse descriptions become explicit strings.** Closes CMT-001 (the CLI-help part).
  - Files: `src/agency/cli.py:297`, `src/agency/entrypoints/server/serve.py:58`,
    `src/agency/entrypoints/server/schema.py:30`.
  - Change: each `description=__doc__` becomes the exact current text, so the help is unchanged.
  - Commit: `refactor(cli): give each argument parser its own description`.
- [x] **Task 3.2 [APPROVAL]: the OpenAPI descriptions are written in English.** Closes CMT-001 (the OpenAPI part).
  - Files:
    - the 27 [O] class docstrings: `insights/views.py`, `flow.py`, `behaviour.py`, `quality.py`, `compare.py`,
      `replay.py` and `domain.py`;
    - `entrypoints/server/api.py:28,30,134,164,179`;
    - `schemas/openapi.json` and `web/src/api/schema.ts`, regenerated with `uv run agency-schemas` and
      `pnpm --dir web run api:types`.
  - Verify: the generated diffs change only `description` strings; `pnpm --dir web run api:check` passes; standard gate,
    without the schema line.
  - Commit: `docs(api): write the OpenAPI descriptions in English`.
- [x] **Task 3.3: the domain vocabulary is documented.** Closes CMT-008 (Q16).
  - Files: `docs/03-DATA-MODEL.md`.
  - Content, in Italian: a "Vocabolario" section giving the rule (identifiers in English; stored and wire values in
    Italian; changing a value is a migration) and the current values, as pinned by Task 1.17.
  - Commit: `docs(data-model): record the stored and wire vocabulary`.
- [x] **Task 3.4: `src/agency/agents/`.** Closes CMT-009 for this package.
  - Keep the reminder, the block reasons and the packet text.
  - Commit: `docs(agents): translate comments and docstrings to English`.
- [x] **Task 3.5: `src/agency/artifacts/`.** Closes CMT-009 for this package, and its CMT-014 items.
  - Commit: `docs(artifacts): translate comments and docstrings to English`.
- [x] **Task 3.6: `src/agency/contracts/`.** Closes CMT-009 for this package, CMT-018, and its CMT-014 items.
  - Keep the model-facing `Field` descriptions and every enum value.
  - Commit: `docs(contracts): translate comments and docstrings to English`.
- [x] **Task 3.7: `src/agency/entrypoints/server/`.** Closes CMT-009 for this package.
  - Keep `Problem.detail` and the server messages.
  - Commit: `docs(server): translate comments and docstrings to English`.
- [x] **Task 3.8: `src/agency/evaluation/`.** Closes CMT-009 for this package.
  - Keep the interview prompts and the `CannotCompare` texts.
  - Commit: `docs(evaluation): translate comments and docstrings to English`.
- [x] **Task 3.9: `src/agency/gateway/`.** Closes CMT-009 and CMT-011 (`transport.py:70`, `client.py:167`) for this
  package, and its CMT-014 items.
  - Commit: `docs(gateway): translate comments, docstrings and internal messages to English`.
- [x] **Task 3.10: `src/agency/graph/`.** Closes CMT-009 and CMT-011 (`workflow.py:291`) for this package.
  - Keep the ticket texts and outcomes.
  - Commit: `docs(graph): translate comments, docstrings and internal messages to English`.
- [x] **Task 3.11: `src/agency/insights/`, apart from 3.2.** Closes CMT-009 for this package, CMT-005 and CMT-019.
  - Commit: `docs(insights): translate comments and docstrings to English`.
- [x] **Task 3.12: `src/agency/ledger/`, apart from the migrations.** Closes CMT-009 and CMT-011 (`store.py:415`) for
  this package, CMT-006, CMT-007 (describe the chain as Task 2.31 left it), and its CMT-014 items.
  - Commit: `docs(ledger): translate comments, docstrings and internal messages to English`.
- [x] **Task 3.13: `src/agency/qa/`, apart from the scripts.** Closes CMT-009 for this package.
  - Keep `qa/checks.py:58`: it can reach the model.
  - Commit: `docs(qa): translate comments and docstrings to English`.
- [x] **Task 3.14: `src/agency/telemetry/`.** Closes CMT-009 for this package.
  - Keep the report texts.
  - Commit: `docs(telemetry): translate comments and docstrings to English`.
- [x] **Task 3.15: `src/agency/tools/`.** Closes CMT-009 for this package, CMT-004, and its CMT-014 items for
  `sandbox.py`.
  - No class docstring on any tool-input model: use `#` comments.
  - Commit: `docs(tools): translate comments and docstrings to English`.
- [x] **Task 3.16: the top-level modules.** Closes CMT-009 for `cli.py`, `config.py`, `doctor.py`, `runtime.py`,
  `__init__.py` and `context/__init__.py`.
  - The CLI help is safe after 3.1; keep every printed string.
  - Commit: `docs(engine): translate the top-level modules' comments and docstrings to English`.
- [x] **Task 3.17: tests, part 1 of 3.** Closes CMT-010 and CMT-011 (the test rows) for:
  - `test_insights.py`, `test_server.py`, `test_schemas.py`, `test_report_views.py`;
  - `test_compare_view.py`, `test_replay_view.py`, `test_quality_view.py`, `test_behaviour_view.py`, `test_flow_view.py`;
  - `dashboard_fixture.py`.

  Keep every assertion on a user-facing string.
  - Commit: `docs(tests): translate the dashboard tests' comments and docstrings to English`.
- [x] **Task 3.18: tests, part 2 of 3.** Closes CMT-010 and CMT-011 for:
  - `test_agent_flow.py`, `test_sketch_flow.py`, `test_hardening.py`, `test_gateway.py`;
  - `test_request_snapshots.py`, `test_board.py`, `drawings.py`.
  - Commit: `docs(tests): translate the engine tests' comments and docstrings to English`.
- [x] **Task 3.19: tests, part 3 of 3.** Closes CMT-010 and CMT-011 for the remaining test files and `conftest.py`.
  - Includes the Python-owner sentence of `test_toolchain.py`, for STR-011.
  - Commit: `docs(tests): translate the remaining tests' comments and docstrings to English`.
- [x] **Task 3.20: web comments and JSDoc.** Closes CMT-012, CMT-002, CMT-003 and CMT-015.
  - Files: `web/src/**`, `web/e2e/**` (comments only), `web/scripts/**`, `web/next.config.mjs`,
    `web/playwright.config.ts`, and the comments of `web/src/app/globals.css`.
  - Keep `fetch(`, `use server` and `generateStaticParams` out of the comments in `web/src` (CMT-002).
  - Verify: `pnpm --dir web run defenses`, `typecheck` and `test`, `make e2e`, then the standard gate.
  - Commit: `docs(web): translate comments to English and document the exported helpers`.
- [x] **Task 3.21: web test titles and build-check messages.** Closes CMT-013.
  - Files: `web/src/*.test.ts`, `web/e2e/*.spec.ts` (the titles), `web/scripts/check-defenses.mjs` and
    `web/scripts/standalone.mjs` (their messages).
  - Keep the UI-copy assertions, and the "Next.js" and "Django" label prefixes.
  - Commit: `test(web): write test titles and build messages in English`.
- [x] **Task 3.22: config and infrastructure comments.** Closes CMT-016, and STR-011 (the comment part).
  - Files:
    - `pyproject.toml` (its comments and the four contract names);
    - `Makefile`;
    - `mise.toml`: line 2 now names `.python-version` as the Python owner;
    - `Taskfile.yml`: comments only, not `desc:`;
    - `.gitignore`, `.env.example`, `docker/*`, `spikes/sandbox_craft.sh` (comments and output);
    - `web/tsconfig.json`, `web/pnpm-workspace.yaml`, and the description in `web/package.json`.
  - Commit: `docs(config): translate configuration comments to English`.

### Phase 3 follow-up: decisions on the open items

Andrea delegated the items Phase 3 left open (2026-11-12). Each decision applies a rule already taken (Q15,
ADR-0019, CLAUDE.md) or corrects a text, so none needs a new ADR.

- [x] **D1 (CMT-004, the model-facing half).** The sketch warning says what it measures: "del lato più lungo del
  disegno", not "della larghezza".
- [x] **D2 (the doctor.py owner note).** `agency doctor` gives Docker's reason as "cruscotto (ADR-0040); da M4 Langfuse
  e ComfyUI". D1 and D2: `fix: say what the sketch warning measures and what Docker serves`.
  Superseded by Task 5.5 (Q13): Docker is now optional, with the reason `task docker:up`.
- [x] **D3 (Task 3.2 follow-up).** The OpenAPI `info.title` is English, "Design agency: dashboard" (Q15).
- [x] **D4 (CMT-011).** `qa/checks.py` `execute` raises its internal error in English: `run`, its only caller, refuses any
  check outside RUNNABLE first, so the model never sees it. D3 and D4: `docs: write the OpenAPI title and the internal
  check error in English`.
- [x] **D5.** The projection's schema fingerprint covers the stored shape, not the models' descriptions.
- [x] **D6.** The Phase 3 language check becomes a test in `make check`: comments through `tokenize`, docstrings through
  `ast`, so a string never matches (`tests/test_language.py`). D5 and D6: `test: fingerprint the stored shape and guard
  the language of comments`.
- [x] **D7 (CMT-016).** Ruff keeps RUF001-RUF003 on and allows `×` through `allowed-confusables`.
- [x] **D8 (STR-002, the pyproject half).** Every slice contract forbids every engine package the slice does not use.
  D7 and D8: `build: allow the multiplication sign and complete the slice contracts`.

## Phase 4: file structure

- [x] **Task 4.1: the insights ledger reader gets the name ledger.** Closes STR-009 (Q18).
  - Files:
    - move `src/agency/insights/adapters/registry.py` to `adapters/ledger.py`, with plain `mv`;
    - in `ports.py`, `application.py` and `domain.py`: `RegistryReader` → `LedgerReader`, `RegistrySnapshot` →
      `LedgerSnapshot`, `ReadOnlyRegistry` → `ReadOnlyLedger`, `RegistryNotReadable` → `LedgerNotReadable`;
    - the callers: `cli.py`, `entrypoints/server/api.py`, `tests/conftest.py`, and the tests.

    Keep `Provenance.from_registry`, `registry_revision` and `Fingerprint.registry`.
  - Verify: the standard gate, with `schemas/openapi.json` byte-identical.
  - Commit: `refactor(insights): call the ledger reader a ledger`.
- [x] **Task 4.2: one module loads the studio rules.** Closes STR-005, SIM-005 (`evidence.ROLES`), and STR-004 (the
  `tools → agents` edge) (Q18, Q19).
  - Files:
    - create `src/agency/registry.py`;
    - `src/agency/agents/prompts.py`: its lookups at :10-27 and :75-77 move out;
    - `src/agency/qa/evidence.py`: the dead `ROLES` loader is deleted;
    - `src/agency/tools/surface.py` and the other importers;
    - `pyproject.toml`: `agency.registry` joins the four contract lists, as Task 1.19 requires.
  - Interfaces: `ROLES: dict[str, RoleSpec]`, `CHECKS: dict[str, CheckSpec]`, `ORG: OrgFile`, `PROMPTS: Path`,
    `skill_names()`, `skills_index()`, `has_prompt(role)`, `can_open(sender, assignee)`.
  - Verify:
    - `mise exec -- uv run python -c "import grimp; g=grimp.build_graph('agency'); print(g.find_shortest_chain('agency.tools','agency.agents'))"`
      prints `None`;
    - the request snapshots are byte-identical;
    - standard gate.
  - Commit: `refactor(registry): load the studio rules in one module`.
  - Done as a pure move (Phase 4, unit U3). Two parts of this task are not moves and are left to the simplification
    phase (SIM-005): deleting the dead `evidence.ROLES` loader, and typing `ROLES` and `CHECKS` as `RoleSpec` and
    `CheckSpec`.
- [x] **Task 4.3: test helpers and the scripted transport live in `tests/support/`.** Closes STR-016 and SIM-006 (its
  move part).
  - Files:
    - move `tests/drawings.py` and `tests/dashboard_fixture.py` into `tests/support/`;
    - move `ScriptedTransport` from `src/agency/gateway/transport.py` into `tests/support/scripted.py`;
    - `pyproject.toml`: `pythonpath = ["tests"]`;
    - update the imports;
    - `web/playwright.config.ts:30`: the new fixture path.
  - Verify: `mise exec -- uv run pytest --import-mode=importlib --collect-only -q` collects everything; `make e2e`
    passes; standard gate.
  - Commit: `refactor(tests): keep test helpers and the scripted transport in tests/support`.
- [x] **Task 4.4: only the gateway imports `anthropic`.** Closes STR-003, for this refactor. `langgraph` and the
  ledger port stay in M1.7.
  - Files: `src/agency/gateway/__init__.py` (it re-exports `APIError`), `src/agency/cli.py` (its import), and
    `pyproject.toml`: a new forbidden contract on `anthropic` for every package except `agency.gateway`, with
    `allow_indirect_imports = true`.
  - Verify: `mise exec -- uv run lint-imports` reports 5 contracts kept; standard gate.
  - Commit: `refactor(cli): catch API errors through the gateway, and let only the gateway import anthropic`.
- [x] **Task 4.5: each dashboard view is mapped to its names.** Closes STR-015.
  - Files: `docs/01-ARCHITECTURE.md`, section "Cruscotto e server". The table, in Italian, maps each view label to its
    page, e2e spec, API route, operationId, read model, module and pytest file.
  - Commit: `docs(architecture): map each dashboard view to its route, API and read model`.
- [x] **Task 4.F1: the no-follow helpers move below `tools`.** Found in Task 2.2a: `artifacts/keeping.py` now imports `agency.tools.files`, while `agency.tools` imports `agency.artifacts`, so the two packages depend on each other; and `evaluation` may not import `tools` (ADR-0027, Task 2.F23). Move `open_under` and the other `*_under` helpers (and `OutsidePerimeter`) to a module both can import, for example `agency.contracts.files` (see Task 6.10), keeping `agency.tools.files` re-exporting them. Move only; no behaviour change.
  - Brought forward (2026-11-10): done before the found-bug fixes, because 2.F20 and 2.F23 need the helpers in `evaluation`. Move only.

## Phase 5: developer experience

- [x] **Task 5.1: the Taskfile ignore test needs a git checkout.** Closes DX-005.
  - Files: `tests/test_taskfile.py:107-110`. It reuses the `skipif` of `tests/test_repository.py:33`, and asserts git's
    return code with its stderr.
  - Verify: in a `git archive` copy, `task test -- tests/test_taskfile.py` skips that test instead of failing; standard
    gate.
  - Commit: `test(taskfile): skip the ignore check outside a git checkout`.
- [x] **Task 5.2 [APPROVAL]: the Craft tests skip without the Craft CLIs, and the sandbox tests fail once without
  bwrap.** Closes DX-001 and TST-017 (its key half) (Q10).
  - Files: `tests/conftest.py`, `tests/test_agent_flow.py`, `tests/test_hardening.py:406`, and `pyproject.toml`
    (the `sandbox` marker).
  - Changes:
    - `needs_craft` on the 8 `runner()` tests;
    - a `sandbox` marker on the 3 bwrap tests;
    - a session-start probe, `bwrap --unshare-net --ro-bind /usr /usr true`. When it fails and a selected test
      carries `sandbox`, the session fails with one line naming bwrap;
    - the fake key is set with `monkeypatch`.
  - Verify: on a PATH without `vectorcraft-cli`, the Craft tests skip; on a PATH without bwrap, the session stops with
    one line; `pytest -m "not sandbox"` runs; standard gate.
  - Commit: `test(dx): skip Craft tests without the CLIs, and fail once without a working bwrap`.
- [x] **Task 5.3: the two slowest tests no longer wait on subprocesses.** Closes TST-018.
  - Files: `tests/test_doctor.py:5` (it patches `doctor._gpu`), and `tests/test_agent_flow.py:655` (it calls
    `cli.main(["--help"])` under `pytest.raises(SystemExit)`).
  - Verify: `--durations=5` no longer lists them above 0.5 s; standard gate.
  - Commit: `test(dx): keep the doctor and help tests off slow subprocesses`.
- [x] **Task 5.4 [APPROVAL]: a stale lock fails instead of being rewritten.** Closes DX-004 (Q12).
  - Files:
    - `Taskfile.yml`: `setup` runs `uv sync --locked`, `UV_LOCKED: "1"` goes in `env:`, and `uv lock --check` becomes
      the first step of `check`;
    - `docker/server.Dockerfile:16,18`: `--locked`;
    - `tests/test_taskfile.py`: `CHECK` gains the first command;
    - `tests/test_docker.py`.
  - Verify: in a copy where `pyproject.toml` disagrees with the lock, `task setup` fails and `uv.lock` is unchanged;
    standard gate.
  - Commit: `build(task): fail on a stale uv.lock instead of rewriting it`.
- [x] **Task 5.5 [APPROVAL]: doctor tells the truth about Docker and Chromium.** Closes DX-006 (Q13).
  - Files: `src/agency/doctor.py`, `tests/test_doctor.py`.
  - Changes:
    - Docker becomes optional, with the reason `task docker:up`.
    - Chromium becomes required. Doctor reads the expected revision from
      `web/node_modules/playwright-core/browsers.json` and checks that its folder exists in the browser cache. When it
      is missing, doctor prints the install command from `docs/04-TOOLS.md:91`.
    - The new strings are Italian.
  - Verify: the tests pass; standard gate.
  - Commit: `fix(doctor): make Docker optional and check Playwright's Chromium`.
- [x] **Task 5.6 [APPROVAL]: `task format` fixes and formats.** Closes DX-008.
  - Files: `Taskfile.yml` (`format`: `uv run ruff check --fix .`, then `uv run ruff format .`), `Makefile` (`format`
    joins `TASKS`), `tests/test_taskfile.py` (`ALIASES`).
  - Verify: `mise exec -- task --list` shows `format`; `make -n format` prints `mise exec -- task format`; standard gate.
  - Commit: `build(task): add a format task that fixes and formats`.
- [x] **Task 5.7 [APPROVAL]: a bare `make` lists the commands.** Closes DX-012.
  - Files: `Makefile` (a first target, `help`, that runs `mise exec -- task`), `tests/test_taskfile.py`.
  - Verify: `make -n` prints `mise exec -- task`; standard gate.
  - Commit: `build(make): list the commands on a bare make`.
- [x] **Task 5.8 [APPROVAL]: `docker:up` checks that the registry folder exists.** Closes DX-010.
  - Files: `Taskfile.yml` (`docker:up` gets a precondition on `AGENCY_DATA_DIR`, with one Italian line),
    `tests/test_taskfile.py`.
  - Verify: `task --dry docker:up` with a missing folder prints the line; standard gate.
  - Commit: `build(docker): refuse docker:up when the registry folder is missing`.
- [x] **Task 5.9 [APPROVAL]: Python is pinned to its exact version.** Closes DX-011, and STR-011 (the Python part).
  - Files: `.python-version` (`3.13.15`), `tests/test_docker.py:116-119` (compares the full version).
  - Verify: `uv run python -V` prints `3.13.15`; standard gate.
  - Commit: `build(python): pin Python to 3.13.15 everywhere`.
- [x] **Task 5.10 [APPROVAL]: the sandbox spike tests the real sandbox.** Closes DX-007, STR-012, and SEC-008 (the
  spike part).
  - Files: `spikes/sandbox_craft.sh`.
  - Changes:
    - check `command -v bwrap blender vectorcraft-cli …` first, and exit with a message if one is missing;
    - take the bwrap prefix from `uv run python -c "from agency.tools.sandbox import Sandbox; …argv([])"`;
    - count only each probe's own exit status.
  - Verify: on a PATH without bwrap, the script exits 1 and prints no `ok`; with bwrap, it prints 8 `ok`.
  - Commit: `fix(spikes): run the Craft spike in the engine's own sandbox`.
- [x] **Task 5.11 [APPROVAL]: a pre-commit hook and a clean-checkout gate.** Closes DX-009 (Q11). New ADR: ADR-0051
  ("Il controllo gira da solo"), since 0049 and 0050 were taken by Phase 2. The hook runs `task check:fast`, a new
  task that is also the start of `task check`, so the fast checks are listed once; `check:clean` copies the index,
  which is HEAD plus what is staged.
  - Files:
    - create `.githooks/pre-commit`. It calls `mise exec -- uv lock --check`, then `ruff check`,
      `ruff format --check`, `lint-imports`, `pyright`, `api:check`, the web typecheck and `defenses`;
    - `Taskfile.yml`:
      - add `check:clean`, which exports `HEAD` with `git archive`, or the index with
        `git checkout-index -a --prefix=`, into a temporary folder, runs `setup` and `check` there, and deletes the
        folder;
      - `setup` prints `git config core.hooksPath .githooks` for Andrea to run;
    - `tests/test_taskfile.py`, `docs/adr/0051-il-controllo-gira-da-solo.md`, `docs/adr/README.md`.
  - Verify:
    - `PATH=/usr/bin:/bin .githooks/pre-commit` exits 0 in about 10 s;
    - `mise exec -- task check:clean` exits 0;
    - standard gate.
  - Commit: `build(gate): add a pre-commit hook and a clean-checkout check`.
- [x] **Task 5.12: the README gets a newcomer to a green run.** Closes DX-002, DX-013, and STR-017 (the README part).
  - Found while writing it:
    - nine presentation tests need `fc-match`. With fontconfig missing they fail with
      `No such file or directory: 'fc-match'`. The README lists fontconfig as a prerequisite instead of skipping them.
    - the sandbox tests need the systemd user session (ADR-0046). A shell started with `env -i`, `sudo -u` or `su`
      has no `XDG_RUNTIME_DIR` or `DBUS_SESSION_BUS_ADDRESS`, and the session stops at once with systemd's own
      line. The README has that row in its common errors.
  - Walk-through (2026-11-12): an index copy with `PATH=/usr/bin:/bin`, so without mise active, and warm caches.
    `mise trust`, `make setup`, the Chromium line and `make check` reach green in 119 s: 1139 passed, and 4 skipped
    for want of a git clone. Then the single-test commands each exit 0.
  - Files: `README.md`, in Italian.
  - Content:
    - prerequisites: mise activated, or the `make` aliases; the machine tools `task doctor` checks; and the Chromium
      install command;
    - the `agency verify` line, `--record`, `task format` and `task check:clean`;
    - the full "Struttura" tree, including `web/`, `schemas/`, `prompts/`, `docker/` and `evals/`.
  - Verify: a README walk-through in a `git archive` copy reaches a green `task check`; standard gate.
  - Commit: `docs(readme): list the prerequisites and every command and folder`.
- [x] **Task 5.13: the editors keep the files as they are.** Added in Phase 5 for the editor-config target, and done
  before 5.12 so the README can name it.
  - Files: create `.editorconfig`; `tests/test_toolchain.py`.
  - Content: UTF-8, LF, a final newline and no trailing whitespace everywhere. Indents follow the files as they
    are: 2 spaces by default, 4 for Python and SQL, tabs in the Makefile, and the generators' 4 in `uv.lock` and
    `web/src/api/schema.ts`. Python wraps at Ruff's 110. A test keeps that number equal to the one in
    `pyproject.toml`. No `.vscode/`: the language servers already read `pyproject.toml` (pyright, Ruff) and
    `web/tsconfig.json`.
  - Found while checking: every versioned file outside `legacy/` is UTF-8 and LF with no trailing whitespace.
    Two files have no final newline, `prompts/skills/critique/SKILL.md` and `registry/checks.json`, and they stay
    so: both are content the runs read, not configuration. An editor adds the newline at their next edit.
  - Not in Phase 5: a formatter and a linter for `web/` (Biome, or Prettier and ESLint). Each is a new dependency
    under the two-week quarantine. Its first run would also reformat every web file. It needs its own decision and
    ADR, after this plan.
  - Verify: Neovim 0.11 (built-in EditorConfig) opens a `.py`, `.tsx`, `.mjs`, `.yml`, `.sql`, `.md` file, the
    Makefile, `uv.lock` and `schema.ts` with the expected indent, and LF; standard gate.
  - Commit: `build(editor): add an .editorconfig that matches the files and Ruff`.
- **Phase 5 verification: a newcomer's clean clone.** A fresh subagent clones `audit/deep-review` into `/tmp` and
  follows only the README.
  - Run 1 (2026-11-12, at `3967e55`): green on the first try, 153 s from the clone to the end of `task check`, of
    which 123 s were commands (`task check` alone 121 s). It ran with mise active and every cache warm.
  - Nothing failed. It found seven gaps in the text: what `task e2e -- …` does first; which folder the web test
    paths start from; the hook hint inside the no-mise paragraph; no way to check the systemd session; no
    `mise exec --` form for the web lines; the harmless hardlink warnings of `task setup` outside the caches'
    filesystem; and what the silent Chromium line should leave behind. Fixed in
    `docs(readme): answer what the clean-clone walk-through found unclear`.
  - Run 2 (2026-11-12, at `8a644d1`), the one repeat the verification allows: green on the first try, again 153 s
    from the clone to green, of which 122 s were commands (`task check` alone 119 s). Every cache was warm again,
    and it again took the mise-active path. Every README step exited 0, and so did each single-test command
    (pytest `1143 passed`, Playwright `22 passed`, web `18/18`). After the gate, `git status --short` in the clone
    printed nothing. The README text fixes left the time unchanged.
  - Open, from run 2. These are not fixed, because the verification stops after one repeat. Each is a small README
    change, unless noted:
    - the clone line `git clone <percorso-o-url>` names no source. It can name one only once a Git remote exists,
      which is the same decision CI waits for (Q11, ADR-0051);
    - nothing says how to tell whether mise is already active, for example that `command -v task` prints a path
      under `mise/installs`. The `echo … >> ~/.zshrc` line also adds a second copy if run twice;
    - the Chromium line carries `mise exec --` while the other lines of its block are bare, and nothing says why.
      The reason is that it works with or without mise active;
    - uv's hardlink warning suggests `UV_LINK_MODE=copy`. The README row says to do nothing, which is right, but
      could add that the variable only hides the warning;
    - there is no cold-machine estimate: no time, download size or disk space for a first `mise install`,
      `task setup` and Chromium. Both runs had warm caches, so measuring it needs a machine or user with empty
      caches. On this one, `.venv` is about 290 MB and `web/node_modules` about 400 MB.
  - Not checked by either run: the skips without VectorCraft or Docker, and the "Errori comuni" rows. Every tool
    was present on this machine. The skips and the `fc-match` failures were checked separately in Task 5.12, with
    a PATH that lacks those tools.

## Phase 6: sanity refactor and simplification

- [x] **Task 6.1: remove the unused OTLP exporter.** Closes SIM-002 (Q5).
  - Files: `pyproject.toml`, `uv.lock` (`uv remove opentelemetry-exporter-otlp-proto-http`).
  - Verify: the lock diff removes 7 packages; standard gate.
  - Done: the default install loses the 7 packages (`uv export --no-dev`: 68 → 61), and so does the API image.
    The lock keeps their entries, because `langfuse` in the `telemetry` extra still requires the exporter. They
    leave the lock with that extra in Task 6.2. No locked version changed.
  - Commit: `build(deps): drop the unused OTLP exporter`.
- [x] **Task 6.2 [APPROVAL]: drop the unused extras.** Closes SIM-003 (Q6).
  - Files: `pyproject.toml`, `uv.lock` (`context`, `qa` and `telemetry` removed), and `docs/04-TOOLS.md`, which notes
    that each package is declared again by the milestone that first imports it. Langfuse returns with M4.
  - Verify: `uv export --all-extras` lists 56 packages fewer; standard gate.
  - Done: `uv remove --optional` for each extra, then the empty `[project.optional-dependencies]` table removed and
    `uv lock`. The lock goes from 136 to 79 packages: 57 removed, none added, no version changed. The 57 are the
    extras' 50 plus the 7 that only the OTLP exporter needed, kept until now by `langfuse` (Task 6.1).
    `uv export --all-extras --no-dev` goes from 124 to 61, the same as the default install. The ADR-0010 row in
    `docs/adr/README.md` records that `langfuse` is declared with M4; the ADR itself is unchanged (Q6).
  - Commit: `build(deps): drop extras that nothing imports yet`.
- [x] **Task 6.3: the code declares what it imports, and a test keeps it that way.** Closes SIM-004 (Q7). New ADR:
  ADR-0052 ("Le dipendenze le dichiara il codice che le importa"), since 0050 and 0051 were taken. The check is by
  top-level name, as planned. A top-level name that several distributions share counts as declared when one of
  them is. So `langgraph-checkpoint` (`langgraph.checkpoint.base`, `.memory`) and `opentelemetry-api`
  (`opentelemetry.trace`) stay transitive. The ADR records this limit; checking per module would declare those two
  as well, and needs its own decision.
  - Files:
    - `pyproject.toml` and `uv.lock`:
      - `uv add 'sqlalchemy>=<locked>' 'langchain-core>=<locked>'`;
      - `uv add --dev 'httpx2>=<locked>'`;
    - create `tests/test_dependencies.py`. It maps every top-level import in `src/` and `tests/` to its distribution
      with `importlib.metadata.packages_distributions()`. It fails on an import that is not declared, and on a
      runtime dependency that nothing imports. Its allow-list covers ruff, pyright, import-linter and django-stubs;
    - `docs/adr/0052-le-dipendenze-le-dichiara-il-codice-che-le-importa.md`, `docs/adr/README.md`.
  - Verify: the test passes; mutant: deleting `sqlalchemy` from the declared dependencies is killed; standard gate.
  - Commit: `build(deps): declare every imported package and test it`.
- [x] **Task 6.4: delete three dead definitions.** Closes SIM-005 (its remainder).
  - Done with a fourth: the dead `qa.evidence.ROLES` loader that Task 4.2 left to this phase, together with the
    `REPO_ROOT` and `read_roles` imports only it used. In render.py only `ImageDraw` became unused; `Path` still
    types `_open` and `_save`. Reviewed with /ce-simplify-code (reuse, quality, efficiency): every reviewer
    confirmed no caller in src/, tests/, web/ or docs/, no dynamic use, and no import-time effect lost, since
    `agency.registry` already loads and validates registry/roles.json.
  - Files:
    - `src/agency/graph/workflow.py:38` (`SKETCH_CHECKS`);
    - `src/agency/tools/render.py` (`contact_sheet`, its entry in `__all__`, and the `ImageDraw` and `Path` imports
      that become unused);
    - `src/agency/ledger/store.py:297` (`render_of`).
  - Verify: `rg -n -w -e SKETCH_CHECKS -e contact_sheet -e render_of src tests` prints nothing; standard gate.
  - Commit: `refactor: delete definitions with no caller`.
- [x] **Task 6.5: drop four parameters that no caller passes.** Closes SIM-007.
  - Done with three. `Sandbox(read_only=…)` stays: since Task 5.10, spikes/sandbox_craft.sh passes it to bind
    Blender's folder. Removed: `Sandbox.run(stdin=…)` with the stdin-feeding branch of `_collect`, `PIPE_BUF` and
    `test_sandbox_feeds_stdin_to_the_command`, its only user. `delivery_problems(inputs_changed=…)` and its
    always-true guard. `Ledger.spent(ticket_id=…)` and its filter. The command still gets `stdin=PIPE`, closed at
    once, as the characterization test pins. Eight test fakes of `Sandbox.run` lose the parameter; one of them
    forwarded it positionally to `super().run`.
  - /ce-simplify-code reviewers (reuse, quality, efficiency, test value, comments). Accepted: the removals and
    the three comments they made false. Rejected:
    - `stdin=DEVNULL`, which changes what the command sees;
    - a `Literal` return type for `_collect` and a `NamedTuple` for `delivery_problems`: new abstractions that
      remove no duplication;
    - inlining `stale`, a matter of taste that would also move its file reads.
  - Before the change, a characterization test: no test pinned what production keeps once `stdin` goes, namely
    that a sandboxed command gets an empty, closed stdin. Every `stdin=` call passed data. New
    `test_a_sandboxed_command_reads_an_empty_closed_stdin`: `cat` answers `Completed(0, "", "")`. With stdin left
    open, it would wait for the timeout and answer 124. Found by the test-value reviewer of /ce-simplify-code.
  - Files: `src/agency/tools/sandbox.py` (`read_only`, `stdin`), `src/agency/qa/delivery.py` (`inputs_changed`),
    `src/agency/ledger/store.py` (`spent(ticket_id)`). `CommandIndex.load(app)` stays.
  - Commit: `refactor: drop parameters that no caller passes`.
- [x] **Task 6.6: one fingerprint reader.** Closes SIM-001.
  - Done: `_fingerprint` had the same body as `read_fingerprint` (Task 2.32): the same call, the same
    `ValidationError` caught, the same input. Its two call sites now use the shared reader, and `ValidationError`
    leaves the imports of compare.py. /ce-simplify-code (reuse, quality, efficiency) agreed and proposed nothing
    else. The efficiency reviewer noted that each side's fingerprints are parsed twice, by `_executions` and
    `_readable`. That is negligible for a handful of runs, and removing it would restructure beyond this task.
  - Files: `src/agency/insights/compare.py:132-136` (it uses `contracts.run.read_fingerprint` and deletes its own
    copy).
  - Commit: `refactor(insights): read fingerprints through the shared reader`.
- [x] **Task 6.7: the concept status is a type.** Closes SIM-009.
  - Done: `ConceptStatus(StrEnum)` in contracts/concept.py owns the six values. The ten places that spelled them
    use it: the `ConceptRow.status` default, 3 in tools/surface.py and 6 in graph/workflow.py. `ConceptRow.status`
    keeps its `str` column type, because an Enum column would need a migration. A `StrEnum` member compares equal
    to the stored string and serializes to the same bytes in the chain (`chain.canonical` is `json.dumps`), so
    stored rows, chain hashes and request snapshots are unchanged. tests/test_vocabulary.py pins the six values.
  - /ce-simplify-code reviewers (reuse, quality, efficiency, test value): no existing enum covers these values,
    and `TicketType`'s three equal words belong to another lifecycle. Rejected: writing `.value` at each writer,
    a matter of taste that gives the same bytes. Noted, not changed: `update_concept(**fields: object)` stays
    untyped, so the enum documents the values but cannot reject a wrong one there.
  - Before the change, a characterization test. No test asserted two of the six values: "idea", the default of a
    new concept row, and "scelta", which production writes for the client's choice. Found by the test-value
    reviewer of /ce-simplify-code. They are now pinned:
    - `test_a_concept_opened_with_its_ticket_starts_as_an_idea` in tests/test_ledger.py;
    - the statuses after the concept decision, in `test_client_only_sees_developed_proposals_then_production_starts`.
  - Files:
    - `src/agency/contracts/concept.py` (`ConceptStatus(StrEnum)`, with the members below);
    - `src/agency/ledger/models.py:134`, `src/agency/tools/surface.py`, `src/agency/graph/workflow.py`;
    - `tests/test_vocabulary.py`, which gains `ConceptStatus`.
  - The members: `IDEA="idea"`, `SKETCH="schizzo"`, `SELECTED="selezionata"`, `IN_DEVELOPMENT="in-sviluppo"`,
    `PROPOSAL="proposta"` and `CHOSEN="scelta"`.
  - Commit: `refactor(contracts): type the concept status`.
- [x] **Task 6.8: closing behaviour is declared on each tool.** Closes SIM-010.
  - Done in part, after review with /ce-simplify-code (reuse, quality, efficiency, comments).
  - Kept: the runnable set. `RUNNABLE = frozenset({Status.OPEN, Status.REWORK})` in contracts/ticket.py replaces
    six spellings: the DELIVER and BLOCK rows of `TRANSITIONS`, workflow.py's own `RUNNABLE`, `hand_off` in
    surface.py and `_block` in loop.py. Every use is a membership test.
  - Rejected: the `closes` and `conditional` fields on `Tool`. They would move `CLOSE_ALWAYS`'s six entries and
    `_restore`'s three branches into the tool table without removing any fact. And `CLOSING` must stay a
    hand-ordered tuple anyway, because the reminder text goes to the model and Task 1.14 pins it byte for byte.
    `CLOSING` and `CLOSE_ALWAYS` answer different questions: what the reminder offers, in what order, and how to
    rebuild an outcome on resume. Only the drift between them is a risk; a separate test unit covers it.
  - The drift guard: `test_the_reminder_offers_every_closing_tool_but_reject_concept` takes the tools that close
    on resume from the Task 1.14 table. It requires every `CLOSE_ALWAYS` name to be in that table, and `CLOSING` to
    equal that set minus reject_concept. Three mutations fail it: a new closer added only to `CLOSE_ALWAYS`, one
    added only to `CLOSING`, and a closer dropped from `CLOSING`. The comment above `CLOSING` no longer says it
    lists "the tools that close an instance". Now it records that reject_concept closes too, but is not offered.
    The history gives no reason: `CLOSING` is unchanged since the bootstrap commit 51c511c. So the comment states
    the fact and gives no reason.
  - Not changed: the CANCEL row and `reject_concept`'s four statuses (cancellable, a different fact) and
    `insights.flow.UNFINISHED` (runnable plus delivered).
  - Files: `src/agency/tools/surface.py` (`Tool`, `CLOSE_ALWAYS` and `_restore`), `src/agency/agents/loop.py:25`
    (`CLOSING`), `src/agency/contracts/ticket.py` (one exported `RUNNABLE`), `src/agency/graph/workflow.py:37`.
  - Changes:
    - `Tool` gains `closes: OutcomeState | None` and `conditional: Callable[[str], Outcome | None] | None`.
    - `CLOSE_ALWAYS` and `_restore` are derived from those fields.
    - The reminder keeps its current order and still leaves out `reject_concept`, as Task 1.14 pins. Record why in a
      comment.
  - Commit: `refactor(tools): declare closing behaviour on each tool`.
- [x] **Task 6.9: check kinds use `CheckKind`.** Closes STR-005 (the literals part).
  - Done: the six string spellings of the kinds in surface.py, qa/delivery.py and qa/evidence.py use
    `CheckKind` members. A `StrEnum` member equals the raw string the registry dict holds. An unknown check still
    gives None, which matches no member. The measure rule in `evidence.record` now asks `check in MEASUREMENTS`,
    the set the same module builds from the same kinds, instead of reading the kind again. That one came from the
    quality reviewer of /ce-simplify-code.
  - Rejected or left out:
    - a `check_kind(name)` helper in agency/registry.py for the five `CHECKS.get(name, {}).get("kind")` lookups.
      It is outside this task's files, and the two reviewers disagreed on its value. Open for a later decision;
    - renaming `LOOKED_AT` (taste);
    - typing `registry.CHECKS` and `ROLES` as `CheckSpec` and `RoleSpec`. That is the part Task 4.2 left to this
      phase; it touches every raw-dict reader and needs its own task.
  - Before the change, characterization tests. Ten mutants of the seven kind comparisons ran on a full copy; seven
    survived, since nothing pinned the refusals and the measure rule:
    - `observe` and `judge` refusing a check of another kind;
    - `record_requirement` refusing an observation, a judgement or a measure;
    - a judgement needing a renderable file;
    - a measure's PASS stored and accepted as MEASURED.
  - New tests:
    - `test_each_kind_of_check_is_recorded_by_its_own_tool` (test_agent_flow.py, five cases);
    - a `critique` case in `test_a_visual_check_needs_something_that_can_be_rendered` (test_hardening.py);
    - `test_a_measurement_is_stored_as_measured_and_passes_as_measured` (test_qa_gates.py).
  - With them, all ten mutants are killed, each by the test meant for it, on a green baseline of 632 tests.
  - Files: `src/agency/tools/surface.py:427,437,466`, `src/agency/qa/delivery.py:26`, `src/agency/qa/evidence.py:20,85`.
  - Commit: `refactor(qa): compare check kinds through CheckKind`.
- [x] **Task 6.10: one copy of each small helper.** Closes SIM-011 (the hash part).
  - Done: the four "sha256 of a file path" copies become one `file_sha256` in contracts/files.py, next to
    `sha256_under`, with the same `hashlib.file_digest` body. The copies were tools/files `sha256`,
    artifacts/files `_digest`, evaluation/blind `_digest` and telemetry/fingerprint `_sha256`. The output and the
    errors are the same: every copy opened the path, following links. blind.py and fingerprint.py now stream the
    file instead of reading it whole. agency.tools.files still exports it as `sha256`, so its importers (two
    tests) are unchanged. The name follows the plan, `file_sha256`, and not `sha256`: `FileStore.intact` has a
    parameter called `sha256`, which would shadow an imported function of that name. The four reviewers of
    /ce-simplify-code had all proposed `sha256`. The module docstrings of contracts/files.py and tools/files.py
    now say what each holds.
  - Not done, behaviour change: one `clip`. tools/files `clip` and insights/adapters/transcripts `_clip`
    cut differently: different markers, and one counts the marker in the limit. Merging them changes either the
    tool results the model reads or the refusals the dashboard shows.
  - Not done, rejected: one `BUSY_SECONDS`. The engine's write timeout and the dashboard's read-only wait are two
    independent waits that both happen to be 30 s. ADR-0019 keeps insights apart from the ledger. A contracts
    module for one number would be a new abstraction. The reviewers disagreed.
  - Files:
    - create `src/agency/contracts/files.py`, with `file_sha256(path: Path) -> str` (streamed in 1 MiB chunks),
      `clip(text: str, limit: int) -> str` and `BUSY_SECONDS = 30`;
    - the eight copies: `tools/files.py:21`, `artifacts/files.py:22`, `evaluation/blind.py:51`,
      `telemetry/fingerprint.py:51`, `tools/files.py:29`, `insights/adapters/transcripts.py:53`, `ledger/schema.py:27`
      and `insights/adapters/ledger.py:32`.
  - Commit: `refactor: share one copy of the hash, clip and busy-timeout helpers`.
- [x] **Task 6.11: `DataLayout` owns every data path.** Closes STR-006 and SIM-013.
  - Done: `Settings.work_dir(project)`, which is `project_dir(project) / WORK`, replaces the four hand-built work
    folders in cli.py, runtime.py, agents/loop.py and the closure in graph/workflow.py, which keeps its
    `parse_project_name`. evaluation/blind.py parses the folder back with the same `WORK`.
    `DataLayout.craft_index` and `DataLayout.blind(comparison)` replace the two `.data` paths built in runtime.py
    and cli.py. In src/, no data path is built by hand any more (7 sites → 0). tests/test_layout.py pins the
    new members. The other tests keep building the paths themselves, on purpose: they check the layout
    independently.
  - /ce-simplify-code (reuse, quality, efficiency). The quality reviewer called `craft_index` and `blind` taste,
    since each has one caller. Kept anyway: DataLayout's own docstring makes it the one owner of `.data`, and
    CLAUDE.md asks for one owner of each datum. A `.data` path spelled in cli.py or runtime.py is a second owner
    of that layout. The characterization unit pins both paths.
  - Before the change, characterization tests for the two `.data` paths that nothing pinned. The work folder
    `projects/<name>/work` was already pinned by the flows: 67 test lines read the files from it.
    - `test_a_session_keeps_the_craft_index_cache_under_the_data_root` (test_layout.py): `open_session` loads
      the Craft index from `<data root>/craft-index`. Before, an index looked for elsewhere would just be
      empty, and no test would fail.
    - `test_judge_lays_the_anonymous_copies_out_under_the_data_root` (test_hardening.py): `agency judge` lays
      the copies out in `<data root>/blind/<comparison>` and names that folder.
  - On a scratch copy with a green baseline, moving either path makes its test fail.
  - Files:
    - `src/agency/contracts/layout.py`: `blind(comparison)`, `craft_index`, and `WORK = "work"`;
    - `src/agency/config.py`: `work_dir(project)`;
    - the seven sites: `cli.py:227`, `runtime.py:129`, `runtime.py:76`, `cli.py:90`, `agents/loop.py:67`,
      `graph/workflow.py:68` and `evaluation/blind.py:60`;
    - `tests/test_layout.py`.
  - Commit: `refactor(config): build every data path through DataLayout`.
- [x] **Task 6.12: one name for each data path.** Closes SIM-017.
  - Done: the five `Settings` proxies are deleted: `ledger_path`, `checkpoints_path`, `artifacts_dir`,
    `traces_path` and `insights_path`. All 76 uses now spell `settings.layout.<path>` (26 in cli.py and
    runtime.py, 50 in tests). The audit called this a preference. The /ce-simplify-code reviewers (reuse,
    quality, test value) judged it real duplication: runtime.py and cli.py mixed both spellings inside the same
    function, and any rename in DataLayout needed a matching one in Settings. No caller outside src/ and tests/
    used the proxies; the Django server already used the layout. In tests/test_layout.py the block that pinned
    the proxies is gone, because it can no longer be written. The rest of that test still pins every path
    with independent literals, and still checks that `Settings.layout` is built from `data_dir`.
  - Files: `src/agency/config.py` (the five proxy properties are deleted, and callers use `settings.layout.<path>`),
    and every caller in `src/` and `tests/`.
  - Commit: `refactor(config): give each data path one name`.
- [x] **Task 6.13: the key names and e2e values have one owner.** Closes STR-011 (the code part).
  - Python part done: `API_KEY_VARIABLES` in a new contracts/secrets.py replaces the two copies of the names. The
    copies were `AliasChoices(...)` in config.py and `SECRETS` in entrypoints/server/serve.py. The order is kept,
    because the first variable set wins. The coupling is real: the server must drop exactly the names the engine
    reads. It lives in contracts and not in config.py, as the quality reviewer of /ce-simplify-code proposed,
    because the server may not import agency.config, which reads .env. doctor.py:113 stays as it is: it
    checks whether the key is present, a different fact. test_server and test_layout pin both names; dropping the
    second from the tuple fails both on a scratch copy.
  - The guard for the copies that cannot import Python is tests/test_consistency.py, in its own test unit. Each
    test reads the values with a pattern, not as a fixed snippet:
    - every `env -u …` in web/package.json, playwright.config.ts and check-defenses.mjs removes exactly
      `API_KEY_VARIABLES`;
    - Playwright plants the fake key in each of those names;
    - the e2e Django port baked into `build:e2e` is the one Playwright calls, the one `agency-server` listens on,
      and run.spec.ts's `DJANGO_PORT`;
    - the e2e build folder of `AGENCY_NEXT_DIST` is the one Playwright serves, run.spec.ts scans,
      tsconfig.json includes and .gitignore ignores.
    Six mutations fail: a third name only in Python, the defense check on one name, one canary, the server on
    another port, and tsconfig or .gitignore on another folder.
  - Files:
    - create `src/agency/contracts/secrets.py` (`API_KEY_VARIABLES`);
    - `src/agency/config.py:26`, `src/agency/entrypoints/server/serve.py:19`;
    - create `tests/test_consistency.py`. It checks that `web/package.json`, `web/playwright.config.ts` and
      `web/scripts/check-defenses.mjs` name the same variables, and that port 18765 and `.next-e2e` agree across
      `package.json`, `playwright.config.ts`, `tsconfig.json` and `.gitignore`.
  - Commit: `refactor(config): give the key names and e2e values one owner`.
- [x] **Task 6.14: one copy of the shared test helpers.** Closes SIM-015.
  - Done:
    - the three `turn()` copies (agent_flow, sketch_flow, recording) are one
      `turn(*blocks, stop="tool_use", output=20)` in tests/support/scripted.py, beside the ScriptedTransport that
      replays those responses. It gives the same dict for every existing call;
    - the four `settings()` copies (hardening, agent_flow, sketch_flow, recording) are one
      `settings(root, **extra)` in a new tests/support/settings.py. It is not a helpers.py as planned, because
      each module there is named after what it holds;
    - the four files still collect the same 391 tests.
  - /ce-simplify-code (reuse, quality): both merges accepted. No `settings` fixture or local name shadows the
    import.
  - Left out:
    - the `turn` in test_insights.py and test_replay_view.py, which build a transcript message and an
      `AssistantTurn`;
    - `reply` in test_hardening.py, which has other token counts;
    - two inline `Settings(data_dir=…, projects_dir=…)` expressions in test_request_snapshots.py and
      test_gate_sandbox.py, outside the sites this task names.
  - Files: `tests/support/helpers.py` (`settings()`, `turn()`), `tests/test_hardening.py:35`,
    `tests/test_agent_flow.py:34,43`, `tests/test_sketch_flow.py:65,122`.
  - Commit: `refactor(tests): share the settings and turn helpers`.
- [x] **Task 6.15: one scroll region and one metric-row helper in the web app.** Closes SIM-016.
  - Done: the 14 hand-written `<div className="scroll" role="region" aria-label=… tabIndex={0}>` wrappers are
    one `ScrollRegion({ label, children })` in web/src/components/scroll-region.tsx. It has no hooks, so the
    server pages and the client context chart both use it, and each caller passes its full label as before.
    In compare/page.tsx, a local `measured(label, before, after, format)` builds the 9 rows that spelled the same
    before/after/delta triple; `rows()` goes from 77 to 42 lines. The 7 other rows have other shapes and stay.
  - /ce-simplify-code (reuse, quality): both accepted. The label stays an explicit prop. It equals the
    inner table's name in 2 wrappers and differs in 12, so deriving it would change one group or the other.
  - Verified by the characterization unit's e2e tests: every wrapper is still a named, tabbable region on every
    page, and the comparison table is the same cell by cell.
  - Before the change, two e2e characterization tests:
    - `every table that scrolls sideways is a named region the keyboard reaches` (run.spec.ts). On every page,
      with every `<details>` open, each `.scroll` wrapper has `role="region"` and `tabindex="0"`, and the
      wrappers' names are pinned page by page. That covers all 14 wrappers: the context chart's turn tables
      appear only with their details open. Before, nothing checked the wrappers; the specs selected the
      tables inside them.
    - `compare view: every measure of the two projects, cell by cell` (compare.spec.ts) pins the whole
      "Affiancati" table. Before, 6 of its 16 rows were checked, and only 3 of the 9 rows that `rows()` builds
      from the same before/after/delta triple.
  - On a copy with a green baseline, three mutations fail: a dropped `tabIndex`, a reversed delta and a
    renamed turn table.
  - Files: create `web/src/components/scroll-region.tsx`, and the seven files that write the wrapper out, including
    `web/src/app/compare/page.tsx` (whose `rows()` uses a metric-row helper).
  - Every label string stays unchanged.
  - Verify: `make e2e` passes; standard gate.
  - Commit: `refactor(web): share the scroll region and the metric rows`.
- [x] **Task 6.16: the before/after comparison.**
  - Done: docs/audit/90-after.md, from a fresh `git clone` of `08f125c` (a worktree would write to the
    repository). Every row of the baseline's §5 exits 0, and so do the three rows Phase 5 added.
  - Files: create `docs/audit/90-after.md`, in English.
  - Content:
    - rerun every command of `00-baseline.md` §5 from a clean worktree of the final HEAD;
    - build the same table as §2, plus a delta column;
    - list the findings closed per phase and the ones deferred, as in this plan.
  - Commit: `docs(audit): compare the final state with the baseline`.

## Final review (2026-11-13)

`/ce-code-review` of `main...audit/deep-review` at `7948aed`: eight reviewers and an independent validator. The
report is in the run folder `/tmp/compound-engineering-1000/ce-code-review/20261113-043354-3c85f76a/report.md`.
Nothing that blocks a merge was introduced by the branch. Andrea chose to fix four findings here, each its own unit.

- [x] **R1: no secret in the environment bwrap starts with.** Pre-existing P1, reproduced at `8d99a5c` and
  `7948aed`. With the key exported in the shell, sandboxed code read it from `/proc/1/environ`: `--clearenv` empties
  only the command's environment, and bwrap is pid 1 inside the sandbox. `Sandbox.run` and `scope_problem` now start
  systemd-run and bwrap with `HOST_VARIABLES` only (`PATH`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`; probed:
  systemd-run needs `PATH` and one of the other two). Test: `test_no_process_in_the_sandbox_holds_the_key`, for both
  key names, red before the change (the canary found once, in pid 1). The audit notes that called the profile clean
  are corrected (20-security.md, SUMMARY.md), and docs/06-SECURITY.md says how the key stays out.
  Not changed, for a later decision: `CommandIndex.load` (tools/craft.py) runs `vectorcraft-cli --version` and
  `commands` on the host with the full environment. That is a trusted host CLI, not a sandbox, but
  `telemetry/fingerprint.py` already strips the environment for the same calls.
- [x] **R2: `agency judge` keeps the project for a path with `..`.** P3, a regression of `01fe687`, which stopped
  resolving the paths so as not to follow a planted link, but left `..` in them. `blind._below` compared
  `path.absolute()` with the projects folder as text, so `../projects/acme/work/a.svg` typed from another folder
  counted as the operator's own file: project `''`, an absolute host path, and links followed. `restore` had the
  same gap, and it was worse: through such a path the projects-folder rule of `_make_parents` was skipped, and the
  version was written through a link a sandbox left below the projects folder. Both now remove `..` as text
  (`os.path.normpath`), never by resolving a link. Tests: `test_a_path_through_dotdot_still_names_its_project`
  (test_judgments.py) and `test_restore_refuses_a_link_inside_the_projects_folder_named_through_dotdot`
  (test_artifacts.py), both red before the change (the second restored into the host folder, exit 0).
- [ ] **R3: the tests ignore the operator's `AGENCY_*` variables.** Testing gap: `AGENCY_EXPLORERS=2` failed four tests.
- [ ] **R4: the chain binds each ticket's project.** P2: `UPDATE tickets SET project = …` passed `agency verify`.

## Not planned in this refactor

| Finding | Why |
|---|---|
| STR-004 (beyond `tools → agents`), STR-007, STR-013, SIM-012 | Deferred to M1.7 (Q18, Q19): the `qa ↔ tools` cycle, the CLI renderer move, the large test files and the `surface.py`/`workflow.build` split. |
| SIM-004 (the `langchain_core` import) | It moves to the process layer in M1.7 (Q7). It is declared in 6.3. |
| CMT-014 (a docstring campaign), CMT-015 (outside 3.20) | Closed by decision (Q14): no campaign and no ruff `D1`. Ports, contracts and platform modules get docstrings in their Phase 3 tasks. |
| CMT-017 | Closed by decision: the fixture names stay (Q14). |
| STR-010 | Closed by decision: the route name stays and the guard holds (STR-010's fix). |
| STR-017 (empty package, ADR file name, `prompts/roles/`) | Closed by decision: they change Fingerprint keys or frozen files. `context/` goes when M3 decides. |
| SIM-014 | Its own fix: drop the column in the next migration that is needed for its own sake, after this plan. |
| DX-009 (the CI stage) | Q11: CI waits until a Git remote exists, before M6 at the latest. Then `check:clean` from 5.11 becomes the `pre-push` hook, and CI runs `task check` on a clean checkout. |

## Coverage check: finding → task

- COR:
  - 001→2.4, 002→2.11, 003→2.20, 004→2.10, 005→2.12, 006→2.9, 007→2.8, 008→2.13;
  - 009→2.21, 010→2.22, 011→2.23, 012→2.8, 013→2.24, 014→2.25, 015→2.5, 016→2.26.
- SEC: 001→2.1–2.3, 002→2.5, 003→2.2 and 2.6, 004→2.7, 005→2.18 and 2.19, 006→2.27, 007→2.28, 008→2.29 and 5.10,
  009→2.30.
- TST:
  - 001→1.1, 002→1.3, 003→1.1, 004→1.4, 005→1.6, 006→1.11, 007→1.7, 008→1.4, 009→1.8 and 2.33;
  - 010→1.8, 011→1.2, 012→1.9, 013→1.5, 014→1.5, 015→1.7, 016→1.10, 017→1.12 and 5.2, 018→5.3.
- CMT:
  - 001→3.1 and 3.2, 002→3.20, 003→3.20, 004→3.15, 005→3.11, 006→3.12, 007→2.31 and 3.12, 008→1.17 and 3.3;
  - 009→3.4–3.16, 010→3.17–3.19, 011→3.9, 3.10, 3.12 and 3.17–3.19, 012→3.20, 013→3.21;
  - 014→by decision and 3.5, 3.6, 3.9, 3.12, 3.15; 015→3.20, 016→3.22, 017→by decision, 018→3.6, 019→3.11.
- STR:
  - 001→2.15–2.17, 002→1.19, 003→4.4, 004→4.2 (the rest in M1.7), 005→2.34, 2.35, 4.2 and 6.9, 006→6.11,
    007→M1.7, 008→2.15;
  - 009→4.1, 010→by decision, 011→3.22, 5.9 and 6.13, 012→5.10, 013→M1.7, 014→1.18, 015→4.5, 016→4.3, 017→5.12 and
    by decision.
- DX: 001→5.2, 002→5.12, 003→2.14 and 2.15, 004→5.4, 005→5.1, 006→5.5, 007→5.10, 008→5.6, 009→5.11, 010→5.8,
  011→5.9, 012→5.7, 013→5.12.
- SIM:
  - 001→2.32 and 6.6, 002→6.1, 003→6.2, 004→6.3, 005→4.2 and 6.4, 006→2.33 and 4.3, 007→6.5, 008→2.34;
  - 009→6.7, 010→6.8, 011→6.10, 012→M1.7, 013→6.11, 014→by decision, 015→6.14, 016→6.15, 017→6.12.
