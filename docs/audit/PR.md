# PR: audit/deep-review → main

## Title

```
fix: close the deep-review audit (sandbox perimeter, hash chain, budget, tests and DX)
```

## Summary

A deep review of the harness at `8d99a5c`, then a sanity refactor in six phases and a final review in four rounds.
The audit reported 109 findings in seven areas; a separate reviewer re-checked every Critical, High and Medium one.
On this branch 101 are Fixed, 5 are Deferred with a destination and 3 are Rejected by decision. Phase 2 found 66 more
defects while fixing (2.F1–2.F66) and the final review 11 more units (R1–R11), all fixed here.

- **Security:** the harness no longer follows links, FIFOs or oversized files the sandbox leaves in the work folder.
  It reads and writes there only through the no-follow helpers of `agency.contracts.files`. Harness inputs and resume
  records left `/job` (ADR-0044). The sandbox runs in a systemd scope with memory and task limits (ADR-0046), and no
  process in it can read the API key any more (R1).
- **Integrity:** the registry's hash chain now binds verdicts, delivered hashes, contracts, concepts, gates, evidence,
  costs, budgets and each ticket's project (ADR-0047, 0049, 0050, 0053), and `agency verify` compares every event's
  project (ADR-0054). Four migrations, 0006–0009.
- **Money:** parallel calls reserve their estimate before any records usage. A fallback or a retry is charged and
  authorized per attempt. One process at a time works on a project.
- **Tests:** 496 → 1218 Python tests, 22 → 24 Playwright tests. Live runs are recorded and replayed (ADR-0048). The
  request and CLI-help snapshots pin what the model and the operator see.
- **DX:** a stale `uv.lock` fails instead of being rewritten, Python is pinned to 3.13.15, a pre-commit hook and a
  clean-checkout gate exist (`task check:clean`, ADR-0051), and the lock holds 57 fewer packages (unused extras
  and the OTLP exporter).
- **Language:** code comments, docstrings and developer messages are in English. Everything the operator or the
  model reads stays in Italian, byte for byte where it was not an approved fix (`99-result.md` §4).

Verification at the final commit `df47e90`, in a fresh clone: all 25 commands of the baseline exit 0, with 0 warnings
from every tool; `make check` 111.7 s; `task check:clean` passes on a copy of git's index. Details in
[`99-result.md`](99-result.md).

## Fixes by severity

Commits per finding are in [`SUMMARY.md`](SUMMARY.md), "Final status".

**Critical (1)**
- SEC-001: `compute` wrote through a `.ops` link planted by the sandbox, so Alembic ran the model's code on the host.
  Inputs moved out of `/job` and every work-folder access goes through no-follow helpers (`480f688`, `74c2a96`,
  `5413af5`, `fe50543`; the same class in `8b558fc`, `642ee28`, `3976aa8`, `9fb7bf1`).

**High (5)**
- COR-001: `observe` and `judge` accepted a render made for an older version of the file (`affdad2`).
- TST-001, TST-002, TST-003: no test saw a QA check, acceptance or a stale-proof refusal stop a delivery (`d76b4f5`).
- TST-005: no test checked that `--budget`, `--model` and `agency budget` reach the ledger (`b9e3617`).

**Medium (17)**
- Budget and billing: COR-002 parallel calls overspent the cap (`75ddfb1`); COR-008 a declined fallback attempt was
  not charged (`bb68b65`).
- Runtime: COR-004 a non-UTF-8 brief left an unusable project (`e8fe18c`); COR-005 no per-project lock (`17ee240`);
  COR-006 a torn transcript line took down report and dashboard (`da8556e`); COR-007 proofs of same-stem sources
  collided (`af41782`).
- Sandbox: SEC-002 Pillow could start Ghostscript on sandbox files (`17cdbdc`); SEC-003 the presentation picked up
  hidden linked host images (`74c2a96`, `b50c32f`); SEC-004 `reviews/../brief.md` passed the reviewer rule
  (`74c2a96`, pinned in `0631cb9`); SEC-005 no memory, file-size, process or tmpfs limits (`449690c`, `55a2f49`,
  `b26910f`).
- Configuration: STR-001 three sources for the data root (`0b2f5dd`, `004e066`, `b453b9e`, `01329dc`); DX-003
  read-only commands created an empty registry that `verify` called intact (`0898e4d`, `0b2f5dd`).
- Tests: TST-004, TST-008, TST-011 (`d76b4f5`), TST-007 (`3dcf60f`), TST-012 (`21e057d`).

**Low (72) and Nit (14):** 78 Fixed, 5 Deferred, 3 Rejected; one row each in `SUMMARY.md`.

**Found while fixing:** 66 defects of Phase 2 (`PLAN.md`, "Found during Phase 2"), most of them more ways for the
sandbox's files to reach the host.

**Final review (four rounds of `/ce-code-review`, Codex as cross-model reviewer in rounds 3 and 4):**

| Unit | Severity | Fix | Commit |
|---|---|---|---|
| R1 | P1, pre-existing | the API key was readable in the sandbox at `/proc/1/environ`; bwrap now starts with three host variables | `1959bd1` |
| R2 | P3 | `agency judge` lost the project for a path with `..` | `0ea7aa0` |
| R3 | testing gap | the tests read the operator's `AGENCY_*` variables and key | `5739f5d` |
| R4 | P2 | the chain binds each ticket's project (ADR-0053, migration 0009) | `fb3952b` |
| R5 | P3 ×3 | one path rule for judge and restore, undoing R2's side effects | `ac5afe1` |
| R6 | P3 | the env isolation also catches lower-case key names | `3290bf9` |
| R7 | P2 | `agency verify` compares the project of every event (ADR-0054) | `59649c7` |
| R8 | P3, pre-existing | the Craft spike started bwrap with the whole shell environment | `cff7084` |
| R9 | P2 | judge and restore walk a typed path as the kernel does (`land`) | `6f78d2b` |
| R10 | testing gap | the spike's key probe has a positive control | `3e1feff` |
| R11 | P3 ×2 | `land` stops at a file; restore refuses a dangling link again | `df47e90` |

