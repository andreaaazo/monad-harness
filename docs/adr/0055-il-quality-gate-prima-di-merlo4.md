# ADR-0055: il quality gate di Python prima di `merlo4`

**Contesto.** M1.6 ha chiuso tutto il lavoro che non spende: restano `merlo4` e il confronto con la CLI, due prove dal
vivo. Il 2026-11-13 l'audit deep-review è entrato in `main` (`ceec412`), con 101 problemi corretti e le prove di Python
passate da 496 a 1218 (`docs/audit/99-result.md`). I controlli di Python restano però quelli di prima:
- Ruff con sette famiglie di regole e righe da 110;
- pyright in modo `standard`;
- import-linter con cinque contratti;
- nessuna soglia di copertura.

Niente impedisce di zittire un controllo. Oggi 107 righe di `src/` e `tests/` usano una direttiva che toglie un controllo
o salta una prova: `noqa`, `type: ignore`, `skipif` e simili. Si contano con il `git grep` in fondo. M2 porta sul motore
il resto dello studio (`docs/PARITY.md`), quindi molto codice nuovo.

ADR-0021 metteva il refactor di M1.7 dopo `merlo4`, perché il comportamento si misura prima di toccarlo. ADR-0048
faceva della cassetta di `merlo4` il golden master di M1.7.

**Decisione.** Decisione di Andrea, 2026-11-13.
- **`merlo4` non parte ora.** M1.6 si chiude senza prove dal vivo. `merlo4` e il confronto con la CLI passano a un
  traguardo nuovo, M1.9, insieme ai criteri ereditati che li aspettavano.
- **Un traguardo nuovo, M1.8: un quality gate di Python molto più severo.** Lo stato finale è in
  `docs/quality-gate/SPEC.md`:
  - un comando decide, `python -m quality_gate changed`;
  - `full` applica gli stessi controlli a tutto il repo;
  - nessuna soppressione ha effetto;
  - il gate si applica da solo, con gli hook di Claude Code e il pre-commit;
  - il gate rispetta per primo le sue regole.

  Il codice esistente non si sistema in blocco. Chi tocca un file lo ripulisce tutto.
- **L'ordine diventa M1.7, M1.8, M1.9, poi M2.** Rovescia la conseguenza di ADR-0021 sul refactor dopo `merlo4`, e
  quella di ADR-0048 sul golden master.

**Conseguenze.**
- **La rete di M1.7.** M1.7 tocca il motore senza una misura dal vivo fatta prima. La rete restano:
  - gli snapshot di strumenti e system prompt, byte per byte (`tests/test_request_snapshots.py`);
  - i test di flusso con risposte registrate.

  Manca il golden master di ADR-0048. Prima del punto 2 di M1.7 Andrea decide tra due strade:
  - registrare E2 con `--record` sul motore di oggi e ripeterlo sul motore diviso, con la stessa spesa di 10 $;
  - affidarsi a snapshot e flussi, ed eseguire E2 dal vivo alla fine come previsto.
- **Il riferimento di E2.** Il criterio di E2 in M1.7 si confronta con `merlo3`, l'ultima esecuzione misurata, perché
  `merlo4` non c'è ancora.
- **La spesa e la preparazione di `merlo4`.** M1.6 si chiude con 0 $ spesi. Il tetto di `merlo4` passa a M1.9 e si
  rivede prima di partire. La preparazione del 2026-11-03 va rifatta: M1.7 e M1.8 cambiano il codice, quindi l'impronta
  di partenza.
- **Il contratto sui cicli.** Il contratto `acyclic_siblings` della specifica (§6.5) può coprire `agency` da subito,
  perché M1.7 toglie il ciclo `qa ↔ tools`. È l'unico rimasto fra i pacchetti di `agency`: quello fra `agents` e `tools`
  l'ha tolto l'audit (`73881ee`). Con il gate prima del refactor, `agency` sarebbe partito come contratto in attesa.
- **Il rischio dell'infrastruttura.** Cresce il rischio «costruire infrastruttura invece di design» di
  `docs/00-PROJECT.md`. M1.7 e M1.8 non finiscono con un lavoro reale, che arriva con M1.9.
