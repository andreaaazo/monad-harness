CMT, comments and language: every comment and docstring in src/, tests/ and web/ is Italian (236 Python comment lines, 433 docstrings, 128 web comments), while all Python and TypeScript identifiers are English; there are no TODO/FIXME markers, no logging or warnings calls and no i18n resources.
Six comments or docstrings are stale or wrong against the code or the ADRs (CMT-002 to CMT-007), and some docstrings are runtime data: 29 feed schemas/openapi.json, 3 are CLI help, and a class docstring on any of 34 tool-input models or enums would change the tool schemas sent to the model.
Public API documentation is thin (228 of 378 public Python functions and classes, 20 exported TypeScript functions). No finding is above Low, but CMT-001, CMT-002 and CMT-008 are traps the translation unit must respect.
Critical 0 · High 0 · Medium 0 · Low 14 · Nit 5

## Findings

### CMT-001 · Low · Confirmed
- Where: src/agency/insights/views.py:31,48,56,87,110; src/agency/insights/flow.py:33,42,60,76,90; src/agency/insights/behaviour.py:29,37,56; src/agency/insights/quality.py:32,60; src/agency/insights/compare.py:33,42,56,84,100; src/agency/insights/replay.py:30,38,61; src/agency/insights/domain.py:135,198,395,405; src/agency/entrypoints/server/api.py:28,30,134,164,179; src/agency/cli.py:1; src/agency/entrypoints/server/serve.py:1; src/agency/entrypoints/server/schema.py:1; src/agency/tools/surface.py:94-259 (30 tool-input models); src/agency/contracts/concept.py:8; src/agency/contracts/ticket.py:11,33,39
- Problem: These docstrings are not comments but data that leaves the process. Translating the 29 OpenAPI ones rewrites schemas/openapi.json and web/src/api/schema.ts, and translating the 3 module docstrings changes the `--help` of `agency`, `agency-server` and `agency-schemas`. Adding a class docstring to a tool-input model, to `ConceptCard` or to `TicketType`/`Medium`/`Verdict`, which is the natural fix for CMT-014, adds a `description` to the tool schema the model receives. That changes tests/snapshots/requests/ and the cached request prefix.
- Evidence: every `components.schemas.*.description` in schemas/openapi.json is one of the 27 class docstrings above (for example `PhaseView` is views.py:31), and the two operation descriptions are the docstrings at api.py:134 and :179. `info.description` and `info.title` come from api.py:28-30, and the image response description comes from api.py:164. `ArgumentParser(..., description=__doc__)` is at cli.py:297, serve.py:58 and schema.py:30. `definition()` (surface.py:884-892) ships `tool.schema.model_json_schema()`, which includes a class docstring. Today none of the 30 `Strict` subclasses, `ConceptCard` or the three enums has one, so the snapshots carry none. A docstring on the `Strict` base class itself does not reach the subclass schemas (probe 2 below). Every edit under src/agency also changes `Fingerprint.code` (src/agency/telemetry/fingerprint.py:72), so the next run's fingerprint lists every file the translation touched.
- Reproduce: run the two probes below from the repo root with `PYTHONDONTWRITEBYTECODE=1 mise exec -- uv run python <file>`. Nothing in the repository is modified. Then `rg -n 'description=__doc__' src/agency`.

```text
probe 1: from agency.tools import surface
         class Doc(surface.ReadFile): "Read a project text file."
         surface.definition(surface.Tool("read_file", "x", Doc, surface.read_file))["input_schema"]
         -> keys gain "description": "Read a project text file."  (the real ReadFile schema has none)
         a StrEnum with a docstring used in a Strict model -> its $defs entry gains "description"
probe 2: class Base(BaseModel): "Base docstring."  /  class Child(Base): path: str
         "description" in Child.model_json_schema()  -> False
```

- Fix: Translate the 29 OpenAPI docstrings in their own schema-change unit, which runs `task schemas` and `pnpm --dir web run api:check` and reviews the diff of both generated files. Treat the 3 module docstrings as CLI help, which is the owner's call. Document the tool-input models, `ConceptCard` and the three enums with `#` comments, never with class docstrings. Fix risk: Med.

### CMT-002 · Low · Confirmed
- Where: web/scripts/check-defenses.mjs:17 (the checks at :61, :62, :66-69, :71)
- Problem: The JSDoc of `code()` says a rule is checked on what runs, not on what describes it. Only two checks use `code()` (:74 and :92); the per-source loop tests the raw file text, comments included. So an English comment in web/src that mentions `fetch(`, `"use server"` or `generateStaticParams` fails `pnpm run defenses`, and a block-commented `export const dynamic = "force-dynamic";` satisfies the page check.
- Evidence: :59 reads `const text = readFileSync(path, "utf8")`, then :61 runs `!/\bfetch\(/.test(text)`, :62 the `use server` test, :67 the `force-dynamic` regex and :71 the `generateStaticParams` test, all on `text`. `code()` is applied only to client.ts (:74) and proxy.ts (:92).
- Reproduce: the script's own regexes, from the repo root.

```text
mise exec -- node -e '
const code = (t) => t.replace(/\/\*[\s\S]*?\*\/|(^|\s)\/\/.*$/gm, "$1");
const c = "/** Never call fetch() from a component. */\n";
console.log(/\bfetch\(/.test(c), /\bfetch\(/.test(code(c)));
const p = "/*\nexport const dynamic = \"force-dynamic\";\n*/\n";
const r = /^export const dynamic = "force-dynamic";$/m;
console.log(r.test(p), r.test(code(p)));'
-> true false
-> true false
```

- Fix: In the translation unit, keep those three tokens out of new web/src comments. Separately, in a bug-fix unit outside CMT, run the loop's checks on `code(text)`, or reword the JSDoc to say which checks ignore comments. Fix risk: Low.

### CMT-003 · Low · Confirmed
- Where: web/next.config.mjs:3
- Problem: "Ogni difesa qui sotto ha un controllo in scripts/check-defenses.mjs" is false for half of the file. `rewrites()` (:18-20) and the four security headers (:21-33) have no check there. A reader who trusts the comment thinks `pnpm run defenses` guards the headers.
- Evidence: check-defenses.mjs:28-30 checks only `images.unoptimized`, `output` and `poweredByHeader`. Playwright asserts Cache-Control, X-Frame-Options and X-Content-Type-Options (web/e2e/run.spec.ts:109-117). `Referrer-Policy` (next.config.mjs:29) is checked nowhere.
- Reproduce: `rg -n "headers|rewrites|Referrer|nosniff" web/scripts/check-defenses.mjs` prints nothing; `rg -n "Referrer" web tests -g '!node_modules'` prints only web/next.config.mjs:29.
- Fix: When translating, say where each defense is checked (check-defenses.mjs or e2e/run.spec.ts), and that Referrer-Policy has no check. Adding that check is a separate test unit. Fix risk: Low.

### CMT-004 · Low · Confirmed
- Where: src/agency/tools/board.py:23 (also :103, and the model-facing text at :113-114)
- Problem: `MAIN_SHARE = 0.75  # il segno principale occupa almeno questa parte del file` names the wrong quantity. The share is measured against the longer side of the inked area, not the file, and the docstring "La tavola rimpicciolisce tutto il file" says the same loosely, because the board crops to the ink before it scales. A developer tuning `MAIN_SHARE` from the comment would reason about the canvas.
- Evidence: `_groups` crops the mask to its bounding box and sets `scale = GRID / max(crop.size)` (:67-71). `mark_problem` compares `max(sides) / GRID` (:110). `build` pastes `_ink(image)`, which returns `clean.crop(box)` (:53-62, :130).
- Reproduce: a 1000×400 white PNG with two black 100 px squares 50 px apart in the middle, passed to `agency.tools.board.mark_problem` with `mise exec -- uv run python`. It answers "il maggiore occupa solo il 42% della larghezza", while each mark is 10% of the file's width.
- Fix: Reword the comment and the docstring as "share of the longer side of the inked area". The warning text at :113-114 ("della larghezza") is model-facing: leave it and flag it to the owner. Fix risk: Low.

### CMT-005 · Low · Confirmed
- Where: src/agency/insights/__init__.py:1-10; src/agency/insights/adapters/__init__.py:1; src/agency/insights/application.py:1; src/agency/entrypoints/server/api.py:30; tests/test_insights.py:1
- Problem: These describe insights as a slice that reads "registro e tracce", with one use case (`rebuild`) and adapters for registry, traces and projection. Since ADR-0036 and ADR-0038 it also reads transcripts and has ten use cases, so a reader looking for the transcript port or the view use cases is told they don't exist. api.py:30 is also the OpenAPI `info.description` (CMT-001).
- Evidence: `TranscriptReader` (ports.py:95), `JsonlTranscripts` (adapters/transcripts.py:70) and `rebuild(registry, traces, transcripts, …)` (application.py:57-63). The other use cases are at application.py:96, 113, 118, 123, 128, 133, 145, 155 and 159. The views, flow, behaviour, quality, compare, replay and sums modules are missing from the package list (__init__.py:6-9).
- Reproduce: `rg -n "class TranscriptReader|class JsonlTranscripts|^def " src/agency/insights/ports.py src/agency/insights/adapters/transcripts.py src/agency/insights/application.py`, then compare the result with `sed -n 1,10p src/agency/insights/__init__.py`.
- Fix: Rewrite these docstrings during translation. Fix risk: Low (api.py:30 needs `task schemas`, see CMT-001).

