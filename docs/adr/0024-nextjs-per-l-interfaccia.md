# ADR-0024: Next.js per l'interfaccia

**Contesto.** ADR-0020 aveva scelto React con Vite, "niente Next", perché il cruscotto non ha bisogno di rendering sul server. Il
2026-11-01 Andrea sceglie Next.js con TypeScript: il progetto diventerà un SaaS (ADR-0023), e l'interfaccia per il cliente di M6
e il prodotto di M7 non vanno rifatti. Questo rovescia solo la scelta di Vite: Django, Django Ninja, Taskfile, Docker e il confine
con il registro di ADR-0020 restano. Next.js è costruito su React, quindi il cruscotto resta fatto di componenti React.

**Decisione.**
- **Next.js con App Router e TypeScript `strict`**, in `web/`, con pnpm.
- **Next.js è solo interfaccia.** Django resta l'unica API. Next.js non legge il registro, `.data/` o `projects/`, non ha un
  database e non riceve la chiave. Nessuna regola dello studio sta lì, e nessuna Server Action o Route Handler con logica: sarebbero
  un secondo backend.
- **Il browser parla solo con Next.js**, che inoltra `/api` a Django con i `rewrites`: stessa origine, niente CORS.
- **Autenticazione e permessi restano in Django**, quando arriveranno in M6.

**Difese obbligatorie.** Di suo Next.js farebbe quattro cose contrarie alle regole del progetto, verificate sulla documentazione
ufficiale il 2026-11-01:
- `next dev` e `next start` ascoltano su `0.0.0.0`: si avviano con `-H 127.0.0.1`.
- Raccoglie telemetria anonima finché non la si spegne, e l'unico servizio esterno ammesso è l'API Anthropic:
  `NEXT_TELEMETRY_DISABLED=1` ovunque, build compresa.
- Scrive su disco le immagini ottimizzate, in `.next/cache/images`: sarebbero copie dei materiali del cliente fuori da `projects/`.
  `images.unoptimized` resta attivo.
- Una `fetch` senza opzioni può essere eseguita una sola volta durante `next build`, e i dati resterebbero fermi: ogni lettura usa
  `cache: 'no-store'`.

**Conseguenze.**
- Rispetto a Vite c'è un processo in più e un albero di dipendenze più grande. Il costo si paga da M1.6, il vantaggio arriva con
  M6 e M7.
- Docker ha due servizi, Django e Next.js, e si pubblica solo Next.js, su `127.0.0.1`. Dentro il container Next.js ascolta su
  `0.0.0.0` con `output: 'standalone'`: lì il confine è la porta pubblicata.
- Quando Next.js sarà raggiungibile dai clienti, le sue correzioni di sicurezza non potranno aspettare due settimane di quarantena.
  La deroga si decide prima di M6.
- ADR-0019 e ADR-0022 non cambiano: in M1.6 l'API resta di sola lettura, e i tipi TypeScript si generano dall'OpenAPI.
