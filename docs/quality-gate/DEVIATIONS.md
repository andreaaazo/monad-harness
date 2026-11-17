# Differenze dalla specifica

Ogni differenza fra il repository e [`SPEC.md`](SPEC.md), con la sua prova. Per ciascuna:
- che cosa dice la specifica;
- che cosa fa il repository;
- perché è almeno altrettanto severo, oppure quale ADR cambia la specifica;
- la prova: un comando e il suo risultato.

Le decisioni dietro le differenze stanno in [ADR-0060](../adr/0060-il-quality-gate-parametri-decisioni-e-ordine.md).
Le voci 1–5 vengono dal piano A di M1.8, le 6–19 dal piano B; il piano C aggiunge le sue.

## 1. Due file di configurazione temporanei, fino al passaggio

- **Specifica.** I file della §8.2, fra cui `ruff.toml` in una sottocartella e `pyrightconfig.json`, non devono
  esistere (§4).
- **Repository.** Fino al passaggio del controllo di ogni giorno al gate (piano C) ce ne sono due:
  - `quality_gate/ruff.toml` tiene la §6.1 per i file del gate, e il `ruff check .` di oggi la applica a quei file;
  - `pyrightconfig.json`, alla radice, tiene la configurazione di pyright di oggi. basedpyright 1.40.2 rifiuta un
    `pyproject.toml` con sia `[tool.pyright]` sia `[tool.basedpyright]` («cannot have both `pyright` and
    `basedpyright` sections»). Senza configurazione, poi, non segnala nulla. `uv run pyright` legge questo file prima
    di `pyproject.toml`, quindi il Taskfile e i suoi test non cambiano.
- **Perché.** Le tabelle di Ruff e di pyright sono condivise con il `task check` di oggi. Con le regole severe lì
  dentro, il controllo di ogni giorno diventerebbe rosso su tutto `src/` e `tests/` (ADR-0060, punto 13). Il gate
  passa sempre `--config pyproject.toml` a Ruff e `--project pyproject.toml` a basedpyright, quindi nessuno dei due
  file indebolisce i suoi controlli. Il passaggio li cancella tutti e due, e da lì in poi `shadow-config` li vieta.
- **Fino al passaggio.** Proprio perché il gate legge la configurazione di Ruff alla radice, che oggi chiede virgolette
  doppie, il gate lanciato sul suo stesso codice fallisce `ruff-format` su ogni file del gate. Gli altri cinque controlli
  per file passano, ma `ruff-lint` applica le regole blande di oggi: fino al passaggio, questa esecuzione non prova nulla
  sulla §6.1. Le regole e il formato della §6.1 li verificano `ruff check quality_gate` e
  `ruff format --check quality_gate`, che leggono `quality_gate/ruff.toml`. Dal passaggio in poi, il gate sul suo codice
  deve uscire con 0.
- **Prova** (2026-11-16):
  - con le due tabelle nello stesso `pyproject.toml`,
    `uv run basedpyright --outputjson src/agency/contracts` stampa sei volte l'errore citato e conta 0 errori;
  - dopo lo spostamento, `uv run pyright --verbose` stampa «Loading configuration file at …/pyrightconfig.json» e
    0 errori;
  - `uv run basedpyright --project pyproject.toml --outputjson src/agency/contracts` conta 41 errori, con regole del
    solo modo `all` come `reportAny` e `reportExplicitAny`;
  - `uv run ruff check --show-settings quality_gate/model.py` mostra `linter.line_length = 80`,
    `formatter.quote_style = single` e `linter.preview = enabled`: le regole della §6.1 valgono per i file del gate.
    Il file nomina le regole invece di darne il codice, perché la regola di anteprima RUF201 di Ruff controlla anche
    questo file e vuole i nomi. I codici restano nei commenti, e il significato è lo stesso.

## 2. L'eccezione (c) di `.flake8` raggiunge anche `tests/`

- **Specifica.** La §6.2 scrive `*/tests/*.py: WPS202, WPS226, WPS432, WPS442` per i soli file di test.
- **Repository.** `.flake8` ha anche la riga `tests/*.py`, con gli stessi codici.
- **Perché.** flake8 legge un modello che contiene `/` come relativo alla cartella della configurazione, quindi
  `*/tests/*.py` diventa `<radice>/*/tests/*.py`. Copre `quality_gate/tests/`, ma non `tests/` alla radice, che è
  `<TESTS>`. La riga aggiunta porta l'eccezione (c) proprio nella cartella che la specifica intende, e in nessun altro
  file.
