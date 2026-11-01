# Regole per lavorare su questa repo

Harness della design agency. Prima di cambiare l'architettura leggi `docs/01-ARCHITECTURE.md` e gli
ADR in `docs/adr/`. Una decisione nuova o rovesciata è un ADR nuovo, non una modifica silenziosa.

## Comandi

- `make check` prima di dichiarare finito un lavoro: lint, tipi, test.
- `uv run …` per tutto ciò che è Python; dipendenze solo con `uv add` e lock aggiornato.
- `make doctor` controlla la macchina.

## Vincoli

- **`legacy/` non si tocca.** È il backup congelato; un test ne verifica gli hash.
- **Niente chiamate all'API nei test**: spendono soldi veri. I test usano risposte registrate; ogni
  prova dal vivo si fa solo su richiesta e con un tetto di spesa dichiarato.
- **La chiave API vive nel gateway**: mai nei log, mai dentro una sandbox, mai in un file versionato.
- **Mai eseguire launcher o programmi sconosciuti per esplorarli**: `artcraft-launcher` installa
  software. Solo le CLI elencate in `docs/04-TOOLS.md`.
- **Lo studio non scrive codice di siti e app.** Consegna design e specifiche.
- **I materiali del cliente** restano nel suo progetto, fuori da `src/`, `registry/` e `docs/`.

## API Claude

Prima di scrivere codice che chiama l'API, usa la skill `claude-api`: i parametri cambiano spesso.
Fatti che il progetto dà per stabiliti:

- Modelli: `claude-opus-5-5` di default, `claude-sonnet-5-5` per i ruoli indicati in
  `registry/roles.json`. Non cambiare modello per ridurre i costi senza una decisione esplicita.
- La cronologia dei turni è **solo in aggiunta**: non modificare mai turni già inviati.
- Niente `tool_choice` forzato, `budget_tokens`, prefill o `temperature`: l'API risponde 400.
- Sempre controllare `stop_reason` prima di leggere `content`.

## Stile

Codice in inglese, documenti e messaggi per l'utente in italiano. Moduli piccoli con un solo
proprietario di ogni dato. Le regole dello studio stanno in dati (`registry/`) o contratti, non in
condizioni sparse. Una regola che si può imporre nel codice non si scrive in un prompt.

Principi di struttura: modular monolith in vertical slices, explicit over implicit, Clean Architecture, Schema-First Design e
testing pyramid (ADR-0021, ADR-0022). Il motore non importa Django. Django non possiede il registro e non esegue il grafo
(ADR-0019, ADR-0020). Next.js è solo interfaccia: legge tutto dall'API Django (ADR-0024).

## Fine traguardo

Aggiorna `docs/PARITY.md` e lo stato in `docs/02-ROADMAP.md`. Un criterio di uscita conta solo se
verificato, con il modo di riprodurlo.
