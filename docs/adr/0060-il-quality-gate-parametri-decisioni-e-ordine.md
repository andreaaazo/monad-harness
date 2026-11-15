# ADR-0060: il quality gate, parametri, decisioni e ordine di costruzione

**Contesto.** [ADR-0055](0055-il-quality-gate-prima-di-merlo4.md) ha aperto M1.8: un quality gate di Python con lo
stato finale in [`docs/quality-gate/SPEC.md`](../quality-gate/SPEC.md). La specifica lascia al repository sette
parametri (§2) e cinque decisioni, D1–D5 (§3). ADR-0055 elenca anche i punti in cui la specifica si scontra con
decisioni già prese, e chiede di risolverli prima di scrivere il gate. Andrea ha lasciato le scelte all'esecuzione.
Il [primo piano](../superpowers/plans/2026-11-15-m1-8-plan-a-per-file-gate.md) le mette in tabella. Questo ADR le
registra, tranne due:
- l'hook di commit e il controllo di ogni giorno, in
  [ADR-0061](0061-il-commit-e-il-controllo-di-ogni-giorno-passano-dal-gate.md);
- le docstring, in [ADR-0062](0062-docstring-complete-nei-file-che-cambiano.md).

Le versioni sono state risolte il 2026-11-15 con `uv lock`, in un progetto di prova con la stessa data di quarantena.
Lo stesso giorno, sempre in un progetto di prova, sono stati verificati i comportamenti degli strumenti citati sotto.

**Decisione.**
1. **I parametri della §2.**
   - `<RUNNER>` è `uv run`, e `<ENV_PY>` è `.venv/bin/python`.
   - `<PY>` è `3.13`; `.python-version` fissa 3.13.15.
   - `<PKGS>` è `agency`, in `src/agency`, e `<TESTS>` è `tests`.
   - `<BASE_BRANCH>` non c'è finché non c'è un remoto.
   - `<T_SUITE>` si misura con `coverage run` alla fine del primo piano.
2. **D1, gli strumenti da togliere.** pyright e `[tool.pyright]` se ne vanno al passaggio del controllo di ogni giorno
   al gate. Con loro escono dal gruppo `dev` le voci degli strumenti: ruff, pyright, import-linter, django-stubs e
   pytest. Fino ad allora i due gruppi le elencano entrambi, e i pin del gate stanno solo nel gruppo `quality`.
   `[tool.pytest.ini_options]` diventa `[tool.pytest]` allo stesso passaggio. Non c'è altro da togliere: oggi non ci
   sono black, isort, mypy, `setup.cfg` o `.flake8`. Il motivo dell'attesa è `tests/test_dependencies.py`, che vuole
   quegli strumenti nel gruppo `dev`: spostarli prima cambierebbe un test che il passaggio cambia comunque.
3. **D2, i contratti di architettura.**
   - I due contratti fissi della §6.5 si aggiungono ai tredici di oggi.
   - I quattro contratti che contano solo gli import diretti (`allow_indirect_imports = true`) restano come sono.
     Toglierli indebolirebbe i confini di ADR-0057 e ADR-0058. Tenerli è più severo che toglierli, come chiede la
     §13: «almeno altrettanto severo».
   - Le loro versioni con gli import indiretti vanno in `BASELINE.md` come contratti in attesa.
   - `docs/quality-gate/DEVIATIONS.md` registra la differenza, con l'uscita di import-linter.
4. **D3, la CI.** Aspetta un remoto, come dice [ADR-0051](0051-il-controllo-gira-da-solo.md). Quando c'è, `changed`
   blocca subito e `full` fa solo rapporto finché il repository non è pulito.
5. **D4, i percorsi esclusi.** Sono `legacy/**` e `src/agency/qa/scripts/**`, in `[tool.quality_gate].exclude` e
   nell'`omit` di coverage.
   - `legacy/` è il backup congelato, e un test ne verifica gli hash.
   - Gli script di QA sono codice copiato e fissato per byte, che gira nel Python della toolchain.
   - Le migrazioni Alembic del registro restano dentro: sono scritte a mano.
6. **D5, `CPY001`.** È ignorata: il repository è privato e ha un solo proprietario.
7. **I test che cambiano in M1.8**, cioè le eccezioni ad A7: `tests/test_taskfile.py` (ADR-0061) e
   `tests/test_dependencies.py` (D1). Cambiano al passaggio. Come ogni file cambiato, si ripuliscono per intero.
