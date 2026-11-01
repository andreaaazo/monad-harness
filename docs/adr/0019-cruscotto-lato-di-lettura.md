# ADR-0019: il cruscotto è un lato di lettura separato

**Contesto.** `agency report` e i referti in `work/reviews/` non bastano a capire come lavora il modello. La maggior parte
dei dati però esiste già: tutte le 1.281 chiamate di `usage` si collegano alle tracce tramite `request_id`, e da lì arrivano
durata, TTFT, effort e token di ragionamento. Un lavoro dura decine di minuti, quindi non può vivere dentro una richiesta
HTTP. `Ledger()` all'apertura prende un lock di scrittura e crea tabelle, quindi un server non può usarlo per leggere.

**Decisione.**
- Motore e server sono processi separati. Il server non esegue mai il grafo.
- Il motore scrive. Il server legge attraverso la slice `agency.insights`, con una connessione SQLite `mode=ro`.
- `insights` proietta registro, tracce e trascrizioni in `.data/insights.sqlite`, che si può cancellare e rigenerare. La
  verità resta nel registro, e `usage` resta la fonte dei costi (ADR-0010).
- In M1.6 l'API non scrive: solo `GET`. Il giudizio alla cieca si registra con `agency judge`.
- Da M2 i comandi dell'operatore (gate, budget, ripresa) passano da casi d'uso e li esegue un worker, mai il processo web.

**Perché.**
- Il breakdown serve prima dell'interfaccia: `agency report --json` usa gli stessi modelli del cruscotto.
- La proiezione recupera `merlo`, `merlo2` e `merlo3` senza toccare le tabelle solo in aggiunta.
- Un server che non può scrivere non può alterare il registro né aggirare la catena di hash.

**Conseguenze.** Il cruscotto di costi passa da M4 a M1.6. Langfuse resta in M4 e si rivaluta con i dati. Le tracce restano
sacrificabili per il budget, ma senza tracce la proiezione perde durata e ragionamento delle chiamate vecchie: da M1.6 questi
campi stanno anche in `usage`. Il ragionamento del modello non si legge: i 463 blocchi `thinking` di `merlo3` non hanno testo,
quindi il cruscotto mostra azioni, risultati e volumi.
