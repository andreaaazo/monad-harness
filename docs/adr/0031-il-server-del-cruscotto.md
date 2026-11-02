# ADR-0031: il server del cruscotto

**Contesto.** ADR-0019 e ADR-0020 hanno deciso un server Django con Django Ninja, separato dal motore, in sola lettura, solo su
loopback e senza chiave. Non dicevano con quale server WSGI gira, come si difende da una pagina web che lo raggiunge dal browser,
come resta aggiornato mentre il motore lavora, né come si impedisce al codice del server di toccare la configurazione del motore.

**Decisione.**
- Il server sta in `agency.entrypoints.server` e si avvia come processo suo: `uv run agency-server`. Gira sul server WSGI della
  libreria standard, con un thread per richiesta: basta per un solo operatore su questa macchina, e non aggiunge dipendenze. Come
  raggiungerlo da fuori, e con quale server, lo decide l'ADR di M6.
- Ascolta solo su indirizzi IPv4 di loopback, scritti come indirizzi: `0.0.0.0`, un IP di rete o un nome si rifiutano prima
  dell'avvio.
- Contro il DNS rebinding, in cui una pagina web fa puntare un suo nome a `127.0.0.1` e legge il server dal browser,
  `ALLOWED_HOSTS` ammette solo `127.0.0.1` e `localhost`. Django lo controlla solo quando qualcuno chiede l'host, quindi il
  middleware lo chiede su ogni richiesta, per primo.
- Solo `GET`, due volte: le route dichiarano solo `GET`, e un middleware rifiuta ogni altro metodo prima di qualunque view.
  Ogni risposta porta `Cache-Control: no-store`, `nosniff` e `X-Frame-Options: DENY`.
- Nessuna app, nessun modello e nessun database: Django non possiede il registro. `DEBUG` è spento, e la `SECRET_KEY` nasce a ogni
  avvio, perché non c'è niente da firmare.
- La documentazione di Ninja è spenta, perché caricherebbe i suoi script da una CDN. Lo schema resta in `/api/openapi.json`.
- Il server non importa `agency.config`, che legge `.env`, né il motore né `Ledger`. Dove stanno i file in `.data/` lo dice
  `agency.contracts.layout`, l'unico proprietario per chi scrive e per chi legge. L'unica variabile che legge è
  `AGENCY_DATA_DIR`, e all'avvio toglie la chiave API dal proprio ambiente.
- La proiezione si rifà solo quando registro o tracce sono cambiati: dimensione e ora di modifica dei file si salvano con la
  proiezione. Un WAL vuoto vale come assente, perché la prima lettura in sola lettura lo crea. `agency report` usa lo stesso
  controllo.
- `import-linter` ha tre contratti. `insights` legge e basta. Il server legge e basta, senza motore, `Ledger` né `.env`. Il motore
  non importa Django né il server: i pacchetti sono elencati a mano, e un test fallisce se uno nuovo non c'è.

**Verifica (2026-11-02).** `tests/test_server.py`. Su una copia del registro reale migrato, con `agency-server` avviato come
processo: elenco dei progetti e rapporto di `merlo3` con 34,38 $ e 13,29 $ fino al gate, scritture rifiutate con 405, host
estraneo con 400, documentazione assente, registro identico byte per byte dopo l'uso. Il rapporto risponde in 0,15 secondi con la
proiezione da rifare, in 0,02 secondi dopo.

**Conseguenze.**
- Il cruscotto vede il lavoro del motore mentre accade, senza comandi in più.
- Togliere la chiave dall'ambiente protegge il codice del server, non il processo che l'ha lanciato: Taskfile e Docker non la
  passano proprio (punti 14 e 15).
- Il server WSGI della libreria standard non è fatto per essere esposto: resta su loopback finché M6 non decide altrimenti.
- Le impronte delle sorgenti entrano nella provenienza, quindi lo schema della proiezione passa alla versione 3. Un test calcola
  l'impronta dei modelli salvati e fallisce se cambiano senza che cambi lo schema: una proiezione vecchia si rifà, non si
  legge male.