### CMT-006 · Low · Confirmed
- Where: src/agency/ledger/schema.py:1; tests/test_migrations.py:1
- Problem: Both say the registry "si aggiorna solo su richiesta (ADR-0022)". ADR-0022 decides only that every registry change is an Alembic migration. The "only on request" rule, the backup, the single transaction and the chain check are ADR-0025, which also names tests/test_migrations.py as its proof. No code cites ADR-0025.
- Evidence: docs/adr/0025-il-registro-si-aggiorna-solo-su-richiesta.md:3 ("ADR-0022 ha deciso che ogni modifica al registro è una migrazione Alembic, ma non come si applica") and :16-17 ("Riproducibile con `tests/test_migrations.py`").
- Reproduce: `rg -n "ADR-0025" src tests` prints nothing; `sed -n 1p src/agency/ledger/schema.py tests/test_migrations.py`.
- Fix: Cite "ADR-0022, ADR-0025". Fix risk: Low.

### CMT-007 · Low · Likely
- Where: src/agency/ledger/__init__.py:1
- Problem: "stato derivato da eventi solo in aggiunta" says ticket state is derived from the event chain. No code derives it, and part of the state cannot be derived: the verdict and the delivered hashes exist only in `tickets`. A reader could think `tickets` can be rebuilt from `events`, and lose verdicts doing so.
- Evidence: `Ledger.apply` writes `row.status`, `row.verdict` and `row.delivered_json` straight into `tickets` (store.py:235-241), and the event it appends carries only the actor, the action and the note (store.py:243, chain.py:13-15). docs/03-DATA-MODEL.md:28 states the same intent ("`tickets` è una vista di comodo dello stato; la verità è la storia degli eventi"), so the owner decides whether the doc or the code is right.
- Reproduce: `rg -n "row\.(status|verdict|delivered_json) =" src/agency/ledger/store.py`; `rg -n "events" src/agency/ledger/store.py` shows only appends, history and chain verification.
- Fix: Reword to "events are append-only and hash-chained; `tickets` holds the current state, verdict and delivered hashes". Fix risk: Low.

### CMT-008 · Low · Suspected
- Where: src/agency/contracts/ticket.py:12-21,40-45; src/agency/contracts/judgment.py:13-15; src/agency/contracts/artifact.py:22-24; src/agency/insights/domain.py:21-23,27-28; src/agency/insights/compare.py:35-38; src/agency/insights/replay.py:32-34; src/agency/tools/surface.py:661,718-719,956; concept statuses and file names in A8
- Problem: The identifiers are English, but the values they hold are Italian words, and those values are stored in ledger rows, transcripts, operations and the projection. They are also sent to the model (tool-schema enums, tool results) and consumed by the web (OpenAPI enums). They look like translation candidates and are not: changing them is a data migration plus a contract change, not a refactor.
- Evidence: the `TicketType` and `Medium` values are in the `open_ticket` schema of tests/snapshots/requests/design-director.json. The `Compared` and `Alignment` values are OpenAPI enums used as keys in web/src/app/compare/page.tsx:259-271 and web/src/app/projects/[name]/replay/[instance]/page.tsx:23-24. `"pagine"` is read back from `operations` on resume (surface.py:956), and `Level` values are stored in `judgments.level` (store.py:429).
- Reproduce: `rg -l '"produzione"|"vettoriale"' tests/snapshots/requests/`; `python3 -I -c "import json; d=json.load(open('schemas/openapi.json')); print({n: s['enum'] for n, s in d['components']['schemas'].items() if 'enum' in s})"`; `rg -n '"pagine"' src/agency/tools/surface.py`.
- Fix: Keep them, and record them as domain vocabulary, for example in docs/03-DATA-MODEL.md (the owner decides), so the translation unit leaves them alone. Fix risk: High if they are translated.

