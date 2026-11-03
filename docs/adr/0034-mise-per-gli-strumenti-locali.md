# ADR-0034: mise per gli strumenti locali

**Contesto.** ADR-0032 avviava pnpm con `npx`, alla versione scritta in `web/package.json`, perché Corepack 0.24 di questa macchina
non verifica i rilasci recenti di pnpm. Funzionava, ma era un giro: le versioni di Node, pnpm, uv e Task dipendevano da ciò che
c'era sulla macchina, e ogni strumento si procurava a modo suo. Il 2026-11-03 Andrea sceglie mise come ambiente locale. Decide
anche che uno strumento da installare sulla macchina lo installa lui, su indicazione precisa, invece di aggirarlo.

**Decisione.**
- `mise.toml` nella radice fissa le versioni esatte: Node 22.22.1, pnpm 12.14.0, uv 0.12.5, Task 3.54.0. Sono quelle già
  verificate con il progetto, e tutte hanno più di due settimane.
- mise scarica pnpm, uv e Task dai rilasci ufficiali su GitHub con verifica del checksum, e Node dal sito ufficiale.
- Python resta a uv, che lo sceglie da `pyproject.toml`: un solo proprietario.
- mise non carica `.env` nell'ambiente delle shell: la chiave API arriverebbe a ogni processo, Next.js e Django compresi. In
  compenso imposta `NEXT_TELEMETRY_DISABLED=1` in ogni shell del progetto.
- `make setup` esegue `mise install`, poi `uv sync` e `pnpm install --frozen-lockfile` attraverso `mise exec`, così funziona anche
  prima che mise sia attivo nella shell. Gli altri comandi usano gli strumenti del PATH, cioè quelli di mise.
- La versione di pnpm compare anche in `web/package.json` (`packageManager`), che pnpm legge: un test verifica che sia la stessa di
  `mise.toml`, e che Node soddisfi il minimo di Next.js.
- Questo rovescia la scelta di `npx` in ADR-0032. Il resto di ADR-0032 resta valido.

**Conseguenze.**
- Chi lavora sul progetto installa mise una volta e lo attiva nella shell.
- Cambiare la versione di uno strumento è una riga in `mise.toml`, rivista come il resto del codice.
- Docker e i browser di Playwright restano strumenti della macchina: mise non li gestisce.
