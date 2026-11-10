# ADR-0050: la catena copre anche i costi

**Contesto.** ADR-0049 ha legato nella catena ciò che decide la consegna. Sono rimaste fuori le tabelle che decidono
i soldi e la ripresa (Task 2.F65 di `docs/audit/PLAN.md`):
- **i consumi.** `usage` ha una riga per chiamata pagata; da lì `spent()` calcola quanto ha speso un progetto, e il
  tetto di spesa decide se la chiamata successiva si fa. La proteggevano solo `usage_no_update` e `usage_no_delete`,
  che un `DROP TRIGGER` toglie;
- **i progetti.** `projects` tiene il budget, il modello e l'effort scelti dal cliente. Non aveva né trigger né
  catena: un `UPDATE projects SET budget_usd = …` alzava il tetto senza lasciare traccia;
- **i record di ripresa.** `operations` dice quali effetti degli strumenti sono già avvenuti: alla ripresa un effetto
  registrato non si ripete. Non aveva né trigger né catena, quindi un record cambiato o cancellato faceva ripetere o
  saltare un effetto. In più `record_operation` scriveva con `session.merge`, e un secondo record con lo stesso id
  riscriveva il primo. Succede alla ripresa di `view_image`: uno strumento senza effetto (`effect=False`) si riesegue
  con lo stesso id del blocco `tool_use`, e il suo gestore registra ogni volta l'immagine guardata.

Il 2026-11-10, su un registro di prova, un costo cambiato dopo `DROP TRIGGER`, una chiamata cancellata, un budget
cambiato e un progetto inserito a mano lasciavano `agency verify` a «registro integro», con codice d'uscita 0.

**Decisione.**
- **Le chiamate pagate e i progetti entrano nella catena come idee, gate e prove (ADR-0049).** Formula e versione
  restano quelle di ADR-0047; il payload di versione 2 ha due chiavi nuove, `usage` e `project`, con la riga intera.
- **Ogni chiamata pagata lega la sua riga.** `record_usage` scrive, nella stessa transazione della riga e con il
  lucchetto della catena (`BEGIN IMMEDIATE`), un evento di versione 2 con attore `harness`, azione `usage` e nota
  vuota. L'evento sta sul ticket della chiamata e porta anche lo stato del ticket, come quello di una prova; una
  chiamata senza ticket va su `-` e lega solo sé stessa. Gli esploratori in parallelo e un altro processo scrivono
  ciascuno il proprio evento, uno dopo l'altro.
- **Ogni scrittura di un progetto lega la riga intera.** `set_project` e `set_budget` aggiungono un evento con ticket
  `-` e azione `project`, con la riga come la lasciano. Il lucchetto vale dalla lettura del progetto al commit: una
  scrittura di un altro processo nel frattempo non può lasciare nella catena una riga letta prima.
- **`agency verify` confronta anche queste righe**, con le stesse tre righe di ADR-0049: «riga non legata alla
  catena», «riga diversa dalla catena» e «mancante nel registro». Una chiamata si nomina con il suo `seq`
  («consumo 12: …»), un progetto con il suo nome («progetto merlo3: …»). Ogni differenza conta come una catena rotta:
  `REGISTRO ALTERATO`, codice d'uscita 1.
- **`operations` diventa solo in aggiunta.** La migrazione 0008 aggiunge `operations_no_update` e
  `operations_no_delete`, come per le altre tabelle solo in aggiunta. `record_operation` non riscrive più un record:
  un secondo record con lo stesso id si ignora, e resta il primo. Alla ripresa si rieseguono solo gli strumenti
  senza effetto, mentre gli altri restituiscono il risultato registrato. Il primo record è quello su cui l'harness ha
  già agito: per `view_image`, è l'immagine guardata che sblocca una consegna. Un'immagine cambiata si guarda di
  nuovo, con un id nuovo.
- **La migrazione 0008 lega le righe di oggi.** Dopo i trigger aggiunge, con l'ora vera della migrazione, attore
  `migrate` e azione `baseline`, un evento per ogni chiamata pagata in ordine di `seq` e poi uno per ogni progetto in
  ordine di nome, tutti con ticket `-`. Non riscrive nessuna riga. Come la 0007, porta una sua copia della formula, del
  JSON canonico e delle colonne che lega (ADR-0025).
