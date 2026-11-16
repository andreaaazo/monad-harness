# Il punto di partenza del gate

Che cosa trova il gate sul codice di oggi. È la misura da cui il repository va verso `full` verde: chi tocca un file lo
ripulisce tutto (§7.5), e nessuno ripulisce in blocco. Lo chiede il criterio A9 della [specifica](SPEC.md).

- **Quando.** 2026-11-16, sul commit `aeb5449`, con gli strumenti pinnati del gruppo `quality`.
- **Su che cosa.** 307 file Python: 139 in `src/`, 91 in `tests/` e 77 in `quality_gate/`. `legacy/` e
  `src/agency/qa/scripts/` sono esclusi (D4).
- **Fino a quando.** Il piano C la rifà dopo il passaggio del controllo di ogni giorno al gate, quando le tabelle
  condivise prendono la forma della §6 (piano B, B11).

## 1. Conteggi e durate per controllo

```bash
uv run python -m quality_gate full --format json
```

Esce con 1 in 165 s. I controlli che `full` non esegue sono `diff-coverage` e `lock-staged` (§7.5) e `mutation`, che
arriva con il piano C.

| Controllo | Esito | Violazioni | Secondi | Nota |
|---|---|---:|---:|---|
| `ruff-lint` | FAIL | 36 | 0,03 | con la tabella `[tool.ruff]` di oggi: le regole della §6.1 sono nella sezione 2 |
| `ruff-format` | FAIL | 67 | 0,03 | tutti file del gate: la radice chiede virgolette doppie ([DEVIATIONS 1](DEVIATIONS.md)) |
| `wps` | FAIL | 3901 | 1,98 | |
| `pydoclint` | FAIL | 1890 | 0,92 | |
| `basedpyright` | FAIL | 4086 | 7,23 | |
| `suppressions` | FAIL | 120 | 0,10 | sezione 7 |
| `import-contracts` | PASS | 0 | 0,11 | i 13 contratti di oggi |
| `dead-code` | FAIL | 70 | 0,51 | 68 sono probabili falsi positivi: sezione 8 |
| `dependencies` | PASS | 0 | 0,11 | |
| `duplication` | FAIL | 86 | 10,08 | |
| `tests` | PASS | 0 | 139,45 | 1604 prove, nessuna saltata |
| `coverage` | FAIL | 83 | 3,71 | sezione 4 |
| `shadow-config` | FAIL | 3 | 0,58 | per costruzione fino al passaggio (B3) |
| `config-lock` | FAIL | 1 | 0,00 | `lock missing`: il blocco lo genera Andrea (B3) |
| `hook-integrity` | FAIL | 3 | 0,00 | per costruzione fino al passaggio (B3) |
| `tool-versions` | PASS | 0 | 0,01 | |

Le violazioni per cartella:

| Controllo | `src/` | `tests/` | `quality_gate/` |
|---|---:|---:|---:|
| `ruff-lint` | 2 | 34 | 0 |
| `ruff-format` | 0 | 0 | 67 |
| `wps` | 1449 | 2452 | 0 |
| `pydoclint` | 1242 | 648 | 0 |
| `basedpyright` | 1365 | 2721 | 0 |
| `suppressions` | 18 | 102 | 0 |
| `dead-code` | 45 | 24 | 1 |
| `duplication` | 24 | 62 | 0 |
| `coverage` | 60 | 23 | 0 |

**La suite.** Sotto coverage, nel controllo `tests`, dura 139 s per 1604 prove. `<T_SUITE>` vale 107 s, misurato dal
piano A su 1423 prove. A6 dà a `changed` `<T_SUITE>` + 60 s, quindi il piano C misura di nuovo `<T_SUITE>` prima delle
prove dei tempi.

## 2. Ruff con le regole della §6.1

Fino al passaggio, `ruff-lint` e `ruff-format` leggono la tabella `[tool.ruff]` di oggi, che conta molto meno della
§6.1. I conteggi veri si prendono con la configurazione del gate, sugli stessi 307 file:

```bash
git ls-files '*.py' '*.pyi' | grep -v -E '^(legacy/|src/agency/qa/scripts/)' \
  | xargs uv run ruff check --no-cache --config quality_gate/ruff.toml --ignore-noqa --output-format json
git ls-files '*.py' '*.pyi' | grep -v -E '^(legacy/|src/agency/qa/scripts/)' \
  | xargs uv run ruff format --no-cache --check --config quality_gate/ruff.toml
```

