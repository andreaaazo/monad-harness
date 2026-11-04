The 496 tests are well formed and stable: every one asserts something, reversed file or test order changes nothing, and the concurrency tests passed 12 of 12 repeats under load.
Of 99 one-line mutants of `src/`, 50 were killed: ledger, chain, migrations, gateway ceiling, perimeter, gates and read-only server are well guarded. Of the 49 survivors, 42 show real gaps, mostly in QA evidence, delivery, acceptance and the CLI budget hand-off.
None of the 23 commits is a fix commit. The one bug fix inside a feature commit (678f94c, read-only registry) shipped with its regression test. The ADR-0018 fix is only half covered (TST-004).
Critical 0 · High 5 · Medium 7 · Low 6 · Nit 0
After review (SUMMARY.md): Critical 0 · High 4 · Medium 5 · Low 9 · Nit 0

Each mutant below is one edit to `src/` at `HEAD` (86f51a1), run against the whole suite in an export of the
repository. "Survived" means the result was identical to the unmutated export: 492 passed, 2 skipped, 2 deselected.
The recipe, the list of mutants and what they show are at the end of this file. Playwright was not run (shared
ports); e2e facts come from `docs/audit/00-baseline.md`.

### TST-001 · High · Confirmed
- Where: src/agency/qa/checks.py:36, src/agency/qa/delivery.py:167; closest tests tests/test_agent_flow.py:85,
  tests/test_agent_flow.py:472, tests/test_hardening.py:406
- Problem: no test sees a QA check fail and stop the work. `svg_audit` and `svg_parity` could report PASS for every
  file, or a FAIL proof could be ignored at delivery and acceptance, and the suite would stay green. Every delivered
  SVG goes through `svg_audit`, so either regression would ship defective files to the client unnoticed.
- Evidence: mutant E12 (`checks.py:36`, `"FAIL" if code else "PASS"` → `"PASS"`) and mutant E13 (`delivery.py:167`,
  the `row.result not in evidence.accepted(check)` branch → `elif False:`) both survived. The only FAIL from a real
  check anywhere in `tests/` is the crashed `optical_check` in `tests/test_hardening.py:406`, which calls `execute`
  directly. No test records a FAIL and then tries to deliver. The real check does fail when it should: through the
  project's `Sandbox`, `checks.execute(box, "svg_audit", name)` returns `PASS` for a one-path SVG and `FAIL` for a
  file containing `<svg` ("unclosed token") and for one with live text and an `<image>`.
- Reproduce: apply E12 or E13 with the recipe at the end. The check itself: `/tmp/audit-tst/scripts/svg_fail.py`, run
  from the worktree with `mise exec -- uv run python /tmp/audit-tst/scripts/svg_fail.py` (writes only under `/tmp`).
- Fix: a tool-level test where `run_check svg_audit` on a broken SVG returns FAIL and `deliver` is then refused with
  "'svg_audit' è FAIL"; a unit test of `evidence_problems` on a FAIL row. Fix risk: Low.
- Review (SUMMARY.md): Confirmed, High. Mutants E12 and E13 survived; delivery and the client gate share `evidence_problems`, so no second check catches it. Effort: S.

### TST-002 · High · Confirmed
- Where: src/agency/graph/workflow.py:398, src/agency/qa/delivery.py:232-242, src/agency/qa/delivery.py:158,
  src/agency/qa/delivery.py:163, src/agency/tools/surface.py:520-526; closest tests tests/test_agent_flow.py:472,
  tests/test_hardening.py:619, tests/test_hardening.py:636
- Problem: acceptance never refuses in any test. Acceptance is where the studio adds the independent checks and the
  "unchanged since delivery" check (`01-ARCHITECTURE.md`: "`accept` aggiunge i controlli indipendenti"). Every test
  that reaches acceptance expects it to pass, so the whole check can be deleted at the client gate and in
  `accept_ticket` with the suite green. In the logo flow the client gate is the only place where `critique` is
  required on the final files.
