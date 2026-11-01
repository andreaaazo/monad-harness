---
name: design-agency
description: Avvia lo studio su una richiesta del cliente di qualsiasi tipo — dal mockup al rebranding, dal logo al sito — con intake, instradamento ai reparti, ticket, gate di qualità e risposta finale.
argument-hint: "[richiesta del cliente, file allegati, vincoli]"
disable-model-invocation: true
---

Richiesta del cliente: $ARGUMENTS

Sei il router (`.claude/CLAUDE.md`).

1. Stato: `.agency/STATE.md`, `.agency/decisions.md`, `python3 .claude/scripts/ticket.py list --open`.
2. Intake con la skill `intake`: classifica in `.claude/design-agency/SERVICES.md`, dimensione,
   livello QA. Poi **scoperta** (`CLIENT.md`): giri di domande senza limite di numero, stimoli,
   materiali del cliente, finché `understanding.md` è confermato e `client.py ready` è PRONTO.
3. Strumenti: `.claude/scripts/py .claude/scripts/tools.py check`. Se manca qualcosa di
   necessario, `tools.py plan` e proponi l'installazione all'utente prima di iniziare.
4. Instrada al punto d'ingresso più basso che basta (`.claude/design-agency/ORG.md`), con
   ticket e messaggio di delega di `.claude/design-agency/ROUTING.md`.
5. Smista le RICHIESTE di ritorno, coordina i server Craft (`craft_lock.py status`).
   Raccogli le DOMANDE CLIENTE degli agenti e falle al cliente (`client.py ask`).
6. A ogni gate previsto da `.claude/design-agency/CLIENT.md`: presenta con `client-review`,
   **chiudi il turno** con le domande e aspetta. Registra feedback e approvazioni con
   `client.py`; traduci il feedback in modifiche e itera. La fase successiva parte con
   ticket `--after-gate`.
7. Accetta i ticket con `ticket.py accept` dopo aver letto l'esito. Prima di presentare o consegnare: `evidence.py gate` sui deliverable con i controlli di
   `.claude/design-agency/QA.md`. Se fallisce, rimanda al reparto.
8. Consegna finale: presentazione `final`, approvazione esplicita registrata, `STATE.md` e
   `decisions.md` aggiornati.
9. Retrospettiva (`.claude/design-agency/templates/retro.md`) e lezioni astratte in
   `.claude/design-agency/references/lessons.md`.

In proporzione alla dimensione (CLAUDE.md, Proporzione); per M e L il contratto creativo
(`.claude/design-agency/templates/creative-contract.md`) si scrive prima delle direzioni. Il primo
render non si presenta: ciclo di qualità di `.claude/design-agency/references/craft.md`.

Non fermarti alla proposta se il cliente ha chiesto di realizzare il lavoro.
