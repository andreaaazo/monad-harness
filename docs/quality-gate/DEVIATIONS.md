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
- **Prova** (2026-11-16):
  - con le due tabelle nello stesso `pyproject.toml`,
    `uv run basedpyright --outputjson src/agency/contracts` stampa sei volte l'errore citato e conta 0 errori;
  - dopo lo spostamento, `uv run pyright --verbose` stampa «Loading configuration file at …/pyrightconfig.json» e
    0 errori;
  - `uv run basedpyright --project pyproject.toml --outputjson src/agency/contracts` conta 41 errori, con regole del
    solo modo `all` come `reportAny` e `reportExplicitAny`;
  - per `quality_gate/ruff.toml`, la prova arriva con il Task 3 del piano A.

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
