# ADR-0061: il commit e il controllo di ogni giorno passano dal gate

**Contesto.** [ADR-0039](0039-taskfile-come-ingresso-unico.md) ha fatto del Taskfile l'ingresso unico.
[ADR-0051](0051-il-controllo-gira-da-solo.md) ha aggiunto l'hook di commit, cioè `.githooks/pre-commit`, che esegue
`task check:fast` e che Andrea attiva con `git config core.hooksPath .githooks`. ADR-0051 ha anche messo `check:fast`
all'inizio di `task check`, e fatto di `check:clean` una copia dell'indice di git.

La specifica del quality gate (`docs/quality-gate/SPEC.md`) chiede altro:
- un hook del framework pre-commit con `repo: local` (§10.1), e `.git/hooks/pre-commit` installato da pre-commit
  (§8.4);
- un guard che vieta `core.hooksPath` (§9.2);
- un solo comando che decide, `quality_gate changed` (P1).

Il codice di oggi non rispetta le regole del gate, quindi `task check` e `check:fast` fallirebbero su tutto il
repository se eseguissero Ruff e basedpyright con la configurazione della specifica.

**Decisione.**
1. **pre-commit sostituisce `.githooks/`.**
   - L'hook è quello della §10.1, che esegue `uv run python -m quality_gate staged`.
   - ADR-0051 scartava il framework perché scarica gli hook da GitHub a revisioni arbitrarie. Un hook `repo: local`
     non scarica nulla, e pre-commit stesso è fissato con `==` nel gruppo `quality`, dentro la quarantena.
   - Andrea, una volta sola, toglie `core.hooksPath` con `git config --unset core.hooksPath` e installa l'hook con
     `uv run pre-commit install`. `task setup` stampa questi due comandi al posto di quello di oggi.
   - `.githooks/` sparisce.
2. **`task check` diventa** `uv lock --check`, `task gate` (`uv run python -m quality_gate changed`), `web:static`,
   `web:unit` ed `e2e`.
   - Spariscono `check:fast`, `lint`, `format`, `imports` e `types`. `ruff format .` riscriverebbe ogni file, e tutto
     il repository diventerebbe «cambiato», quindi da ripulire per intero. Un file alla volta lo formatta l'hook
     PostToolUse.
   - `task test` resta, per eseguire una prova sola.
   - Il Taskfile aggiunge `gate`, `gate-full`, `gate-mutation` e `gate-lock` (§10.3), e il Makefile li riporta.
3. **`check:clean` diventa un clone locale di `HEAD`, con il diff in stage applicato.**
   - Fuori da un repository git il gate esce con 2, e la copia dell'indice di oggi non è un repository.
   - Nel clone il gate vede come cambiato ciò che è in stage, quindi il contenuto del prossimo commit, e le quattro
     prove che vogliono un clone git non si saltano più.
   - Né il clone né l'applicazione del diff scrivono la storia, l'indice o i remoti del repository di partenza.

**Che cosa rovescia.**
- Di ADR-0051: l'hook in `.githooks/`, `check:fast` come inizio di `task check`, e `check:clean` sulla copia
  dell'indice.
- Di ADR-0039: i compiti `lint`, `format`, `imports` e `types`.

**Conseguenze.**
- Tutto arriva nel piano C di M1.8, al passaggio del controllo di ogni giorno al gate. Fino ad allora l'hook, i compiti
  e `check:clean` restano quelli di oggi.
- Il commit controlla solo i file in stage, più l'integrità del gate (§10.1). Le difese dell'interfaccia e i controlli
  su tutto il progetto restano in `task check`.
- `tests/test_taskfile.py` cambia con il Taskfile e l'hook. È una delle due eccezioni ad A7 di
  [ADR-0060](0060-il-quality-gate-parametri-decisioni-e-ordine.md).
