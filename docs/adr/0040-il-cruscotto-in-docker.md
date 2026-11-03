# ADR-0040: il cruscotto in Docker

**Contesto.** ADR-0020 vuole Docker per Django e Next.js, con il motore sull'host. ADR-0024 ha fissato il confine: si pubblica solo
Next.js, su `127.0.0.1`. Il cruscotto legge il registro, le tracce e le trascrizioni in `.data/`, mentre il motore li scrive. Tre
fatti, verificati il 2026-11-03, hanno deciso la forma:
- Compose legge da solo il `.env` della cartella del progetto per le sue variabili, e il `.env` della radice contiene la chiave.
- Il registro è in modalità WAL: per leggerlo, SQLite crea il file `-shm` se non c'è, e il motore lo cancella quando chiude. Su un
  mount di sola lettura il registro non si apre: provato, `unable to open database file`.
- Il contesto di build è la radice del repo, con `.env`, `.data/` e i progetti del cliente.

**Decisione.**
- **Due servizi, uno spazio di rete.** `api` è Django, che anche nel container ascolta solo su `127.0.0.1`. `web` è Next.js e
  condivide la rete di `api` (`network_mode: service:api`): raggiunge Django su `127.0.0.1:8000`, con gli stessi `rewrites` e
  lo stesso `ALLOWED_HOSTS` di quando gira sull'host. Next.js ascolta su `0.0.0.0` del suo spazio di rete, e l'unica porta
  pubblicata è la 3000, su `127.0.0.1` della macchina.
- **Il file Compose sta in `docker/`**, così Compose non legge il `.env` della radice. Niente `env_file`, niente chiavi: i
  container ricevono solo `AGENCY_DATA_DIR` e `AGENCY_PROJECTION_DIR`.
- **`.data` è montato in lettura e scrittura, con l'utente dell'host.** In sola lettura il cruscotto si romperebbe ogni volta che il
  motore è spento. Con lo stesso UID e GID, i file che SQLite crea leggendo restano dell'utente, e il motore li riscrive. Il server
  ha gli stessi diritti di quando gira sull'host, e le stesse difese: connessione `mode=ro`, `query_only`, API solo GET, nessun
  modello Django.
- **La proiezione di insights sta in memoria** (`AGENCY_PROJECTION_DIR` su tmpfs): si rifà a ogni avvio, e il container non
  aggiunge file al registro. Senza la variabile la proiezione resta accanto al registro, come prima.
- **Ogni container ha il disco in sola lettura e niente privilegi**: `read_only`, `cap_drop: ALL`, `no-new-privileges`, un init che
  inoltra i segnali. Django gira con l'utente dell'host, Next.js come `node`.
- **I contesti di build sono elenchi di ciò che può entrare.** Un `.dockerignore` per Dockerfile esclude tutto e riammette solo
  `pyproject.toml`, `uv.lock`, `README.md` e `src/` per l'API, e solo `web/` senza `node_modules`, build, dati delle prove e `.env`
  per l'interfaccia.
- **Le immagini sono bloccate per digest**, pubblicate da più di due settimane (ADR-0006), alle versioni di `mise.toml` e
  `.python-version`: Python 3.13.15, uv 0.12.5, Node 22.22.1, pnpm 12.14.0. L'interfaccia si costruisce nell'immagine dal lock,
  con la quarantena di pnpm. La build è la stessa standalone delle prove Playwright.
- Un registro che SQLite non riesce ad aprire ora diventa il solito 503 con il motivo, e non più un 500: valeva anche fuori da
  Docker.
- `task docker:up` avvia con il registro di `.data`, o con quello di `AGENCY_DATA`, e con l'utente di chi lo lancia. Un Ctrl-C
  ferma tutto, `task docker:down` toglie i container. Le prove leggono la configurazione con `docker compose config`, senza
  demone, e su una macchina senza il client docker si saltano.

**Conseguenze.**
- Verificato dal vivo il 2026-11-03, su un registro di prova chiuso dal motore e su una copia migrata di quello vero:
  - tutte le viste rispondono, immagini comprese;
  - la porta 3000 risponde solo su `127.0.0.1`, la 8000 non è pubblicata, e dalla rete tutte e due rifiutano;
  - un `Host` estraneo riceve 400, e una chiave finta nell'ambiente di chi avvia non arriva a nessun container;
  - il motore scrive mentre il cruscotto legge, senza conflitti.
- L'immagine dell'API pesa 464 MB, perché installa tutte le dipendenze del pacchetto. Un gruppo di dipendenze solo per il server
  la ridurrebbe: si decide quando serve.
- Aggiornare Node, pnpm, uv o Python vuol dire cambiare insieme `mise.toml` e i Dockerfile: un test li confronta.
