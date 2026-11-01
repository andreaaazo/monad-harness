# ADR-0015: modello e budget li sceglie il cliente

**Contesto.** Lo studio aveva accumulato limiti propri: tetti per ticket, due esplorazioni, otto turni del direttore,
300 turni per agente, passi del grafo, riletture, dimensione delle immagini. Ognuno poteva fermare un lavoro con i
soldi ancora disponibili. Inoltre il budget si perdeva tra un comando e l'altro, e un progetto fermato dal budget non
ripartiva davvero. Decisione di Andrea, 2026-10-31.

**Decisione.** Gli unici vincoli al lavoro sono **il modello e il budget**, scelti dal cliente per progetto. Dentro quei
due vincoli lo studio lavora finché il lavoro è fatto bene.

- Budget, modello ed effort si salvano nel progetto con `agency run --budget --model --effort`.
- Il budget ferma il lavoro prima di una chiamata che lo supererebbe. Il lavoro resta salvato: non è un errore né un
  blocco del ticket. `agency budget <progetto> <tetto>` e `agency resume <progetto>` riprendono da dove era.
- Al 75% e al 90% del budget l'agente riceve un avviso, così resta la riserva per prove e consegna.
- Le quote per tipo di lavoro (esploratore, proposta, altri ticket) sono indicative: producono un avviso, mai un blocco.
- Le immagini grandi si riducono da sole. Una rilettura si permette, segnalandola.
- `registry/budgets.json` è dismesso: conteneva solo limiti per ruolo.

**Cosa resta, perché non limita il lavoro.** Sicurezza (sandbox, rete, chiave), qualità (primo sguardo, master, prove e
firme), metodo dello studio (2 o 3 proposte, 5 direzioni di partenza, configurabili). `API_MAX_TOKENS` e il limite di
passi del grafo sono valori tecnici.

**Conseguenze.** Un solo agente può consumare gran parte del budget, e un'esplorazione può ripetersi finché il budget lo
permette. È una scelta consapevole: il report mostra dove va la spesa. Un cliente con budget piccolo può fermarsi prima
del risultato: l'avviso e il report lo rendono visibile.
