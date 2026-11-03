# ADR-0043: il tetto di spesa si dichiara all'avvio

**Contesto.** Per ADR-0015 il budget lo sceglie il cliente, progetto per progetto. Ma se `agency run` partiva senza
`--budget`, il tetto veniva da `AGENCY_PROJECT_BUDGET_USD` o dal codice. Preparando `merlo4`, il 2026-11-03, c'erano tre
tetti diversi:
- 25 $ nel codice;
- 40 $ nell'ambiente di Andrea, che si vedeva solo leggendo le impostazioni effettive;
- 30 $ nella roadmap.

Un lavoro avviato senza il flag avrebbe speso sotto un tetto che nessuno aveva dichiarato per lui. `CLAUDE.md` vuole che ogni
prova dal vivo abbia un tetto dichiarato, e una regola che si può imporre nel codice non si scrive in un prompt.

**Decisione.**
- `agency run` richiede `--budget`. Senza, si ferma prima di aprire la sessione: nessun progetto creato, nessuna chiamata.
- Un tetto è un importo positivo e finito in dollari, sia in `agency run --budget` sia in `agency budget`: zero, negativi,
  `nan`, `inf` e i testi si rifiutano.
- `Session.start` vuole il budget, senza valore di default. `project_budget_usd` e `AGENCY_PROJECT_BUDGET_USD` non esistono
  più.
- Il gateway rifiuta una chiamata per un progetto che non ha un tetto salvato. Lo fa prima della stima, quindi non esce
  nemmeno il conteggio dei token. È una seconda difesa: `agency run` salva il tetto prima di ogni chiamata.

**Conseguenze.**
- Una variabile `AGENCY_PROJECT_BUDGET_USD` rimasta in un `.env` non ha più effetto, e si può togliere.
- I progetti già nel registro tengono il tetto salvato: `merlo3` ha 50 $. `merlo` e `merlo2` vengono da prima della tabella
  `projects` e non hanno tetto, ma sono chiusi e `agency resume` già non li riapriva.
- Anche i test dichiarano il loro tetto quando aprono un progetto, come farebbe chi avvia.
- Verifica: `tests/test_hardening.py` per `agency run` e `agency budget`, `tests/test_gateway.py` per il gateway. A mano,
  `uv run agency run merlo4 evals/briefs/E1.md` si ferma con `--budget` obbligatorio, senza creare `merlo4`.
