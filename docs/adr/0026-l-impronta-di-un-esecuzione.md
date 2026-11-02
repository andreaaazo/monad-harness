# ADR-0026: l'impronta di un'esecuzione

**Contesto.** ADR-0022 ha deciso che `runs` registra prompt, registry, lock, CLI, modello ed effort, ma non che cos'è
un'esecuzione né quando si prende l'impronta. Quella lista non basta: le definizioni degli strumenti e il ciclo dell'agente stanno
nel codice, e le impostazioni `AGENCY_*` cambiano l'effort degli esploratori e delle proposte e il numero delle direzioni. Due
esecuzioni con codice o impostazioni diversi risulterebbero identiche.

**Decisione.**
- Un'esecuzione è ogni comando che fa lavorare il grafo: `agency run`, `agency resume` e `agency decide`. Ognuna ha una riga in
  `runs`, scritta prima che il grafo parta: anche un'esecuzione fermata dal budget o da un errore dell'API ha la sua impronta.
- L'impronta è il contratto `Fingerprint` in `agency.contracts.run`. Contiene modello ed effort scelti dal cliente, le
  impostazioni `explorer_effort`, `proposal_effort`, `explorers` e `max_parallel`, lo sha256 di ogni file di `prompts/`,
  `registry/` e `src/agency/`, lo sha256 di `uv.lock`, la versione di Python e la prima riga di `--version` delle cinque CLI di
  produzione di `docs/04-TOOLS.md`.
- Le CLI si interrogano solo con `--version`, fuori dalla sandbox come già fa l'indice dei comandi Craft, ma con il solo `PATH`
  nell'ambiente: la chiave API non le raggiunge. Una CLI mancante vale `assente`, una che non risponde vale `non risponde`:
  l'esecuzione non si ferma per questo.
- `runs` è solo in aggiunta, con i trigger nella propria migrazione (ADR-0025).
- Le differenze tra due impronte sono una regola pura, `changes`, che le elenca nell'ordine dell'impronta. `agency runs` mostra
  cosa cambia da un'esecuzione alla precedente, e `agency compare` cosa cambia tra due esecuzioni qualsiasi, anche di progetti
  diversi.
- Il brief, i file del cliente e le risposte del modello non fanno parte dell'impronta: l'impronta descrive il sistema, non il
  lavoro.

**Verifica (2026-11-02).** `tests/test_runs.py` e due test di flusso in `tests/test_sketch_flow.py`. Su una copia del registro
reale, la migrazione `0002` aggiunge `runs` e lascia identiche tutte le 3.814 righe, con la catena integra. L'impronta reale si
prende in meno di un decimo di secondo e occupa circa 8 KB.

**Conseguenze.**
- Un file modificato mentre un'esecuzione lavora non compare nella sua impronta: si vede nella successiva.
- I lavori precedenti a M1.6 non hanno impronta. Nessuna si ricostruisce a posteriori.
- `usage` non sa ancora a quale esecuzione appartiene una chiamata: il legame arriva con il punto 6 di M1.6, insieme agli altri
  campi nuovi.
