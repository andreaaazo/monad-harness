# Quality gate Python: specifica dello stato finale

Questo documento descrive **cosa deve esistere e come deve comportarsi** a lavoro finito. Non dice in che ordine costruirlo: la roadmap è tua. "DEVE" indica un requisito verificabile. I valori tra `<...>` sono parametri del repo (sezione 2).

---

## 1. Obiettivo

Il lavoro è finito quando valgono tutte e cinque queste proprietà.

| # | Proprietà | Come si verifica |
|---|---|---|
| P1 | **Un comando decide.** `<RUNNER> python -m quality_gate changed` esce 0 solo se: ogni file Python toccato rispetto a HEAD è pulito al 100% su tutti i check per file, ogni riga cambiata è coperta da test, la suite passa, i contratti di architettura reggono, la config del gate è intatta. | Sezione 11, A2–A4 |
| P2 | **Stesso giudizio su tutto il repo.** `full` applica gli stessi check a ogni file e pretende 100% di branch coverage. Oggi fallisce sul codice esistente: è previsto. | A2 |
| P3 | **Non si passa zittendo.** Nessun commento di soppressione ha effetto, nessun file di config alternativo viene letto, nessun tool mancante o in crash conta come superato. Una modifica al gate non arriva a un commit senza la tua approvazione esplicita. | A4, A5 |
| P4 | **Si applica da solo.** Dopo ogni modifica di un file (hook PostToolUse), a fine turno dell'agent (hook Stop), al commit (pre-commit) e in CI. | A5, A6 |
| P5 | **Il gate rispetta se stesso.** `quality_gate/` ha zero violazioni, 100% di branch coverage e mutation score ≥ 90%. | A3 |

**Fuori obiettivo:** sistemare il codice esistente. Nessun file applicativo o di test viene modificato.

---

## 2. Parametri del repo (da fissare prima di tutto)

| Parametro | Significato | Esempio |
|---|---|---|
| `<RUNNER>` | Prefisso per eseguire nell'ambiente di progetto | `uv run` |
| `<ENV_PY>` | Interprete dell'ambiente, relativo alla radice | `.venv/bin/python` |
| `<PY>` | Versione minima di Python (DEVE essere ≥ 3.11, serve `tomllib`) | `3.12` |
| `<PKGS>` | Package applicativi importabili | `myapp` |
| `<TESTS>` | Directory dei test applicativi | `tests` |
| `<BASE_BRANCH>` | Branch di riferimento in CI | `origin/main` |
| `<T_SUITE>` | Durata misurata della suite di test, in secondi | `40` |

---

## 3. Decisioni che spettano a te

| # | Decisione | Default proposto |
|---|---|---|
| D1 | Tool e config esistenti da rimuovere (black, isort, flake8 vecchio, mypy, pylint, `setup.cfg`…) | Rimuovere tutto ciò che il gate sostituisce |
| D2 | Contratti di architettura oltre a quelli fissi (6.5): `layers`, `independence`, `forbidden` | Solo quelli che il codice di oggi rispetta già |
| D3 | CI: quando `full` diventa bloccante | `changed` bloccante da subito, `full` solo report fino a fine pulizia |
| D4 | Percorsi esclusi (codice generato o di terze parti copiato nel repo) | Nessuno |
| D5 | Regola Ruff `CPY001` (intestazione di copyright in ogni file) | Ignorata |

---

## 4. File presenti a lavoro finito

```
pyproject.toml              tabelle di config (sezione 6) + gruppo di dipendenze "quality"
.flake8                     config di wemake-python-styleguide
.pre-commit-config.yaml     un hook locale
.gitignore                  + riga "mutants/"
.claude/settings.json       quattro hook
AGENTS.md                   regole per gli agent (testo in 10.4)
CLAUDE.md                   contiene la riga "@AGENTS.md"
Makefile (o task runner)    alias: gate, gate-full, gate-mutation, gate-lock
docs/quality-gate/
  SPEC.md                   questo documento
  DEVIATIONS.md             ogni differenza dalla specifica, con prova
  BASELINE.md               conteggi iniziali di "full" per check
quality_gate/
  __init__.py
  __main__.py               entry point
  cli.py                    argomenti, scelta del modo, exit code
  settings.py               lettura di [tool.quality_gate]
  model.py                  Status, Violation, CheckResult
  discovery.py              elenco dei file (7.2)
  execution.py              UNICO modulo che lancia processi (7.3)
  report.py                 output testo e JSON (7.6)
  checks/                   un modulo per check (7.4)
  integrity/                suppressions, shadow_config, config_lock, hook_integrity, tool_versions (sezione 8)
  hooks/                    guard, post_edit, stop, config_change (sezione 9)
  config.lock               hash della config (8.3)
  tests/                    test del gate
```

DEVE NON esistere, in nessuna directory: qualsiasi file della lista "config ombra" (8.2).

---

## 5. Dipendenze

Un gruppo di dipendenze di sviluppo chiamato `quality`, nel formato del package manager del repo. Ogni voce DEVE essere pinnata con `==`. Il lockfile DEVE essere aggiornato.

| Pacchetto | Ruolo | Generazione minima |
|---|---|---|
| `ruff` | lint + formato | recente, con `--ignore-noqa` e preview |
| `flake8`, `wemake-python-styleguide` | regole WPS | WPS ≥ 1.0 (compatibile con Ruff) |
| `pydoclint` | docstring complete | con le opzioni di 6.3 |
| `basedpyright` | tipi | con `typeCheckingMode = "all"` |
| `import-linter` | architettura | con contratto `acyclic_siblings` |
| `vulture` | codice morto | – |
| `deptry` | dipendenze | – |
| `pylint` | solo duplicazione | – |
| `pytest`, `pytest-randomly` | test | pytest ≥ 9.0 |
| `coverage` | copertura | ≥ 7 |
| `diff-cover` | copertura delle righe cambiate | – |
| `mutmut` | mutation testing | ≥ 3 |
| `pre-commit` | hook di commit | – |
| `types-*` | stub delle dipendenze non tipizzate | – |

