# ADR-0029: la proiezione di insights

**Contesto.** ADR-0019 ha deciso che il cruscotto legge attraverso la slice `agency.insights`, in sola lettura, e che le chiamate
vecchie recuperano le misure dalle tracce. Non diceva come si fonde ciò che il registro sa con ciò che sanno le tracce, quale
registro `insights` sa leggere, né come si sostituisce una proiezione mentre qualcuno la legge.

**Decisione.**
- Il registro si apre con `mode=ro` e `PRAGMA query_only`: due difese indipendenti, provate una alla volta. Chiamate e ticket si
  leggono nella stessa transazione, quindi in una fotografia coerente anche mentre il motore scrive.
- `insights` legge una sola revisione del registro, `READS_REVISION`. Un test la confronta con l'ultima migrazione: una migrazione
  nuova obbliga a decidere se cambia qualcosa per chi legge. Su un registro più vecchio dice di eseguire `agency migrate`, su uno
  più nuovo di aggiornare `insights`.
- Le misure di una chiamata vengono tutte da una sola fonte: dal registro se la chiamata le ha salvate (da M1.6), altrimenti dalle
  tracce dell'SDK unite con `request_id`, altrimenti nessuna. Mai metà da una e metà dall'altra. Ogni chiamata dice da dove vengono
  le sue misure, e la fase se è registrata o ricavata.
- La fase di una chiamata vecchia si ricava con la stessa regola che il motore usa per le nuove. La regola e il formato dei nomi
  delle istanze stanno in `agency.contracts.phase`, con un solo proprietario. Un test su un flusso completo verifica che la fase
  ricavata coincida con quella registrata per ogni chiamata.
- La proiezione si scrive sempre per intero, in un file accanto che prende il posto del vecchio solo quando è completo. Lo schema
  sta in `user_version` e le colonne nascono dal modello `Call`. Una proiezione di uno schema diverso non si migra: si rigenera con
  `agency insights`.
- `import-linter` in `make check` impone due confini. `insights` non importa il motore, `Ledger`, gli artefatti, la telemetria né
  le librerie del motore. Il motore non importa Django.

**Verifica (2026-11-02).** `tests/test_insights.py` e un test di flusso in `tests/test_sketch_flow.py`. Su copie del registro
reale migrato e delle tracce: tutte le 1.281 chiamate recuperano le misure dalle tracce, i costi coincidono con il registro (15,91,
4,45 e 34,38 $), e il registro è identico byte per byte dopo la proiezione.

**Conseguenze.**
- Ogni migrazione del registro tocca anche `insights`, almeno per aggiornare `READS_REVISION`.
- Senza tracce, le chiamate prima di M1.6 restano senza durata, TTFT, effort e ragionamento, e la proiezione lo dice.
- Le trascrizioni entrano nella proiezione con la vista Replay, non prima.
