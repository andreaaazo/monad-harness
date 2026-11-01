# ADR-0020: Django e React per il server, Taskfile e Docker attorno

**Contesto.** Il cruscotto ha bisogno di un server, e il progetto diventerà un SaaS (ADR-0023). Per il solo cruscotto locale
sarebbe bastato FastAPI. Andrea sceglie Django il 2026-11-01: account, organizzazioni, permessi, pannello di amministrazione e
migrazioni serviranno, e rifare il server dopo costerebbe di più.

**Decisione.**
- **Django** nell'ultima LTS supportata, in `agency.entrypoints.server`. È un ingresso: le view chiamano casi d'uso, e nessuna
  regola dello studio sta lì.
- **Django Ninja** per l'API: usa i modelli Pydantic come schema e genera l'OpenAPI (ADR-0022). Django REST Framework
  duplicherebbe quei modelli nei serializer.
- **React, Vite e TypeScript** in `web/`. Niente Next: il cruscotto non ha bisogno di rendering sul server.
- **Taskfile** come ingresso unico per Python, frontend e Docker. `make check` resta come alias.
- **Docker** per il server e per i servizi, con immagini bloccate per digest. Il motore resta sull'host: `bwrap`, Craft, Blender
  e GPU stanno lì (ADR-0005).

**Il confine con il registro.** Django non possiede il registro: nessun modello Django sulle sue tabelle, neppure con
`managed = False`, e nessun admin. Una scrittura fuori da `agency.ledger` aggirerebbe transizioni e catena di hash. Django riceve
un database proprio solo quando nascono i suoi dati, utenti e organizzazioni. Fino ad allora non ne ha.

**Conseguenze.**
- Due strumenti di migrazione, uno per proprietario: Alembic per il registro, Django per i dati del server.
- Il motore non importa Django, e lo impone `import-linter`.
- Le dipendenze JavaScript rispettano la quarantena di due settimane, con `minimumReleaseAge` di pnpm.
- Nel container non entrano chiave e `.env`, e la porta si pubblica solo su `127.0.0.1`. `.data` non si monta `:ro`, che con WAL
  è fragile: la sola lettura sta nella connessione.