8. **La quarantena di [ADR-0006](0006-niente-litellm.md).** Ogni pin è l'ultima versione uscita prima di
   `exclude-newer = 2026-10-17`, e rispetta i minimi della specifica:
   - pytest 9.1.1, contro un minimo di 9.0;
   - wemake-python-styleguide 1.8.1, contro 1.0;
   - mutmut 3.8.0, contro 3;
   - coverage 7.16.2, contro 7.

   La data non si sposta.
9. **`.claude/settings.json` si può versionare così com'è.** Sotto `.claude/`, `.gitignore` ignora solo `memory/`,
   `sessions/`, `state/` e `settings.local.json`. ADR-0055 dava per ignorata tutta la cartella: la premessa era
   sbagliata.
10. **La memoria dell'assistente.** Il guard (§9.2) protegge tutto `~/.claude/**` tranne
    `~/.claude/projects/*/memory/**`. La memoria non contiene impostazioni, hook o variabili, e bloccarla farebbe
    perdere ciò che l'assistente impara fra una sessione e l'altra. È una modifica alla specifica, e
    `DEVIATIONS.md` la riporta.
11. **L'ambiente della sandbox.** `env_passthrough` elenca solo le variabili che le prove della sandbox chiedono
    nell'ambiente ripulito. La sandbox di [ADR-0046](0046-i-limiti-della-sandbox.md) lancia `systemd-run --user`, che
    probabilmente vuole `XDG_RUNTIME_DIR` e `DBUS_SESSION_BUS_ADDRESS`. Decide una misura, fatta quando esiste il
    controllo `tests`. Fino ad allora la lista è vuota.
12. **Le prove saltate.** Una prova saltata fa fallire il gate (§8.6).
    - Questa macchina ha VectorCraft e Docker (`make doctor`).
    - Le quattro prove che vogliono un clone git girano quando `check:clean` usa un clone (ADR-0061).
    - Le righe `skipif` di oggi restano finché i loro file non si toccano.
13. **L'ordine di costruzione.** Il gate si costruisce in tre piani:
    - il piano A arriva al modo `file`;
    - il piano B aggiunge i modi `changed`, `full` e `staged`, i controlli sul progetto, quelli di integrità, `lock`
      e `BASELINE.md`;
    - il piano C fa il passaggio del controllo di ogni giorno, poi aggiunge gli hook, `AGENTS.md`, il mutation
      testing e le prove, e si chiude con il blocco di Andrea.

    Fino al passaggio, il controllo di ogni giorno resta quello di oggi:
    - le tabelle condivise (`[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.importlinter]`) e `.editorconfig`
      cambiano solo al passaggio. Con le regole severe lì dentro, `make check` diventerebbe rosso su tutto `src/` e
      `tests/`;
    - le tabelle che legge solo il gate sono già quelle finali;
    - `quality_gate/ruff.toml` è temporaneo. Tiene la §6.1 per i file del gate, li fa rispettare dal `ruff check .`
      di oggi, e il passaggio lo cancella.
14. **Gli eseguibili.** Il gate cerca gli strumenti Python nella cartella degli script dell'interprete (§7.3), e cerca
    git nel `PATH`. git non è un pacchetto Python e non può stare nell'ambiente virtuale. `DEVIATIONS.md` lo riporta.
15. **I file arrivano agli strumenti come `./percorso`, mai dopo `--`.** basedpyright 1.40.2 legge `--` come il nome
    di un file. Il prefisso `./` impedisce a qualunque nome di file di diventare un'opzione, con ogni strumento. Chi
    legge l'uscita riporta ogni percorso alla forma relativa alla radice.

**Conseguenze.**
- Il piano A non cambia il controllo di ogni giorno. Aggiunge il gruppo `quality`, le tabelle proprie del gate,
  `.flake8` e il pacchetto `quality_gate/` con il modo `file`.
- Il piano B misura `env_passthrough` (punto 11) e scrive `BASELINE.md` con i contratti in attesa (punto 3).
- Il piano C fa il passaggio:
  - le tabelle condivise prendono la forma della §6;
  - `quality_gate/ruff.toml` sparisce, e `.editorconfig` passa a 80 colonne;
  - pyright e le voci del gruppo `dev` se ne vanno, insieme ai due test del punto 7;
  - vengono le parti di ADR-0061.

  Il piano C porta anche l'eccezione della memoria nel guard (punto 10).
- Dal passaggio in poi, ogni modifica al gate chiede ad Andrea `make gate-lock` prima del commit (§8.3).
- Ogni differenza dalla specifica finisce in `docs/quality-gate/DEVIATIONS.md`, con la sua prova.
