# ADR-0053: la catena lega il progetto di ogni ticket

**Contesto.** ADR-0047 e ADR-0049 hanno legato nella catena lo stato, il verdetto, la consegna, il contratto e gli hash
d'apertura di ogni ticket. È rimasto fuori `tickets.project`, e la revisione finale del refactor l'ha trovato
(`docs/audit/PLAN.md`, R4): un `UPDATE tickets SET project = 'altro'` lasciava `agency verify` su «registro integro»,
codice 0. Eppure il progetto di un ticket decide due cose:
- **la cartella di lavoro** in cui scrivono i suoi agenti: `AgentRunner` la ricava da `ledger.project_of`;
- **il budget** su cui il gateway autorizza e registra ogni chiamata pagata del ticket (`CallContext.project`).

Spostare un ticket su un altro cliente faceva quindi lavorare i suoi agenti nella cartella di quel cliente, e gli
addebitava le chiamate. `tickets` non ha trigger, e nessun codice cambia il progetto dopo `open`.

**Decisione.**
- **Il payload di versione 2 si allarga ancora; formula e versione restano quelle di ADR-0047.** L'evento di un ticket
  porta anche `project`, il nome del progetto così come è salvato (`chain.ticket_binding`). Basta il nome: è la chiave
  del progetto, e non cambia.
- **La migrazione 0009 lega i progetti di oggi.** Non cambia lo schema e non riscrive righe. Aggiunge, con l'ora vera
  della migrazione, attore `migrate` e azione `baseline`, un evento per ticket in ordine di creazione con stato,
  contratto e progetto. Come le 0006-0008, porta una sua copia della formula e del legame del ticket, perché una
  migrazione applicata non cambia (ADR-0025).
- **`agency verify` confronta anche il progetto.** Un ticket il cui progetto è diverso da quello legato dal suo ultimo
  evento dà «progetto diverso dalla catena»: `REGISTRO ALTERATO`, codice d'uscita 1.

**Verifica (2026-11-13).** Su una copia del registro reale, alla revisione 0005 con 35 ticket di tre progetti e 319
eventi: `agency migrate` porta alla 0009 con una copia in `backups/`, la 0009 aggiunge un evento `baseline` per ticket
con il suo progetto, e `agency verify` dà «registro integro» e «artefatti integri: 2», codice 0. Sulla stessa copia, un
ticket di `merlo3` spostato su `merlo2` dà `REGISTRO ALTERATO` con «T-0021: progetto diverso dalla catena», codice 1.
Il registro reale non è cambiato: stesso sha256 prima e dopo. Riproducibile con `tests/test_ledger.py`
(`test_moving_a_ticket_to_another_project_breaks_verify`) e `tests/test_migrations.py`
(`test_migration_binds_every_ticket_project_into_the_chain`).

**Conseguenze.**
- Il progetto in `tickets` diventa una proiezione della catena, come stato, verdetto, consegna e contratto. Il codice
  continua a leggerlo da lì.
- Un registro alle revisioni 0006-0008 non lega ancora il progetto. I comandi si fermano finché non si esegue
  `agency migrate` (ADR-0025); un test che apre un registro di quelle revisioni con il codice di oggi trova una riga
  «progetto diverso dalla catena» per ticket.
- `insights` legge la revisione 0009 senza altri cambiamenti: gli eventi `baseline` non sono passi del ciclo di vita.
- Il limite di ADR-0047 sul controllo di ripresa si ripete una volta: subito dopo la 0009 l'ultimo evento di ogni
  ticket è di nuovo `baseline`.
- La catena resta uno sha256 senza chiave (ADR-0047): chi può scrivere il registro può ricalcolarla tutta. `agency
  verify` scopre, come prima, le modifiche che lasciano intatti gli eventi.