- **Prova** (2026-11-16):
  `uv run flake8 --config .flake8 --format default --no-show-source tests/test_taskfile.py | awk '{print $2}' | grep -c -E "WPS(202|226|432|442)"`
  - con la sola riga della specifica stampa 11 (WPS202 una volta, WPS226 sei volte, WPS432 quattro volte);
  - con la riga aggiunta stampa 0.

## 3. Un file di test corretto prima del passaggio

- **Specifica.** A7 vuole che nessun file applicativo o di test cambi, oltre alle eccezioni decise all'inizio di
  M1.8.
- **Repository.** `tests/test_server.py` è cambiato in `c032194`. `test_django_owns_no_model_and_no_database` leggeva
  `settings.DATABASES["default"]`, che Django riempie solo quando configura le connessioni la prima volta: passava solo
  se un altro test le aveva già toccate. Ora chiede il motore a `connections["default"]`.
- **Perché.** pytest-randomly, che la specifica installa (§5), mescola l'ordine dei test e ha fatto emergere il
  difetto. Senza la correzione il controllo `tests` fallirebbe a caso. Il test verifica ancora la stessa cosa: con un
  database SQLite l'espressione nuova vede `django.db.backends.sqlite3`, e l'asserzione fallisce.
- **Prova.** Prima della correzione,
  `uv run pytest -p no:randomly "tests/test_server.py::test_django_owns_no_model_and_no_database"` falliva con
  `KeyError: 'default'`. Dopo passa da solo, e passa su `tests/test_server.py` con `--randomly-seed` 1, 2 e 3.

## 4. git si trova nel `PATH`

- **Specifica.** La §7.3 vuole che ogni eseguibile si risolva nella cartella degli script dell'interprete
  (`sysconfig.get_path("scripts")`), mai dal `PATH`.
- **Repository.** `quality_gate/execution.py` cerca così gli strumenti Python. git lo cerca nel `PATH` dell'ambiente
  ripulito, con `shutil.which("git", path=...)`. Senza `PATH`, o con un `PATH` vuoto, git manca e il gate dà errore.
- **Perché.** git non è un pacchetto Python e non può stare nell'ambiente virtuale. Il rischio che la §7.3 chiude, un
  finto strumento di qualità messo prima nel `PATH`, resta chiuso: nessuno strumento Python arriva dal `PATH`. Un
  finto git potrebbe nascondere dei file alla scoperta. È un limite della §12: una shell può sempre offuscare, e il
  commit resta di Andrea (ADR-0060, punto 14).
- **Prova** (2026-11-16), in `quality_gate/tests/test_execution.py`:
  - `test_a_tool_never_comes_from_path`: uno strumento che c'è solo in una cartella del `PATH` dà
    `missing executable`;
  - `test_git_comes_from_path`: `git --version` risponde dal `PATH`;
  - `test_git_missing_from_path_is_a_failure`: senza `PATH`, con un `PATH` vuoto o con uno che non contiene git, il
    risultato è `missing executable: git`.

## 5. isort è installato

- **Specifica.** La §5 vuole pylint nel gruppo `quality`, solo per la duplicazione, e vieta di installare isort.
- **Repository.** isort 9.0.2 è installato, perché pylint 4.1.3 lo dichiara come dipendenza propria.
- **Perché.** È una contraddizione interna alla §5: con pylint, isort arriva per forza. Nessuno lo esegue. Il gate non
  lo lancia, nessun compito del Taskfile lo usa, e l'ordine degli import lo controlla Ruff. Il rischio che il divieto
  chiude, una seconda configurazione dell'ordinamento che contraddice Ruff, oggi non esiste: nel repository non c'è né
  una tabella `[tool.isort]` né un `.isort.cfg`. L'elenco della §8.2 non nomina isort; se aggiungerlo fra le
  configurazioni ombra lo decide il piano B.
- **Prova** (2026-11-16): `uv tree --invert --package isort` stampa `isort v9.0.2`, poi `pylint v4.1.3`, poi
  `design-agency-harness v0.1.0 (group: quality)`.

## 6. I test del gate fanno commit, ma solo nei repository temporanei