- Evidence: `delivery_problems` passes `include_independent=False` (`delivery.py:227`), so the root ticket is delivered
  with no critique at all. A script on the unmutated code shows it: delivery problems `[]`, then acceptance problems
  `["exports/segno.svg: manca la prova 'critique'"]`. Seven mutants survived: W2 `workflow.py:398` → `problems = []`;
  T9 `surface.py:523` → `if False:`; D1 `delivery.py:241` `True` → `False`; D9 `delivery.py:241` deleted; E14
  `delivery.py:158` ignores `include_independent`; E6 `delivery.py:163` (independent check signed by the assignee) →
  `elif False:`; E7 `delivery.py:239` ("modificato dopo la consegna") → `if False`. None of "Accettazione rifiutata
  dal sistema", "accettazione rifiutata", "modificato dopo la consegna" or "firmata dall'autore" occurs in `tests/`.
- Reproduce: apply any of the seven with the recipe at the end. The behaviour on unmutated code:
  `mise exec -- uv run python /tmp/audit-tst/scripts/root_without_critique.py` from the worktree.
- Fix: a flow test where the director delivers the root without a critique, the client approves, and the root goes
  back to REWORK with "Accettazione rifiutata dal sistema". Unit tests of `accept_ticket` for a missing independent
  check, an independent check signed by the assignee, and a file changed after delivery. Fix risk: Low.
- Review (SUMMARY.md): Confirmed, High. Six acceptance mutants survived (W2, T9, D1, E6, E7, E14); the client gate is the last system check. Effort: S.

### TST-003 · High · Confirmed
- Where: src/agency/qa/evidence.py:124-134, src/agency/qa/delivery.py:165-166, src/agency/qa/delivery.py:216-224,
  src/agency/qa/delivery.py:183-184, src/agency/qa/delivery.py:199, src/agency/tools/master.py:98-113; closest tests
  tests/test_agent_flow.py:85, tests/test_agent_flow.py:610
- Problem: delivery checks that each proof belongs to the current version of its file, that the ticket's inputs did
  not change after opening, that a production ticket has its master, and that each export comes from the current
  master. None of these refusals is tested. The common path breaks first: an author runs the checks, makes one last
  `craft_run` and export, and delivers without running them again. Today that is refused as STALE; without the hash
  comparison it is accepted on proofs of the old version.
