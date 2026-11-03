# ADR-0038: la vista Replay

**Contesto.** La roadmap chiede alla vista Replay cosa è successo davvero: un'istanza turno per turno, con le immagini. Tutto sta
nella trascrizione dell'istanza: il compito, il ragionamento, il testo, gli strumenti chiesti e le loro risposte, le immagini
restituite da `view_image` in base64, l'esito. ADR-0029 voleva le trascrizioni nella proiezione con questa vista. Ma sono 19 MB
per tre progetti, quasi tutte immagini, e una copia in SQLite non aggiungerebbe niente. Le misure di ogni chiamata stanno invece
in `usage`: la trascrizione non diceva a quale chiamata appartiene ogni risposta.

**Decisione.**
- **Il Replay legge la trascrizione quando la si apre, in sola lettura, e non la copia.** La proiezione resta come in ADR-0036:
  dalle trascrizioni solo strumenti e rifiuti. Questo rovescia la parte di ADR-0029 sulle trascrizioni.
- **Il motore scrive il `request_id` accanto a ogni risposta del modello** in trascrizione. La ripresa legge solo il messaggio,
  quindi le trascrizioni vecchie e nuove si riprendono uguali. Il Replay lega ogni turno alla sua riga di `usage` con quel
  `request_id`.
- Per le trascrizioni di prima, turni e chiamate si legano **per ordine**. Si tolgono le risposte che il ciclo dell'agente non
  scrive in trascrizione: `max_tokens`, che richiede, e `refusal`, dopo cui blocca il ticket. Verificato il 2026-11-03 su tutte le
  56 istanze di `merlo`, `merlo2` e `merlo3`. Se i conti non tornano nessun turno prende le misure di un altro, e la pagina lo dice.
- Una chiamata senza turno, cioè una risposta scartata, si mostra dove è avvenuta: prima del turno che la segue, o in fondo.
- **Le immagini passano da una route di Django**, `/api/projects/{name}/instances/{instance}/images/{n}`. Si decodificano dalla
  trascrizione e si servono solo se sono PNG, JPEG, GIF o WebP: mai SVG, che può contenere script. Arrivano con
  `Cache-Control: no-store`, `nosniff` e `Content-Security-Policy: default-src 'none'; sandbox`. Il browser le chiede a Next.js,
  che le inoltra con i `rewrites` di ADR-0033: è la prima vista che li usa. Next.js non le ottimizza e non le scrive, e un test
  cerca file PNG nella build.
- Un nome che non è quello di un'istanza non diventa mai un percorso, e il file deve stare nella cartella delle trascrizioni: sono
  due difese, ognuna con la sua prova. Il percorso lo decide `DataLayout`.
- Le pagine sono `/projects/{name}/replay`, l'elenco delle istanze, e `/projects/{name}/replay/{istanza}`. Ragionamento e
  richieste agli strumenti stanno chiusi; i risultati si leggono su una riga e per intero a richiesta. Un risultato oltre 20.000
  caratteri tiene l'inizio e la fine.

**Conseguenze.**
- Da `merlo4` ogni turno è legato alla sua chiamata in modo esatto. Per i progetti di prima vale l'ordine.
- L'istanza più lunga di `merlo3` (T-0029-a1: 128 turni, 41 immagini) pesa 1,1 MB di HTML, 167 KB compressi, servita in 74 ms. Le
  immagini si caricano solo quando entrano nello schermo.
- Le immagini sono materiali del cliente: escono dalla trascrizione solo verso il browser, su loopback, e non restano da nessuna
  parte.
