# ADR-0014: pensare disegnando, primo sguardo, nessun blocco a metà

**Contesto.** `merlo2` ha mostrato che la macchina funziona ma il risultato creativo è sceso rispetto a `merlo`. Le
idee sono nate a parole in un'istanza senza vista, lo schizzo era un'unica esecuzione a effort `low`, il direttore ha
vietato il merlo come idea ovvia, il critico ha promosso un segno che lui stesso leggeva come tasto di accensione.
Il limite di 45 strumenti ha poi bloccato entrambe le proposte con il lavoro fatto. Decisione di Andrea, 2026-10-31.

**Decisione.**

1. **Si pensa disegnando.** Un esploratore è una sola istanza con la vista: legge il mestiere, disegna 3–5 miniature,
   guarda, sceglie, ridisegna la migliore. Sostituisce la separazione tra idea e schizzo di ADR-0011.
2. **Le risorse del cliente non si vietano.** Il piano dichiara le risorse, e il sistema rifiuta gli esclusi che le
   toccano. Si esclude un cliché di esecuzione, mai un soggetto.
3. **Il primo sguardo è un vincolo.** Il critico, che non conosce le motivazioni, scrive cosa si vede davvero e chi
   passa. Il direttore può scegliere solo tra chi passa. Una buona spiegazione non salva un'immagine debole.
4. **Nessun blocco a metà lavoro.** Niente limiti rigidi su strumenti e immagini. Il freno è il budget in dollari, con
   avvisi al 75% e al 90%, così resta sempre la riserva per prove e consegna. Il tetto di turni resta solo come rete di
   sicurezza contro un agente che gira a vuoto.
5. **Effort `high` su esplorazione e proposte.** Il `medium` resta selezionabile per il confronto.

**Conseguenze.** Il costo sale: un esploratore può arrivare a 2 $ e una proposta a 3 $, stime da verificare. La parte
di mestiere torna dove nascono le idee. Il critico resta un giudice automatico: il suo primo sguardo è filtro, non
verità, e il giudizio alla cieca di Andrea rimane la misura principale.