### CMT-009 · Low · Confirmed
- Where: src/agency/** without qa/scripts: 126 comment lines in 36 files, 299 docstrings in 85 files and 15 developer-facing `Field(description=…)` strings (A1, A2, A3)
- Problem: CLAUDE.md requires English for code comments and docstrings, and these are Italian. Behavior is unaffected, apart from the exceptions in CMT-001.
- Evidence: Python `tokenize` for comments and `ast` for docstrings, then a manual review of every item the language heuristic could not place. The only non-language comment in src is the section header `# Ticket` (ledger/store.py:127), and the only English text is pragmas (17 in src).
- Reproduce: `python3 -I -c "import tokenize,pathlib,re;print(sum(1 for p in pathlib.Path('src/agency').rglob('*.py') if 'qa/scripts' not in str(p) for t in tokenize.generate_tokens(open(p,encoding='utf-8').readline) if t.type==tokenize.COMMENT and not re.match(r'#\s*(noqa|type: ignore|fmt:)',t.string)))"` prints 127, which is 126 plus `# Ticket`. The same loop with `ast.get_docstring` over `Module`, `ClassDef`, `FunctionDef` and `AsyncFunctionDef` nodes prints 299.
- Fix: Translate one package per unit. Skip the CMT-001 docstrings and the frozen migration docstrings (00-baseline §1.7, the owner decides), and keep contracts/concept.py:11-15 because it is model-facing. Fix risk: Low.

### CMT-010 · Low · Confirmed
- Where: tests/**: 110 comment lines in 21 files, 134 docstrings in 27 files (A1, A2)
- Problem: Test comments and docstrings are Italian. Test function names are already English.
- Evidence: the same extraction as CMT-009. Leaving out 41 pragmas, there are 117 comment tokens: the 110 above and 7 non-language tokens (tests/test_hardening.py:183 "Loop", :577-580 ticket ids, tests/test_judgments.py:150 a date, tests/test_server.py:187 "SVG").
- Reproduce: the CMT-009 one-liners with `pathlib.Path('tests')` print 117 and 134.
- Fix: Translate them, and leave test data and assertions on user- or model-facing strings unchanged (see "Do not translate"). Fix risk: Low.

### CMT-011 · Low · Confirmed
- Where: 13 messages in src and 12 in tests (A4)
- Problem: Internal assertions, invariant errors, fake errors in tests and test-helper output are Italian, and none of them reaches the operator or the model on a normal path.
- Evidence: each raise was traced. gateway/transport.py:70 belongs to `ScriptedTransport`, which only tests use. gateway/client.py:167 follows a loop that always returns or raises. graph/workflow.py:291 is guarded by `draft_presentation` (surface.py:701-702), and ledger/store.py:415 runs after `Judgment` validation. qa/checks.py:58 cannot be reached through `run` (:64-65), but it would go to the model through `Toolbox` (surface.py:924-937), so that one stays Suspected. The five `downgrade()` messages are in migration files frozen by convention.
- Reproduce: `rg -n 'raise (AssertionError|RuntimeError|TypeError|NotImplementedError)' src/agency -g '!qa/scripts/*'`, plus the rows of A4.
- Fix: Translate the src rows except the 5 migration rows (the owner decides) and qa/checks.py:58 (decide first). Translate the test rows freely. Fix risk: Low.

### CMT-012 · Low · Confirmed
- Where: 114 comment blocks (184 lines) in 38 TS/TSX/MJS files under web/, and 14 comments in web/src/app/globals.css (A5)
- Problem: The web comments are Italian, except the `/** @type {import("next").NextConfig} */` annotation at web/next.config.mjs:9.
- Evidence: comment ranges from the TypeScript compiler (`getLeadingCommentRanges` and `getTrailingCommentRanges` on every token, skipping JSX text), so URLs and strings are not miscounted.
- Reproduce: `rg -n "//|/\*" web/src web/e2e web/scripts web/next.config.mjs web/playwright.config.ts -g '!schema.ts'` gives the leads; the compiler-based count is in A5.
- Fix: Translate them, and respect CMT-002: no `fetch(`, `use server` or `generateStaticParams` in web/src comments. Fix risk: Low.

### CMT-013 · Low · Confirmed
- Where: 40 test titles (18 in web/src/*.test.ts, 22 in web/e2e/*.spec.ts), 22 messages in web/scripts/check-defenses.mjs, 2 in web/scripts/standalone.mjs and 6 in web/e2e/run.spec.ts (A6)
- Problem: Web test names and build-check output are developer-facing and Italian; the Python test names are English.
- Evidence: the e2e title at web/e2e/run.spec.ts:173 is quoted in docs/audit/00-baseline.md:483. The `program` labels at run.spec.ts:203 are matched by their "Next.js" and "Django" prefixes (:219, :223).
- Reproduce: `rg -c "^\s*(test|test\.describe|describe)\(" web/src web/e2e` adds up to 40.
- Fix: Translate the titles and messages, and keep the UI-copy assertions and the "Next.js" and "Django" label prefixes. Note the baseline reference when renaming run.spec.ts:173. Fix risk: Low.

### CMT-014 · Low · Confirmed
- Where: src/agency (A10): 228 of 378 public module-level functions and classes have no docstring (107 of 195 classes, 121 of 183 functions)
- Problem: Most of the engine's public surface is undocumented, for example `Ledger` (ledger/store.py:61), `ModelGateway` (gateway/client.py:82), `Toolbox` (tools/surface.py:895), `SqliteProjection` (insights/adapters/projection.py:100) and `migrate` (ledger/schema.py:112).
- Evidence: an `ast` scan of top-level `def` and `class` nodes without a leading underscore, outside src/agency/qa/scripts.
- Reproduce: `python3 -I -c "import ast,pathlib;r=[(str(p),n.name) for p in pathlib.Path('src/agency').rglob('*.py') if 'qa/scripts' not in str(p) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and not n.name.startswith('_') and ast.get_docstring(n) is None];print(len(r))"` prints 228.
- Fix: Document the 158 plain items. Document the 34 items tagged [T] only with `#` comments (CMT-001), and the 26 tagged [O] (19 API models, 7 routes) only together with `task schemas`. Leave the 10 migration functions tagged [M] alone. Fix risk: Low, or High for [T] if done with docstrings.

### CMT-015 · Nit · Confirmed
- Where: 20 exported functions and components without JSDoc (A11)
- Problem: The framework entry points (`Layout`, `NotFound`, `Projects`, six `generateMetadata`), the `api` client object and small helpers in format.ts, labels.ts and chart.ts have no JSDoc, while their siblings do.
- Evidence: exported declarations read with the TypeScript compiler, checked for a leading `/**` comment.
- Reproduce: `rg -n -B1 "^export (default )?(async )?function|^export const \w+ = \(|^export const api = " web/src -g '!schema.ts' -g '!*.test.ts'`, then keep the hits whose previous line does not end with `*/`: 20.
- Fix: Add one-line JSDoc where the name does not say enough (`api`, `when`, `share`, `line`, the labels helpers). The framework conventions can stay as they are. Fix risk: Low.

### CMT-016 · Nit · Confirmed
- Where: pyproject.toml:49,59,100; Makefile:1-2,6; mise.toml:1-2,10,12; Taskfile.yml:3-6,86; .gitignore:8-9,17,20; .env.example:1,3,5,6; docker/compose.yaml:1-5,8,22,28-30,34,38-39; docker/server.Dockerfile:1-3,11,14,23; docker/web.Dockerfile:1-3,12,16,23-24; docker/server.Dockerfile.dockerignore:1-2; docker/web.Dockerfile.dockerignore:1-2; spikes/sandbox_craft.sh:2-3; web/tsconfig.json:16,18-19; web/pnpm-workspace.yaml:1; import-linter contract names at pyproject.toml:75,98,122,146; web/package.json:4
- Problem: 59 comment lines in 14 config and infra files, the 4 contract names that `lint-imports` prints and the package description are Italian. The output strings of spikes/sandbox_craft.sh:21,23-25 are developer-facing and Italian too.
- Evidence: read by hand, since these files have no tokenizer in the toolchain. No test reads the contract names: tests/test_server.py:421 selects the contract by `forbidden_modules`.
- Reproduce: `rg -n "^\s*#|\s#\s" pyproject.toml Makefile mise.toml Taskfile.yml .gitignore .env.example docker spikes web/pnpm-workspace.yaml` and `rg -n "//" web/tsconfig.json`.
- Fix: Translate them. pyproject.toml:59 ignores RUF001, RUF002 and RUF003 "for Italian text": after translation RUF002 and RUF003 may no longer be needed, while RUF001 still covers the Italian strings (the owner decides). Fix risk: Low.

### CMT-017 · Nit · Confirmed
- Where: test fixture data in tests/** and web/e2e/project.ts:2,11 (A9)
- Problem: Invented project names and fixture tokens are Italian words: `officina` 161 times, `fantasma` 11, `forno` 6, `bottega` 3, `officina-e2e` and `officina-prima` once each, plus about 70 other tokens such as `prova-spia-cli` and `segreto`. `merlo`, `merlo3` and `merlo4` (121 uses) are the names of real projects and stay.
- Evidence: an `ast` scan of identifier-like string literals in tests that are not English words and are not engine vocabulary from src (A9). `officina-e2e` and `fantasma` are shared between tests/dashboard_fixture.py and web/e2e (project.ts:2,11, run.spec.ts:62, compare.spec.ts:61).
- Reproduce: `rg -c '"officina' tests` and `rg -n 'officina|fantasma' web/e2e`.
- Fix: Leave them as they are: they are data, coupled to assertions and to the e2e specs. If they are ever renamed, do it per file, together with its assertions. Fix risk: Med.

### CMT-018 · Nit · Likely
- Where: src/agency/contracts/__init__.py:1
- Problem: "tutto ciò che attraversa un confine è un modello Pydantic" does not hold inside the package itself. `DataLayout`, shared by the engine and the server, is a frozen dataclass, and `ArtifactStore` is a Protocol.
- Evidence: src/agency/contracts/layout.py:12-13 (`@dataclass(frozen=True) class DataLayout`), whose docstring says it serves "il motore che scrive e … chi legge" (:1). src/agency/contracts/artifact.py:38 (`class ArtifactStore(Protocol)`).
- Reproduce: `rg -n "@dataclass|Protocol\)" src/agency/contracts`.
- Fix: Reword as "data that crosses a boundary is a typed contract: Pydantic models, plus `DataLayout` and the `ArtifactStore` port". Fix risk: Low.

### CMT-019 · Nit · Likely
- Where: src/agency/insights/domain.py:147
- Problem: `# I passi indietro: un ticket rimandato, bloccato o annullato.` only restates the next line, `SETBACKS = frozenset({Lifecycle.REWORK, Lifecycle.BLOCK, Lifecycle.CANCEL})`. It is the only comment in scope found to do nothing but restate code; the other short comments are section headers or say why.
- Evidence: domain.py:147-148.
- Reproduce: `sed -n 147,148p src/agency/insights/domain.py`.
- Fix: Drop it, or say why these three count as setbacks and RESUME does not. Fix risk: Low.

## Do not translate

There are no i18n resources: no catalogues, locale folders, message files or i18n libraries (`git ls-files` has no `*.po`, `*.mo`, `*.ftl`, `locales/` or `i18n/`, and nothing in src or web imports gettext, i18next or next-intl). Every user-facing string is an inline Italian literal. The rule of the audit forbids editing them, and translating any of them is a product decision, not a refactor.

### Operator-facing (CLI, server, errors that reach the operator)

| File | Lines | What |
|---|---|---|
| src/agency/cli.py | 1, 39-363 | module docstring = `agency --help` description; printed messages; 25 `help=` strings; REGISTRO, BUDGET and API messages |
| src/agency/doctor.py | 13-24, 46, 56 | the detail column of `agency doctor` |
| src/agency/telemetry/report.py | 18-199 | all text of `agency report`, `runs`, `compare`, `judge`, `artifacts`, `restore`, `verify` and `insights` |
| src/agency/telemetry/fingerprint.py | 28, 39, 41 | "assente", "non risponde": stored in `runs.fingerprint_json`, shown by `agency compare` |
| src/agency/evaluation/blind.py | 23, 38-48, 87, 116-135 | interview prompts and accepted answers; `CannotCompare` printed by cli.py:223,256 |
| src/agency/evaluation/board.py | 41, 67-138 | `SHOWN` printed by cli.py:233; `CannotCompare` messages |
| src/agency/contracts/judgment.py | 45-49, 65 | validation and `below_the_top` reason, shown again in the interview (blind.py:131-135) |
| src/agency/artifacts/keeping.py | 72-109 | `CannotRestore`, printed by cli.py:280 |
| src/agency/gateway/client.py | 129, 136 | `BudgetExceeded`, printed by cli.py:109 |
| src/agency/ledger/schema.py | 91-92, 98, 127 | `LedgerOutdated`, `LedgerMismatch`, `ChainBroken`, printed by cli.py:362 |
| src/agency/insights/application.py | 43-48 | `RegistryNotReadable` reasons, shown by the CLI and as the dashboard's 503 |
| src/agency/insights/adapters/registry.py | 90, 100, 145 | same |
| src/agency/insights/adapters/projection.py | 135, 141 | `ProjectionOutdated` (Suspected: reached only while the projection is missing or old) |
| src/agency/graph/workflow.py | 77, 102, 178, 274, 283, 371, 392, 404 | run outcomes ("bloccato: …", "approvato") printed by cli.py:117 |
| src/agency/entrypoints/server/serve.py | 1, 96, 107-108, 113-125 | `agency-server --help` (module docstring) and its messages |
| src/agency/entrypoints/server/api.py | 81, 136, 157, 185 | `Problem.detail`, shown by the dashboard |
| src/agency/entrypoints/server/schema.py | 1, 32, 37-43 | `agency-schemas` help and output (Suspected: developer tooling; the owner decides) |
| docker/compose.yaml | 23, 32 | `${VAR:?…}` messages shown by `docker compose` |
| Taskfile.yml | 13-133 (18 `desc:`) | `task --list` help (Suspected: command help; the owner decides) |

### Client-facing document

| File | Lines | What |
|---|---|---|
| src/agency/tools/presentation.py | 184, 193, 196, 202, 205 | page labels of the PDF the client receives |
| src/agency/tools/presentation.py | 208, 224, 236 | file names of the deliverable (see A8) |

### Model-facing (changes agent behavior and tests/snapshots/requests/)

| File | Lines | What |
|---|---|---|
| src/agency/tools/surface.py | 105-250 | 22 `Field` descriptions in tool schemas |
| src/agency/tools/surface.py | 774-825 | the 28 tool descriptions (`TOOLS`) |
| src/agency/tools/surface.py | 275-742, 911, 923, 940, 951 | `Refused` messages, tool result notes (347-349, 625, 719), ledger notes (750), `Toolbox` errors |
| src/agency/tools/surface.py | 598-611 | the exploration ticket each explorer receives |
| src/agency/contracts/concept.py | 11-15 | `submit_concept` schema |
| src/agency/contracts/ticket.py | 12-21, 40-45, 111-123 | enum values in the `open_ticket` schema; validator messages returned by surface.py:508-509 |
| src/agency/agents/prompts.py | 35-36, 43-72 | system-prompt suffix and ticket packet |
| src/agency/agents/loop.py | 145, 148, 165, 188 | block reasons (ledger notes, shown in packets and the dashboard) and the reminder |
| src/agency/graph/workflow.py | 74-404 | ticket titles, requests, notes and client notes |
| src/agency/runtime.py | 81, 89 | root ticket title and exemption reason |
| src/agency/qa/checks.py | 34, 65, 68 | check outcomes and refusals |
| src/agency/qa/evidence.py | 116, 148, 150, 169 | refusals |
| src/agency/qa/delivery.py | 28-29, 70-237 | contract refusals and delivery problems |
| src/agency/tools/master.py | 38-113 | master problems |
| src/agency/tools/craft.py | 105 | unknown command |
| src/agency/tools/board.py | 113-116 | the sketch warning (see CMT-004) |
| src/agency/tools/files.py | 17, 34 | perimeter error, clip marker |
| src/agency/tools/render.py | 48 | render error |
| src/agency/tools/sandbox.py | 84 | timeout output |
| src/agency/tools/presentation.py | 40 | missing font (through `draft_presentation`) |
| src/agency/ledger/store.py | 227-234 | `ForbiddenAction`, `IllegalTransition`, returned by surface.py:924-937 |
| prompts/**, registry/*.json | all | out of scope by rule |
| src/agency/qa/scripts/*.py | all output | returned to the model by `run_check` (vendored) |

### Dashboard copy

| File | Lines |
|---|---|
| web/src/labels.ts | 8-70 |
| web/src/format.ts | 39 (and the `it-IT` formatters at 3-8) |
| web/src/app/layout.tsx | 8-24 (`lang="it"`, title) |
| web/src/app/not-found.tsx | 6-9 |
| web/src/app/page.tsx | 18-46 |
| web/src/app/compare/page.tsx | 13-407 |
| web/src/app/projects/[name]/page.tsx | 29-191 |
| web/src/app/projects/[name]/phases/page.tsx | 16-168 |
| web/src/app/projects/[name]/model/page.tsx | 16-128 |
| web/src/app/projects/[name]/quality/page.tsx | 16-186 |
| web/src/app/projects/[name]/replay/page.tsx | 26-36 |
| web/src/app/projects/[name]/replay/[instance]/page.tsx | 23-175 |
| web/src/components/context-chart.tsx | 34-170 |
| web/src/components/project-header.tsx | 6-20 |
| web/src/components/said.tsx | 12 |
| web/src/components/setbacks.tsx | 8-19 |
| web/src/components/timeline.tsx | 28-71 |
| web/src/components/unavailable.tsx | 8-31 |
| web/src/api/client.ts | 47-55 (`ApiError` details shown by `Unavailable`) |
| web/src/proxy.ts | 12 (body of the 400) |

Mirrors that must change only together with the copy above: the UI-copy assertions in web/e2e/*.spec.ts, and the Python tests that assert on Italian messages and output (for example tests/test_hardening.py, tests/test_judgments.py, tests/test_artifacts.py, tests/test_server.py, tests/test_report_views.py).

### Generated files and where their text comes from

| Generated file | Source of its text | Regenerate |
|---|---|---|
| schemas/openapi.json | the 27 class docstrings and api.py:28,30,134,164,179 (CMT-001); enum values of CMT-008 | `task schemas`; guarded by tests/test_schemas.py |
| web/src/api/schema.ts | openapi.json (`@description` JSDoc) | `pnpm --dir web run api:types`; `api:check` |
| tests/snapshots/requests/*.json | prompts/**, agents/prompts.py:35-36, the surface.py tool and `Field` descriptions, concept.py:11-15, enum values in ticket.py | `UPDATE_SNAPSHOTS=1 uv run pytest tests/test_request_snapshots.py` |

Owner note on content, not language: src/agency/doctor.py:23 says Docker is needed for "Langfuse e ComfyUI", while Docker now runs the dashboard (ADR-0040; tests/test_docker.py:1-5).

## Vendored code (not translation work)

`src/agency/qa/scripts/{logo_proof,optical_check,svg_audit,svg_parity}.py` are byte-identical to `legacy/claude-code-v1/src/.claude/skills/*/scripts/` (sha256 prefixes 0d7fe4e5…, 6340cbab…, 2fdbffa5…, 457a586c… match), and ruff and pyright skip them (pyproject.toml:55, 63). Leave them as they are.

| File | Italian comments | Docstrings | Message lines (exit, print, argparse, raise) |
|---|---:|---:|---:|
| logo_proof.py | 2 (133, 157) | 3 | 11 |
| optical_check.py | 2 (32, 41) | 1 | 19 |
| svg_audit.py | 1 (80) | 2 | 7 |
| svg_parity.py | 2 (100-101) | 1 | 9 |

Their module docstrings are argparse descriptions (logo_proof.py:184, optical_check.py:130, svg_audit.py:115, svg_parity.py:76), and their output reaches the model through `run_check` (src/agency/qa/checks.py:25-37). One observation, not a fix: optical_check.py:25 and svg_parity.py:24 tell the reader to run `bash .claude/tools/setup_tools.sh`, a path that exists only under legacy/.

## Appendix: inventory

### A0. Method and scope

- Python: `tokenize` COMMENT tokens; `ast` for docstrings, top-level public definitions, identifiers (definitions, arguments, assignment targets) and string literals passed to `raise`, `assert`, `print`, argparse and `pytest.fail`/`skip`. Each `raise` was then traced to its handler: `Toolbox.call` (surface.py:924-937) returns every `ValueError`, `RuntimeError`, `KeyError`, `FileNotFoundError` and `Refused` raised by a tool handler to the model, and cli.py prints the rest.
- TypeScript: the project's TypeScript compiler (web/node_modules/typescript), with comment ranges at every token, skipping JSX text, plus exported declarations and string literals.
- Language: a stopword and accent heuristic, then a dictionary fallback, then manual review of every item it could not place. Comments are counted per line, docstrings per docstring and web comments per block.
- Out of scope: legacy/, lockfiles, docs/**, prompts/**, registry/*.json and generated files. The vendored scripts are listed above only.

### Totals per kind

| Kind | Count | Where |
|---|---:|---|
| Python comment lines, Italian | 236 | src 126 in 36 files, tests 110 in 21 files (A1) |
| Python comment lines, not language | 66 | 58 pragmas (17 in src), 8 tokens (headers, ids, dates) |
| Python docstrings, Italian | 433 | src 299 in 85 files, tests 134 in 27 files (A2); [O] 29 feed OpenAPI, [H] 3 are CLI help |
| Python `Field` descriptions, Italian | 42 | 27 model-facing, 15 developer-facing (A3) |
| Python developer-facing messages, Italian | 25 | src 13, tests 12 (A4) |
| TODO, FIXME, XXX, HACK | 0 | `rg -n "\b(TODO|FIXME|XXX|HACK)\b"` over the scope |
| logging and warnings calls | 0 | |
| Python identifiers, Italian | 0 | of 2,172 distinct names (7,829 uses) |
| TypeScript identifiers, Italian | 0 | of 214 declared names |
| Persisted Italian vocabulary | 12 groups | A8 (CMT-008) |
| Italian fixture identifiers | about 255 uses | A9 (CMT-017) |
| Web comments, Italian | 114 blocks, 184 lines + 14 CSS | 38 TS/TSX/MJS files + globals.css (A5) |
| Web developer-facing strings, Italian | 70 | 40 test titles, 24 build-script messages, 6 e2e messages (A6) |
| Config and infra comments, Italian | 59 lines + 5 strings | 14 files, 4 contract names, 1 package description (A7) |
| Public Python API without docstring | 228 of 378 | A10 |
| Exported TS functions without JSDoc | 20 | A11 |
| Vendored files | 4 | not work |

### Totals per file (files with 9 or more Italian comments and docstrings)

| File | Comments | Docstrings | Total |
|---|---:|---:|---:|
| tests/test_insights.py | 22 | 11 | 33 |
| src/agency/insights/domain.py | 1 | 24 | 25 |
| tests/test_hardening.py | 9 | 16 | 25 |
| src/agency/tools/surface.py | 9 | 13 | 22 |
| tests/dashboard_fixture.py | 14 | 6 | 20 |
| tests/test_sketch_flow.py | 9 | 11 | 20 |
| src/agency/ledger/store.py | 10 | 7 | 17 |
| tests/test_server.py | 9 | 7 | 16 |
| tests/test_judgments.py | 10 | 5 | 15 |
| web/e2e/run.spec.ts | 15 blocks | – | 15 |
| src/agency/evaluation/board.py | 7 | 7 | 14 |
| src/agency/tools/presentation.py | 5 | 9 | 14 |
| src/agency/insights/adapters/registry.py | 8 | 5 | 13 |
| src/agency/insights/application.py | 3 | 10 | 13 |
| src/agency/ledger/models.py | 3 | 10 | 13 |
| src/agency/graph/workflow.py | 8 | 3 | 11 |
| src/agency/insights/flow.py | 3 | 8 | 11 |
| src/agency/insights/ports.py | 0 | 11 | 11 |
| src/agency/tools/board.py | 5 | 6 | 11 |
| web/scripts/check-defenses.mjs | 11 blocks | – | 11 |
| src/agency/agents/loop.py | 7 | 3 | 10 |
| src/agency/entrypoints/server/api.py | 5 | 5 | 10 |
| src/agency/gateway/client.py | 4 | 6 | 10 |
| tests/test_docker.py | 4 | 6 | 10 |
| src/agency/artifacts/keeping.py | 3 | 6 | 9 |

#### A1. Python comments (Italian), by file

| File | Lines | Line numbers |
|---|---|---|
| `src/agency/agents/loop.py` | 7 | 65,108,122,149,159,161,179 |
| `src/agency/artifacts/files.py` | 1 | 63 |
| `src/agency/artifacts/keeping.py` | 3 | 21,88,97 |
| `src/agency/cli.py` | 3 | 36,177,244 |
| `src/agency/contracts/phase.py` | 1 | 11 |
| `src/agency/contracts/ticket.py` | 2 | 19,59 |
| `src/agency/entrypoints/server/api.py` | 5 | 26,33,65-66,161 |
| `src/agency/entrypoints/server/middleware.py` | 3 | 17-18,24 |
| `src/agency/entrypoints/server/schema.py` | 3 | 15,19-20 |
| `src/agency/entrypoints/server/serve.py` | 2 | 50-51 |
| `src/agency/entrypoints/server/settings.py` | 5 | 14,16,18,32-33 |
| `src/agency/evaluation/blind.py` | 1 | 57 |
| `src/agency/evaluation/board.py` | 7 | 24,28-29,33-35,109 |
| `src/agency/gateway/client.py` | 4 | 34,108,141,164 |
| `src/agency/gateway/pricing.py` | 2 | 24,29 |
| `src/agency/graph/workflow.py` | 8 | 70,95,180,278,290,325,333,368 |
| `src/agency/insights/adapters/projection.py` | 2 | 63,171 |
| `src/agency/insights/adapters/registry.py` | 8 | 33,44-45,53,71,79,96,124 |
| `src/agency/insights/adapters/traces.py` | 1 | 18 |
| `src/agency/insights/adapters/transcripts.py` | 6 | 30-31,34,38,122,159 |
| `src/agency/insights/application.py` | 3 | 28-29,66 |
| `src/agency/insights/behaviour.py` | 2 | 19-20 |
| `src/agency/insights/domain.py` | 1 | 147 |
| `src/agency/insights/flow.py` | 3 | 23-24,207 |
| `src/agency/insights/replay.py` | 1 | 122 |
| `src/agency/ledger/models.py` | 3 | 66,69,211 |
| `src/agency/ledger/schema.py` | 1 | 86 |
| `src/agency/ledger/store.py` | 10 | 65,73,107,256,275,332,364,383,409,449 |
| `src/agency/qa/checks.py` | 3 | 42,44,55 |
| `src/agency/qa/delivery.py` | 3 | 26,150,176 |
| `src/agency/runtime.py` | 1 | 30 |
| `src/agency/telemetry/report.py` | 1 | 14 |
| `src/agency/tools/board.py` | 5 | 19-23 |
| `src/agency/tools/presentation.py` | 5 | 25,27-28,118,230 |
| `src/agency/tools/render.py` | 1 | 51 |
| `src/agency/tools/surface.py` | 9 | 57,61,340,415,761,898,914,937,956 |
| `tests/conftest.py` | 1 | 19 |
| `tests/dashboard_fixture.py` | 14 | 34,48,59,72,118-120,134,136,150,171,204,297,366 |
| `tests/drawings.py` | 1 | 48 |
| `tests/test_agent_flow.py` | 2 | 202,247 |
| `tests/test_artifacts.py` | 7 | 32,55,95,120,148,206,245 |
| `tests/test_board.py` | 4 | 56,78,125,128 |
| `tests/test_compare_view.py` | 1 | 247 |
| `tests/test_docker.py` | 4 | 77-78,83,132 |
| `tests/test_explicit_types.py` | 3 | 22,51,64 |
| `tests/test_gateway.py` | 1 | 214 |
| `tests/test_hardening.py` | 9 | 77,112,134,141,302,352,403,413,534 |
| `tests/test_insights.py` | 22 | 104,116,136,139,175,200-201,222,277,361,375,387,389,408,450,571,609,678,766,775,811,853 |
| `tests/test_judgments.py` | 10 | 34,75,88,155,206,272,280,326,350,419 |
| `tests/test_ledger.py` | 1 | 125 |
| `tests/test_report_views.py` | 3 | 110,211,351 |
| `tests/test_repository.py` | 1 | 18 |
| `tests/test_request_snapshots.py` | 1 | 77 |
| `tests/test_runs.py` | 4 | 45,116,215,245 |
| `tests/test_server.py` | 9 | 19,93,232,234,254,312,317,330,414 |
| `tests/test_sketch_flow.py` | 9 | 119,238,445,493,581,613,1044,1054,1120 |
| `tests/test_taskfile.py` | 3 | 20,105-106 |

#### A2. Python docstrings (Italian), by file

[O] = text in schemas/openapi.json; [H] = argparse description (CLI help). See CMT-001.

| File | Docstrings | Opening line of each docstring |
|---|---|---|
| `src/agency/agents/__init__.py` | 1 | 1 |
| `src/agency/agents/loop.py` | 3 | 1,55,186 |
| `src/agency/agents/prompts.py` | 3 | 1,26,31 |
| `src/agency/agents/transcript.py` | 3 | 1,18,50 |
| `src/agency/artifacts/__init__.py` | 1 | 1 |
| `src/agency/artifacts/files.py` | 2 | 1,31 |
| `src/agency/artifacts/keeping.py` | 6 | 1,30,47,69,85,114 |
| `src/agency/cli.py` | 5 | 1[H],75,104,122,287 |
| `src/agency/config.py` | 1 | 1 |
| `src/agency/context/__init__.py` | 1 | 1 |
| `src/agency/contracts/__init__.py` | 1 | 1 |
| `src/agency/contracts/artifact.py` | 6 | 1,20,35,40,44,50 |
| `src/agency/contracts/concept.py` | 1 | 1 |
| `src/agency/contracts/gate.py` | 4 | 1,22,35,49 |
| `src/agency/contracts/judgment.py` | 6 | 1,11,19,33,56,69 |
| `src/agency/contracts/layout.py` | 3 | 1,14,42 |
| `src/agency/contracts/outcome.py` | 2 | 1,21 |
| `src/agency/contracts/phase.py` | 3 | 1,21,28 |
| `src/agency/contracts/run.py` | 5 | 1,13,39,45,56 |
| `src/agency/contracts/ticket.py` | 2 | 1,82 |
| `src/agency/doctor.py` | 1 | 1 |
| `src/agency/entrypoints/__init__.py` | 1 | 1 |
| `src/agency/entrypoints/server/__init__.py` | 1 | 1 |
| `src/agency/entrypoints/server/__main__.py` | 1 | 1 |
| `src/agency/entrypoints/server/api.py` | 5 | 1,49,78,134[O],179[O] |
| `src/agency/entrypoints/server/middleware.py` | 1 | 1 |
| `src/agency/entrypoints/server/schema.py` | 1 | 1[H] |
| `src/agency/entrypoints/server/serve.py` | 3 | 1[H],33,41 |
| `src/agency/entrypoints/server/settings.py` | 1 | 1 |
| `src/agency/entrypoints/server/urls.py` | 1 | 1 |
| `src/agency/evaluation/__init__.py` | 1 | 1 |
| `src/agency/evaluation/blind.py` | 6 | 1,26,69,76,92,124 |
| `src/agency/evaluation/board.py` | 7 | 1,51,77,92,142,147,159 |
| `src/agency/gateway/__init__.py` | 1 | 1 |
| `src/agency/gateway/client.py` | 6 | 1,25,67,97,126,133 |
| `src/agency/gateway/pricing.py` | 1 | 1 |
| `src/agency/gateway/transport.py` | 6 | 1,17,25,41,57,80 |
| `src/agency/graph/__init__.py` | 1 | 1 |
| `src/agency/graph/workflow.py` | 3 | 1,147,328 |
| `src/agency/insights/__init__.py` | 1 | 1 |
| `src/agency/insights/adapters/__init__.py` | 1 | 1 |
| `src/agency/insights/adapters/projection.py` | 1 | 1 |
| `src/agency/insights/adapters/registry.py` | 5 | 1,64,75,87,104 |
| `src/agency/insights/adapters/stamps.py` | 1 | 1 |
| `src/agency/insights/adapters/traces.py` | 1 | 1 |
| `src/agency/insights/adapters/transcripts.py` | 3 | 1,65,79 |
| `src/agency/insights/application.py` | 10 | 1,34,38,103,114,119,124,129,134,148 |
| `src/agency/insights/behaviour.py` | 5 | 1,29[O],37[O],56[O],86 |
| `src/agency/insights/compare.py` | 6 | 1,33[O],42[O],56[O],84[O],100[O] |
| `src/agency/insights/domain.py` | 24 | 1,19,32,60,71,87,100,115,135[O],152,167,184,198[O],209,223,237,259,274,286,317,323,378,395[O],405[O] |
| `src/agency/insights/flow.py` | 8 | 1,33[O],42[O],60[O],76[O],90[O],156,213 |
| `src/agency/insights/ports.py` | 11 | 1,31,47,79,83,97,103,107,113,125,132 |
| `src/agency/insights/quality.py` | 3 | 1,32[O],60[O] |
| `src/agency/insights/replay.py` | 5 | 1,30[O],38[O],61[O],107 |
| `src/agency/insights/sums.py` | 4 | 1,16,23,57 |
| `src/agency/insights/views.py` | 9 | 1,31[O],48[O],56[O],87[O],110[O],147,196,301 |
| `src/agency/ledger/__init__.py` | 1 | 1 |
| `src/agency/ledger/chain.py` | 2 | 1,19 |
| `src/agency/ledger/migrations/env.py` | 1 | 1 |
| `src/agency/ledger/migrations/versions/0001_baseline.py` | 1 | 1 (frozen file) |
| `src/agency/ledger/migrations/versions/0002_runs.py` | 1 | 1 (frozen file) |
| `src/agency/ledger/migrations/versions/0003_judgments.py` | 1 | 1 (frozen file) |
| `src/agency/ledger/migrations/versions/0004_usage_measures.py` | 1 | 1 (frozen file) |
| `src/agency/ledger/migrations/versions/0005_artifacts.py` | 1 | 1 (frozen file) |
| `src/agency/ledger/models.py` | 10 | 1,10,47,78,121,139,154,166,179,198 |
| `src/agency/ledger/schema.py` | 6 | 1,33,37,41,69,75 |
| `src/agency/ledger/store.py` | 7 | 1,50,54,86,136,412,452 |
| `src/agency/qa/__init__.py` | 1 | 1 |
| `src/agency/qa/checks.py` | 1 | 1 |
| `src/agency/qa/delivery.py` | 4 | 1,34,60,92 |
| `src/agency/qa/evidence.py` | 4 | 1,24,44,105 |
| `src/agency/runtime.py` | 4 | 1,35,57,75 |
| `src/agency/telemetry/__init__.py` | 1 | 1 |
| `src/agency/telemetry/fingerprint.py` | 3 | 1,26,62 |
| `src/agency/telemetry/report.py` | 3 | 1,22,147 |
| `src/agency/telemetry/setup.py` | 1 | 1 |
| `src/agency/tools/__init__.py` | 1 | 1 |
| `src/agency/tools/board.py` | 6 | 1,27,41,54,66,103 |
| `src/agency/tools/craft.py` | 3 | 1,35,98 |
| `src/agency/tools/files.py` | 3 | 1,10,30 |
| `src/agency/tools/master.py` | 3 | 1,35,73 |
| `src/agency/tools/presentation.py` | 9 | 1,33,69,110,153,163,212,217,228 |
| `src/agency/tools/render.py` | 1 | 1 |
| `src/agency/tools/sandbox.py` | 1 | 1 |
| `src/agency/tools/surface.py` | 13 | 1,43,69,77,319,413,475,630,651,692,724,873,949 |
| `tests/conftest.py` | 3 | 1,39,49 |
| `tests/dashboard_fixture.py` | 6 | 1,96,146,192,220,253 |
| `tests/drawings.py` | 3 | 1,19,36 |
| `tests/test_agent_flow.py` | 3 | 1,61,332 |
| `tests/test_artifacts.py` | 2 | 1,275 |
| `tests/test_behaviour_view.py` | 3 | 1,84,129 |
| `tests/test_board.py` | 4 | 1,39,53,133 |
| `tests/test_compare_view.py` | 6 | 1,200,208,219,240,267 |
| `tests/test_docker.py` | 6 | 1,31,57,88,114,137 |
| `tests/test_explicit_types.py` | 3 | 1,79,132 |
| `tests/test_flow_view.py` | 6 | 1,60,128,149,175,211 |
| `tests/test_gateway.py` | 4 | 56,93,158,202 |
| `tests/test_hardening.py` | 16 | 1,58,82,116,158,187,232,244,266,289,306,344,476,500,607,637 |
| `tests/test_insights.py` | 11 | 1,126,243,287,307,380,457,492,592,781,825 |
| `tests/test_judgments.py` | 5 | 1,46,182,285,404 |
| `tests/test_migrations.py` | 5 | 1,36,65,78,90 |
| `tests/test_quality_view.py` | 4 | 1,141,184,203 |
| `tests/test_replay_view.py` | 3 | 1,58,90 |
| `tests/test_report_views.py` | 5 | 1,143,252,293,304 |
| `tests/test_repository.py` | 2 | 1,44 |
| `tests/test_request_snapshots.py` | 4 | 1,32,57,61 |
| `tests/test_runs.py` | 1 | 1 |
| `tests/test_schemas.py` | 3 | 1,17,59 |
| `tests/test_server.py` | 7 | 1,140,282,329,369,418,431 |
| `tests/test_sketch_flow.py` | 11 | 1,85,201,218,227,707,936,953,1017,1039,1125 |
| `tests/test_taskfile.py` | 5 | 1,46,72,87,94 |
| `tests/test_toolchain.py` | 3 | 1,35,40 |

#### A3. Python `Field(description=…)` strings (Italian)

| Where | Count | Facing |
|---|---:|---|
| `src/agency/tools/surface.py:105,111,120,132,137,153,160,168,206,210,211,218,220,222,228,229,237,243,244,245,246,250` | 22 | model (do not translate) |
| `src/agency/contracts/concept.py:11-15` | 5 | model (do not translate) |
| `src/agency/contracts/ticket.py:91,93,95,103,105` | 5 | developer |
| `src/agency/contracts/run.py:24,26,31,32,33,34,36` | 7 | developer |
| `src/agency/contracts/judgment.py:28,74` | 2 | developer |
| `src/agency/contracts/artifact.py:31` | 1 | developer |

surface.py:133 (`CraftRun.steps`) is left out: it holds a JSON example, not Italian, though it is model-facing too.

#### A4. Python developer-facing messages (Italian)

| Where | Kind | First ~60 chars |
|---|---|---|
| `src/agency/artifacts/files.py:45` | ValueError | non è uno sha256: {…} |
| `src/agency/gateway/client.py:167` | AssertionError | non raggiungibile |
| `src/agency/gateway/transport.py:70` | AssertionError | risposte registrate esaurite |
| `src/agency/graph/workflow.py:291` | ValueError | presentazione senza raccomandazione: non si arriva al gate |
| `src/agency/insights/adapters/projection.py:54` | TypeError | {…}: tipo {…} senza colonna SQLite |
| `src/agency/ledger/schema.py:60` | RuntimeError | nessuna migrazione trovata |
| `src/agency/ledger/store.py:415` | ValueError | lettere giudicate {…}, lettere con un file {…} |
| `src/agency/qa/checks.py:58` | ValueError (Suspected) | controllo non eseguibile: {…} |
| `src/agency/ledger/migrations/versions/0001_baseline.py:272` | NotImplementedError (frozen) | il registro non torna indietro: si ripristina dalla copia di… |
| `src/agency/ledger/migrations/versions/0002_runs.py:46` | NotImplementedError (frozen) | same text |
| `src/agency/ledger/migrations/versions/0003_judgments.py:55` | NotImplementedError (frozen) | same text |
| `src/agency/ledger/migrations/versions/0004_usage_measures.py:27` | NotImplementedError (frozen) | same text |
| `src/agency/ledger/migrations/versions/0005_artifacts.py:53` | NotImplementedError (frozen) | same text |
| `tests/conftest.py:43` | print | Le prove hanno scritto nel registro vero {…}: {…} |
| `tests/dashboard_fixture.py:389` | print | registro di prova in {…} |
| `tests/test_agent_flow.py:215` | ConnectionError (fake) | processo ucciso |
| `tests/test_artifacts.py:282` | AssertionError | diciassette hash in sedici cifre: due coincidono sempre |
| `tests/test_docker.py:43` | assert message | la chiave dell'ambiente è finita nella configurazione |
| `tests/test_gateway.py:224` | ValueError (fake) | JSON illeggibile |
| `tests/test_hardening.py:492` | pytest.fail | non doveva partire |
| `tests/test_request_snapshots.py:111` | assert message | manca lo snapshot di {…}. Se è voluto: {…} |
| `tests/test_request_snapshots.py:112` | assert message | prefisso cambiato. Se è voluto: {…} |
| `tests/test_sketch_flow.py:115` | AssertionError | risposte esaurite per {…}: {…} |
| `tests/test_sketch_flow.py:919` | ConnectionError (fake) | processo ucciso |
| `tests/test_taskfile.py:40` | pytest.fail | Task manca dal PATH: viene da mise.toml, si esegue con mis… |

#### A5. Web comments (Italian), by file

| File | Blocks | Lines |
|---|---|---|
| `web/e2e/canary.ts` | 1 | 1-4 |
| `web/e2e/compare.spec.ts` | 2 | 8,56 |
| `web/e2e/model.spec.ts` | 4 | 14,27,33,45 |
| `web/e2e/phases.spec.ts` | 3 | 15,26,54 |
| `web/e2e/project.ts` | 5 | 1,4,7,10,13 |
| `web/e2e/quality.spec.ts` | 3 | 16,21,26 |
| `web/e2e/replay.spec.ts` | 1 | 23 |
| `web/e2e/run.spec.ts` | 15 | 32,39-40,72,84,98,110,135,156,186,193,197,205,242,247 |
| `web/next.config.mjs` | 5 | 1-4,6,11,15,17 (line 9 `@type` excluded) |
| `web/playwright.config.ts` | 6 | 5-8,11,14,25,38,51 |
| `web/scripts/check-defenses.mjs` | 11 | 1-4,17,27,32,55,64,73,79-80,96,100 |
| `web/scripts/standalone.mjs` | 1 | 1-5 |
| `web/src/api/client.ts` | 5 | 1-8,11,16,19-22,76-79 |
| `web/src/api/index.ts` | 3 | 1-4,9,16 |
| `web/src/api/read.ts` | 1 | 5-8 |
| `web/src/app/compare/page.tsx` | 2 | 18,23 |
| `web/src/app/page.tsx` | 1 | 8 |
| `web/src/app/projects/[name]/model/page.tsx` | 2 | 19,106 |
| `web/src/app/projects/[name]/page.tsx` | 1 | 18 |
| `web/src/app/projects/[name]/phases/page.tsx` | 1 | 19 |
| `web/src/app/projects/[name]/quality/page.tsx` | 1 | 19 |
| `web/src/app/projects/[name]/replay/[instance]/page.tsx` | 2 | 28,163 |
| `web/src/app/projects/[name]/replay/page.tsx` | 1 | 17 |
| `web/src/chart.test.ts` | 1 | 14 |
| `web/src/chart.ts` | 4 | 1-4,11,25,34 |
| `web/src/components/context-chart.tsx` | 2 | 13-17,88-91 |
| `web/src/components/project-header.tsx` | 2 | 3,14 |
| `web/src/components/said.tsx` | 2 | 3,6-9 |
| `web/src/components/setbacks.tsx` | 1 | 6 |
| `web/src/components/timeline.tsx` | 2 | 5-9,22 |
| `web/src/components/unavailable.tsx` | 2 | 5,26 |
| `web/src/format.test.ts` | 1 | 22 |
| `web/src/format.ts` | 6 | 1,11,15,22,27,36 |
| `web/src/labels.ts` | 6 | 1-4,16,27,38,52,59 |
| `web/src/loopback.ts` | 2 | 1-5,8 |
| `web/src/proxy.ts` | 1 | 5-9 |
| `web/src/timescale.test.ts` | 1 | 19 |
| `web/src/timescale.ts` | 4 | 1-4,6,9,14-18 |
| `web/src/app/globals.css` | 14 | 1,9,180,196,236,275,348,376,387,420,437,479,521,585 |

#### A6. Web developer-facing strings (Italian)

| Where | Kind | Count |
|---|---|---:|
| `web/src/chart.test.ts:8,18,25,33` | test title | 4 |
| `web/src/format.test.ts:6,12,19,29,37,42,49` | test title | 7 |
| `web/src/labels.test.ts:6` | test title | 1 |
| `web/src/loopback.test.ts:6,12` | test title | 2 |
| `web/src/timescale.test.ts:8,13,18,29` | test title | 4 |
| `web/e2e/compare.spec.ts:5,46` | test title | 2 |
| `web/e2e/model.spec.ts:5,20` | test title | 2 |
| `web/e2e/phases.spec.ts:5` | test title | 1 |
| `web/e2e/quality.spec.ts:5,53` | test title | 2 |
| `web/e2e/replay.spec.ts:5,35,45` | test title | 3 |
| `web/e2e/run.spec.ts:16,24,61,69,80,102,109,148,163,173,216,238` | test title | 12 |
| `web/e2e/run.spec.ts:178,217` | `test.skip` reason | 2 |
| `web/e2e/run.spec.ts:180,181,182` | `expect` message | 3 |
| `web/e2e/run.spec.ts:203` | process label (keep the prefixes) | 1 |
| `web/scripts/check-defenses.mjs:28,29,30,37,41,44,46,48,51,62,63,68,71,77,84,87,93,94,98,105,108,111` | check message | 22 |
| `web/scripts/standalone.mjs:16,27` | build message | 2 |

#### A7. Config and infra (Italian)

| Where | Kind | First ~60 chars |
|---|---|---|
| `pyproject.toml:49` | comment | Nessun pacchetto pubblicato da meno di due settimane: difes… |
| `pyproject.toml:59` | comment | testi in italiano con ×, – e simili |
| `pyproject.toml:100` | comment | Ogni pacchetto tranne gli ingressi, elencato a mano: un tes… |
| `pyproject.toml:75` | contract name | insights legge e basta: niente motore, niente Ledger, nient… |
| `pyproject.toml:98` | contract name | il motore non importa Django né il server: Django legge att… |
| `pyproject.toml:122` | contract name | il server legge e basta: niente motore, niente Ledger, nien… |
| `pyproject.toml:146` | contract name | il giudizio dipende solo dai contratti: niente motore, nien… |
| `Makefile:1-2,6` | comment | Alias di Taskfile.yml, l'ingresso unico dei comandi (ADR-00… |
| `mise.toml:1-2,10,12` | comment | Gli strumenti locali, con una versione sola (ADR-0034)… |
| `Taskfile.yml:3-6,86` | comment | L'ingresso unico dei comandi (ADR-0020, ADR-0039)… |
| `.gitignore:8-9,17,20` | comment | I materiali del cliente non si versionano, ovunque stiano… |
| `.env.example:1,3,5,6` | comment | Copia in .env. Non committare mai la chiave. |
| `docker/compose.yaml:1-5,8,22,28-30,34,38-39` | comment (13 lines) | Il cruscotto in Docker (ADR-0040): l'API Django e l'interfa… |
| `docker/server.Dockerfile:1-3,11,14,23` | comment | L'API del cruscotto (ADR-0040): Django in sola lettura… |
| `docker/web.Dockerfile:1-3,12,16,23-24` | comment | L'interfaccia del cruscotto (ADR-0040): la build standalone… |
| `docker/server.Dockerfile.dockerignore:1-2` | comment | Il contesto è la radice del repo, che contiene .env… |
| `docker/web.Dockerfile.dockerignore:1-2` | comment | Il contesto è la radice del repo, che contiene .env… |
| `spikes/sandbox_craft.sh:2-3` | comment | Collaudo ADR-0005: Craft e Blender in bwrap, senza rete… |
| `spikes/sandbox_craft.sh:21,23-25` | output string | ok / FAIL lines ("altre cartelle invisibili", "rete assente"…) |
| `web/tsconfig.json:16,18-19` | comment | Le prove unitarie girano con node --test… |
| `web/pnpm-workspace.yaml:1` | comment | Quarantena: nessun pacchetto pubblicato da meno di due sett… |
| `web/package.json:4` | description | L'interfaccia del cruscotto (ADR-0024, ADR-0033): solo lett… |

#### A8. Persisted Italian vocabulary (keep; CMT-008)

| Where | Values | Stored in or sent to |
|---|---|---|
| `src/agency/contracts/ticket.py:12-21` | TicketType: produzione, consulenza, revisione, ricerca, consegna, disaccordo, idea, schizzo, proposta | tickets.spec_json, `open_ticket` schema, packets, dashboard |
| `src/agency/contracts/ticket.py:40-45` | Medium: vettoriale, immagine, interfaccia, nessuno | tickets.spec_json, `open_ticket` schema |
| `src/agency/contracts/judgment.py:13-15` | Level: ordinario, buono, eccellente | judgments.level, `agency judge` answers |
| `src/agency/contracts/artifact.py:22-24` | Origin: consegna, presentazione, giudizio | artifacts.origin, `agency artifacts` output |
| `src/agency/insights/domain.py:21-23,27-28` | Measures: registro, tracce, nessuna; PhaseSource: registrata, ricavata | insights.sqlite columns (`SqliteProjection.SCHEMA`) |
| `src/agency/insights/compare.py:35-38` | Compared: entrambe, manca prima, manca dopo, nessuna | OpenAPI enum; web/src/app/compare/page.tsx:259-271 |
| `src/agency/insights/replay.py:32-34` | Alignment: per richiesta, per ordine, nessuna | OpenAPI enum; web/src/app/projects/[name]/replay/[instance]/page.tsx:23-24 |
| `src/agency/tools/surface.py:644,685,693`; `src/agency/graph/workflow.py:197,237,260,272,332`; `src/agency/ledger/models.py:135` | concept status: idea, schizzo, selezionata, in-sviluppo, proposta, scelta | concepts.status, the "Idee" lines of `agency report` |
| `src/agency/tools/surface.py:661,718-719,956` | result keys: passano, pagine, poi | tool results; operations.result_json, read back on resume |
| `src/agency/tools/surface.py:583,605-608,611,656,671,716`; `src/agency/graph/workflow.py:107,113,134,157-166,195,208-209,218-221,262`; `src/agency/tools/presentation.py:208,224,236`; `src/agency/cli.py:39` | file names: applicazioni.json, scheda.json, schizzi-/foglio-/schizzo-‹l›, reviews/valutazione.json, reviews/selezione.md, testi.json, tavola.png, schede.md, fogli/, proposta-‹l›.*, applicazioni-‹l›/, insieme-‹l›.png, presentazione.pdf, pagina-‹n›.png, source/segno.vectorcraft, exports/segno.svg | the work contract between the engine, prompts/** and the client deliverables |
| `src/agency/telemetry/fingerprint.py:28,39,41` | assente, non risponde | runs.fingerprint_json |
| `src/agency/evaluation/blind.py:23` | sì, si, no | accepted answers in `agency judge` |

#### A9. Italian fixture identifiers in tests (Nit; CMT-017)

Counts come from a heuristic (identifier-like string literals that are neither English words nor values used in src), so they are approximate.

| File | Uses | Main tokens |
|---|---:|---|
| `tests/test_sketch_flow.py` | about 103 | officina ×94, calore, sparisce, timbro, parola |
| `tests/test_runs.py` | about 34 | officina ×14, fantasma ×3, prova-muta-cli, prova-guasta-cli, prova-spia-cli ×3 each, comune, esplora |
| `tests/test_hardening.py` | about 21 | officina ×9, fantasma ×2, lavora ×2, altra-direzione, segreto, dentro |
| `tests/test_server.py` | about 21 | officina ×9, bottega ×3, fantasma ×2, in-memoria, scritto |
| `tests/test_agent_flow.py` | about 14 | forno ×6, req_blocco ×2, identici, uguale, corretta, req_tagliata |
| `tests/test_flow_view.py` | 12 | officina ×11, fantasma |
| `tests/test_quality_view.py` | 12 | officina ×11, fantasma |
| `tests/test_report_views.py` | 10 | officina ×9, fantasma |
| `tests/test_insights.py` | about 6 | oggi ×2, dati, appunti, segreto, illeggibile |
| `tests/test_behaviour_view.py` | 5 | officina ×4, fantasma |
| `tests/test_judgments.py` | about 5 | ottimo, forse, identici, sovrascritto |
| `tests/test_artifacts.py` | about 4 | alterata ×2, esadecimal, seconda |
| `tests/test_gateway.py`, `tests/test_doctor.py`, `tests/test_explicit_types.py` | 4 | chiave-finta, ciao, sk-ant-segreto, intermedio |
| `tests/test_compare_view.py` | 2 | illeggibile, nodi |
| `tests/dashboard_fixture.py` | 2 | officina-e2e, officina-prima (shared with web/e2e/project.ts:2,11) |
| `web/e2e/run.spec.ts:62`, `web/e2e/compare.spec.ts:61` | 2 | fantasma |

Proper names that stay: merlo, merlo3 and merlo4, real projects named in docs/02-ROADMAP.md (121 uses).

#### A10. Public Python API without a docstring (CMT-014)

[T] = tool-input model or enum in a tool schema: document only with `#`. [O] = in schemas/openapi.json: a docstring needs `task schemas`. [M] = migration, frozen.

| File | Missing | Items (line, name) |
|---|---:|---|
| `src/agency/agents/loop.py` | 1 | 37 AgentRunner |
| `src/agency/agents/prompts.py` | 4 | 17 skill_names(), 21 skills_index(), 40 packet(), 75 can_open() |
| `src/agency/agents/transcript.py` | 1 | 11 Transcript |
| `src/agency/artifacts/files.py` | 1 | 39 FileStore |
| `src/agency/artifacts/keeping.py` | 2 | 33 media_type(), 120 versions() |
| `src/agency/cli.py` | 1 | 296 main() |
| `src/agency/config.py` | 1 | 15 Settings |
| `src/agency/contracts/artifact.py` | 2 | 27 Blob, 38 ArtifactStore |
| `src/agency/contracts/concept.py` | 1 | 8 ConceptCard[T] |
| `src/agency/contracts/gate.py` | 1 | 16 GateKind |
| `src/agency/contracts/judgment.py` | 1 | 23 Rating |
| `src/agency/contracts/outcome.py` | 1 | 10 OutcomeState |
| `src/agency/contracts/phase.py` | 1 | 16 instance() |
| `src/agency/contracts/run.py` | 1 | 20 Fingerprint |
| `src/agency/contracts/ticket.py` | 5 | 11 TicketType[T], 24 Status, 33 Verdict[T], 39 Medium[T], 48 Action |
| `src/agency/doctor.py` | 2 | 29 Finding, 50 run_checks() |
| `src/agency/entrypoints/server/api.py` | 9 | 36 Problem[O], 61 registry_not_readable(), 68 provenance()[O], 73 projects()[O], 89 report()[O], 100 flow()[O], 111 behaviour()[O], 122 quality()[O], 150 replay()[O] |
| `src/agency/entrypoints/server/middleware.py` | 1 | 12 ReadOnly |
| `src/agency/entrypoints/server/schema.py` | 2 | 18 render(), 29 main() |
| `src/agency/entrypoints/server/serve.py` | 2 | 46 build(), 57 main() |
| `src/agency/evaluation/blind.py` | 4 | 30 Candidate, 35 candidates(), 64 comparison_id(), 111 interview() |
| `src/agency/gateway/client.py` | 4 | 29 CallContext, 38 ModelRequest, 48 ModelResponse, 82 ModelGateway |
| `src/agency/gateway/pricing.py` | 3 | 9 Price, 33 price_of(), 37 cost_usd() |
| `src/agency/graph/workflow.py` | 2 | 41 ProjectState, 64 build() |
| `src/agency/insights/adapters/projection.py` | 1 | 100 SqliteProjection |
| `src/agency/insights/adapters/registry.py` | 1 | 82 ReadOnlyRegistry |
| `src/agency/insights/adapters/stamps.py` | 1 | 10 stamp() |
| `src/agency/insights/adapters/traces.py` | 1 | 39 JsonlTraces |
| `src/agency/insights/adapters/transcripts.py` | 1 | 70 JsonlTranscripts |
| `src/agency/insights/application.py` | 3 | 57 rebuild(), 155 image(), 159 projects() |
| `src/agency/insights/behaviour.py` | 3 | 69 InstanceTurns[O], 78 BehaviourReport[O], 145 behaviour_report() |
| `src/agency/insights/compare.py` | 5 | 92 FingerprintDiff[O], 107 Vote[O], 117 BlindComparison[O], 124 CompareReport[O], 262 compare_report() |
| `src/agency/insights/domain.py` | 4 | 26 PhaseSource, 251 TranscriptImage, 338 project_calls(), 422 provenance() |
| `src/agency/insights/flow.py` | 3 | 100 FlowReport[O], 108 ticket_phase(), 197 flow_report() |
| `src/agency/insights/ports.py` | 7 | 63 TraceReading, 70 TranscriptReading, 77 RegistryReader, 89 TraceReader, 95 TranscriptReader, 111 ProjectionWriter, 117 ProjectionReader |
| `src/agency/insights/quality.py` | 4 | 41 CheckFailure[O], 52 ToolSummary[O], 71 QualityReport[O], 105 quality_report() |
| `src/agency/insights/replay.py` | 3 | 51 ReplayTool[O], 74 ReplayReport[O], 118 replay_report() |
| `src/agency/insights/sums.py` | 6 | 30 cost(), 34 minutes(), 38 measured(), 42 mean_duration_ms(), 47 median_ttft_ms(), 52 reasoning_tokens() |
| `src/agency/insights/views.py` | 7 | 22 RoleView[O], 42 TypeCost[O], 64 IdeaView[O], 72 JudgmentView[O], 100 TicketView[O], 120 ProjectReport[O], 215 project_report() |
| `src/agency/ledger/chain.py` | 1 | 13 digest() |
| `src/agency/ledger/migrations/versions/0001_baseline.py` | 2 | 266 upgrade()[M], 271 downgrade()[M] |
| `src/agency/ledger/migrations/versions/0002_runs.py` | 2 | 40 upgrade()[M], 45 downgrade()[M] |
| `src/agency/ledger/migrations/versions/0003_judgments.py` | 2 | 49 upgrade()[M], 54 downgrade()[M] |
| `src/agency/ledger/migrations/versions/0004_usage_measures.py` | 2 | 21 upgrade()[M], 26 downgrade()[M] |
| `src/agency/ledger/migrations/versions/0005_artifacts.py` | 2 | 47 upgrade()[M], 52 downgrade()[M] |
| `src/agency/ledger/models.py` | 4 | 20 TicketRow, 33 EventRow, 96 RenderRow, 107 DerivationRow |
| `src/agency/ledger/schema.py` | 5 | 45 Migration, 57 head(), 64 revision_of(), 81 ensure_current(), 112 migrate() |
| `src/agency/ledger/store.py` | 2 | 57 now(), 61 Ledger |
| `src/agency/qa/checks.py` | 3 | 18 CheckOutcome, 29 execute(), 60 run() |
| `src/agency/qa/delivery.py` | 9 | 37 matches(), 41 checks_for(), 49 exempted(), 114 expected(), 132 coverage_problems(), 140 evidence_problems(), 172 master_problems(), 205 delivery_problems(), 232 acceptance_problems() |
| `src/agency/qa/evidence.py` | 6 | 27 check_problem(), 35 is_independent(), 39 accepted(), 56 guard(), 68 record(), 124 freshness() |
| `src/agency/runtime.py` | 2 | 43 Session, 121 open_session() |
| `src/agency/telemetry/report.py` | 6 | 112 render_runs(), 132 render_comparison(), 165 render_artifacts(), 176 render_restored(), 184 render_damaged(), 190 render_provenance() |
| `src/agency/telemetry/setup.py` | 2 | 14 JsonlExporter, 36 configure() |
| `src/agency/tools/board.py` | 1 | 120 build() |
| `src/agency/tools/craft.py` | 1 | 27 Command |
| `src/agency/tools/files.py` | 2 | 13 inside(), 21 sha256() |
| `src/agency/tools/master.py` | 2 | 17 MediumSpec, 98 derivation_problem() |
| `src/agency/tools/presentation.py` | 5 | 44 font(), 49 Proposal, 95 Block, 102 Line, 221 proposal_files() |
| `src/agency/tools/render.py` | 2 | 24 render_one(), 74 contact_sheet() |
| `src/agency/tools/sandbox.py` | 2 | 16 Completed, 26 Sandbox |
| `src/agency/tools/surface.py` | 60 | 47 ToolContext, 90 Strict, 94 ReadFile[T], 100 ListFiles[T], 104 WriteFile[T], 109 ReadSkill[T], 114 ViewImage[T], 118 Render[T], 123 CraftSearch[T], 127 CraftDescribe[T], 131 CraftRun[T], 136 Compute[T], 140 ExportMaster[T], 146 RunCheck[T], 151 Observe[T], 158 Judge[T], 166 RecordRequirement[T], 173 OpenTicket[T], 187 TicketRef[T], 192 HandOff[T], 196 Deliver[T], 201 Block[T], 205 Lever[T], 209 Application[T], 214 PlanExploration[T], 226 BoardRating[T], 232 RateBoard[T], 236 SelectConcepts[T], 241 ProposalText[T], 249 PresentConcepts[T], 255 ConfirmPresentation[T], 259 RejectConcept[T], 264 Tool, 278 read_file(), 286 list_files(), 298 write_file(), 308 read_skill(), 328 view_image(), 359 render_tool(), 364 craft_search(), 368 craft_describe(), 375 craft_run(), 388 compute(), 397 export_master(), 407 run_check(), 424 observe(), 436 judge(), 464 record_requirement(), 480 open_ticket(), 520 accept_ticket(), 529 rework_ticket(), 537 hand_off(), 549 deliver(), 571 plan_exploration(), 664 select_concepts(), 740 reject_concept(), 755 block(), 862 role_tools(), 884 definition(), 895 Toolbox |

Breakdown: 34 [T], 26 [O], 10 [M], 158 plain.

#### A11. Exported TypeScript functions and components without JSDoc (CMT-015)

| Where | Name |
|---|---|
| `web/src/api/client.ts:59` | `api` (object of read functions) |
| `web/src/app/layout.tsx:13` | `Layout` |
| `web/src/app/not-found.tsx:3` | `NotFound` |
| `web/src/app/page.tsx:11` | `Projects` |
| `web/src/app/projects/[name]/page.tsx:13` | `generateMetadata` |
| `web/src/app/projects/[name]/phases/page.tsx:14` | `generateMetadata` |
| `web/src/app/projects/[name]/model/page.tsx:14` | `generateMetadata` |
| `web/src/app/projects/[name]/quality/page.tsx:14` | `generateMetadata` |
| `web/src/app/projects/[name]/replay/page.tsx:12` | `generateMetadata` |
| `web/src/app/projects/[name]/replay/[instance]/page.tsx:15` | `generateMetadata` |
| `web/src/chart.ts:21` | `line` |
| `web/src/format.ts:9,10,14,42` | `usd`, `count`, `share`, `when` |
| `web/src/labels.ts:45,46,47,48,70` | `status`, `pending`, `step`, `stop`, `outcome` |
