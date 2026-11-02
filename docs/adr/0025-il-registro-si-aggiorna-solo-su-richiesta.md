# ADR-0025: il registro si aggiorna solo su richiesta

**Contesto.** ADR-0022 ha deciso che ogni modifica al registro è una migrazione Alembic, ma non come si applica. Il registro è il
dato che non si può ricostruire, e ogni comando lo apre. Alembic su SQLite non è transazionale di suo: una migrazione fallita a
metà lascerebbe lo schema cambiato a metà.

**Decisione.**
- Un registro nuovo si crea da solo. Uno esistente non si aggiorna mai aprendolo: `Ledger` rifiuta di aprirlo e indica
  `agency migrate`.
- `agency migrate` fa una copia in `.data/backups/`, lavora in una sola transazione e conferma solo se la catena di hash regge.
- Un registro precedente ad Alembic si adotta solo se il suo schema coincide con la base. Se differisce, si ferma e dice cosa.
- Non esiste `downgrade`: si torna indietro dalla copia.
- Le migrazioni si scrivono in SQL e non importano i modelli: una migrazione vecchia non deve cambiare quando cambiano i modelli.

**Verifica (2026-11-02).** Su una copia del registro reale, 3.814 righe in 10 tabelle: rifiuto prima di `agency migrate`, tutte le
righe identiche dopo, `agency verify` integro e copia di sicurezza uguale all'originale. Riproducibile con
`tests/test_migrations.py`, che copre anche la migrazione fallita a metà e quella che rompe la catena.

**Conseguenze.** Dopo ogni migrazione nuova i comandi si fermano finché non si esegue `agency migrate`. I trigger solo in aggiunta
ora stanno nelle migrazioni: una tabella nuova che deve restare solo in aggiunta li dichiara nella propria. Un test verifica che
modelli e migrazioni coincidano.