L'elenco di `git ls-files` coincide con i file che il gate scopre. Con `--ignore-noqa` contano anche le righe con un
`noqa`.

- **`ruff check`:** 8638 violazioni, 3791 in `src/` e 4847 in `tests/`. In `quality_gate/` nessuna.
- **`ruff format`:** 207 file da riformattare. In `src/` sono 118 su 139, in `tests/` 89 su 91; in `quality_gate/`
  nessuno su 77.

Le dieci regole più frequenti:

| Regola | Violazioni | Che cosa chiede |
|---|---:|---|
| E501 | 4727 | righe di 80 colonne al massimo |
| D103 | 953 | una docstring per ogni funzione pubblica |
| DOC201 | 353 | la docstring documenta il valore restituito |
| TC001 | 258 | un import del progetto usato solo nei tipi va sotto `TYPE_CHECKING` |
| D205 | 216 | una riga vuota fra il sommario e la descrizione |
| D209 | 210 | le virgolette che chiudono una docstring su più righe stanno su una riga propria |
| D102 | 172 | una docstring per ogni metodo pubblico |
| TRY003 | 127 | un messaggio lungo sta nella classe dell'eccezione, non nel `raise` |
| PLR0917 | 123 | al massimo tre argomenti posizionali |
| TC003 | 108 | un import della libreria standard usato solo nei tipi va sotto `TYPE_CHECKING` |

I 36 rilievi della tabella di oggi sono E402 (import non in cima al modulo, 22), F401 (import inutilizzato, 12) e E731
(lambda assegnata a un nome, 2).

## 3. WPS e basedpyright

**WPS:** 3901 violazioni, 89 regole diverse.

| Regola | Violazioni | Che cosa chiede |
|---|---:|---|
| WPS221 | 923 | complessità di Jones di una riga non oltre 14 |
| WPS118 | 647 | nomi di 45 caratteri al massimo |
| WPS110 | 465 | niente nomi vaghi come `data`, `result` o `value` |
| WPS210 | 213 | al massimo cinque variabili locali |
| WPS111 | 147 | niente nomi troppo corti |
| WPS237 | 134 | niente f-string troppo complesse |
| WPS432 | 127 | niente numeri magici (nei test sono ammessi, eccezione (c)) |
| WPS407 | 103 | niente costanti di modulo mutabili |
| WPS204 | 81 | niente espressioni ripetute troppe volte |
| WPS430 | 80 | niente funzioni annidate |

**basedpyright:** 4086 violazioni, 29 regole diverse.

| Regola | Violazioni | Che cosa chiede |
|---|---:|---|
| `reportUnusedCallResult` | 759 | il risultato di una chiamata non resta inutilizzato |
| `reportUnknownVariableType` | 720 | ogni variabile ha un tipo noto |
| `reportUnknownMemberType` | 699 | ogni attributo ha un tipo noto |
| `reportAny` | 532 | niente `Any`, scritto o ereditato da una libreria |
| `reportUnknownArgumentType` | 329 | ogni argomento ha un tipo noto |
| `reportMissingTypeArgument` | 215 | un tipo generico ha i suoi argomenti (`list[str]`, non `list`) |
| `reportUnknownParameterType` | 197 | ogni parametro ha un tipo noto |
| `reportUnannotatedClassAttribute` | 147 | ogni attributo di classe è annotato |
| `reportImplicitRelativeImport` | 119 | niente import relativi impliciti: tutti nei test, come `from support.rules import …` |
| `reportUnknownLambdaType` | 59 | ogni lambda ha un tipo noto |

Tre violazioni sono cicli di import (`reportImportCycles`) in `src/agency/ledger/__init__.py`. basedpyright li segnala
senza una riga, e il gate li mette alla riga 1.

**pydoclint**, per completezza: 1890 violazioni, quasi tutte argomenti non documentati (DOC101 e DOC103, 583 ciascuna)
e valori restituiti non documentati (DOC201, 364).

## 4. La copertura di oggi

| Misura | Coperto | Totale | Mancante | Percentuale |
|---|---:|---:|---:|---:|
| Righe | 20203 | 20439 | 236 | 98,85% |
| Rami | 1975 | 2162 | 187 | 91,35% |
| Insieme, come la conta coverage | | | | 98% (98,13%) |

La soglia è 100%. Coverage misura 304 file: 224 sono coperti del tutto, 80 no. La riga `TOTAL` del rapporto è
`20439 236 2162 169 98%`, dove 169 sono le righe con un ramo coperto solo in parte. I rami mancanti, 187, sono la somma
dei rilievi `not-covered` del controllo.

