# ADR-0054: `agency verify` confronta il progetto di ogni evento

**Contesto.** ADR-0053 lega nella catena il progetto di ogni ticket, e `agency verify` lo confronta con quello
legato dall'ultimo evento del ticket. La seconda revisione del refactor (`docs/audit/PLAN.md`, R7) ha trovato il
limite: l'evento successivo del ticket lega la riga come la trova, progetto spostato compreso. Un `UPDATE tickets SET
project = 'altro'` si vedeva quindi solo finché il ticket non riceveva un altro evento, e ne riceve subito uno: la
prima chiamata pagata dei suoi agenti, che dopo lo spostamento lavorano nella cartella dell'altro cliente e gli
addebitano la chiamata, scrive un evento con il progetto nuovo. Da lì `agency verify` tornava a dire «registro
integro». Il caso che ADR-0053 voleva scoprire cancellava da solo la propria traccia.

**Decisione.**
- **`agency verify` confronta il progetto di ogni evento di versione 2 del ticket, non solo dell'ultimo.** Nessun
  codice cambia il progetto dopo `open` (ADR-0053), quindi ogni evento del ticket che porta un progetto deve portare
  quello della riga. Un valore diverso in un evento qualsiasi dà la riga già esistente «progetto diverso dalla
  catena»: `REGISTRO ALTERATO`, codice d'uscita 1.
- **Gli eventi che non portano un progetto non contano.** Sono quelli scritti prima della revisione 0009; per loro
  vale il confronto dell'ultimo evento di ADR-0053, come prima.
- **Niente migrazione e niente testo nuovo.** La catena e il formato degli eventi non cambiano: cambia solo come
  `agency verify` li legge.

**Verifica (2026-11-13).** Su una copia del registro reale portata alla revisione 0009, `agency verify` dà «registro
integro», codice 0. Spostato T-0021 da `merlo3` a `merlo2` e aggiunta una chiamata pagata su T-0021, come farebbero i
suoi agenti, dà `REGISTRO ALTERATO` con «T-0021: progetto diverso dalla catena», codice 1; prima di questa decisione
la stessa sequenza dava codice 0. Il registro reale non è cambiato. Riproducibile con `tests/test_ledger.py`
(`test_a_moved_ticket_stays_caught_after_its_next_event`, con un `block` e con una chiamata pagata come evento
successivo).

**Conseguenze.**
- `agency verify` legge tutti gli eventi una volta in più: costo lineare nel numero di eventi, come il resto della
  verifica.
- Lo stesso limite resta per gli altri campi che `open` fissa e la catena lega, lo sha256 del contratto e degli hash
  d'apertura (ADR-0049): l'evento successivo li lega come li trova. Estendere loro questo confronto è una decisione a
  parte.
- La catena resta uno sha256 senza chiave (ADR-0047): chi può scrivere il registro può anche riscrivere gli eventi e
  ricalcolarla tutta.
