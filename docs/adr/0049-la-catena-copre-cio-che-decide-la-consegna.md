# ADR-0049: la catena copre ciò che decide la consegna

**Contesto.** ADR-0047 ha legato nella catena lo stato, il verdetto e la consegna di ogni ticket, e ha lasciato fuori
tre cose che decidono che cosa arriva al cliente (domanda 17 di `docs/audit/SUMMARY.md`, stessa famiglia di CMT-007):
- **il contratto e gli hash d'apertura del ticket.** `tickets.spec_json` dice chi consegna e chi accetta, se una
  consegna vuole un verdetto, quali output e quali controlli chiede `delivery_problems`; `tickets.inputs_json` tiene gli
  hash con cui si riconosce un input cambiato. Nessun codice li cambia dopo `open`, ma un `UPDATE tickets SET spec_json
  = …` che toglie un controllo faceva passare la consegna successiva senza quel controllo, e `agency verify` diceva
  «registro integro»;
- **le idee.** `concepts` si aggiorna per costruzione e non ha trigger. Il suo `status` decide quali idee si sviluppano
  e quali proposte il direttore può mettere nella presentazione; `anon`, `card_json` e `sketch_file` decidono che cosa
  mostrano la presentazione e le tavole. Un `UPDATE concepts SET status = …` cambiava ciò che arriva al cliente senza
  lasciare traccia;
- **i gate e le prove.** `gates` tiene le decisioni del cliente con gli hash dei file su cui le ha prese, `evidence` gli
  esiti dei controlli da cui dipende una consegna. Li proteggevano solo i trigger, che un `DROP TRIGGER` toglie; un
  gate non aveva alcun evento, e la nota dell'evento di una prova (`file:controllo:esito:sha256[:16]`) non veniva mai
  confrontata con la riga.

**Decisione.**
- **Il payload di versione 2 si allarga; formula e versione restano quelle di ADR-0047.** `chain.digest_v2` copre già
  tutto il testo di `payload_json`: le chiavi nuove entrano nella catena senza una versione 3.
- **Un evento di un ticket lega anche il contratto.** Oltre a `status`, `verdict` e `delivered`, porta `spec_sha256` e
  `inputs_sha256`: lo sha256 del testo di `spec_json` e di `inputs_json` così come sono salvati (`chain.ticket_binding`).
  Bastano gli hash: il contratto resta in `tickets`, e nessun codice lo cambia dopo `open`.
- **Ogni scrittura di un'idea o di un gate aggiunge un evento che lega la riga intera.** `add_concept`,
  `update_concept`, l'apertura di un ticket con la sua idea e `add_gate` scrivono, nella stessa transazione della riga,
  un evento di versione 2 con ticket `-`, attore `harness` e azione `concept` o `gate`, il cui payload è la riga dopo la
  scrittura: `{"concept": {…}}` o `{"gate": {…}}`, con il suo `seq`. Il ticket `-` tiene questi eventi fuori dalla
  storia dei ticket: il controllo di ripresa degli strumenti, i prompt e insights non li vedono.
- **L'evento di una prova lega anche la prova.** Resta sul suo ticket, con la stessa nota e lo stato del ticket, e
  porta in più la riga intera sotto `evidence`. Una prova senza ticket ha come payload solo `{"evidence": {…}}`: un
  evento con ticket `-` non ha più per forza il payload vuoto, come diceva ADR-0047.
- **La migrazione 0007 lega le righe di oggi.** Non cambia lo schema. Aggiunge, con l'ora vera della migrazione,
  attore `migrate` e azione `baseline`, un evento per ticket in ordine di creazione con stato e contratto, poi uno per
  ogni idea, gate e prova in ordine di `seq`, con ticket `-`. Come la 0006, porta una sua copia della formula, del JSON
  canonico e delle colonne che lega, perché una migrazione applicata non cambia (ADR-0025).
- **`agency verify` confronta anche queste righe.** Per ogni ticket, oltre a stato, verdetto e consegna, il contratto
  («contratto diverso dalla catena») e gli hash d'apertura («hash d'apertura diversi dalla catena»); un ticket di cui
  un evento lega lo stato ma che non è più in `tickets` dà «ticket mancante nel registro». Per ogni idea, gate e prova,
  la riga come SQLite la conserva contro l'ultimo evento che lega il suo `seq`: «riga non legata alla catena», «riga
  diversa dalla catena», e «mancante nel registro» per una riga legata che non c'è più. La riga si legge senza
  le conversioni dei modelli: `approved = 'no'` tornerebbe `True` attraverso il modello, uguale al valore legato, ma
  non è ciò che è stato scritto. Ogni differenza conta come una catena rotta: `REGISTRO ALTERATO`, codice d'uscita 1.

**Verifica (2026-11-10).** Su una copia del registro reale, alla revisione 0005 con 35 ticket, 319 eventi, 10 idee, 1
gate e 221 prove: `agency migrate` porta alla 0007 con una copia in `backups/` e aggiunge 302 eventi `baseline`, 35
della 0006 e 267 della 0007 (35 ticket, 10 idee, 1 gate, 221 prove); le altre tabelle e i 319 eventi di prima restano
identici. Dopo, con il deposito degli artefatti copiato accanto, `agency verify` dà «registro integro» e codice 0. Sulla
stessa copia, un'idea cambiata, un gate cambiato dopo `DROP TRIGGER`, una prova cancellata e un contratto cambiato danno
`REGISTRO ALTERATO`, una riga per ciascuno, e codice 1. Riproducibile con `tests/test_migrations.py`
(`test_migration_binds_every_contract_idea_gate_and_proof_into_the_chain`) e `tests/test_ledger.py`
(`test_changing_a_ticket_contract_breaks_verify`, `test_changing_an_idea_a_gate_or_a_proof_breaks_verify`,
`test_deleting_a_ticket_breaks_verify`, `test_every_idea_and_gate_write_binds_the_row`).

**Conseguenze.**
- `concepts`, `gates`, `evidence` e il contratto in `tickets` diventano proiezioni della catena, come stato, verdetto e
  consegna con ADR-0047. Il codice continua a leggerli da lì.
- La catena cresce: un evento per ogni scrittura di un'idea e per ogni gate, e l'evento di una prova porta la riga
  intera. Una scrittura di un'idea prende ora il lucchetto della catena (`BEGIN IMMEDIATE`), come le altre.
- Una migrazione futura che aggiunge una colonna a `concepts`, `gates` o `evidence` deve legare di nuovo le righe di
  quel momento: altrimenti ogni riga ha una chiave che la versione legata non ha, e `agency verify` la dà diversa.
- Dopo questa migrazione i comandi si fermano finché non si esegue `agency migrate` (ADR-0025). `insights` legge la
  revisione 0007 senza altri cambiamenti: gli eventi nuovi non sono passi del ciclo di vita, e quelli con ticket `-`
  non appartengono a nessun ticket.
- Il limite di ADR-0047 sul controllo di ripresa si ripete una volta: subito dopo la 0007 l'ultimo evento di ogni
  ticket è di nuovo `baseline`.
- La formula, il JSON canonico e le colonne legate esistono in due copie, `agency.ledger` e la migrazione 0007. Un test
  confronta gli eventi della migrazione con `chain.ticket_binding`, `chain.canonical` e le righe lette dai modelli.
- Restano protette dai soli trigger `usage`, `renders`, `derivations`, `runs`, `judgments` e `artifacts`; `projects` e
  `operations` non hanno né trigger né catena.
