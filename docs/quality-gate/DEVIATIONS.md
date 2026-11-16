# Differenze dalla specifica

Ogni differenza fra il repository e [`SPEC.md`](SPEC.md), con la sua prova. Per ciascuna:
- che cosa dice la specifica;
- che cosa fa il repository;
- perché è almeno altrettanto severo, oppure quale ADR cambia la specifica;
- la prova: un comando e il suo risultato.

Le decisioni dietro le differenze stanno in [ADR-0060](../adr/0060-il-quality-gate-parametri-decisioni-e-ordine.md).
I piani B e C di M1.8 aggiungono le loro.

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
