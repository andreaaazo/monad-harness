# ADR-0048: le esecuzioni si registrano e si ripetono

**Contesto.** Il punto 2 di M1 in `02-ROADMAP.md` è segnato fatto («registratore per ripetere nei test le chiamate senza
spendere») e `CLAUDE.md` dice che i test usano risposte registrate. Nessuna delle due cose era vera (SIM-006, TST-009,
domanda 8 di `docs/audit/SUMMARY.md`). La coppia di M1, `RecordingTransport` e `ScriptedTransport.from_cassette`, non
era collegata a nessun comando, e comunque non poteva ripetere un'esecuzione vera:
- salvava le risposte senza le richieste, e `from_cassette` le restituiva nell'ordine del file. Cinque esploratori in
  parallelo non chiamano mai due volte nello stesso ordine, quindi una richiesta riceveva la risposta di un'altra;
- non registrava `count_tokens`: ripetuta, ogni stima valeva 1000 token, e l'autorizzazione del budget non era più
  quella dell'esecuzione vera;
- scriveva da thread paralleli senza lock.

Il 2026-11-10, su `2fb371e`: registrate le richieste A e B in quest'ordine, la ripetizione chiesta prima B e poi A dava
a B la risposta di A e ad A quella di B; un `count_tokens` che dal vivo valeva 110 ripetuto valeva 1000; la riga
registrata aveva solo `model` e `response`.

**Decisione.**
- **La chiave è la richiesta canonica.** `request_key` (`agency.gateway.recording`) è lo sha256 del JSON di `model`,
  `system`, `tools`, `messages` e `output_config`, con le chiavi ordinate, senza spazi, in UTF-8. Ne restano fuori
  `thinking` e `cache_control`, uguali in ogni chiamata del gateway, e `max_tokens`. Quest'ultimo cambia solo quando il
  loop ripete una risposta troncata con la stessa richiesta: le due chiamate hanno la stessa chiave, e la ripetizione
  le serve nell'ordine in cui sono state registrate.
- **Ogni riga dice il tipo di chiamata.** Una riga è `{"kind", "key", "request", "response"}`, con `kind`
  `count_tokens` o `stream`. Il gateway passa gli stessi parametri a tutte e due, quindi senza il tipo le chiavi
  coinciderebbero. `count_tokens` si registra: ripetuta, l'autorizzazione del budget è la stessa.
- **Una riga per chiamata, sotto un solo lock.** `RecordingTransport` chiama il trasporto vero fuori dal lock, così gli
  esploratori restano in parallelo. Poi, tenendo il lock, apre il file in aggiunta, scrive la riga intera e lo chiude.
  Una chiamata che solleva un errore non lascia righe.
- **Una cassetta per esecuzione:** `.data/cassettes/<progetto>/<esecuzione>.jsonl` (`DataLayout.cassette`). La
  registrazione parte quando il numero dell'esecuzione è noto (`Session._record`) e avvolge sempre il trasporto con cui
  si è aperta la sessione: un secondo comando nella stessa sessione scrive nella sua cassetta, senza registratori
  annidati.
- **Si registra solo su richiesta:** `agency run|resume|decide --record`, cioè `open_session(..., record=True)`. Senza
  l'opzione nulla cambia e la cartella non nasce. Il comando di avvio di `merlo4` in `02-ROADMAP.md` ha `--record`.
- **La cartella non è versionata.** Sta sotto la radice dei dati, come `.data/runs/`: l'esecuzione di un cliente vero
  contiene i suoi materiali, dal brief ai turni interi.
- **La ripetizione sta nei test.** `ReplayTransport` (`tests/support/replay.py`) indicizza le risposte per tipo e
  chiave, con una coda per chiave: richieste uguali ricevono le risposte nell'ordine in cui sono state registrate, in
  qualunque ordine arrivino le altre. Una richiesta che la cassetta non ha solleva `MissingRecording`, che nomina tipo,
  modello, numero di messaggi e l'inizio dell'ultimo: la prima differenza dice a quale turno la ripetizione ha lasciato
  la strada registrata. Nulla sotto `src/` la importa, quindi nessun percorso di produzione risponde da una cassetta.
  `ScriptedTransport` resta in `gateway/transport.py` fino al Task 4.3 di `docs/audit/PLAN.md`.
- **Nei test entrano solo esecuzioni su brief inventati.** La cassetta di un brief inventato (E1–E8) si può copiare a
  mano in `tests/`, dopo una revisione che confermi che non contiene la chiave. Le risposte non portano intestazioni, e
  un test lo verifica con una chiave canarino; la revisione si fa lo stesso.

**Verifica (2026-11-10).** `tests/test_recording.py`. `test_a_recorded_run_replays_to_the_same_ledger` registra il
progetto completo di `test_agent_flow.py`, con VectorCraft, rendering e sandbox veri, fino al gate finale e poi un
rifiuto del cliente: due esecuzioni, due cassette. Ripetuto su un'altra cartella dei dati, fa tutte le chiamate
registrate e nessun'altra, e lascia gli stessi ticket, eventi e righe di consumo.
`test_parallel_recording_replays_in_any_order` registra cinque esploratori in parallelo e li ripete in ordine mescolato;
`test_count_tokens_is_replayed` e `test_a_recording_never_contains_the_key` coprono il resto.

**Conseguenze.**
- La ripetizione chiede strumenti locali deterministici. Nel progetto di prova lo sono: le richieste ripetute sono
  identiche byte per byte, anche da un'altra cartella dei dati. Il master di VectorCraft no: porta in `"created"` l'ora
  della creazione, in secondi, e il suo hash cambia da un'esecuzione all'altra. Oggi nessuna richiesta lo contiene; un
  turno che leggesse il master, o il suo hash, mancherebbe la registrazione proprio lì, e `MissingRecording` lo
  direbbe.
- Una cassetta di `merlo4` è il golden master di M1.7: ripetuta sul motore diviso, una richiesta che cambia anche di un
  byte manca la registrazione al turno che è cambiato.
- Un tentativo fallito non lascia righe. Uno stream con il JSON degli strumenti illeggibile si ripete dal vivo con la
  stessa richiesta: ripetuta, quella richiesta riceve subito la risposta del tentativo riuscito, e il registro ha una
  riga di consumo `malformed_stream` in meno. Un'esecuzione fermata da un errore dell'API, ripetuta, si ferma con
  `MissingRecording` alla chiamata fallita.
- Una cassetta contiene le richieste intere, immagini comprese: pesa quanto le trascrizioni, o di più.
