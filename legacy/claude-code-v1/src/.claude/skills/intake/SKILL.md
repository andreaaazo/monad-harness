---
name: intake
description: Accoglie una nuova richiesta del cliente — la classifica nel catalogo dei servizi, ne stima la dimensione, individua cosa manca, scrive il brief e decide l'instradamento. Da usare all'arrivo di ogni richiesta o domanda nuova, anche vaga ("facciamo un rebranding", "preparami un mockup").
---

# Intake

## 1. Capire

Rileggi la richiesta e i file allegati. Scrivi in tre righe: cosa vuole il cliente, per
quale scopo, entro quali vincoli. Separa ciò che è detto da ciò che stai deducendo.

## 2. Classificare

In `.claude/design-agency/SERVICES.md` trova il servizio (o i servizi, se la richiesta
li combina). Dimensione:
- **S** — un artefatto, un autore, poche ore: "un mockup di questo poster";
- **M** — un reparto, più fasi: "un logo", "una brochure";
- **L** — più reparti: "rebranding", "sito di lancio", "identità completa".

## 2b. Norme, decisori, asset

Fin dall'intake annota: norme del settore che toccano il design (accessibilità digitale UE,
claim, diciture), chi decide e chi userà il sistema, quali asset esistono (foto, illustrazioni,
contenuti) e quali la direzione potrebbe richiedere. Sono domande della scoperta.

## 3. Cosa manca

Per ogni informazione mancante chiediti: **cambia la soluzione?**
- sì e non è reperibile → domanda al cliente, subito, con il motivo;
- no, o è reperibile (sito, file, ricerca) → assunzione scritta e si procede.

Domande tipiche che cambiano la soluzione: pubblico e mercato, cosa conservare in un
rebrand, supporti finali (stampa? quale processo?), lingue, scadenze vincolanti,
approvatori, budget per font, foto o stampa.

Regole (`.claude/design-agency/CLIENT.md`, sezione Scoperta): **nessun numero massimo di
domande**. Si fanno giri successivi finché lo studio ha capito davvero: ogni giro scava nelle
risposte precedenti (perché, esempi, casi concreti), mostra stimoli visivi quando le parole non
bastano e chiede i materiali del cliente. Ogni domanda con il perché, opzioni concrete e la
raccomandazione dello studio; registrala con
`python3 .claude/scripts/client.py ask --from router --question "…" --why "…" --options "A|B" --blocking`,
poi **chiudi il turno** e aspetta. Intanto si avvia solo il lavoro che non dipende dalle risposte.
Le risposte con `client.py answer` e i fatti con `facts.py add --kind client`.
La scoperta finisce con `work/context/understanding.md` confermato dal cliente e `client.py ready`.

Per richieste L, il brief stesso si presenta al cliente e si approva (gate `brief`).

## Mondo del cliente

Per M e L chiedi da subito i materiali del cliente (prodotto, materiali, linguaggio, documenti,
foto, utenti, situazioni d'uso) e avvia `client-world`. Ogni risposta del cliente che contiene un
fatto si registra anche in `facts.py add --kind client --ref A-…`.

## 4. Brief

Scrivi `work/brief.md` da `.claude/design-agency/templates/brief.md`: solo i campi
pertinenti, requisiti verificabili R1…Rn con metodo di prova, livello QA da
`.claude/design-agency/QA.md`. Per le richieste S basta un brief di 10 righe.

## 5. Instradare

- Punto d'ingresso secondo SERVICES.md e ORG.md (il più basso che basta).
- Ticket: `ticket.py new --from router --to <agente> --type … --title … --brief work/brief.md --qa …`.
- Messaggio di delega nel formato di `.claude/design-agency/ROUTING.md`.
- Gate del cliente previsti per la dimensione (CLIENT.md) scritti nel brief e in `STATE.md`.
- Aggiorna `.agency/STATE.md` (crealo dal template se il lavoro durerà più di una sessione).

## Domande del cliente

Se il cliente fa una domanda, non una richiesta di lavoro: rispondi dai file se la risposta
c'è; altrimenti apri una **consulenza** allo specialista competente (es. "che carattere per
il sito?" → `typographer`; "si può stampare su kraft?" → `production-manager`) e riporta la
risposta con le sue fonti.