- **Specifica.** Non dice come provare `changed`. CLAUDE.md vieta all'assistente ogni commit nel repository.
- **Repository.** I test di `changed` costruiscono una storia: creano un repository temporaneo sotto `tmp_path` e ci
  fanno commit con `commit_all` (`quality_gate/tests/conftest.py`), attraverso `Runner.git` e con
  `-c commit.gpgsign=false`. Nel repository del progetto non scrivono mai.
- **Perché.** `changed` confronta con la merge-base di un riferimento e di `HEAD`: senza commit non c'è nulla da
  confrontare. La regola di CLAUDE.md protegge la storia del progetto, e un repository temporaneo non ne ha. Andrea l'ha
  lasciato all'esecuzione («You make the decisions», piano B, B2).
- **Prova.** `quality_gate/tests/test_changes.py`: ogni test parte da `repository`, una cartella sotto `tmp_path` con il
  suo `git init`.

## 7. git riceve `GIT_INDEX_FILE`, e un timeout ferma tutto il gruppo di processi

- **Specifica.** La §7.3 passa ai processi solo le variabili elencate e quelle di `env_passthrough`, e ferma un
  controllo al suo timeout.
- **Repository.**
  - **`GIT_INDEX_FILE`.** `Runner.git` aggiunge la variabile, se il gate la ha. Nessun altro strumento la riceve.
  - **Il timeout.** Ogni processo parte in una sessione propria, e a un timeout il gate uccide l'intero gruppo di
    processi.
  - **L'output.** Va su file in una cartella temporanea fuori dal repository.
- **Perché.**
  - Dentro un hook di commit git può usare un indice temporaneo: `staged` deve leggere quello, non l'indice di sempre.
  - Prima, uno strumento che avvia altri processi (basedpyright avvia node) lasciava vivi i figli dopo il timeout
    (revisione finale del piano A).
  - Entrambe le scelte sono più severe, o uguali, a quanto chiede la §7.3.
- **Prova** (2026-11-16), in `quality_gate/tests/test_execution.py`:
  - `test_git_sees_the_index_variable`: git risponde con l'indice indicato;
  - `test_tools_never_see_the_index_variable`: un finto strumento non vede la variabile;
  - `test_a_timeout_kills_the_process_group`: il figlio di uno strumento fermato dal timeout non scrive più il suo file.

## 8. Nel blocco, un file assente vale `"absent"`

- **Specifica.** La §8.3 marca `"absent"` una tabella che manca, così che aggiungerla sia una differenza. Per i file
  dice solo che un file in più o in meno è una differenza.
- **Repository.** Anche un file bloccato che manca vale `"absent"`. Il gruppo di dipendenze `quality` è bloccato con la
  chiave `dependency-groups.quality`. Il documento del blocco sta in `quality_gate/integrity/lockfile.py`, il controllo
  in `quality_gate/integrity/config_lock.py`.
- **Perché.** Fino al piano C mancano `.pre-commit-config.yaml`, `.claude/settings.json` e `AGENTS.md`: con
  `"absent"`, crearli è una differenza visibile, come per le tabelle.
- **Prova** (2026-11-16): `test_absent_tables_and_files_are_marked` e `test_a_file_added_to_the_gate_fails`
  (`quality_gate/tests/test_config_lock.py`). Sul repository, oggi, `config-lock` dà FAIL con `lock missing`.

## 9. `hook-integrity` fallisce anche con `core.hooksPath`

- **Specifica.** La §8.4 chiede che `.git/hooks/pre-commit` esista e sia quello installato da pre-commit.
- **Repository.** `hook-integrity` fallisce anche quando `git config --get core.hooksPath` trova un valore, a qualunque
  livello della configurazione di git.
- **Perché.** Con `core.hooksPath` impostato git non esegue mai `.git/hooks/pre-commit`: l'hook ci sarebbe, ma il commit
  lo salterebbe. È più severo della §8.4. Un hook è di pre-commit se contiene la riga
  `# ID: 138fd403232d2ddd5efb44317e38bf03`, che pre-commit 4.7.0 scrive in ogni hook che installa.
- **Prova** (2026-11-16): `test_a_hooks_path_fails` e `test_a_foreign_pre_commit_hook_fails`
  (`quality_gate/tests/test_hook_integrity.py`). Sul repository, oggi, `hook-integrity` dà FAIL per tre ragioni:
  manca `.claude/settings.json`, manca l'hook di pre-commit e `core.hooksPath` vale `.githooks`. Tutte e tre se ne
  vanno con il passaggio del piano C (ADR-0061).

## 10. deptry: il pacchetto del motore, il filtro e il verdetto

