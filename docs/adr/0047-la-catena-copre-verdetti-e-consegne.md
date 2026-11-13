# ADR-0047: la catena copre verdetti e consegne

**Contesto.** La catena di hash di ADR-0001 copriva di ogni evento solo `prev, ticket_id, at, actor, action, note`. Il
verdetto di una revisione e gli hash dei file consegnati stavano soltanto in `tickets`, una tabella che si aggiorna per
costruzione e non ha trigger. Sono i due fatti che decidono che cosa arriva al cliente, ed erano fuori dalla catena. Il
2026-11-09, su un registro di prova, un `UPDATE tickets SET verdict = 'READY'` diretto su una revisione consegnata con
`REVISE` lasciava `agency verify` a «registro integro», con codice d'uscita 0 (CMT-007, domanda 17 di
`docs/audit/SUMMARY.md`). `03-DATA-MODEL.md` diceva già che `tickets` è una vista e che la verità è la storia degli
eventi: il codice non lo garantiva.

**Decisione.**
- **Gli eventi hanno una versione.** `events` ha due colonne nuove, `version` e `payload_json`. Un evento di versione 2
  porta in `payload_json` lo stato del suo ticket dopo l'evento, in JSON canonico (chiavi ordinate, senza spazi):
  `{"delivered": {…}, "status": "…", "verdict": …}`. Il suo hash copre anche quel testo: è lo sha256 di
  `[prev, ticket_id, at, actor, action, note, payload_json]` (`chain.digest_v2`).
- **Ogni evento nuovo è di versione 2 e porta lo stato intero**: l'apertura, ogni transizione e anche le prove. La
  domanda 17 lo chiedeva per consegna e rimando; lo stato intero su ogni evento è un di più voluto, perché così per
  sapere che cosa deve dire `tickets` basta l'ultimo evento del ticket, senza rifare la storia. Un evento che non
  appartiene a nessun ticket (una prova registrata senza ticket, `-`) ha il payload vuoto.
- **Le righe vecchie non si riscrivono.** Restano di versione 1, con `payload_json` vuoto, e si verificano con la formula
  con cui sono state scritte. `chain.intact` sceglie la formula dalla versione di ogni riga; una versione che nessuna
  formula conosce rompe la catena.
- **La migrazione 0006 lega lo stato di oggi.** Aggiunge le due colonne e poi, per ogni ticket in ordine di creazione, un
  evento `baseline` di versione 2 (attore `migrate`, nota vuota) con lo stato che `tickets` ha in quel momento e con
  l'ora vera della migrazione. Da lì in poi lo stato di ogni ticket è nella catena. La migrazione porta una sua copia
  della formula e del JSON canonico, perché una migrazione applicata non cambia (ADR-0025).
- **`agency verify` rifà il conto.** Per ogni ticket confronta `tickets` con lo stato legato dal suo ultimo evento
  (`Ledger.replay_mismatches`). Un ticket senza eventi, o con l'ultimo evento di versione 1, dà «stato non legato alla
  catena»; uno stato, un verdetto o una consegna diversi danno «stato diverso dalla catena», «verdetto diverso dalla
  catena» o «consegna diversa dalla catena». Una differenza conta come una catena rotta: `REGISTRO ALTERATO`, una riga
  per differenza, codice d'uscita 1.

**Verifica (2026-11-09).** Su una copia del registro reale, alla revisione 0005 con 35 ticket e 319 eventi:
`agency migrate` porta alla 0006 con una copia in `backups/`, aggiunge 35 eventi `baseline`, uno per ticket, e lascia
identiche tutte le altre righe. Dopo, con il deposito degli artefatti copiato accanto, `agency verify` dà «registro
integro» e codice 0. Riproducibile con `tests/test_migrations.py` (`test_migration_binds_every_ticket_state_into_the_chain`,
`test_v1_events_still_verify`) e `tests/test_ledger.py` (`test_changing_a_verdict_in_tickets_breaks_verify`).

**Conseguenze.**
- `tickets` è ora ciò che `03-DATA-MODEL.md` ha sempre detto: una proiezione degli eventi. Il codice continua a leggere
  da lì stato, verdetto e consegna, ma una modifica diretta si vede in `agency verify`.
- Dopo questa migrazione i comandi si fermano finché non si esegue `agency migrate` (ADR-0025). `insights` legge la
  revisione 0006 senza altri cambiamenti: gli eventi `baseline` non sono passi del ciclo di vita e non entrano nella
  storia dei ticket che mostra.
- Subito dopo la migrazione l'ultimo evento di ogni ticket è `baseline`. Il controllo di ripresa degli strumenti
  (`surface._replayed`, Task 2.20) guarda l'azione dell'ultimo evento: una consegna interrotta esattamente a cavallo di
  `agency migrate`, già scritta nel registro ma non ancora nel registro della ripresa, non viene riconosciuta come fatta.
  Lo strumento la tratta come una consegna nuova, che il registro rifiuta. Serve un'interruzione con una migrazione in
  mezzo; qui non si corregge.
- La formula v2 e il JSON canonico esistono in due copie, `agency.ledger.chain` e la migrazione 0006. Un test confronta
  gli eventi della migrazione con `chain.ticket_state` e con `chain.intact`.
- Restano fuori dalla catena il contratto e gli hash d'apertura del ticket, le idee, e le tabelle protette solo dai
  trigger, come gate e prove: `docs/audit/PLAN.md`, Task 2.F56, 2.F57 e 2.F58.