DEVE NON essere installato: mypy, ty, black, isort, pytest-cov (la copertura la lancia il gate con `coverage run`).

---

## 6. Configurazione esatta

Regola generale: ogni tabella contiene **solo** le chiavi elencate. Qualsiasi chiave in più che escluda file, ignori regole o alzi soglie è vietata.

### 6.1 Ruff

```toml
[tool.ruff]
required-version = "==<pin>"
target-version = "py<PY senza punto>"
line-length = 80
preview = true

[tool.ruff.format]
quote-style = "single"            # stessa scelta della config di riferimento di WPS
docstring-code-format = true

[tool.ruff.lint]
select = ["ALL"]
preview = true
explicit-preview-rules = false    # ALL include anche le regole preview
ignore = [
  # (a) coperte dal formatter: Ruff stesso sconsiglia di attivarle insieme a "ruff format"
  "W191", "E111", "E114", "E117", "D206", "D300",
  "Q000", "Q001", "Q002", "Q003", "Q004", "COM812", "COM819",
  # (e) decisione D5
  "CPY001",
]

[tool.ruff.lint.per-file-ignores]
"**/tests/**/*.py" = ["S101", "PLR2004"]            # (c) assert e valori attesi letterali
"**/conftest.py" = ["S101", "PLR2004"]
"quality_gate/execution.py" = ["S404", "S603"]      # (d) unico modulo autorizzato a lanciare processi

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.pylint]
max-args = 4
max-positional-args = 3
max-branches = 8
max-returns = 4
max-statements = 30
max-bool-expr = 3
max-locals = 8
max-nested-blocks = 3
max-public-methods = 10

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"typing.cast".msg = "Fix the types instead of escaping them."
"typing.Any".msg = "Fix the types instead of escaping them."
"typing_extensions.Any".msg = "Fix the types instead of escaping them."

[tool.ruff.lint.flake8-type-checking]
strict = true

[tool.ruff.lint.isort]
known-first-party = ["<PKGS>", "quality_gate"]
```

Vietate: `exclude`, `extend-exclude`, `extend-ignore`, `extend-per-file-ignores`, `unfixable`, `external`, `task-tags`.

### 6.2 wemake-python-styleguide (`.flake8`)

```ini
[flake8]
select = WPS
max-line-length = 80
format = wemake
show-source = true
per-file-ignores =
    */tests/*.py: WPS202, WPS226, WPS432, WPS442
    */conftest.py: WPS202, WPS226, WPS432, WPS442
```

- WPS202 (troppi membri per modulo), WPS226 (stringa ripetuta), WPS432 (numero magico), WPS442 (nome che copre uno esterno: le fixture). Solo per i test.
- Nessuna soglia WPS viene ridefinita: i default sono già i più severi.
- Vietate: `ignore`, `extend-ignore`, `exclude`, `extend-exclude`, `max-*`, `i-control-code`, `noqa`-related.

### 6.3 pydoclint

```toml
[tool.pydoclint]
style = "google"
arg-type-hints-in-signature = true
arg-type-hints-in-docstring = false     # i tipi stanno solo nelle firme
check-return-types = false              # coerente con la riga sopra
check-yield-types = false
check-arg-order = true
check-arg-defaults = false
skip-checking-short-docstrings = false  # anche le docstring di una riga vengono controllate
skip-checking-raises = false
allow-init-docstring = false
check-class-attributes = true
ignore-private-args = false
ignore-underscore-only-args = true
ignore-private-class-attributes = true
treat-property-methods-as-class-attributes = false
require-return-section-when-returning-nothing = false
require-yield-section-when-yielding-nothing = true
should-document-star-arguments = true
check-style-mismatch = true
```

Vietate: `baseline`, `generate-baseline`, `auto-regenerate-baseline`, `exclude`.

Divisione dei compiti: Ruff `D` obbliga ad avere la docstring; pydoclint obbliga a documentare ogni argomento, ritorno, yield ed eccezione.

### 6.4 basedpyright

```toml
[tool.basedpyright]
typeCheckingMode = "all"
pythonVersion = "<PY>"
enableTypeIgnoreComments = false
failOnWarnings = true
reportIgnoreCommentWithoutRule = "error"
```

Vietate: qualsiasi `report* = ...` che abbassi una regola, `ignore`, `exclude`, `strict`, `allowedUntypedLibraries`, `executionEnvironments`, `baselineFile`. La tabella `[tool.pyright]` DEVE NON esistere.

### 6.5 import-linter

```toml
[tool.importlinter]
root_packages = ["<PKGS>", "quality_gate"]

[[tool.importlinter.contracts]]
name = "No import cycles between sibling modules"
type = "acyclic_siblings"
ancestors = ["<PKGS>", "quality_gate"]

[[tool.importlinter.contracts]]
name = "The gate and the application do not import each other"
type = "independence"
modules = ["<PKGS>", "quality_gate"]

# + contratti D2
```

- Vietate in ogni contratto: `ignore_imports`, `skip_descendants`, `allow_indirect_imports`.
- import-linter è globale e non ha ratchet. Quindi un contratto entra in config **solo se il codice di oggi lo rispetta**. Quelli che oggi sono violati vanno in `BASELINE.md` come "contratti in attesa" e si aggiungono quando il codice li soddisfa. Se oggi esistono cicli tra moduli fratelli di `<PKGS>`, `acyclic_siblings` parte solo su `quality_gate` e il package applicativo è il primo contratto in attesa.