- **Specifica.** La §6.6 vuole `[tool.deptry]` senza chiavi, e la §7.3 trae il verdetto dal codice d'uscita.
- **Repository.**
  - **La chiave.** `[tool.deptry]` ha una sola chiave, `known_first_party = ["agency"]`.
  - **Il filtro.** Il gate tiene solo le segnalazioni in un file scoperto o in `pyproject.toml`, e scarta DEP004 in un
    file di test.
  - **Il verdetto.** Il controllo `dependencies` giudica dalle segnalazioni rimaste. Le uscite 0 e 1 sono entrambe
    attese; ogni altra, o un rapporto illeggibile, è un errore.
- **Perché.**
  - Senza la chiave, deptry non trova `agency` nel layout `src/` e lo segnala 408 volte come dipendenza transitiva di
    sé stesso. La chiave non esclude nulla.
  - deptry analizza tutto l'albero: `legacy/` (D4) dà 49 segnalazioni che il gate non deve vedere.
  - deptry scarta da solo solo la cartella `tests/` alla radice, quindi pytest in `quality_gate/tests` dà 11 DEP004.
  - Se il gate scarta tutte le segnalazioni, deptry è comunque uscito con 1: il codice d'uscita da solo darebbe un FAIL
    sbagliato.
- **Prova** (2026-11-16):
  - sul repository, `dependencies` dà PASS: delle 67 segnalazioni di deptry, nessuna resta;
  - in `quality_gate/tests/test_dependencies_check.py`: `test_findings_outside_discovery_are_dropped`,
    `test_dep004_in_test_files_is_dropped`, `test_filtered_findings_pass`, e il canarino
    `test_an_undeclared_import_fails`.

## 11. pylint: niente cache, e i blocchi letti per modulo

- **Specifica.** La §7.3 spegne le cache. La §7.5 tiene in `changed` solo i blocchi duplicati che toccano un file
  cambiato.
- **Repository.**
  - pylint gira con `--persistent n`.
  - Il gate risale dal nome di modulo di un blocco al suo file, come pylint nomina i moduli: il percorso a punti dalla
    prima cartella senza `__init__.py`.
- **Perché.** pylint scrive le sue statistiche in `~/.cache/pylint` se non glielo si vieta. Per un blocco duplicato dà
  solo i nomi di modulo, e il suo campo `path` indica l'ultimo file letto, non quelli duplicati.
- **Prova** (2026-11-16): `test_module_names_follow_packages`, `test_duplicate_blocks_become_violations` e il
  canarino `test_a_copied_block_is_found` (`quality_gate/tests/test_duplication.py`).

## 12. `env_passthrough`: due variabili per la sandbox

- **Specifica.** La §7.3 passa ai processi solo poche variabili fisse, più quelle di `env_passthrough`, che il
  repository decide.
- **Repository.** `env_passthrough = ["XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"]`.
- **Perché.** La sandbox di ADR-0046 lancia `systemd-run --user`, che senza queste due variabili non raggiunge la
  sessione dell'utente. Non è una deviazione: è il valore che la specifica lascia al repository, misurato.
- **Prova** (2026-11-16):
  - con le sole variabili fisse, le prove della sandbox si fermano: `systemd-run` scrive «$DBUS_SESSION_BUS_ADDRESS
    and $XDG_RUNTIME_DIR not defined»;
  - con le due variabili, l'intera suite passa: 1429 test, nessuno saltato;
  - il controllo `tests` del gate, sul repository, dà PASS: 1562 test in 119,7 s sotto coverage, nessuno saltato.

## 13. Il controllo `tests` legge JUnit con `expat`, e l'uscita 5 è un fallimento

- **Specifica.** La §8.6 chiede al rapporto JUnit almeno un test raccolto, nessun test saltato o atteso in errore, e
  nessun errore di raccolta.
- **Repository.**
  - **Lettura.** Il rapporto si legge con `xml.parsers.expat`.
  - **I test.** Ogni test fallito o saltato è una violazione col suo nome, e un rapporto senza test ne dà una.
  - **L'uscita 5** di pytest, «nessun test raccolto», conta come fallimento leggibile: il rapporto lo dice.
  - **Un errore di raccolta** fa uscire pytest con 2, che è un errore del controllo.
- **Perché.** Ruff, in modo ALL, rifiuta `xml.etree` come parser di XML non fidato (S314, S405), e sopprimere la regola
  non è ammesso. `expat` è il parser a eventi su cui `xml.etree` poggia, e il file è quello di pytest, nella cartella
  temporanea del gate.
