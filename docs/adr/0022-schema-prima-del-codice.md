# ADR-0022: lo schema viene prima del codice

**Contesto.** Il progetto ha già contratti Pydantic e strumenti `strict`, ma il resto non segue la stessa regola.
`ledger/models.py` promette che ogni modifica è una migrazione, mentre `ledger/store.py` usa solo `create_all`, che non aggiunge
colonne alle tabelle esistenti. `03-DATA-MODEL.md` descriveva artefatti per hash mai costruiti. Con un server e un frontend,
ogni dato avrebbe più copie da tenere allineate a mano. Due esecuzioni oggi non si confrontano: né il giudizio alla cieca né le
versioni di prompt, CLI e lock vengono salvati.

**Decisione.**
- Una capacità nuova inizia dal suo schema: contratto, tabella o risposta API. Il codice viene dopo.
- I modelli Pydantic sono l'unica fonte. L'OpenAPI si genera da lì e si versiona in `schemas/openapi.json`, e i tipi TypeScript
  si generano dall'OpenAPI. Un test fallisce se divergono.
- Le risposte dell'API sono modelli di lettura propri, non tabelle esposte.
- Ogni modifica al registro è una migrazione Alembic, provata su una copia del registro vero. Dopo deve passare `agency verify`.
- Le righe storiche non si riscrivono. Le colonne nuove restano vuote sulle righe vecchie, e i dati storici si ricavano nella
  proiezione di `insights`.
- `runs` registra l'impronta di ogni esecuzione: prompt, registry, lock, CLI, modello ed effort.
- `judgments` registra il punteggio alla cieca, legato allo sha256 del file giudicato.
- Gli artefatti per hash si costruiscono in M1.6: un giudizio deve restare legato a un file che non cambia.

**Conseguenze.** Il primo lavoro di M1.6 riguarda i dati, non l'interfaccia. Un cambiamento di schema non può più passare in
silenzio tra motore, API e frontend. `checkpoints.sqlite` resta fuori dalle migrazioni: lo gestisce LangGraph.