### 6.6 vulture, deptry, pylint

```toml
[tool.vulture]
min_confidence = 0

[tool.deptry]
# nessuna chiave: regole di default, nessuna eccezione

[tool.pylint.main]
disable = ["all"]
enable = ["duplicate-code"]
jobs = 1

[tool.pylint.similarities]
min-similarity-lines = 4
ignore-comments = true
ignore-docstrings = true
ignore-imports = true
ignore-signatures = true
```

Vietate: `ignore_names`, `ignore_decorators`, `exclude` (vulture); `ignore`, `per_rule_ignores`, `exclude`, `extend_exclude` (deptry).

### 6.7 pytest e coverage

```toml
[tool.pytest]
minversion = "9.0"
strict = true                 # config, marker, id dei parametri e xfail in modalità strict
addopts = ["-ra"]
filterwarnings = ["error"]
testpaths = ["<TESTS>", "quality_gate/tests"]

[tool.coverage.run]
branch = true
source = ["."]
relative_files = true

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = true
exclude_lines = ['^\s*if TYPE_CHECKING:', '^\s*@(typing\.)?overload']
partial_branches = []
```

- `exclude_lines` e `partial_branches` **sostituiscono** i default di coverage. Effetto voluto: i commenti `pragma: no cover` e `pragma: no branch` smettono di funzionare del tutto.
- Nessun flag di coverage in `addopts`: romperebbe i test singoli e mutmut.
- `[tool.pytest.ini_options]` DEVE NON esistere.
- Vietate: `omit`, `include`, `exclude_also`, `[tool.coverage.paths]` (salvo `omit` per i percorsi D4).

### 6.8 mutmut

```toml
[tool.mutmut]
source_paths = ["<directory dei PKGS>", "quality_gate"]
do_not_mutate = ["*/tests/*"]
pytest_add_cli_args = ["-p", "no:randomly"]
mutate_only_covered_lines = false
```

Vietate: `only_mutate`, `do_not_mutate_patterns`, qualsiasi voce di `do_not_mutate` che non sia una directory di test.

### 6.9 Parametri del gate

```toml
[tool.quality_gate]
exclude = []                    # D4, glob relativi alla radice
env_passthrough = []            # variabili d'ambiente di cui i test hanno bisogno
check_timeout_seconds = 600
mutation_min_score = 0.90
```

### 6.10 Eccezioni ammesse (lista chiusa)

| Tipo | Cosa | Dove |
|---|---|---|
| (a) | Regole Ruff già garantite dal formatter | `lint.ignore` |
| (b) | Coppia Ruff/WPS che nessun codice può soddisfare insieme, dimostrata con un esempio minimo in `DEVIATIONS.md` | `lint.ignore` |
| (c) | Idiomi di pytest nei soli file di test | `per-file-ignores` di Ruff e WPS |
| (d) | Lancio di processi nel solo `quality_gate/execution.py` | `per-file-ignores` di Ruff |
| (e) | `CPY001`, se D5 conferma | `lint.ignore` |
| (f) | Percorsi D4 | `[tool.quality_gate].exclude`, `coverage omit` |

Ogni eccezione ha un commento di una riga con il motivo ed è elencata in `BASELINE.md`. Qualsiasi altra è una modifica alla specifica.

---

## 7. Il pacchetto `quality_gate`

### 7.1 Interfaccia

```
<RUNNER> python -m quality_gate <modo> [--format text|json]
```

| Modo | Cosa controlla |
|---|---|
| `file PATH...` | Check per file sui percorsi dati. Veloce: lo usa l'hook PostToolUse. |
| `staged` | Check per file sui file Python nell'indice git + integrità + `lock-staged`. Lo usa pre-commit. |
| `changed [--base REF]` | Il ratchet. Base di default: `HEAD`. |
| `full` | Tutto, su tutto. |
| `mutation` | mutmut + soglia. |
| `lock` | Rigenera `config.lock` (8.3). |
| `hook guard\|post-edit\|stop\|config-change` | Entry point degli hook (sezione 9). |

Exit code: `0` tutti i check PASS; `1` almeno un FAIL o ERROR; `2` errore d'uso o errore interno del gate. Fuori da un repository git: exit 2.

### 7.2 Quali file vede