- Evidence: five mutants survived. E5 `evidence.py:128` (`sha256(target) != row.sha256`) → `if False:`; E4
  `evidence.py:132` (hashes of a judgment's comparison files) → `if False:`; E8 `delivery.py:223` (stale ticket inputs)
  → `if False:`; E18 `delivery.py:183` ("manca il master") → `if False:`; E9 `delivery.py:199` → `why = None` (no
  derivation check). No test mentions `STALE`, "è cambiato", "input superato", "manca il master", "non risulta
  esportato" or "riesporta". `test_author_cannot_deliver_without_master_then_can` asserts only "consegna rifiutata",
  which the missing outputs and proofs already cause. Nothing else covers these checks: `derivation_problem` links an
  export to a master, not a proof to a file, and "modificato dopo la consegna" runs only after delivery. Without E18 and
  E9, an SVG written by `compute`, which can write any file under `/job`, is accepted as a delivery with no master.
- Reproduce: apply E5, E4, E8, E18 or E9 with the recipe at the end.
- Fix: unit tests of `delivery_problems`: a proof on an older hash gives "è STALE"; a changed comparison file makes a
  `judge` proof stale; a changed input gives "input superato"; a vector production ticket without a `.vectorcraft`
  gives "manca il master"; an SVG with no derivation row gives "non risulta esportato da un master del ticket"; a
  master changed after export gives "riesporta". Fix risk: Low.
- Review (SUMMARY.md): Confirmed, High. Five mutants survived (E4, E5, E8, E9, E18); nothing else compares proofs with the current file. Effort: S.

### TST-004 · High · Confirmed
- Where: src/agency/qa/evidence.py:104-121, src/agency/qa/delivery.py:151; closest test tests/test_hardening.py:636
- Problem: ADR-0018 says "Un revisore risponde delle sue prove: quelle di un altro non lo sostituiscono e non lo
  annullano. Sulla consegna al cliente restano valide tutte le firme, e un FAIL di chiunque continua a fermarla." The
  regression test covers only "non lo annullano". The other two rules can be removed with the suite green: a reviewer
  can deliver READY on the author's own `run_check`, and a later PASS by another signer hides a FAIL on the same
  version, for example the director overriding the critic's `critique` FAIL.
- Evidence: mutant D2 `evidence.py:108` (`if signer and row.signer != signer:`) → `if False:` survived: a review's
  table then holds every signer, so a QA ticket that checks `svg_audit` is satisfied by the author's PASS. Mutant E3
  `evidence.py:120` → `table[key] = ordered[-1]` survived: after the critic's FAIL and another signer's PASS on the
  same hash, the last row wins. `test_a_reviewer_who_repeats_a_check_does_not_unsign_the_other` records only PASS
  results.
- Reproduce: apply D2 or E3 with the recipe at the end.
- Fix: next to `tests/test_hardening.py:636`, test that (a) a reviewer with no proof of their own is refused "manca
  la prova" even when the author has a PASS, and (b) a critic's FAIL still blocks after another signer's PASS on the
  same version, and clears when the critic signs PASS or the file changes. Fix risk: Low.
- Review (SUMMARY.md): Downgraded to Medium. D2 and E3 survived, but the client gate's assignee-signature check (src/agency/qa/delivery.py:163) still stops the director overriding the critic. Effort: S.

### TST-005 · High · Confirmed
- Where: src/agency/cli.py:143-151, src/agency/cli.py:189, src/agency/runtime.py:79; closest tests
  tests/test_hardening.py:462-509, tests/test_sketch_flow.py:604
- Problem: ADR-0043 makes the cap declared at `agency run` the only limit on spend, and `agency budget` the way to
  raise it. No test checks that either value reaches the ledger. The CLI tests stop before a session starts (a fake
  session, argparse errors, an unknown project), and the flow tests call `Session.start` and `Ledger.set_budget`
  directly. So `agency run` could ignore `--budget` (and `--model`), and `agency budget` could print "budget portato
  a …" without changing anything, and the suite would stay green. The first runs a client's project under a cap they
  never chose.
- Evidence: mutants B2 (`cli.py:148` `budget=args.budget` → `budget=1000.0`), B3 (`cli.py:149`, `--model` ignored)
  and B1 (`cli.py:189` `ledger.set_budget(...)` deleted) survived. The parsing is tested (`_dollars`, mutant B5
  killed); only the hand-off is not.
- Reproduce: apply B2, B3 or B1 with the recipe at the end.
- Fix: run `cli.main(["run", "p", "brief.md", "--budget", "12", "--model", ...])` with `agency.runtime.open_session`
  monkeypatched to the real function plus a `ScriptedTransport`, and assert the `projects` row (12 $, the model);
  then `cli.main(["budget", "p", "40"])` and assert 40 $. Fix risk: Low.
- Review (SUMMARY.md): Confirmed, High. B2 survived: `--budget` could be ignored, and the report shows the cap only after the spend. Effort: S.

### TST-006 · Medium · Confirmed
- Where: tests/test_agent_flow.py:441-456 (src/agency/tools/sandbox.py:35, src/agency/tools/sandbox.py:52),
  web/e2e/run.spec.ts:173-184
- Problem: two of the sandbox's isolation assertions pass for reasons unrelated to the sandbox. "No network" is proved
  by failing to reach `1.1.1.1:53`, which also fails when the test host is offline or the port is filtered. "`/usr` is
  read-only" is proved by `touch /usr/x` failing, which a non-root user gets from Unix permissions anyway. So a sandbox
  with network access, which could send client material out, passes the suite on such a host. The e2e loopback test
  has the same weakness: it skips when the host has no non-loopback IPv4 address, and the run stays green (baseline
  §4, F1: skipped in 1 of 8 runs).
- Evidence: in the audit environment, where the host itself gets "Network is unreachable" for 1.1.1.1:53, mutant X2
  (`--unshare-net` removed) survived, and so did X3 (`--ro-bind /usr` → `--bind /usr`). Run through the project's
  `Sandbox`, the probe prints `no-rete` with and without `--unshare-net`, but `socket.if_nameindex()` gives `['lo']`
  against `['docker0', 'lo', 'wlp99s0']`. Likewise `touch /usr/x` exits 1 with and without the read-only bind, while
  `os.statvfs("/usr").f_flag & os.ST_RDONLY` is true only with it.
- Reproduce: from the worktree, `mise exec -- uv run python /tmp/audit-tst/scripts/sandbox_net.py` and
  `.../sandbox_usr.py` (both write only under `/tmp`); X2 and X3 with the recipe at the end. For F1, see baseline §4.
- Fix: inside the sandbox, assert that `lo` is the only interface and that `/usr` is mounted read-only (the two probes
  above). In e2e, read the listening addresses of the three servers from `/proc/net/tcp` instead of probing external
  interfaces, so the test never needs to skip. Fix risk: Low.
- Review (SUMMARY.md): Downgraded to Low. X2 (`--unshare-net` removed) is killed on an online host, the normal state; the `/usr` regression has no effect for a non-root operator. Effort: S.
- Related: DX-007 (the same probe pattern in the spike).

### TST-007 · Medium · Confirmed
- Where: src/agency/tools/surface.py:944-945; closest tests tests/test_agent_flow.py:208, tests/test_agent_flow.py:259
- Problem: a tool with an effect records its result under its `operation_id`, so that on resume it is not run again
  (ADR-0002). Only `open_ticket` is tested, and it records itself inside `Ledger.open`. For every other effect tool,
  deleting the recording leaves the suite green. Tool results reach the transcript only after the whole batch
  (`agents/loop.py:180-182`), so a process killed during a batch replays it on resume. Without the record, `run_check`,
  `observe`, `render` and `export_master` add duplicate rows, `compute` runs its code again, and a closing tool such as
  `deliver` hits `IllegalTransition` instead of returning its stored result, so the instance does not close as
  delivered. `craft_run` and `plan_exploration` have their own guards (`tools/craft.py:108-111`, `surface.py:588-592`).
- Evidence: mutant H1 (`surface.py:945` `record_operation(...)` → `pass`) survived. Mutant T7 (restoring a stored
  result) was killed by a test that pre-records the operation; no test checks that the recording happens.
- Reproduce: apply H1 with the recipe at the end.
- Fix: a test like `test_interruption_resumes_without_repeating_effects`, with a `run_check` and a `deliver` in one
  turn and the process killed after the tools ran but before the transcript was written: after resume each tool's
  effect happened once, `ledger.operation(id)` holds its result, and the instance closes as delivered. Fix risk: Low.
- Review (SUMMARY.md): Confirmed, Medium. H1 survived. Effort: S.

### TST-008 · Medium · Confirmed
- Where: src/agency/qa/evidence.py:61-65; closest test tests/test_agent_flow.py:472 (only allowed signers)
- Problem: `guard` refuses an independent check signed by the author of the file, or by a role outside the check's
  `roles`. Both branches can be deleted with the suite green. They are reachable: `copy_review` and `proof_read` have
  kind `reading`, which `record_requirement` accepts (`surface.py:464-467`), and `copywriter` is in their roles, so
  this guard alone stops a copywriter from approving their own copy. TST-002's assignee check does not help at the
  root, whose assignee is the director. `qa-inspector` has `judge` but is not in the roles of `critique`.
- Evidence: mutants E1 (`evidence.py:62`) and E2 (`evidence.py:64`), each `→ if False:`, both survived. Medium, not
  High: the M1 logo flow uses only `critique`, and authors have no `judge`.
- Reproduce: apply E1 or E2 with the recipe at the end.
- Fix: a parametrized test of `evidence.record`: an author signing `copy_review` is refused "è indipendente";
  `qa-inspector` signing `critique` is refused "lo firma"; `critic` signing `critique` is accepted. Fix risk: Low.
- Review (SUMMARY.md): Confirmed, Medium. E1 and E2 survived; the client-gate assignee check covers neither signer. Effort: S.

### TST-009 · Medium · Confirmed
- Where: src/agency/gateway/transport.py:36-37, src/agency/gateway/transport.py:44, src/agency/gateway/transport.py:74,
  src/agency/gateway/transport.py:79; closest test tests/test_gateway.py:157
- Problem: the only `AnthropicTransport` test streams a hand-written three-key request. `count_tokens`, the gateway's
  real parameters and `fallbacks` never pass through the SDK in a test. If `count_tokens` forwarded every parameter,
  the SDK would raise `TypeError` on `max_tokens` before any request, so every live run would fail at its first call
  with the suite green. `RecordingTransport` and `ScriptedTransport.from_cassette` have no caller in `src/` or
  `tests/`, and the repository holds no recorded API response: every model response in the tests is a hand-written
  dict (`tests/test_agent_flow.py:33`).
- Evidence: mutants P1 (`transport.py:37` → `fields = params`) and P2 (`fallbacks="default"` removed at
  `transport.py:44`) survived. Over `httpx2.MockTransport`, with no network, the code as written sends
  `['messages', 'model', 'system']` to `/v1/messages/count_tokens`, while `client.messages.count_tokens(**params)`
  with the gateway's params raises `TypeError: Messages.count_tokens() got an unexpected keyword argument
  'max_tokens'`. `rg 'RecordingTransport|from_cassette' src tests` finds only the definitions and the re-export.
- Reproduce: `mise exec -- uv run python /tmp/audit-tst/scripts/p1_count_tokens.py` from the worktree.
- Fix: in `tests/test_gateway.py`, run `ModelGateway` over `AnthropicTransport` on `httpx2.MockTransport` and assert
  the bodies of the `count_tokens` and `messages` requests (thinking, `output_config`, `cache_control`, `fallbacks`,
  the beta header). Then either test the cassette round trip or remove it; that choice belongs to SIM. Fix risk: Low.
- Review (SUMMARY.md): Downgraded to Low. P1 and P2 survived, but both regressions fail safe before any spend. Effort: S.
- Duplicate: the unused cassette pair is tracked under SIM-006; the request-shape gap stays here.

### TST-010 · Medium · Confirmed
- Where: src/agency/gateway/client.py:66-79, src/agency/gateway/client.py:121-122; closest test
  tests/test_gateway.py:192
- Problem: from the second call on, the estimate that decides whether a call may go out is context × cache-read price
  plus new tokens (an image counts 2,500) plus 4,000 output tokens. The only test with a previous response,
  `test_project_ceiling_counts_previous_spend`, already exceeds the ceiling on past spend plus output, so the whole
  input part can be zero with no failure. An underestimate lets the last call go past the ceiling the client
  declared; an overestimate stops the work early.
- Evidence: mutants G4 (`client.py:122` → `input_cost = 0.0`), G6 (`client.py:121` → `fresh = 0`) and G2
  (`client.py:76` → `total += 0`) survived. In that test, 0.2004 $ spent plus 0.08 $ of output already exceeds the
  0.25 $ ceiling. For scale: merlo3's peak context of 267,966 tokens (02-ROADMAP) costs 0.054 $ of cache reads per
  call at the Opus 5.5 price, and 1.07 $ if mistakenly priced at the input rate.
- Reproduce: apply G4, G6 or G2 with the recipe at the end.
- Fix: unit tests of `estimate_usd` with a known previous usage and a last message of text, a `tool_result` and an
  image, plus a ceiling test where only the input part crosses the limit. Fix risk: Low.
- Review (SUMMARY.md): Downgraded to Low. G2, G4 and G6 survived, but the missed error is a few cents; the dominant output term is guarded (G0 killed). Effort: S.

### TST-011 · Medium · Confirmed
- Where: src/agency/qa/delivery.py:63, src/agency/qa/delivery.py:81-84, src/agency/qa/delivery.py:226,
  src/agency/qa/delivery.py:155-156, src/agency/qa/delivery.py:167; closest tests tests/test_hardening.py:585,
  tests/test_agent_flow.py:562
- Problem: the rules that make a contract checkable and deliverable are mostly untested. Breaking them opens tickets
  nobody can deliver, the failure that cost 3.10 $ of blocked reviews on merlo3 (ADR-0018), or delivers a file with no
  check. Untested: an unknown check name is refused at opening (a typo like `svg-audit` is realistic for a model); an
  output with no check is refused at opening; a glob output's files must each be covered at delivery; a reviewer may
  deliver NOT_VERIFIED without proofs and REVISE on a FAIL.
- Evidence: mutants D4 (`delivery.py:63` → `why = None`), E10 (`delivery.py:81` → `if False:`), E16 (`delivery.py:226`
  deleted), D3 (`delivery.py:155-156` deleted) and D6 (REVISE exemption at `delivery.py:167` removed) all survived.
  "controllo sconosciuto" does not occur in `tests/`. `tests/test_agent_flow.py:562` delivers REVISE with no proof at
  all, so it never reaches the exemption. With D4, `guard` still refuses every proof for the unknown name
  (`evidence.py:57-59`), so the ticket can never be delivered.
- Reproduce: apply D4, E10, E16, D3 or D6 with the recipe at the end.
- Fix: unit tests of `delivery.validate` (unknown name, uncovered output) and of `delivery_problems` (an uncovered file
  under a glob output; a review delivered NOT_VERIFIED with no proofs; REVISE on a FAIL proof). Fix risk: Low.
- Review (SUMMARY.md): Confirmed, Medium. Five mutants survived (D3, D4, D6, E10, E16). Effort: S.

### TST-012 · Medium · Confirmed
- Where: src/agency/agents/loop.py:135-136; closest tests tests/test_sketch_flow.py:589,
  tests/test_request_snapshots.py:99
- Problem: when the client chooses no model or effort, each role takes them from `registry/roles.json`: three roles on
  Sonnet 5.5 (`qa-inspector`, `researcher`, `legal-reviewer`) and 14 at effort `medium`. No test checks what a role
  sends without a client choice. The request snapshots keep only `system` and `tools`, and the tests that check
  `model` or `effort` set them explicitly or through the explorer and proposal settings. Every role could silently run
  on Opus at high effort, which costs more, or on the wrong model the other way round, which lowers quality.
  CLAUDE.md treats the role-to-model mapping as settled ("Non cambiare modello … senza una decisione esplicita").
- Evidence: mutants A1 (`loop.py:135`, `config["model"]` → `"claude-opus-5-5"`) and A2 (`loop.py:136`,
  `config["effort"]` → `"high"`) survived. `tests/test_registry.py:23` checks only that the registry names known
  models.
- Reproduce: apply A1 or A2 with the recipe at the end.
- Fix: add `model` and `output_config` to the request snapshots at `tests/test_request_snapshots.py:99`, then
  regenerate them with `UPDATE_SNAPSHOTS=1` and review the diff; or assert the first request of `qa-inspector`.
  Fix risk: Low.
- Review (SUMMARY.md): Confirmed, Medium. A1 and A2 survived, and so did A3 (every role silently on Sonnet). Effort: S.

### TST-013 · Low · Confirmed
- Where: src/agency/cli.py:54-58; closest tests tests/test_ledger.py:108, tests/test_artifacts.py:330,
  tests/test_migrations.py:289
- Problem: `agency verify` prints "REGISTRO ALTERATO" for a broken chain, but no test checks that it then exits 1. If
  the exit code stopped reflecting the chain, anything relying on it would miss tampering. The message is still
  printed, hence Low.
- Evidence: mutant L5 (`cli.py:58` → `return 0 if not broken else 1`) survived. `test_chain_detects_tampering_that_bypasses_the_triggers`
  covers `Ledger.verify_chain` only; the CLI tests cover an outdated registry and a damaged artifact (mutant K2,
  killed).
- Reproduce: apply L5 with the recipe at the end.
- Fix: drop `events_no_update`, update an event, assert `cli.main(["verify"]) == 1` and the message. Fix risk: Low.

### TST-014 · Low · Confirmed
- Where: src/agency/ledger/store.py:238-239; closest test tests/test_ledger.py:84
- Problem: REWORK must clear a review's verdict; no test checks it. Without it, a review sent back keeps READY until it
  is delivered again, and the dashboard, which reads `tickets.verdict` (`insights/adapters/registry.py:35`), shows it
  as READY.
- Evidence: mutant L2 (`elif action is Action.REWORK:` → `elif False:`) survived.
- Reproduce: apply L2 with the recipe at the end.
- Fix: extend `test_review_needs_a_verdict_and_keeps_it_apart_from_status` with a rework and
  `status() == (Status.REWORK, None)`. Fix risk: Low.

### TST-015 · Low · Confirmed
- Where: src/agency/graph/workflow.py:305-306; closest test tests/test_sketch_flow.py:660
- Problem: on resume a node runs again from the start (01-ARCHITECTURE, ADR-0002), so `concept_gate` writes its gate
  row only once per PDF version. No test runs the gate twice, so a resume after a crash between `add_gate` and the
  checkpoint could record the client's decision twice, and no test would notice.
- Evidence: mutant W3 (`if json.dumps(digest) not in recorded:` → `if True:`) survived.
- Reproduce: apply W3 with the recipe at the end.
- Fix: a test that resumes the same concept decision twice and asserts a single `gates` row. Fix risk: Low.

### TST-016 · Low · Confirmed
- Where: src/agency/tools/surface.py:669, src/agency/tools/surface.py:444-445, src/agency/tools/surface.py:399;
  closest tests tests/test_sketch_flow.py:803, tests/test_sketch_flow.py:856
- Problem: three refusals in the tool surface have no test: at most three ideas go on to proposals (a proposal cost
  4.22 $ on merlo3), a file cannot be judged against itself, and `export_master` accepts only known options.
- Evidence: mutants T13 (`len(a.chosen) > 3` → `if False:`), T15 (self-comparison refusal → `pass`) and T18
  (`flags - EXPORT_OPTIONS` → `if False:`) survived.
- Reproduce: apply T13, T15 or T18 with the recipe at the end.
- Fix: one `Toolbox.call` test per refusal, asserting `is_error` and the specific message. Fix risk: Low.

### TST-017 · Low · Likely
- Where: tests/test_agent_flow.py:442-454, tests/test_insights.py:564-582
- Problem: two tests skip a precondition check. The sandbox test sets the fake key with `os.environ[...]` and deletes
  it only on the success path, so if `box.run` raises (for example without `bwrap`), the key stays set for every later
  test. The registry-reader test ignores the result of `writing.wait(timeout=10)`: if the writer thread fails to take
  the lock, the read runs with no writer, and the test passes without testing anything.
- Evidence: `tests/test_agent_flow.py:442` assigns and `:454` deletes, with no `try`/`finally` or `monkeypatch`.
  `tests/test_insights.py:578` discards the boolean from `Event.wait`; an exception in the thread only becomes a pytest
  warning.
- Reproduce: not reproduced; it needs `bwrap` to be missing or `BEGIN IMMEDIATE` to fail in the thread.
- Fix: `monkeypatch.setenv` for the key; `assert writing.wait(timeout=10)`. Fix risk: Low.
- Duplicate: the fake key left set after a crash without bwrap is tracked under DX-001; the `Event.wait` half stays here.

### TST-018 · Low · Confirmed
- Where: tests/test_doctor.py:5, src/agency/doctor.py:36-47, tests/test_agent_flow.py:655-658
- Problem: the slowest test (2.25 s) spends its time in `nvidia-smi`, which has nothing to do with what it asserts
  (the key is never printed). `test_cli_lists_new_commands` (1.87 s) runs `uv run agency --help` in a subprocess,
  which needs `uv` on PATH and may sync the environment as a side effect of a test.
- Evidence: `doctor._gpu()` alone took 2.24 s here, and the twelve `shutil.which` calls under 1 ms
  (`mise exec -- uv run python -c ...`); `--durations=25` gave 2.25 s and 1.87 s for the two tests.
- Reproduce: `mise exec -- uv run pytest -p no:cacheprovider --durations=5 tests/test_doctor.py tests/test_agent_flow.py::test_cli_lists_new_commands`.
- Fix: monkeypatch `doctor._gpu` in the doctor test; call `cli.main(["--help"])` under `pytest.raises(SystemExit)` with
  `capsys`. Fix risk: Low.

---

## How the mutants were run

```text
mkdir -p /tmp/audit-tst/copy && git archive HEAD | tar -x -C /tmp/audit-tst/copy
cd /tmp/audit-tst/copy && MISE_TRUSTED_CONFIG_PATHS=$PWD mise exec -- uv sync
mise exec -- uv run python -c "import agency.config as c; print(c.REPO_ROOT)"   # prints the copy's path
# for each mutant: one str.replace in src/, delete every __pycache__, then
PYTHONDONTWRITEBYTECODE=1 MISE_TRUSTED_CONFIG_PATHS=$PWD mise exec -- uv run pytest -p no:cacheprovider -x \
  --deselect tests/test_taskfile.py::test_check_runs_every_control_in_order \
  --deselect tests/test_taskfile.py::test_the_dashboard_starts_api_and_interface_together_and_stops_both_if_one_stops
# restore the file, delete __pycache__ again
```

The unmutated export gave 492 passed, 2 skipped (`tests/test_repository.py` needs `.git`), 2 deselected. The two
deselected tests need `.git` and `web/node_modules`, which an export lacks; both pass in the worktree. Three copies
ran in parallel, each checked green before its first mutant and checked identical to the worktree's `src/` after its
last one. The harness is `/tmp/audit-tst/mut.py`, the mutant definitions are `/tmp/audit-tst/batch{1..4}.py`, and
the logs are next to them.

A kill was counted only when pytest reported a failing test (99 mutants: 50 killed, 49 survived). Survivors were
analysed one by one, and 42 of them are cited in the findings above. Four did not lead to a
finding because another defence still refuses the action: T2, T11 (`Ledger.apply` refuses a non-sender), T20 (the
`is_relative_to` filter) and D5 (`sha256` raises on a missing file). Two have no effect through any tool: E15, since
no tool records a measure as PASS, and L4, since the hash already covers `prev_hash`. G8, which retries a malformed
stream once instead of twice, is a boundary not worth a test.

Killed, so guarded by a test: L1, L3, L6–L10 (ledger permissions, write lock, migration chain check, schema
recognition, idempotent opening, transitions, outdated registry); M1 (migration backup); G1, G3, G5, G7, G9 (ceiling
counts past spend and output, usage cost, prices); W1, W4–W6 (concept choice, client rejection, gate digest); T1,
T3–T8, T10, T12, T14, T16, T17, T19 (first look, ratings, client assets, unseen presentation, identical redelivery,
operation replay, tool sets, org chart, recommendation, observed proof, finisher scope, reviewer writes, perimeter);
X1 (`--clearenv`); R1–R5 (key scrub, Host check, loopback only, `mode=ro`, `query_only`); A3, A4 (refusal and
truncated answers in the loop); P3 (adaptive thinking); D7, D8, E11 (review contract shape); E17 (missing proof);
K1, K2 (artifact keeping, `verify` on damaged artifacts); Q1 (a crashed measure is no proof); J1, J2 (blind
judgments); B4, B5 (`decide` choice, positive budget).

Order and time: all 27 files in reverse order gave 496 passed; 241 tests from eight files, each test in reverse order,
gave 241 passed; six thread-based tests (`test_hardening.py:305`, `:343`, `test_migrations.py:122`,
`test_insights.py:564`, `test_sketch_flow.py:388`, `:486`) passed 12 times out of 12 while three mutant runs loaded the
machine.

Git history: `git log -i --grep=fix` and a search for bug words in subjects and bodies find nothing (every body is
empty). Within the feature commits, the one bug fix is in 678f94c: the read-only registry crashed when the folder could
not be written; it came with `tests/test_insights.py:591`. The behaviour changes of 30d2c7e (no default budget,
ADR-0043) came with `tests/test_gateway.py:201` and `tests/test_hardening.py:473-501`; a7e2a70 (the best must be
coherent) came with `tests/test_judgments.py:45`. The merlo3 fixes recorded in ADR-0014, ADR-0017 and ADR-0018 have
regression tests (killed mutants T1, T4, T5, D7, D8, E11), except the parts in TST-004.