- **I conflitti con le decisioni accettate.** La specifica si scontra con nove punti già decisi. M1.8 risolve ciascuno
  prima di scrivere il gate, con un ADR nuovo o in `docs/quality-gate/DEVIATIONS.md`:
  - **ADR-0051 scarta il framework pre-commit.** L'hook versionato sta in `.githooks/` e git lo trova con
    `core.hooksPath`. La specifica invece:
    - usa pre-commit con un hook `repo: local`, che non scarica nulla, quindi il motivo dello scarto non vale per lui;
    - controlla `.git/hooks/pre-commit` (§8.4), ma pre-commit non si installa finché `core.hooksPath` è impostato;
    - fa vietare `core.hooksPath` al guard (§9.2).
  - **ADR-0039 e ADR-0051 fissano `task check` e `check:fast`.** Eseguono Ruff, pyright e pytest su tutto il codice.
    Con la configurazione della specifica fallirebbero sul codice di oggi, come `full` (§1, P2): righe da 80, virgolette
    singole, `select = ["ALL"]` e basedpyright in modo `all`. La parte Python del controllo di ogni giorno deve passare
    da `quality_gate changed`.
  - **La specifica vieta di toccare i test (A7), ma due test fissano gli strumenti di oggi.**
    `tests/test_taskfile.py` fissa i comandi di `check:fast`, e `tests/test_toolchain.py` legge `[tool.ruff]`. Cambiare
    il controllo di ogni giorno li cambia.
  - **ADR-0006 mette in quarantena per due settimane ogni pacchetto.** Ogni pin `==` deve stare dentro la quarantena
    (`exclude-newer` in `pyproject.toml`). Deve anche rispettare i minimi della specifica: pytest ≥ 9.0,
    wemake-python-styleguide ≥ 1.0 e mutmut ≥ 3.
  - **La risposta a Q14 dell'audit escludeva le docstring obbligatorie.** Non prevedeva campagne di docstring né la
    regola Ruff `D1` (`docs/audit/PLAN.md`). Il gate non fa campagne, ma chiede docstring complete in ogni file toccato,
    con Ruff `D` e pydoclint.
  - **`legacy/` e `src/agency/qa/scripts/` sono fissati per byte.** `legacy/` è congelato e un test ne verifica gli
    hash. `src/agency/qa/scripts/` è codice copiato e fissato per byte. Sono i candidati di D4. Oggi li escludono
    `extend-exclude` di Ruff ed `exclude` di pyright, che la specifica vieta in quelle tabelle.
  - **`.gitignore` esclude tutta `.claude/`, che tiene lo stato locale.** `.claude/settings.json` deve diventare un
    file versionato.
  - **Il guard protegge anche `~/.claude/**` (§9.2).** Fuori dalla manutenzione blocca quindi anche la memoria
    dell'assistente in `~/.claude/projects/`.
  - **La sandbox lancia `systemd-run --user` (ADR-0046), ma il gate passa ai test un ambiente ripulito (§7.3).**
    `env_passthrough` deve contenere le variabili che servono alla sessione utente di systemd. Sono da misurare.
  - **Le prove si saltano in tre casi, ma §8.6 vuole zero prove saltate.** Oggi si saltano senza VectorCraft, senza
    Docker, e quattro fuori da un clone git (`task check:clean`).
- **La CI aspetta il remoto.** Senza un remoto la CI non ha dove girare (ADR-0051), quindi la §10.2 della specifica
  aspetta che ci sia.

Il conteggio delle direttive si rifà con:
`git grep -c -i -E "skipif|mark\.skip|pytest\.skip|importorskip|xfail|pytest_collection_modifyitems|pytest_plugins|collect_ignore|noqa|type: ?ignore|pyright:|pragma: ?no|fmt: ?(off|on|skip)" -- 'src/*.py' 'tests/*.py'`.
È un conteggio di righe, vicino ma non uguale alla scansione di §8.1: il numero esatto lo dà `BASELINE.md`.
