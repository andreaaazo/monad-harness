# ADR-0013: cinque direzioni interne

**Contesto.** Con 3 esploratori il direttore sceglieva 2 o 3 idee su 3: quasi nessuna selezione vera. Gli schizzi
restano interni e sono la parte economica del lavoro. Decisione di Andrea, 2026-10-31.

**Decisione.** L'esplorazione parte da 5 direzioni, con 5 leve diverse. Il direttore sceglie sempre 2 o 3 idee da
sviluppare, quindi il costo delle fasi successive non cambia.

**Regole.**
- Il numero è configurabile con `AGENCY_EXPLORERS`.
- Il direttore può usare meno leve se il brief non ne regge cinque vere: meglio tre idee reali che cinque copie.
- `direction-d` e `direction-e` sono ruoli nuovi rispetto al setup precedente.
- La tavola anonima passa su due righe, per restare entro i 1.600 px. Le lettere vanno da V a Z.

**Conseguenze.** Stima di circa 1 $ in più per progetto, da verificare con la prima prova reale. Dopo ADR-0014 ogni
direzione costa di più, perché disegna davvero. Il tempo quasi non
cambia, perché gli esploratori lavorano insieme. Una chiave API nuova può avere limiti sulle chiamate contemporanee:
in quel caso il sistema ritenta e rallenta. Il rischio principale resta la convergenza delle idee, che la prima tavola
mostrerà subito.