Tre file scoperti non li importa nessuna prova (`never-imported`), e non entrano nei numeri sopra:
- `src/agency/context/__init__.py`, riservato al contesto visivo di M3: contiene solo la docstring;
- `src/agency/entrypoints/server/__main__.py`, cioè `python -m agency.entrypoints.server`;
- `tests/support/dashboard_fixture.py`, 391 righe, che le prove del cruscotto lanciano come programma
  ([ADR-0033](../adr/0033-il-cruscotto-next-js.md)).

## 5. I contratti di import-linter

**Attivi**, in `[tool.importlinter]`. Oggi sono tredici, e reggono tutti:
1. insights only reads: no engine, no Ledger, no engine libraries (ADR-0019);
2. the engine imports neither Django nor the server: Django reads through insights (ADR-0020);
3. the server only reads: no engine, no Ledger, no .env (ADR-0019);
4. the judgment depends only on the contracts: no engine, no registry (ADR-0027);
5. only the gateway imports anthropic: the API calls and the key stay in one place (ADR-0021), solo diretti;
6. no import cycles between sibling modules, at any depth (STR-004);
7. the slices do not import each other (ADR-0021);
8. the engine's layers: each imports only from the layers below (ADR-0057);
9. langgraph only in the process and the studio's graph adapters (ADR-0021, ADR-0058), solo diretti;
10. sqlmodel, sqlalchemy and alembic only in the ledger (ADR-0021), solo diretti;
11. only the composition roots reach the SQLite ledger: the session and the CLI (ADR-0058);
12. a domain depends only on the contracts: no other package of the engine, no module beside it (ADR-0021,
    ADR-0058);
13. domain and application import no framework and no adapter (ADR-0021, ADR-0058), solo diretti.

**I due della §6.5**, che aspettano il passaggio: «No import cycles between sibling modules» e «The gate and the
application do not import each other», con `root_packages = ["agency", "quality_gate"]`. Il codice di oggi li
rispetta: in una configurazione di prova con i soli due contratti, import-linter dice «2 kept, 0 broken». Entrano con
la tabella della §6.5, al passaggio (ADR-0060, punto 13).

**In attesa.** Sono le versioni con gli import indiretti dei quattro contratti «solo diretti» (D2, ADR-0060 punto 3).
Si aggiungono quando il codice le soddisfa (§6.5). Oggi tutte e quattro si rompono, con 16 coppie vietate:

| Contratto | Chi arriva, anche indirettamente, a che cosa |
|---|---|
| only the gateway imports anthropic | `agency.agents`, `agency.entrypoints` e `agency.process` ad `anthropic` (3) |
| langgraph only in the process and the studio's graph adapters | `agency.entrypoints` a `langgraph` e `langchain_core` (2) |
| sqlmodel, sqlalchemy and alembic only in the ledger | `agency.entrypoints` e `agency.process` a `sqlmodel`, `sqlalchemy` e `alembic` (6) |
| domain and application import no framework and no adapter | le applicazioni di `delivery`, `presentation` e `selection` a `PIL` (3), quelle di `presentation` e `selection` a `opentelemetry` (2) |

La misura: la sezione `[tool.importlinter]` copiata in un file di prova, senza le righe
`allow_indirect_imports = true`, poi

```bash
COLUMNS=1000 uv run lint-imports --no-cache --config <file di prova>
```

dice «9 kept, 4 broken».

## 6. Le eccezioni della §6.10

Ogni eccezione ha nel suo file un commento di una riga con il motivo. Fino al passaggio, quelle di Ruff stanno in
`quality_gate/ruff.toml`. Al passaggio vanno nella tabella `[tool.ruff]` di `pyproject.toml`, con i percorsi della
§6.1. Le differenze dalla specifica che non sono eccezioni, come la chiave di deptry, stanno in
[`DEVIATIONS.md`](DEVIATIONS.md).

