# Lezioni dello studio

Lezioni astratte dalle retrospettive dei progetti (`templates/retro.md`): **nessun dato di cliente**,
solo ciò che vale per altri lavori. Ogni lezione ha la prova da cui nasce e dove si applica. Le
lezioni confermate più volte si trasferiscono nelle skill, negli anti-pattern o in `craft.md`.

| Data | Lezione | Prova (tipo di progetto, osservazione) | Applicata in |
|---|---|---|---|
| 2026-10-29 | Tre esploratori isolati con lo stesso brief convergono sulla stessa idea se non hanno leve di partenza diverse e territori esclusi. | Due sprint di prova: 3/3 concept uguali senza leve; convergenza ridotta con leve e libreria di caratteri. | `direction-sprint` |
| 2026-10-29 | Gli agenti scelgono i caratteri tra quelli installati e tornano sempre agli stessi. | Sprint di prova: tre direzioni su Inter; FigCraft usa Inter quando non se ne sceglie uno. | `type-system` (libreria), `figcraft_audit` |
| 2026-10-30 | Un render 3D "plausibile" può falsare il colore della grafica di molto. | Packaging di prova: ΔEok 0.146 con luce e vista di default, 0.058 dopo calibrazione. | `production-3d` (autoverifica) |
| 2026-10-30 | Una misura visiva grossolana non vede la convergenza di concept. | Sprint 1: "diversità sufficiente" su tre direzioni con la stessa idea. | `direction_board.py concepts`, critica |
| 2026-10-31 | "Scegli lo strumento" produce script: senza un obbligo per mezzo, ogni agente sceglie ciò che conosce meglio. | Identità M: centinaia di SVG e PNG da script, nessun master, server Craft connessi e mai usati; il direttore l'ha scritto come scelta. | `TOOLS.md`, `ticket.py --medium`, `master.py` |
| 2026-10-31 | Un controllo che non colpisce nessun file sembra un controllo. | Ticket con output a cartella e pattern `*.png`: nessuna verifica, nessun errore. | `ticket.py` (copertura, glob) |
| 2026-10-31 | La firma libera non separa autore e revisore, anche quando quasi tutti firmano giusto. | Autore che registra un giudizio di qualità sul proprio segno; QA soddisfatto da prove dell'autore. | `checks.json`, `identity-guard.py` |
| 2026-10-31 | Il costo sta nel contesto che resta, non nel testo scritto. | ~190k token per chiamata, 71% delle scritture in cache dopo pause oltre 5 minuti, immagini fino a 9000 px, ricerche legali su candidati poi scartati. | `budgets.json`, `budget-guard.py`, agenti monouso |