## Audit files

- [`00-baseline.md`](00-baseline.md): the starting point, every command with its numbers.
- Area reports: [`10-correctness.md`](10-correctness.md), [`20-security.md`](20-security.md),
  [`30-tests.md`](30-tests.md), [`40-comments-language.md`](40-comments-language.md),
  [`50-structure.md`](50-structure.md), [`60-dx.md`](60-dx.md), [`70-simplification.md`](70-simplification.md).
- [`SUMMARY.md`](SUMMARY.md): the reviewed findings, the owner's answers, and the final status of all 109.
- [`PLAN.md`](PLAN.md): every unit with its verification, the Phase 2 discoveries and the four review rounds.
- [`90-after.md`](90-after.md): the measurement before the final review (`08f125c`), superseded by
  [`99-result.md`](99-result.md): the before/after at `df47e90`.
- New ADRs: [0044](../adr/0044-i-file-dell-harness-fuori-dalla-sandbox.md) to
  [0054](../adr/0054-agency-verify-confronta-il-progetto-di-ogni-evento.md).
- Rules for future sessions, linked from `CLAUDE.md`: [`docs/solutions/`](../solutions/) (links left by the sandbox,
  the key reaching the sandbox through the environment, binding a field into the chain).
- Review reports of rounds 3 and 4: `/tmp/compound-engineering-1000/ce-code-review/20261113-160140-09c52ed9/` and
  `…/20261113-164340-2366b381/` (local, not versioned; `PLAN.md` records all four rounds).

## Look at these closely

1. **`src/agency/contracts/files.py`.** The whole security perimeter: `open_under` and the `*_under` helpers open
   each component with `O_NOFOLLOW` from the parent's descriptor, and `land` walks an operator-typed path as the
   kernel would. Any reader of the work folder that bypasses them reopens SEC-001. `tests/test_safe_files.py` holds a
   parametrized table of every harness reader against a planted link and a FIFO. R2, R5 and R9 each changed a path
   case nobody asked to change, so `land` deserves a slow read: links outside `projects/`, `..` before and after a
   link, a file mid-path, a dangling link.
2. **`src/agency/tools/sandbox.py`.** The bwrap argv, the systemd scope (memory, tasks, `/dev/shm`), the read-only
   `/ops` mount and `host_environment()`. The first run checks that a capped scope can start; without it the sandbox
   does not start and the run stops with its work saved (`SandboxUnavailable`, 2.19 and 2.F43).
3. **Migrations 0006–0009 and `src/agency/ledger/chain.py`, `store.py`.** They append baseline events to the real
   registry, and an applied migration is never edited (ADR-0025). Each migration carries its own copy of the formula;
   its test compares the payloads with today's `chain.canonical(...)`. `replay_mismatches` is what `agency verify`
   prints.
4. **`src/agency/gateway/` (`client.py`, `recording.py`).** Money: the reservation of each call's estimate, per-attempt
   charging on fallback and retry, and the cassettes that replay live runs in tests without calling the API.
5. **`src/agency/config.py`, `src/agency/runtime.py`, `src/agency/contracts/project.py`.** Approved behaviour
   changes an operator will notice: `.env` must hold only the key (a setting there is refused, ADR-0045), the data
   root must be absolute, project names follow the DNS-label rule, and a second process on the same project is
   refused.
6. **`tests/conftest.py` and `tests/support/`.** Autouse fixtures keep `.env`, the operator's `AGENCY_*` variables
   and the key out of every test. The request snapshots in `tests/snapshots/requests/` are unchanged since the
   baseline: a diff there means the model sees something different.
7. **`uv.lock`, `pyproject.toml`, `Taskfile.yml`, `.githooks/pre-commit`.** Extras and the OTLP exporter removed,
   imported packages declared (ADR-0052), a fifth import-linter contract (only the gateway imports `anthropic`), and
   the new gates.

## Notes for Andrea

- **Before using the real registry:** it is at revision 0005. Run `uv run agency migrate`, which saves a copy of the
  registry first and prints where; a scratch copy reached 0009 and `agency verify` exited 0 on it. Until then the
  engine refuses it, and the dashboard says «esegui agency migrate».
- **Open decisions** (`99-result.md` §5): `agency budget` re-binding a hand-edited project row; resuming a ticket
  moved to another client; project folders that are links out of `projects/`; `CommandIndex.load` running
  `vectorcraft-cli` with the full environment; the contract and opening hashes re-bound by the next event
  (ADR-0054).
- **Deferred to M1.7:** STR-004, STR-007, STR-013, SIM-012 and the import remainders of STR-003 and SIM-004. CI
  waits for a Git remote (ADR-0051).
- **Commit history:** one subject has a typo (`builld(deps)` in `ab7d394`); fixing it would rewrite history, so it
  stays.
- **`main` moved by one commit:** `4183817` adds `/.worktrees/` to `.gitignore`. The branch rewrote comments next to
  that line; a three-way `git merge-file` of the three versions on scratch copies merges cleanly.
- **No push, no PR:** this file is the description to paste. The branch has 159 commits on top of `8d99a5c`, plus
  the final documentation commit.
