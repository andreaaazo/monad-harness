# ADR-0018: un contratto impossibile non si apre

**Contesto.** Su `merlo3`, dopo il gate `concept`, quattro revisioni su quattro hanno finito il lavoro senza poterlo
consegnare. `T-0030` e `T-0031` chiedevano il referto fuori da `reviews/`, dove un revisore non può scrivere. `T-0032` e
`T-0033` mettevano i controlli visivi sul referto, che non si può rendere né guardare. Il direttore aveva scritto il
contratto sensato, referto come output e controllo sullo SVG, e il sistema lo aveva rifiutato con un messaggio che
spingeva verso quello impossibile. Costo: 3,10 $ di revisioni bloccate. Il lavoro è andato avanti solo perché il
direttore ha letto i referti da solo.

Lo stesso giro ha mostrato un terzo blocco, non ancora scattato: il critico ha ripetuto `svg_audit` dopo il QA, e
contava solo l'ultima firma, quindi il QA non si sarebbe più potuto accettare.

**Decisione.**
- Un contratto che nessuno può rispettare si rifiuta all'apertura: costa una chiamata del direttore, non una revisione.
- La revisione ha una sola forma: `outputs` elenca i file giudicati e il referto in `reviews/`, e i controlli stanno sui
  file giudicati, mai sul referto. Il rifiuto mostra un esempio di questa forma.
- Un revisore consegna solo referti e file che esistono o che un altro ticket dello stesso lavoro sta producendo.
- Un controllo che si registra guardando vale solo su ciò che il sistema sa rendere.
- Un revisore risponde delle sue prove: quelle di un altro non lo sostituiscono e non lo annullano. Sulla consegna
  al cliente restano valide tutte le firme, e un FAIL di chiunque continua a fermarla.

**Conseguenze.** Il direttore continua a scrivere i ticket di revisione, ma non può più sbagliarne la forma. I ticket
già bloccati restano nel registro così come sono: il registro non si riscrive. Quando un mezzo nuovo entra in `render`,
i suoi controlli visivi diventano ammessi da soli.