- **Prova:** `quality_gate/tests/test_suite.py`, con i canarini `test_a_runtime_skip_fails_the_suite` (un test
  saltato con `SkipTest` importato sotto un altro nome) e `test_pytest_addopts_does_not_reach_pytest`.

## 14. `coverage` giudica dal JSON, non dal codice d'uscita

- **Specifica.** La §7.3 trae il verdetto dal codice d'uscita. La §7.5 chiede al controllo `coverage`, in `changed`, solo
  la coerenza degli insiemi di file, e in `full` anche il 100%.
- **Repository.**
  - **Il verdetto.** Il controllo esegue `coverage json`, `xml` e `report` e giudica dal JSON. Le uscite 0 e 2 sono
    entrambe attese; ogni altra, o la mancanza di dati, è un errore.
  - **Le violazioni.** Sono tre:
    - `not-discovered`: un file misurato che il gate non vede;
    - `never-imported`: un file scoperto che nessun test importa, gli stub `.pyi` esclusi. In `full` vale per ogni
      file, in `changed` per i file cambiati (voce 18);
    - `not-covered`, solo in `full`: righe o rami mancanti.
- **Perché.** Sotto `fail_under = 100` coverage esce con 2 in tutti e tre i comandi, anche quando ha scritto il
  rapporto. Il codice d'uscita farebbe fallire `changed` per la copertura totale, che in `changed` non va giudicata.
- **Prova** (2026-11-16): sul repository, dopo la suite, `coverage` dà PASS in `changed` e FAIL in `full`, con 80 file
  non coperti del tutto e 3 mai importati. In `quality_gate/tests/test_covered.py`: `test_coherent_sets_pass_in_changed`
  e il canarino `test_an_ignored_module_fails_coherence`.

## 15. diff-cover: `--format json:` e `--branch-coverage`, nessun file di configurazione

- **Specifica.** La §7.4 scrive `--json-report <tmp>`. La §13.6 cerca il modo di contare i rami parziali come non
  coperti.
- **Repository.** diff-cover gira con:
  - `--format json:<tmp>/diff-cover.json`;
  - `--branch-coverage`;
  - nessun `-c`.
- **Perché.**
  - diff-cover 10.6.0 ha sostituito `--json-report` con `--format json:<percorso>`.
  - `--branch-coverage` tratta i rami parziali come righe non coperte.
  - diff-cover legge un file di configurazione solo con `-c`. Con `-c pyproject.toml`, senza una tabella
    `[tool.diff_cover]`, si fermerebbe con un errore.
- **Prova:**
  - l'aiuto di diff-cover 10.6.0, e il suo `config_parser.py`, che legge un file solo se `config_file` è dato;
  - in `quality_gate/tests/test_covered.py`, il canarino `test_an_untested_branch_fails_diff_coverage`.

## 16. `changed` senza commit, e senza prove da eseguire

- **Specifica.** La §7.5 elenca per `changed` i controlli `tests`, `coverage` (la sola coerenza dei file) e
  `diff-coverage`, e dice che quando cambiano solo file `.md` o sotto `docs/` i test non girano. Non dice che cosa fare
  in un repository senza commit.
- **Repository.**
  - **Senza commit** non c'è una base da confrontare, e ogni file scoperto conta come cambiato. I controlli sul
    progetto non si filtrano. `coverage` chiede anche il 100%, come in `full`. `diff-coverage` non gira.
  - **Con soli documenti cambiati** non girano `tests`, `coverage` e `diff-coverage`: i due controlli di copertura
    leggono i dati che scrive la suite.
  - Un controllo che il modo non esegue non compare nel rapporto.
- **Perché.** Senza una base, diff-cover non ha righe cambiate da leggere. Ogni riga è nuova, quindi il 100% di
  `coverage` chiede su tutto il repository quello che `diff-coverage` chiederebbe sulle righe cambiate: è almeno
  altrettanto severo.
- **Prova** (2026-11-16), in `quality_gate/tests/test_modes.py`:
  - `test_without_a_commit_everything_has_changed`: in un repository senza commit girano tutti i controlli di `full`, e
    un file che nessuna prova importa fa fallire `coverage` con `never-imported`;
  - `test_docs_only_skips_the_suite`: con un `README.md` e un `docs/x.md` cambiati, i tre controlli non compaiono.