- **`renders`, `derivations`, `runs`, `judgments` e `artifacts` restano protette dai soli trigger.** Registrano fatti
  che l'harness ha osservato, non scelte, e ognuno è legato all'hash di un file. `runs` e `judgments` servono solo a
  confrontare esecuzioni e giudizi. Un render (`_seen_proof`) e una derivazione (`derivation_problem`) si confrontano a
  ogni controllo con gli hash dei file di adesso, e di un artefatto `agency verify` riverifica il contenuto contro il
  suo hash.

**Verifica (2026-11-10).** Il registro reale non è stato aperto: è stato copiato byte per byte, e sha256 e data di
modifica sono rimasti gli stessi. La copia era alla revisione 0005, con 35 ticket, 319 eventi, 10 idee, 1 gate, 221
prove, 1281 chiamate pagate, 1 progetto e 1486 record di ripresa. `agency migrate` la porta alla 0008, con una copia in
`backups/`, e aggiunge 1584 eventi `baseline`: 35 della 0006, 267 della 0007 e 1282 della 0008 (1281 chiamate e 1
progetto, tutti con ticket `-`). Confrontate colonna per colonna con `quote()`, le righe di tutte le tabelle e i 319
eventi di prima restano identici. Dopo, con il deposito degli artefatti copiato accanto, `agency verify` dà «registro
integro» e codice 0. Su una seconda copia, un costo cambiato dopo `DROP TRIGGER`, una chiamata cancellata e un budget
cambiato danno `REGISTRO ALTERATO`, una riga per ciascuno, e codice 1 a catena intatta. Un `UPDATE` e un `DELETE` di un
record di ripresa sono rifiutati («operations è solo in aggiunta»). Riproducibile con `tests/test_migrations.py`
(`test_migration_binds_every_cost_and_budget_into_the_chain`) e `tests/test_ledger.py`
(`test_changing_a_cost_or_a_budget_breaks_verify`, `test_every_cost_and_budget_write_binds_the_row`,
`test_parallel_paid_calls_each_bind_their_row`, `test_a_project_write_binds_the_row_it_leaves_while_another_writes`,
`test_resume_records_cannot_be_rewritten`, `test_a_repeated_operation_keeps_its_first_record`,
`test_a_replayed_view_image_shows_the_image_and_keeps_the_first_record`).

**Conseguenze.**
- `usage` e `projects` diventano proiezioni della catena, come `concepts`, `gates` ed `evidence` con ADR-0049. Il
  codice continua a leggerli da lì: `spent()` e il tetto non cambiano.
- La catena cresce di un evento per ogni chiamata pagata e per ogni scrittura di un progetto. Ora una chiamata prende il
  lucchetto della catena, come le altre scritture.
- Gli eventi `usage` stanno nella storia del loro ticket, e chi la legge filtra per azione. Il controllo di ripresa
  (`surface._replayed`) guarda l'ultimo evento: fra una transizione e il suo record di ripresa non c'è nessuna chiamata
  al modello, quindi l'ultimo evento resta la transizione. `insights` legge solo i passi del ciclo di vita, e i prompt
  prendono l'ultima nota non vuota, mentre un evento `usage` ha la nota vuota.
- La 0008 lega le righe con ticket `-`: l'ultimo evento di ogni ticket resta quello di prima, e il limite di ADR-0047
  sul controllo di ripresa questa volta non si ripete.
- Un record di ripresa ripetuto tiene il primo. Se l'immagine cambia fra la prima esecuzione e la ripresa, il record
  dice la versione di prima, e il controllo «non hai guardato un render della versione attuale» rifiuta finché il
  modello non la guarda di nuovo: al massimo un rifiuto in più, mai una consegna accettata in più.
- Una migrazione futura che aggiunge una colonna a `usage` o a `projects` deve legare di nuovo le righe di quel
  momento, come ADR-0049 chiede per idee, gate e prove.
- Dopo questa migrazione i comandi si fermano finché non si esegue `agency migrate` (ADR-0025). `insights` legge la
  revisione 0008 senza altri cambiamenti: gli eventi nuovi non sono passi del ciclo di vita.
- La formula, il JSON canonico e le colonne legate esistono in due copie, `agency.ledger` e la migrazione 0008. Un test
  confronta gli eventi della migrazione con le righe lette dai modelli.
- Restano fuori dalla catena `operations`, ora solo in aggiunta, e le cinque tabelle protette dai soli trigger: un
  `DROP TRIGGER` seguito da una riga cambiata o inventata non si vede in `agency verify`. Per `operations` e `renders`
  vuol dire che chi scrive nel registro può far risultare guardato un render che il modello non ha visto. Il controllo
  serve a far guardare il modello, non a difendersi da chi ha accesso al registro.
