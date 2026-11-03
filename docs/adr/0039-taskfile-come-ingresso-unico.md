# ADR-0039: Taskfile come ingresso unico

**Contesto.** ADR-0020 ha scelto Taskfile come ingresso unico per Python, interfaccia e Docker, con `make check` come alias. Fino a
M1.6 i comandi stavano nel Makefile, e il cruscotto si avviava con due comandi in due terminali: `uv run agency-server` e
`pnpm --dir web build && pnpm --dir web start`. Task 3.54.0 arriva da `mise.toml` (ADR-0034).

**Decisione.**
- **`Taskfile.yml` nella radice ha tutti i comandi dello studio**, ognuno con una riga che dice cosa fa: `task` li elenca.
  `check` esegue gli stessi controlli del Makefile di prima, nello stesso ordine: lint, confini, tipi, test, interfaccia,
  prove Playwright.
- **Il Makefile è solo un alias**: ogni bersaglio è `mise exec -- task <nome>`, così funziona anche senza mise attivo nella
  shell. `make setup` installa prima gli strumenti con `mise install`, perché Task viene da lì.
- **`task dashboard` avvia insieme l'API e l'interfaccia**, solo su loopback, e con `failfast`: se una delle due si ferma, Task
  ferma anche l'altra. Verificato il 2026-11-03 con la porta 8000 occupata: Task esce in un secondo e l'interfaccia non resta
  accesa da sola. Un Ctrl-C le ferma entrambe. `task dashboard:dev` fa lo stesso con l'interfaccia ricaricata a ogni modifica.
- La build di produzione dell'interfaccia si rifà solo quando cambiano le sue fonti: Task ne tiene l'impronta.
- **Niente dotenv nel Taskfile**: la chiave sta in `.env` e la legge solo il gateway, mentre qui arriverebbe a ogni comando,
  Next.js compreso. `NEXT_TELEMETRY_DISABLED=1` vale per tutti i comandi.
- `task test -- …` e `task e2e -- …` passano gli argomenti a pytest e a Playwright. `web`, `e2e` e la build dicono di eseguire
  `task setup` se manca `web/node_modules`.
- `agency-server` con la porta occupata lo dice in una riga e suggerisce `--port`, invece di un traceback.
- Le prove leggono il Taskfile con Task stesso: `--list-all --json` per i nomi, `--dry` per i comandi, senza eseguirne nessuno.
- I comandi di Docker arrivano con il punto 15.

**Conseguenze.**
- `make check`, come chiedono `CLAUDE.md` e la roadmap, resta valido: è `task check`.
- Le prove sul Taskfile hanno bisogno di Task nel PATH. Se manca, falliscono dicendo di usare mise, invece di saltare in silenzio.
