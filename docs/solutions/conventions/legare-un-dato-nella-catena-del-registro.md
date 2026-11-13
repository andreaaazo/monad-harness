---
title: Legare un dato nella catena del registro, e perché l'evento successivo può cancellarne la traccia
date: 2026-11-13
category: conventions
module: agency.ledger
problem_type: convention
component: database
severity: high
applies_when:
  - "si aggiunge un campo o una tabella che decide una consegna, un costo o dove lavora un agente"
  - "si scrive una migrazione che lega righe già esistenti con eventi baseline"
  - "si cambia come agency verify confronta le tabelle con la catena"
symptoms:
  - "UPDATE tickets SET project = ... lasciava agency verify su registro integro"
  - "dopo lo spostamento, la prima chiamata pagata del ticket rilegava il progetto falso e verify tornava verde"
root_cause: data_integrity
tags: [ledger, hash-chain, agency-verify, migrations, baseline-events, tamper-evidence]
---

# Legare un dato nella catena del registro, e perché l'evento successivo può cancellarne la traccia

## Context

La catena di hash di `events` rende visibile a `agency verify` una modifica fatta a mano nel registro SQLite: ogni
evento di versione 2 porta in `payload_json` lo stato che lega, e `replay_mismatches` confronta le tabelle con
quello stato (ADR-0047, ADR-0049, ADR-0050). Il refactor ha esteso la catena tre volte, e la revisione finale ha
trovato due modi in cui un dato restava fuori: un campo mai legato (il progetto del ticket, R4) e un campo legato ma
rilegato dall'evento successivo così come lo trovava nella riga (R7). Il secondo è sottile: il caso che si voleva
scoprire, un ticket spostato su un altro cliente, produce da solo l'evento che ne cancella la traccia, perché la
prima chiamata pagata dei suoi agenti lega la riga già alterata.

## Guidance

Per legare un dato nuovo:

1. **Aggiungerlo a ciò che un evento lega**: un campo del ticket in `chain.ticket_binding` (e in `Ledger._append`),
   una riga intera in `BOUND_ROWS` di `agency.ledger.store`. La formula e la versione restano quelle di ADR-0047:
   `digest_v2` copre tutto il testo di `payload_json`, quindi una chiave nuova non chiede una versione 3.
2. **Confrontarlo in `replay_mismatches`**, con una riga in italiano nello stile delle altre («… diverso dalla
   catena»), e chiedersi su **quali eventi**: per un dato che nessun codice cambia dopo la creazione (progetto,
   contratto, hash d'apertura) l'ultimo evento non basta, perché l'evento successivo lo rilega com'è. Confrontarlo con
   ogni evento che lo porta (ADR-0054, `_bound_projects`).
3. **Scrivere una migrazione nuova**, mai toccare una applicata (ADR-0025). Porta la sua copia della formula, del JSON
   canonico e del legame, e aggiunge un evento `baseline` per riga in ordine di creazione (`rowid`), con l'ora vera
   della migrazione. La sua prova confronta i payload con `chain.canonical(...)` del codice di oggi, così una
   divergenza fra le due copie fallisce subito.
4. **Aggiornare chi legge la revisione**: `READS_REVISION` in `agency.insights.application` e la riga «revisione
   NNNN» di `web/e2e/run.spec.ts`.
5. **Adattare le prove delle migrazioni precedenti**: fermarle alla loro revisione e dire esplicitamente che cosa
   il codice di oggi trova lì (`without_project` e `unbound_projects` in `tests/test_migrations.py`), invece di
   cancellare l'asserzione.
6. **Verificare su una copia del registro reale**, mai sull'originale: `agency migrate`, `agency verify` con codice 0,
   poi una modifica a mano e `REGISTRO ALTERATO` con codice 1. Confrontare lo sha256 dell'originale prima e dopo.

## Why This Matters

Una tabella fuori dalla catena è una tabella che si può cambiare senza traccia; un dato rilegato dall'evento
successivo è peggio, perché `agency verify` lo dà per integro proprio quando l'alterazione ha già avuto effetto
(lavoro nella cartella sbagliata, spesa sul budget sbagliato).

## When to Apply

- Ogni dato nuovo che decide che cosa arriva al cliente, chi paga o dove lavora un agente.
- Ogni riga che il motore aggiorna sul posto: lì il problema resta aperto. `agency budget` rilegge la riga del
  progetto e la rilega intera, quindi una modifica a mano del suo modello o effort sparisce alla prossima modifica del
  budget, e lo stesso vale per le idee. La correzione (rifiutare la scrittura se la riga non è più quella legata, o
  confrontare ogni evento) aspetta un ADR (`docs/audit/PLAN.md`, "Third review round").

## Examples

- R4 (ADR-0053, migrazione 0009): il progetto del ticket entra in `ticket_binding`; su una copia del registro reale
  la 0009 aggiunge 35 eventi baseline e uno spostamento di T-0021 dà «T-0021: progetto diverso dalla catena».
- R7 (ADR-0054): `test_a_moved_ticket_stays_caught_after_its_next_event` sposta il ticket, aggiunge un `block` o una
  chiamata pagata, e si aspetta comunque `REGISTRO ALTERATO`.

## Related

- ADR-0047, ADR-0049, ADR-0050, ADR-0053, ADR-0054; `docs/03-DATA-MODEL.md` ("Registro: solo in aggiunta").
- Limite noto: la catena è uno sha256 senza chiave, quindi chi può scrivere il registro può ricalcolarla tutta;
  `agency verify` scopre le modifiche che lasciano intatti gli eventi.
