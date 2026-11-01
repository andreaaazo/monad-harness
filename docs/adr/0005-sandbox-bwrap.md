# ADR-0005: sandbox `bwrap` e istanze per lavoro

**Contesto.** Gli strumenti eseguono comandi decisi dal modello su materiali non fidati. Il lock di server
della CLI serializza il lavoro.

**Decisione.** Ogni lavoro gira in `bwrap`, con una sola cartella scrivibile e senza rete. Docker solo per i
servizi.

**Verifica (2026-10-31, `spikes/sandbox_craft.sh`).** VectorCraft, FigCraft, PhotoCraft, EffectCraft e Blender
creano il proprio master in sandbox. Altre cartelle inesistenti, rete assente, `/usr` non scrivibile. Due
`vectorcraft-cli mcp --headless` si inizializzano in parallelo, con 33 tool.

**Conseguenze.** Il lock di server diventa inutile se il lavoro concorrente regge: va collaudato in M3. Non
è stata provata la modifica simultanea reale, né l'uso della GPU in sandbox.
