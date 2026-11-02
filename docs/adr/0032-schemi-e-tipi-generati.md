# ADR-0032: schemi e tipi generati

**Contesto.** ADR-0022 vuole i modelli Pydantic come unica fonte: l'OpenAPI si genera da lì e si versiona, i tipi TypeScript si
generano dall'OpenAPI, e un test fallisce se divergono. Restava da decidere con quali strumenti, in quali versioni e dove gira il
controllo, prima che il punto 13 porti Next.js.

**Decisione.**
- La catena è una sola: modelli di `agency.insights` → `schemas/openapi.json` → `web/src/api/schema.d.ts` → il codice
  dell'interfaccia. Ogni anello si rigenera dal precedente, e nessuna forma di dato si scrive a mano.
- `uv run agency-schemas` scrive lo schema con le chiavi in ordine, così il diff si legge. Un test confronta il file versionato con
  l'API com'è, e verifica che ogni operazione sia un `GET`.
- Ogni operazione ha un nome esplicito (`listProjects`, `projectReport`, `provenance`) e dichiara il 503 con `Problem`. I tipi non
  dipendono da dove sta il codice Python, e l'interfaccia sa che forma ha l'errore quando il registro non si legge.
- I tipi TypeScript li genera `openapi-typescript`, lo strumento standard, non un generatore scritto qui. Sono `readonly`, come
  un'interfaccia che legge e basta, e i modelli si esportano con il loro nome. `--check` dice se i tipi versionati sono quelli
  dello schema, e `tsc --noEmit` in modalità `strict` controlla che si compilino.
- `web/` nasce qui, con i soli strumenti dei tipi. Next.js lo aggiunge il punto 13.
- pnpm è alla versione scritta in `web/package.json`, 12.14.0, e si avvia con `npx`: Corepack 0.24 di questa macchina non conosce le
  chiavi con cui npm firma i rilasci recenti, e spegnere la verifica non è accettabile. pnpm 12 blocca anche sé stesso nel lock.
- La quarantena è `minimumReleaseAge: 20160`, due settimane, in `web/pnpm-workspace.yaml`. Il lock è versionato e `make setup` lo
  installa con `--frozen-lockfile`.
- TypeScript resta alla 5.9.3: `openapi-typescript` 7.13.0 dichiara `^5.x`, e Next.js 16 la accetta. Le versioni 6 e 7 si
  valutano quando lo strumento le supporta.
- `make check` comprende `make web`: allineamento dei tipi e compilazione. Il punto 14 lo sposta nel Taskfile.

**Verifica (2026-11-03).** `tests/test_schemas.py` e `make web`. Ogni anello rompe `make check` quando diverge dal precedente: un
modello cambiato senza rigenerare lo schema, uno schema cambiato senza rigenerare i tipi, un tipo corretto a mano, un'operazione
usata dall'interfaccia e sparita dall'API. I 48 pacchetti del lock, pnpm compreso, hanno tutti più di due settimane.

**Conseguenze.**
- `make check` ora richiede Node e le dipendenze di `web/`, che `make setup` installa.
- Una modifica a un modello di lettura si fa in tre passi nello stesso commit: modello, `uv run agency-schemas`,
  `pnpm run api:types`. Il diff di schema e tipi si rivede insieme al codice.
