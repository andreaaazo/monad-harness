# ADR-0033: il cruscotto Next.js

**Contesto.** ADR-0024 ha scelto Next.js come sola interfaccia e ha elencato quattro difese obbligatorie. Restava da decidere come
l'interfaccia legge i dati, come si provano quelle difese e in che ordine nascono le sei viste di M1.6. Costruendo la prima vista
sono emersi tre fatti che ADR-0024 non prevedeva:
- Con `output: 'standalone'` Next.js non supporta `next start`. Il server è `server.js`, che sceglie l'indirizzo da `HOSTNAME`
  e di suo ascolta su `0.0.0.0`.
- Next.js accetta qualunque `Host`, e il suo proxy riscrive l'`Host` verso Django. Una pagina ostile che fa puntare il suo dominio
  a `127.0.0.1` (DNS rebinding) leggeva le pagine e anche `/api`: `ALLOWED_HOSTS` di Django non vedeva il nome estraneo. Verificato
  il 2026-11-03 con `Host: evil.example`: 200 e i dati del registro.
- Da sola, Next.js serve le pagine statiche, come `/_not-found`, con `Cache-Control: s-maxage=31536000`.

**Decisione.**
- Le pagine leggono sul server di Next.js e mandano al browser HTML già pronto. Il browser parla solo con Next.js: niente Django
  diretto, niente CDN, niente telemetria. I `rewrites` di `/api` verso Django restano, per le viste che dovranno aggiornarsi da
  sole, ma oggi nessuna pagina li usa.
- **`src/proxy.ts` rifiuta con 400 ogni richiesta il cui `Host` non è `127.0.0.1` o `localhost`**, gli stessi di `ALLOWED_HOSTS`.
  Gira prima dei `rewrites` e senza `matcher`, quindi copre pagine, `/api` e file statici. Conta solo `Host`, che il browser non
  lascia cambiare: `X-Forwarded-Host` una pagina ostile può aggiungerlo alle sue `fetch`. È l'unico codice fra il browser e le
  pagine, e non contiene altra logica.
- Ogni pagina è dinamica (`force-dynamic`), senza `generateStaticParams`: nessuna pagina si costruisce con i dati della build.
- `src/api/client.ts` è l'unico punto che chiama `fetch`, sempre con `cache: "no-store"` e un limite di 30 secondi. I tipi vengono
  dallo schema (ADR-0032). Ogni lettura che non va diventa `ApiError`, con lo stato di Django e il suo motivo. Quando Django non
  risponde, Next.js fa come un proxy: 502 se non risponde affatto, 504 se non risponde in tempo. La pagina dice cosa è successo e
  come rimediare: 404 è un progetto sconosciuto, 503 un registro che non si legge, 502 un `agency-server` da avviare.
- Il server di produzione è `server.js` di `output: 'standalone'`, lo stesso che girerà in Docker, avviato con
  `HOSTNAME=127.0.0.1`. `next dev` parte con `-H 127.0.0.1`. La build copia accanto al server i file statici, che Next.js lascia
  fuori dalla cartella standalone (`scripts/standalone.mjs`).
- `Cache-Control: no-store` su tutto tranne `/_next/static`: copre anche le pagine statiche.
- **La vista Run** mostra il tempo di lavoro e, a parte, le attese del cliente. Un'attesa va dall'ultima chiamata prima di un
  gate, o dalla decisione prima, fino alla decisione, e conta solo se il lavoro è ripartito. La calcola `agency.insights`
  (`ProjectReport.waits`, `working_minutes`, `elapsed_minutes`), non l'interfaccia. La timeline toglie le attese dalla scala e
  le scrive in una riga loro. Senza questo, i 980 minuti di attesa del gate `concept` di `merlo3` schiacciavano in un angolo le
  due ore di lavoro.
- Le difese si provano in tre modi:
  - `scripts/check-defenses.mjs`, in `make web`, legge configurazione, script e sorgenti senza commenti. Controlla telemetria
    spenta e chiave tolta in ogni script che avvia Next.js, `-H` e `HOSTNAME` di loopback, niente `next start`, una sola `fetch`
    e sempre `no-store`, pagine dinamiche, niente Server Action, Route Handler, `middleware` o `.env`, e `src/proxy.ts` con il
    controllo dell'`Host` e senza `matcher`.
  - Le prove Playwright, in `make e2e`, verificano dal vivo ciò che la lettura non può dire: loopback, `Host` estranei, chiave
    assente nei processi dei server, intestazioni, cache, file statici serviti, Django spento.
  - `node --test`, in `make web`, prova la logica pura: formati, scala del lavoro, controllo dell'`Host`.
- Le prove usano i server veri e la build di produzione in `.next-e2e`, su porte proprie, con un registro di prova inventato
  (`tests/dashboard_fixture.py`). Un secondo server Next.js punta a una porta dove Django non c'è. Ogni server parte da un
  ambiente con una chiave finta, che il suo comando deve togliere. Tracce, video e schermate di Playwright restano spenti:
  conterrebbero i dati delle pagine.
- I tipi generati stanno in `src/api/schema.ts`. I tipi di Next.js 16 usano `URLPattern`, che TypeScript 5.9 non ha ancora, quindi
  `skipLibCheck` è attivo; il nome `.ts` fa controllare lo stesso i tipi dell'API. `next typegen` precede `tsc`, così le pagine
  usano `PageProps` delle loro rotte.
- Nessun font esterno, nessuna libreria di grafici o di stile: CSS semplice, tema chiaro e scuro dal sistema, una colonna sul
  telefono. Ciò che dicono le barre della timeline è scritto anche in testo.
- Le versioni: Next.js 16.4.2, React 19.3.1, `@types/react` 19.3.0, Playwright 1.64.1, che è la versione dei browser già in cache
  sulla macchina.
- Le viste nascono in cinque parti, ognuna con i suoi dati e le sue prove: Run; Fasi e Modello; Strumenti e QA; Confronto; Replay.

**Conseguenze.**
- ADR-0024 resta valida. Le sue difese diventano sei: si aggiungono il controllo dell'`Host` e `no-store` sulle pagine statiche,
  e per il server standalone `-H 127.0.0.1` diventa `HOSTNAME=127.0.0.1`.
- Quando arriveranno i clienti (M6), l'elenco degli host ammessi cambierà in Django e in `src/loopback.ts` insieme.
- `make check` costruisce Next.js e avvia quattro server: dura circa un minuto, ma le difese si provano a ogni modifica.
- La porta di Django nei `rewrites` si fissa quando si costruisce: le prove costruiscono per le loro porte, in una cartella propria.
- La prova sulla chiave legge `/proc`, quindi gira su Linux; altrove si salta e lo dice.