- **File scoperti** = output di `git ls-files -z --cached --others --exclude-standard`, limitato ai file che esistono, con suffisso `.py` o `.pyi` (più i file eseguibili senza suffisso con shebang Python), meno i glob di `[tool.quality_gate].exclude`.
- Nessuna lista di directory scritta a mano: un file messo in una cartella nuova viene visto comunque.
- **File cambiati** (modo `changed`) = `git diff --name-only -z --diff-filter=ACMR <merge-base di REF e HEAD>` (confronto con l'albero di lavoro: include staged e unstaged) ∪ file non tracciati e non ignorati; il tutto ∩ file scoperti. Con repo senza commit: tutti i file scoperti.

### 7.3 Come lancia i tool

Tutte le regole valgono per ogni processo esterno.

- `shell=False`, lista di argomenti, directory di lavoro = radice del repo.
- L'eseguibile si risolve nella directory degli script dell'interprete corrente (`sysconfig.get_path("scripts")`), mai dal `PATH`.
- **Ambiente ripulito:** al processo passano solo `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`, `VIRTUAL_ENV`, le variabili di `env_passthrough` e quelle che il gate imposta da sé. Così `PYTEST_ADDOPTS`, `COVERAGE_RCFILE`, `RUFF_*`, `PYTHONPATH` e simili non possono cambiare il comportamento dei tool.
- **Config esplicita:** dove il tool lo permette, il file di config si passa a mano (`--config pyproject.toml`, `--config .flake8`, `-c pyproject.toml`, `--rcfile pyproject.toml`), così la ricerca automatica nelle sottocartelle è spenta.
- Cache disattivate (`--no-cache`, `-p no:cacheprovider`). I file temporanei (coverage, junit, report) vanno in una directory temporanea fuori dal repo.
- Timeout per check: `check_timeout_seconds`.
- **Fail closed:** eseguibile mancante, exit code non previsto, timeout, output non interpretabile → stato `ERROR`, che conta come fallimento.
- **Il verdetto viene dall'exit code, i dettagli dal parsing.** Se il tool dice "fallito" ma il parsing trova zero violazioni, il check resta FAIL e mostra l'output grezzo.

### 7.4 Catalogo dei check

Argomenti obbligatori oltre a quelli di 7.3. "PASS se" indica l'exit code del tool.

| Check | Comando | PASS se |
|---|---|---|
| `ruff-lint` | `ruff check --no-fix --ignore-noqa --output-format json <file>` | exit 0 |
| `ruff-format` | `ruff format --check <file>` | exit 0 |
| `wps` | `flake8 --disable-noqa --format default <file>` | exit 0 |
| `pydoclint` | `pydoclint --quiet <file>` | exit 0 |
| `basedpyright` | `basedpyright --pythonpath <interprete> --outputjson <file>` | exit 0 e `summary.errorCount == 0` e `warningCount == 0` |
| `suppressions` | interno (8.1) | zero occorrenze |
| `import-contracts` | `lint-imports --no-cache` | exit 0 |
| `dead-code` | `vulture <tutti i file scoperti>` | exit 0 (3 = codice morto trovato) |
| `dependencies` | `deptry .` con output JSON | exit 0 |
| `duplication` | `pylint --output-format json <tutti i file scoperti>` | exit 0 |
| `tests` | `coverage run -m pytest --junit-xml <tmp>` | exit 0 e integrità dei test (8.6) |
| `coverage` | `coverage json`, `coverage xml`, `coverage report` | 100% e insiemi di file coerenti (8.6) |
| `diff-coverage` | `diff-cover <xml> --compare-branch <REF> --fail-under 100 --include-untracked --json-report <tmp>` | exit 0; una riga con branch parziale conta come non coperta |
| `shadow-config` | interno (8.2) | nessun file vietato |
| `config-lock` | interno (8.3) | hash identici |
| `hook-integrity` | interno (8.4) | tutte le condizioni vere |
| `tool-versions` | interno (8.5) | versioni installate = pin |
| `lock-staged` | interno (8.3) | `config.lock` non nell'indice, oppure approvazione presente |
| `mutation` | `mutmut run`, poi `mutmut export-cicd-stats` | soglie di 7.5 |

### 7.5 Quali check in quale modo

| Check | `file` | `staged` | `changed` | `full` |
|---|---|---|---|---|
| ruff-lint, ruff-format, wps, pydoclint, basedpyright, suppressions | file dati | file nell'indice | file cambiati | tutti i file |
| import-contracts | – | – | sì | sì |
| dead-code | – | – | solo risultati dentro file cambiati | sì |
| duplication | – | – | solo blocchi che toccano un file cambiato | sì |
| dependencies | – | – | solo violazioni localizzate in file cambiati | sì (incluse dipendenze inutilizzate) |
| tests | – | – | sì | sì |
| coverage | – | – | solo coerenza degli insiemi di file | 100% + coerenza |
| diff-coverage | – | – | sì | – |
| shadow-config, config-lock, hook-integrity, tool-versions | – | sì | sì | sì |
| lock-staged | – | sì | – | – |

Regole del ratchet in `changed`:

- Un file cambiato DEVE essere pulito **per intero**, non solo nelle righe toccate.
- Se nessun file è cambiato: girano solo i quattro check di integrità.
- Se sono cambiati solo file `.md` o sotto `docs/`: i test non girano.
- I check su tutto il progetto (vulture, pylint, deptry) girano sempre sull'intero repo; il filtro si applica ai risultati.

Soglie di `mutation`, lette da `mutants/mutmut-cicd-stats.json`: `total > 0`, `killed / total ≥ mutation_min_score`, `no_tests == 0`, `skipped == 0`, `segfault == 0`, `check_was_interrupted_by_user == 0`. Timeout e sospetti contano come non uccisi.

### 7.6 Output

Formato testo, su stdout, ordine dei check fisso (quello di 7.4). Tutti i check girano sempre, anche dopo un fallimento.

```
quality-gate changed  base=HEAD  python-files=3
CHECK             STATUS  COUNT  SECONDS
ruff-lint         FAIL       12     0.41
ruff-format       PASS        0     0.08
basedpyright      ERROR       -    600.0
...
RESULT: FAIL  failed=1  errors=1  checks=17

== ruff-lint (12) ==
src/app/orders.py:10:5 D103 Missing docstring in public function
...
== basedpyright (ERROR) ==
timeout after 600s
```

- Stati possibili: `PASS`, `FAIL`, `ERROR`. Non esiste "saltato": un check non previsto dal modo non compare.
- Una violazione per riga: `percorso:riga:colonna CODICE messaggio`, ordinata per percorso e riga.
- `--format json`: oggetto con `mode`, `base`, `result`, e `checks[]` con `name`, `status`, `seconds`, `violations[]` (`path`, `line`, `column`, `code`, `message`), `raw`.
- Negli hook l'output è troncato alle prime 40 violazioni per check, più il totale per codice.

---

## 8. Livello anti-aggiramento

### 8.1 Scansione delle soppressioni

Si applica al **testo grezzo** di ogni file scoperto (non solo ai commenti: alcuni tool riconoscono la direttiva anche dentro una stringa). Confronto senza distinzione tra maiuscole e minuscole. File non decodificabile in UTF-8: FAIL.

| Espressione vietata | Chi la onorerebbe |
|---|---|
| `\bnoqa\b` | Ruff, flake8, vulture, pydoclint |
| `type:\s*ignore` | type checker |
| `pyright:` | basedpyright (ignore di riga e direttive di file come `basic` o `reportX=false`) |
| `pragma:\s*no\s*(cover\|branch\|mutate)` | coverage, mutmut |
| `pylint:\s*\w` | pylint |
| `fmt:\s*(off\|on\|skip)` | ruff format |
| `isort:\s*\w` | ordinamento import di Ruff |
| `pytest\.mark\.(skip\|skipif\|xfail)` | pytest |
| `(pytest\|unittest)\.(skip\|xfail\|importorskip\|SkipTest)` | pytest |
| `collect_ignore`, `pytest_collection_modifyitems`, `pytest_ignore_collect`, `pytest_plugins` | pytest |

Divieto totale, nessuna lista di eccezioni. Lo scanner costruisce le espressioni da frammenti, così non segnala se stesso, e non è escluso dalla scansione.

### 8.2 Config ombra

Il check percorre il **filesystem** sotto la radice (non `git ls-files`: un file ignorato da git viene letto lo stesso dai tool), escludendo `.git/` e l'ambiente virtuale. Fallisce se trova:

| Tool | File o sezione vietati |
|---|---|
| Ruff | `ruff.toml`, `.ruff.toml`; `[tool.ruff]` in un `pyproject.toml` non di radice |
| flake8 | `.flake8` non di radice; `[flake8]` in `setup.cfg` o `tox.ini` |
| basedpyright | `pyrightconfig.json`, `basedpyrightconfig.json`, `.basedpyright/` (baseline), `[tool.pyright]` |
| pytest | `pytest.ini`, `.pytest.ini`, `pytest.toml`, `.pytest.toml`; `[pytest]` o `[tool:pytest]` in `tox.ini`/`setup.cfg`; `[tool.pytest.ini_options]` |
| coverage | `.coveragerc`; `[coverage:*]` in `setup.cfg`/`tox.ini` |
| pylint | `pylintrc`, `.pylintrc`, `pylintrc.toml`, `.pylintrc.toml`; `[pylint*]` in `setup.cfg`/`tox.ini` |
| import-linter | `.importlinter`; `[importlinter*]` in `setup.cfg` |
| mutmut | `[mutmut]` in `setup.cfg` |
| pydoclint | qualsiasi file di baseline |

L'elenco definitivo si costruisce dalla documentazione di ogni tool nella versione pinnata.

### 8.3 Blocco della config (`quality_gate/config.lock`)

**Cosa garantisce, esattamente:** non che i file non possano essere modificati, ma che ogni modifica al gate diventi una differenza visibile in un solo file, che non entra in un commit senza la tua approvazione.

Contenuto (JSON, chiavi ordinate, newline finale):

```json
{
  "schema": 1,
  "tables": { "tool.ruff": "<sha256>", "tool.pyright": "absent" },
  "files": { ".flake8": "<sha256>", "quality_gate/cli.py": "<sha256>" }
}
```

- **Tabelle di `pyproject.toml`:** `tool.ruff`, `tool.basedpyright`, `tool.pyright`, `tool.pydoclint`, `tool.importlinter`, `tool.vulture`, `tool.deptry`, `tool.pylint`, `tool.pytest`, `tool.coverage`, `tool.mutmut`, `tool.diff_cover`, `tool.quality_gate`, più il gruppo di dipendenze `quality`.
  - Hash = SHA-256 di `json.dumps(valore, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` in UTF-8, dopo lettura con `tomllib`.
  - Tabella assente = stringa `"absent"`. Aggiungerne una è quindi una differenza.
  - Le sezioni di dipendenze e build normali restano modificabili.
- **File (hash dei byte):** `.flake8`, `.pre-commit-config.yaml`, `.claude/settings.json`, `AGENTS.md`, `CLAUDE.md`, e ogni file sotto `quality_gate/` secondo la scoperta di 7.2, tranne `config.lock`. Un file in più o in meno è una differenza.
- **Check `config-lock`:** FAIL se il lock manca, non è leggibile o differisce in qualsiasi voce. L'output elenca le voci diverse.
- **Modo `lock`:** rifiuta di girare se
  - stdin o stdout non sono un terminale interattivo,
  - la variabile `CLAUDECODE` è presente nell'ambiente (è quella che Claude Code imposta nei suoi comandi),
  - uno tra `shadow-config`, `hook-integrity`, `tool-versions` fallisce.

  Poi mostra le voci aggiunte, rimosse e cambiate e chiede di digitare `LOCK`.
- **Check `lock-staged`** (solo pre-commit): FAIL se `quality_gate/config.lock` è nell'indice e `QUALITY_GATE_LOCK_CHANGE_OK=1` non è nell'ambiente. Il commit di un lock nuovo si fa quindi con `QUALITY_GATE_LOCK_CHANGE_OK=1 git commit`.

### 8.4 Integrità degli hook

Il check fallisce se una di queste è falsa:

- `.claude/settings.json` contiene `"disableAllHooks": false` e le quattro registrazioni di 9.1.
- `.claude/settings.local.json`, se esiste, è JSON valido, non contiene `disableAllHooks: true`, non contiene la chiave `hooks`, non definisce in `env` variabili che iniziano con `QUALITY_GATE_` né `CLAUDECODE`.
- `~/.claude/settings.json`, se esiste, non definisce in `env` variabili `QUALITY_GATE_*` né `CLAUDECODE`.
- `.git/hooks/pre-commit` esiste ed è quello installato da pre-commit (solo fuori dalla CI).

### 8.5 Versioni dei tool

Per ogni pacchetto del gruppo `quality`: `importlib.metadata.version()` DEVE coincidere con il pin. Pin non esatto, pacchetto mancante o versione diversa: FAIL.

### 8.6 Integrità dei test e della copertura

Dal report JUnit (check `tests`):

- test raccolti > 0;
- saltati = 0, xfail = 0 (struttura: vale per qualsiasi modo di saltare un test, non solo per quelli elencati in 8.1);
- nessun errore di raccolta.

Dal report JSON di coverage (check `coverage`):

- ogni file eseguito sotto la radice è un file scoperto. Un modulo nascosto in un percorso ignorato da git, ma importato, fa fallire il check;
- in `full`: ogni file scoperto compare nel report. Un file mai importato conta 0%;
- in `full`: copertura totale di righe e branch = 100%.

### 8.7 Tipi

- `typing.cast` e `Any` sono vietati da Ruff (`banned-api`), che risolve anche gli alias (`import typing as t`).
- Gli accessi indiretti (`getattr(typing, "cast")`) producono un valore di tipo sconosciuto, che basedpyright in modo `all` rifiuta.

---

## 9. Hook di Claude Code

### 9.1 `.claude/settings.json` (contenuto completo)

```json
{
  "disableAllHooks": false,
  "hooks": {
    "PreToolUse": [
      { "matcher": "*",
        "hooks": [{ "type": "command", "timeout": 10,
          "command": "cd \"$CLAUDE_PROJECT_DIR\" && <ENV_PY> -m quality_gate hook guard || exit 2" }] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [{ "type": "command", "timeout": 120,
          "command": "cd \"$CLAUDE_PROJECT_DIR\" && <ENV_PY> -m quality_gate hook post-edit || exit 2" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "timeout": <2 × T_SUITE + 120>,
          "command": "cd \"$CLAUDE_PROJECT_DIR\" && <ENV_PY> -m quality_gate hook stop || exit 2" }] }
    ],
    "ConfigChange": [
      { "matcher": "project_settings|local_settings",
        "hooks": [{ "type": "command", "timeout": 10,
          "command": "cd \"$CLAUDE_PROJECT_DIR\" && <ENV_PY> -m quality_gate hook config-change || exit 2" }] }
    ]
  }
}
```

Il `|| exit 2` è obbligatorio: per Claude Code solo l'exit code 2 blocca; un hook che termina con 1 (interprete mancante, eccezione) verrebbe ignorato. Con `|| exit 2` ogni guasto dell'hook blocca.

Tutti gli hook leggono un oggetto JSON da stdin. JSON non valido o campo mancante: exit 2.

### 9.2 `hook guard` (PreToolUse)

Modalità manutenzione = variabile `QUALITY_GATE_MAINTENANCE=1` nell'ambiente del processo Claude Code.

Ordine di valutazione:

1. **Sempre vietato, anche in manutenzione:** comando Bash che esegue `git commit` o `git push`; comando che invoca il modo `lock`.
2. **In manutenzione:** tutto il resto è permesso.
3. **In modalità normale** valgono le regole sotto. Blocco = exit 2 con una riga su stderr che dice quale regola e cosa fare ("fermati e chiedi ad Andrea").

Percorsi protetti (dopo `realpath`, quindi anche tramite link simbolici):

- `quality_gate/**`, `.flake8`, `.pre-commit-config.yaml`, `AGENTS.md`, `CLAUDE.md`
- `.claude/**`, `~/.claude/**`, `.git/**`, `.basedpyright/**`
- qualsiasi file con un nome della lista 8.2, in qualsiasi directory

| Tool | Regola |
|---|---|
| `Read`, `Grep`, `Glob` | Sempre permessi |
| `Write`, `Edit`, `MultiEdit`, `NotebookEdit` | Vietati se `file_path`/`notebook_path` è un percorso protetto |
| Gli stessi, su `pyproject.toml` | Il guard calcola il contenuto risultante (per `Write` è `content`; per `Edit` applica `old_string`→`new_string`) e vieta se cambierebbe l'hash di una tabella bloccata (8.3) o se il risultato non è TOML valido |
| `Bash` | Vietato se `command` corrisponde a una riga della tabella sotto |
| Qualsiasi altro tool (inclusi `mcp__*`) | Vietato se un valore stringa di `tool_input`, letto come percorso, è protetto |

Comandi Bash vietati in modalità normale:

| Cosa contiene il comando | Motivo |
|---|---|
| `--no-verify`, `core.hooksPath`, `git config`, `SKIP=`, `pre-commit uninstall` | Aggirano l'hook di commit |
| `QUALITY_GATE_`, `CLAUDECODE` | Manipolano le variabili del gate |
| `claude` come comando | Sessione annidata con ambiente diverso |
| `--add-noqa`, `--writebaseline`, `--baselinefile`, `--baseline`, `--generate-baseline`, `--make-whitelist` | Creano soppressioni o baseline |
| Un percorso protetto o un nome della lista 8.2 | Modifica indiretta dei file del gate |

Unica eccezione all'ultima riga: il comando coincide per intero con un'invocazione ammessa del gate, cioè `<RUNNER> python -m quality_gate (file …|changed [--base REF]|full|mutation) [--format …]` o un alias del task runner.

Il filtro sui comandi Bash è un ostacolo, non una garanzia: una shell può sempre offuscare. La garanzia è in 8.3 e nella sezione 12.

### 9.3 `hook post-edit` (PostToolUse)

1. Legge `tool_input.file_path`. Se non è un file scoperto (7.2): exit 0.
2. Esegue su quel solo file `ruff check --fix --ignore-noqa` (solo correzioni sicure) e poi `ruff format`.
3. Esegue il modo `file` su quel file.
4. Tutto pulito: exit 0, nessun output. Altrimenti: exit 2, con l'output troncato (7.6) su stderr.

### 9.4 `hook stop` (Stop)

1. Esegue il modo `changed`.
2. PASS: azzera il contatore della sessione, exit 0.
3. FAIL: incrementa il contatore in `.git/quality-gate/stop-<session_id>`.
   - Contatore ≤ 5: exit 2 con riepilogo e violazioni troncate su stderr. L'agent deve continuare.
   - Contatore > 5: exit 0 e stampa su stdout `{"systemMessage": "Quality gate ancora in errore dopo 5 tentativi: <riepilogo>"}`. Tu vedi l'avviso; il commit resta bloccato da pre-commit.

### 9.5 `hook config-change` (ConfigChange)

In modalità normale: exit 2 su ogni modifica a `.claude/settings.json` o `.claude/settings.local.json` avvenuta durante la sessione. In manutenzione: exit 0. Serve perché Claude Code ricarica i file di impostazioni mentre la sessione è aperta.

---

## 10. Collegamenti

### 10.1 pre-commit (`.pre-commit-config.yaml`, contenuto completo)

```yaml
repos:
  - repo: local
    hooks:
      - id: quality-gate
        name: quality gate (staged)
        entry: <RUNNER> python -m quality_gate staged
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

I check su tutto il progetto restano fuori dal commit: le violazioni del codice esistente bloccherebbero ogni commit.

### 10.2 CI (se esiste)

| Job | Comando | Blocca |
|---|---|---|
| ratchet | `python -m quality_gate changed --base <BASE_BRANCH>` da checkout pulito | Sì, da subito |
| full | `python -m quality_gate full` | Secondo D3 |
| mutation | `python -m quality_gate mutation`, una volta a settimana | Solo report |

### 10.3 Task runner

Alias: `gate` (changed), `gate-full`, `gate-mutation`, `gate-lock`.

### 10.4 `AGENTS.md` (testo)

```markdown
# Agent rules

## Quality gate

- A task is done only when `<RUNNER> python -m quality_gate changed` exits 0. Run it before you say you are finished.
- Touching a Python file means owning it: fix every violation in that file, not only the lines you changed.
- Every line you change must be executed by a test, on both sides of every branch.
- Never silence a check: no noqa, type-ignore, pyright or pylint directives, coverage or mutation pragmas, formatter or import-sorting switches, skipped or expected-to-fail tests.
- Never use `typing.cast` or `Any`. Fix the types.
- Never create or edit `quality_gate/`, `.flake8`, `.pre-commit-config.yaml`, `.claude/`, `AGENTS.md`, `CLAUDE.md`, the quality tables or the `quality` dependency group in `pyproject.toml`, or any other config file for a quality tool.
- Do not game the limits: no splitting a function only to get under a threshold, no parameter objects without meaning, no docstrings that restate the name. Change the design.
- If a rule looks wrong for a specific case, stop and ask Andrea. Do not work around it.
- Never run `git commit` or `git push`. Andrea commits.

## Maintainer (Andrea only)

- Maintenance session: start Claude Code with `QUALITY_GATE_MAINTENANCE=1 claude`.
- After any change to the gate: `make gate-lock` in your own terminal, then `QUALITY_GATE_LOCK_CHANGE_OK=1 git commit`.
- Tool upgrades: one tool at a time, new exact pin, run `full`, review the new rules, re-lock.
```

`CLAUDE.md` contiene `@AGENTS.md`.

---

## 11. Criteri di accettazione

**A1. Installazione.** Tutti i pacchetti della sezione 5 pinnati con `==`, lockfile aggiornato, `tool-versions` PASS.

**A2. Esecuzione.** `full` esegue tutti i check, stampa il riepilogo ed esce 1 sul repo di oggi. `changed` su albero pulito esce 0.

**A3. Il gate rispetta se stesso.** `file` su ogni file di `quality_gate/`: zero violazioni. Copertura di `quality_gate/`: 100% righe e branch. `mutation` limitato a `quality_gate/`: soglie rispettate.

**A4. Canarini.** Per ogni riga: si crea un file temporaneo con quella sola violazione, si esegue il modo indicato, il check indicato DEVE essere FAIL. Poi si elimina tutto.

| Violazione introdotta | Modo | Check che deve fallire |
|---|---|---|
| Funzione pubblica senza docstring | file | ruff-lint |
| Docstring che non documenta un argomento | file | pydoclint |
| Codice segnalato solo da WPS | file | wps |
| File non formattato | file | ruff-format |
| Annotazione `Any` | file | ruff-lint e basedpyright |
| `cast(...)` tramite alias `import typing as t` | file | ruff-lint |
| Commento `noqa` | file | suppressions |
| Direttiva `pyright:` a inizio file | file | suppressions |
| Stringa che contiene `pragma: no cover` | file | suppressions |
| Test con marker skip | changed | suppressions |
| Test saltato a runtime senza usare i nomi vietati | changed | tests |
| Ciclo di import tra due moduli fratelli | changed | import-contracts |
| Funzione mai usata in un file cambiato | changed | dead-code |
| Blocco copiato di 4+ righe in un file cambiato | changed | duplication |
| Import di un pacchetto non dichiarato | changed | dependencies |
| Ramo non testato in un file cambiato | changed | diff-coverage |
| File `.py` in una nuova directory di primo livello | changed | check per file (viene visto) |
| Modulo in percorso ignorato da git, importato dai test | changed | coverage |
| `ruff.toml` in una sottocartella | changed | shadow-config |
| `pyrightconfig.json` in radice | changed | shadow-config |
| Una soglia modificata in `[tool.ruff.lint.pylint]` | changed | config-lock |
| File aggiunto in `quality_gate/` | changed | config-lock |
| Pin di un tool cambiato senza reinstallare | changed | tool-versions |
| `settings.local.json` con `disableAllHooks: true` | changed | hook-integrity |
| `settings.local.json` con `env.QUALITY_GATE_MAINTENANCE` | changed | hook-integrity |
| Eseguibile di un tool reso irraggiungibile | file | quel check in stato ERROR, exit 1 |
| `PYTEST_ADDOPTS="-k niente"` nell'ambiente | changed | nessun effetto: stesso risultato di prima |
| `config.lock` nell'indice senza approvazione | staged | lock-staged |

**A5. Hook.** Verifica inviando JSON di esempio su stdin a ogni comando.

| Ingresso | Atteso |
|---|---|
| guard, `Edit` su file applicativo | exit 0 |
| guard, `Write` su `quality_gate/cli.py` | exit 2 |
| guard, `Edit` di `pyproject.toml` che aggiunge una dipendenza normale | exit 0 |
| guard, `Edit` di `pyproject.toml` che tocca `[tool.ruff]` | exit 2 |
| guard, `Write` di `src/ruff.toml` | exit 2 |
| guard, Bash `git commit -m x` | exit 2 |
| guard, Bash con `sed -i ... .flake8` | exit 2 |
| guard, Bash `<RUNNER> python -m quality_gate changed` | exit 0 |
| guard, tool `mcp__x__write` con percorso protetto | exit 2 |
| guard, stdin non JSON | exit 2 |
| guard in manutenzione, `Write` su `quality_gate/cli.py` | exit 0 |
| guard in manutenzione, Bash `git push` | exit 2 |
| post-edit, file pulito | exit 0, file invariato |
| post-edit, file con violazione non correggibile | exit 2, violazione su stderr |
| stop, albero pulito | exit 0 |
| stop, violazione presente, tentativi 1–5 | exit 2 |
| stop, sesto tentativo | exit 0 con `systemMessage` |
| config-change in modalità normale | exit 2 |
| modo `lock` senza terminale | rifiuto, exit 2 |

**A6. Tempi (budget).** `hook guard` ≤ 300 ms. `file` su un file ≤ 15 s. `staged` su 10 file ≤ 30 s. `changed` ≤ `<T_SUITE>` + 60 s.

**A7. Pulizia.** `git status` mostra solo i file della sezione 4. Nessun canarino rimasto. Nessun file applicativo o di test modificato.

**A8. Blocco.** `config.lock` generato da te con il modo `lock`; `config-lock` PASS.

**A9. Documenti.** `DEVIATIONS.md` con ogni differenza e la sua prova. `BASELINE.md` con: conteggi e durate per check, le 10 regole più frequenti per Ruff, WPS e basedpyright, copertura attuale, contratti attivi e in attesa, tutte le eccezioni di 6.10, candidati falsi positivi di vulture.

---

## 12. Limiti noti (non risolvibili in locale)

| Limite | Cosa lo copre |
|---|---|
| Un agent con una shell può riscrivere `config.lock` o i file del gate con comandi offuscati | Il lock cambiato non entra in un commit senza `QUALITY_GATE_LOCK_CHANGE_OK=1`, e i commit li fai solo tu: guarda sempre il diff di `config.lock` |
| Dopo 5 stop bloccati l'agent può fermarsi con il gate rosso | Avviso a schermo; pre-commit e CI restano rossi |
| vulture senza whitelist dà falsi positivi con framework che chiamano il codice per nome | Elencati in `BASELINE.md`; la soluzione è una modifica alla specifica, non un'eccezione locale |
| Un test può eseguire una riga senza verificarne il risultato | `mutation` settimanale |
| "Chi tocca un file lo ripulisce tutto" rende costosa ogni piccola modifica a un file vecchio | Voluto: è il meccanismo che porta il repo verso `full` verde |

---

## 13. Da confermare sulla versione pinnata

Questi punti dipendono dalla versione esatta dei tool. Regola: se il comportamento reale è diverso, si adotta l'equivalente **almeno altrettanto severo** e lo si scrive in `DEVIATIONS.md`.

1. **Ruff:** se `S603`/`S404` scattano davvero su `execution.py` (altrimenti l'eccezione (d) si toglie); elenco aggiornato delle regole in conflitto col formatter.
2. **WPS:** che non segnali le virgolette singole; eventuali coppie Ruff/WPS inconciliabili (candidata: `ISC003`).
3. **basedpyright:** nome esatto di `failOnWarnings`; percorso della baseline; che `--outputjson` con una lista di file usi la config di radice.
4. **pytest:** chiavi della tabella nativa `[tool.pytest]` e di `strict`.
5. **coverage:** che `source = ["."]` non misuri l'ambiente virtuale; che `partial_branches = []` sostituisca i default.
6. **diff-cover:** flag per trattare i branch parziali come non coperti (`--branch-coverage` nelle versioni recenti). Se manca, il check lo calcola da `coverage.json`.
7. **mutmut:** nomi delle chiavi (sono cambiati dentro la serie 3.x) e posizione del file di statistiche.
8. **import-linter:** disponibilità di `acyclic_siblings` e sintassi TOML di `layers`.
9. **pydoclint:** exit code e nomi delle opzioni rinominate.
10. **Claude Code:** campi di `MultiEdit` e `NotebookEdit`; che un hook `ConfigChange` con exit 2 impedisca davvero di applicare la modifica; presenza di `CLAUDECODE` nell'ambiente dei comandi; campo `stop_hook_active`.
