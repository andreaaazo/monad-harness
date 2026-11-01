---
name: ux-design
description: UX design — obiettivi e compiti degli utenti, architettura dell'informazione, mappa e flussi, contenuti per pagina, wireframe e prototipi in FigCraft, criteri di successo dei compiti, revisione euristica, audit di siti esistenti, piani di test con utenti. Da usare prima dell'UI di siti e app e per valutare usabilità.
---

# UX design

## Obiettivi e compiti

In `work/ux/obiettivi.md`: obiettivi del brand (misurabili quando possibile) e 3–7 compiti
principali degli utenti ("Come <utente> voglio <azione> per <scopo>"), ognuno con la fonte
(cliente, ricerca, ipotesi). Non inventare interviste o test.

## Architettura

- Inventario dei contenuti, raggruppamenti, etichette nella lingua degli utenti (lessico del
  cliente da `client-world`).
- Mappa e navigazione. **Non esiste una regola valida dei "tre clic"**: NN/g la contesta perché
  non supportata dai dati [U2]. Si valutano invece comprensione, riuscita del compito, errori e
  fatica percepita lungo il percorso.
- Flussi per i compiti principali, con errori e percorsi alternativi.

## Wireframe e prototipo

In FigCraft: bassa fedeltà, testi veri o marcati, componenti con stati, frame per desktop e
touch, collegati in un prototipo navigabile. Per ogni compito: punto di partenza, passi attesi,
**criterio di successo** (cosa deve riuscire a fare e capire l'utente) e segnali di fatica.

## Revisione euristica e audit

- Interfacce progettate o esistenti: le 10 euristiche di Nielsen [U1], ogni rilievo con
  posizione (frame o pagina, componente), gravità (0–4), proposta.
- Siti pubblicati del cliente: `web_audit.mjs <url>` misura contrasto, target, overflow, alt,
  console, prestazioni di laboratorio.

## Test con utenti

Quando il progetto lo giustifica, scrivi un piano di test (compiti, partecipanti del pubblico
pertinente, misure: riuscita, tempo, errori, commenti) da proporre al cliente. I risultati entrano
nel dossier come fatti di fonte; senza test, le aspettative sugli utenti restano ipotesi.
