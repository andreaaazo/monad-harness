# ADR-0045: una radice dei dati, e `.env` solo per i segreti

**Contesto.** La radice dei dati, cioè la cartella di registro, tracce, trascrizioni e artefatti, non aveva un
proprietario (STR-001 e DX-003, riprodotti il 2026-11-07):
- il motore leggeva `AGENCY_DATA_DIR` dall'ambiente o da `.env`, e cercava `.env` nella cartella da cui partiva il
  comando. Il valore predefinito era `.data`, relativo a quella stessa cartella;
- il server del cruscotto leggeva solo l'ambiente, perché non legge `.env` (ADR-0031), e risolveva `.data` rispetto
  alla propria cartella;
- `task docker:up` usava una terza variabile, `AGENCY_DATA` (ADR-0040).

Così il motore e il cruscotto potevano guardare due registri diversi, e niente lo diceva. Un comando lanciato da
`web/` ignorava il `.env` della radice e cercava un `.data` in `web/`. Un valore relativo, come
`AGENCY_DATA_DIR=.data`, cambiava significato con la cartella.

Il difetto non riguarda solo la radice: un'impostazione scritta in `.env` la vede solo il motore. ADR-0043 aveva già
trovato un tetto di 40 $ che si vedeva solo nelle impostazioni effettive. L'altra strada, dare al cruscotto la radice
risolta dal motore, vorrebbe che il Taskfile facesse girare il caricatore del motore. Quel caricatore legge `.env`, e
con lui la chiave: proprio ciò che ADR-0031 e ADR-0039 escludono.

**Decisione.**
- **Un'ancora: il checkout da cui gira il codice.** `CHECKOUT`, in `agency.contracts.layout`, è la radice del
  repository, e `agency.config.REPO_ROOT` è lo stesso valore, che già trova `prompts/` e `registry/`. Codice e dati
  vengono quindi da un solo checkout. Ogni worktree in `.worktrees/` ha il suo `.data`, così un worktree di audit o di
  refactor non scrive mai nel registro vero. Anche `.env` si cerca nel checkout, non nella cartella corrente.
- **Un risolutore, per il motore e per il server.** `data_root()` dà `.data` nel checkout, o il valore di
  `AGENCY_DATA_DIR`. `projects_root()` fa lo stesso per `projects/`, con `AGENCY_PROJECTS_DIR`. Stanno accanto a
  `DataLayout`, che il server già importa senza passare da `agency.config`.
- **Un valore dato deve essere assoluto.** Uno relativo riporterebbe la dipendenza dalla cartella corrente. Il motore e
  il server lo rifiutano allo stesso modo: escono con 1 e stampano la stessa riga, che nomina la variabile.

  ```text
  AGENCY_DATA_DIR deve essere un percorso assoluto, non '.data': uno relativo dipende dalla cartella da cui parte il comando
  ```

- **`.env` tiene solo i segreti.** `Settings` legge da `.env` solo la chiave API.
  - Se `.env` ha ancora una riga `AGENCY_*` che non è un segreto, il motore si ferma con una riga che nomina la
    variabile e dice che va nell'ambiente del processo. ADR-0043 lasciava ignorare in silenzio una variabile rimasta,
    e qui non è sicuro: un `.env` che punta al registro vero lascerebbe il motore a scriverne uno nuovo e vuoto.
  - Le impostazioni che servono a più di un processo vengono solo dall'ambiente: `AGENCY_DATA_DIR`, e
    `AGENCY_PROJECTS_DIR` dove un secondo processo legge `projects/`. Task e Compose danno quell'ambiente a ogni
    processo allo stesso modo.
  - Le manopole del solo motore in `.env.example` (`AGENCY_EXPLORERS`, i due effort, `AGENCY_MAX_PARALLEL`) valgono
    quanto i default del codice, quindi toglierle non cambia nulla. Un esperimento le imposta sulla riga di comando, e
    l'impronta dell'esecuzione le registra (ADR-0026).
- **Un nome solo.** `task docker:up` e `compose.yaml` usano `AGENCY_DATA_DIR` anche per la cartella dell'host, al posto
  di `AGENCY_DATA` di ADR-0040. Il container tiene il suo valore, `/data`. Così il nome vuol dire sempre "la radice dei
  dati come la vede questo processo".

**Conseguenze.**
- La decisione si attua in tre unità di `docs/audit/PLAN.md`: l'ancora e il risolutore (Task 2.15), `.env` solo per la
  chiave (Task 2.16), il nome unico in Docker (Task 2.17). Finché manca la seconda, un `AGENCY_DATA_DIR` assoluto
  scritto in `.env` sposta ancora solo il motore.
- Un `.env` copiato dal vecchio `.env.example` contiene `AGENCY_DATA_DIR=.data`. Il motore si ferma subito con la riga
  sopra, e dalla Task 2.16 con quella che dice dove spostare la variabile. In nessuno dei due casi parte un registro
  vuoto.
- Le prove non leggono `.env`, se non lo passano esse stesse: quello del checkout contiene la chiave vera. Una fixture
  di `tests/conftest.py` lo spegne in ogni prova.
- Le prove Playwright danno al server un `AGENCY_DATA_DIR` assoluto.
- Quando il motore sarà un pacchetto installato, in M7, `prompts/` e `registry/` diventeranno dati del pacchetto e
  `AGENCY_DATA_DIR` sarà obbligatoria (STR-008). Lo deciderà l'ADR di M7, non questo.
- Restano tre occorrenze della stessa dipendenza dalla cartella corrente: il file scritto da `agency-schemas`,
  `AGENCY_PROJECTION_DIR` e `AGENCY_TOOLCHAIN_DIR`. Sono le Task 2.F34–2.F36 di `docs/audit/PLAN.md`.
- Verifica: `tests/test_layout.py`, con `test_the_default_data_root_is_the_checkout_from_any_directory` e
  `test_engine_and_server_resolve_the_same_root`, e `tests/test_server.py`, con
  `test_a_relative_data_root_is_refused_by_engine_and_server`.