## 17. In `changed` conta ogni percorso cambiato, anche cancellato

- **Specifica.**
  - La §7.2 definisce i file cambiati con `git diff --diff-filter=ACMR`, uniti ai non tracciati e intersecati con i
    file scoperti.
  - La §7.5 fa girare solo l'integrità quando nessun file è cambiato, e salta i test quando sono cambiati solo file
    `.md` o sotto `docs/`. Un file `.md` però non è mai fra i file scoperti: questa seconda regola parla di tutti i
    percorsi.
- **Repository.**
  - I controlli per file girano sui file cambiati e scoperti, come vuole la §7.2.
  - «Nulla è cambiato» e «solo documenti» si decidono da tutti i percorsi cambiati, di qualunque tipo, cancellazioni
    comprese.
  - `git diff` gira senza filtro e con `--no-renames`: una rinomina conta come il vecchio percorso cancellato più il
    nuovo aggiunto.
- **Perché.**
  - Con `ACMR` una cancellazione non era un cambiamento. Se l'unica modifica era cancellare un modulo che la suite
    importa, `changed` faceva girare solo l'integrità.
  - Una cancellazione accanto a un `.md` saltava la suite come «solo documenti», e lo stesso valeva per un modulo
    rinominato dentro `docs/`.
  - Letta alla lettera, la §7.2 farebbe girare solo l'integrità anche quando cambia soltanto `pyproject.toml`.
  - Ogni scelta qui fa girare più controlli, mai meno (revisione finale del piano B).
- **Prova** (2026-11-17):
  - `test_untracked_and_unstaged_files_count` e `test_a_rename_counts_both_paths`, in
    `quality_gate/tests/test_changes.py`: un file cancellato è nell'elenco, e una rinomina dà entrambi i percorsi;
  - `test_a_deletion_runs_the_suite`, in `quality_gate/tests/test_modes.py`: un modulo cancellato accanto a un
    `NOTES.md` fa girare `tests`, `coverage` e `diff-coverage`.

## 18. In `changed`, un file cambiato che nessuna prova importa fallisce `coverage`

- **Specifica.** In `changed` la §7.5 chiede a `coverage` solo la coerenza degli insiemi di file. Le righe cambiate le
  giudica `diff-coverage`.
- **Repository.** In `changed`, ogni file cambiato e scoperto che coverage non ha misurato è `never-imported`, come in
  `full`. Uno stub `.pyi` non conta. Uno script senza suffisso, scoperto per lo shebang, conta.
- **Perché.**
  - Con `source = ["."]`, coverage cerca da solo i file mai eseguiti solo nelle cartelle con `__init__.py`, e `src/`
    non ne ha uno.
  - diff-cover salta un file su cui non ha dati: «No lines with coverage information in this diff».
  - Un modulo nuovo che nessuna prova importa passava così `tests`, `coverage` e `diff-coverage` senza che una sola
    sua riga girasse. È più severo della §7.5 (revisione finale del piano B).
- **Prova** (2026-11-17):
  - `test_a_changed_module_nothing_imports_fails`, in `quality_gate/tests/test_covered.py`: un file cambiato che nessun
    test importa fallisce, uno non cambiato no;
  - `test_a_never_imported_file_fails_in_full`: anche uno script senza suffisso;
  - `test_a_new_top_level_folder_is_seen`, in `quality_gate/tests/test_modes.py`: il modulo nuovo in una cartella nuova
    fallisce `coverage` con `never-imported`.

## 19. Le impostazioni di Claude Code non possono impostare `CI`

- **Specifica.** La §8.4 vieta alle impostazioni locali e a quelle dell'utente di impostare in `env` le variabili
  `QUALITY_GATE_*` e `CLAUDECODE`.
- **Repository.** `hook-integrity` vieta in `env` anche `CI`.
- **Perché.** Il gate legge `CI` per non controllare l'hook di commit, che in CI non c'è. Se le impostazioni di Claude
  Code impostassero `CI`, ogni comando lanciato dall'assistente lo erediterebbe, e `hook-integrity` smetterebbe di
  guardare `.git/hooks/pre-commit`. Ogni variabile che il gate ascolta merita lo stesso divieto. È più severo della
  §8.4 (revisione finale del piano B).
- **Prova** (2026-11-17): `test_local_settings_cannot_set_gate_variables[CI]`, in
  `quality_gate/tests/test_hook_integrity.py`.