| Tipo | Che cosa | Dove | Motivo |
|---|---|---|---|
| (a) | W191, E111, E114, E117, D206, D300, Q000–Q004, COM812, COM819 | `lint.ignore` di Ruff | le garantisce già il formatter, e Ruff sconsiglia di attivarle insieme a `ruff format` |
| (b) | nessuna | | finora nessuna coppia di regole Ruff e WPS si è rivelata impossibile da soddisfare insieme |
| (c) | S101, PLR2004 | `per-file-ignores` di Ruff, per `**/tests/**/*.py` e `**/conftest.py` | gli `assert` e i valori attesi letterali di pytest |
| (c) | WPS202, WPS226, WPS432, WPS442 | `per-file-ignores` di `.flake8`, per `tests/*.py`, `*/tests/*.py` e `*/conftest.py` | molti membri per modulo, stringhe ripetute, valori attesi, fixture con il nome di una funzione esterna; la riga `tests/*.py` è [DEVIATIONS 2](DEVIATIONS.md) |
| (d) | S404, S603 | `per-file-ignores` di Ruff, per `quality_gate/execution.py` | l'unico modulo autorizzato a lanciare processi |
| (e) | CPY001 | `lint.ignore` di Ruff | D5: il repository è privato e ha un solo proprietario (ADR-0060) |
| (f) | `legacy/**`, `src/agency/qa/scripts/**` | `[tool.quality_gate].exclude`, e `omit` di coverage (`legacy/*`, `src/agency/qa/scripts/*`) | D4: il backup congelato, e gli script di QA copiati e fissati per byte (ADR-0060) |

## 7. Le soppressioni

Il controllo `suppressions` conta 120 direttive, le stesse che aveva contato il piano A:

| Codice | Direttiva | `src/` | `tests/` | Totale |
|---|---|---:|---:|---:|
| SUP002 | `type: ignore` | 14 | 53 | 67 |
| SUP001 | `noqa` | 2 | 28 | 30 |
| SUP008 | `pytest.mark.skip`, `skipif` o `xfail` | 0 | 18 | 18 |
| SUP006 | `fmt: off`, `on` o `skip` | 2 | 3 | 5 |

Se ne vanno file per file: un file cambiato deve essere pulito per intero. Le righe `skipif` di oggi restano finché i
loro file non si toccano (ADR-0060, punto 12).

## 8. I probabili falsi positivi di vulture

Dei 70 rilievi di `dead-code`, 68 hanno confidenza 60%. Indicano codice che un framework o una libreria chiama per nome,
o che un decoratore registra: vulture non vede l'uso. Gli altri 2, al 100%, sono veri.

| Perché vulture non vede l'uso | Rilievi | Quali |
|---|---:|---|
| Un framework o una libreria li legge per nome | 47 | Django: le 8 impostazioni di `server/settings.py` e `urlpatterns`. Alembic: `down_revision` e `downgrade` delle 9 migrazioni (18). pytest: i 3 hook di `tests/conftest.py`, `session.exitstatus` e gli 8 `pytestmark`. pydantic-settings: `settings_customise_sources`. La libreria standard: `daemon_threads` (socketserver), `row_factory` (sqlite3, 2), `client_address` (http.server) e `StartElementHandler` (expat, nel gate). unittest.mock: `return_value` (2) |
| Un decoratore li registra | 13 | i validatori di pydantic (i tre `_absolute_*` di `config.py`, `_coherent`, `_contract`); l'handler di Django Ninja `registry_not_readable`; il listener di SQLAlchemy `pause` in `tests/test_ledger.py`; 6 fixture di pytest (`_no_dotenv`, `_no_operator_environment`, `own_data_folder`, `sandbox_scope_ready`, `no_gpu_probe`, `unfaked_studio`) |
| Campi e membri letti dalla serializzazione | 8 | campi di modelli pydantic e SQLModel (`sketch_ticket` due volte, `comment`, `modified_ns`, `first_at`, `first_look`); membri di un enum (`READING`, `REQUIREMENT`) |
| Argomenti inutilizzati, al 100% | 2 | `exitstatus` di `pytest_sessionfinish` (`tests/conftest.py:76`); `unfaked_studio`, chiesto solo per il suo effetto (`tests/test_judgments.py:521`). Sono veri: si correggono quando il file cambia |

**Il punto aperto.** La §6.6 vieta `ignore_names` e `ignore_decorators`. Per la §12 la soluzione è una modifica alla
specifica, non un'eccezione locale. Finché la specifica non cambia, `changed` fallisce su ogni modifica a uno dei 41
file che contengono uno dei 68. Fra questi ci sono `tests/conftest.py`, `src/agency/config.py`, le impostazioni di
Django, ogni migrazione e `quality_gate/checks/suite.py`. La decisione spetta ad Andrea, prima che il piano C faccia
passare dal gate il controllo di ogni giorno.
