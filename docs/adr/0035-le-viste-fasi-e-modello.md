# ADR-0035: le viste Fasi e Modello

**Contesto.** La roadmap chiede alla vista Fasi dove il lavoro si è fermato o è tornato indietro, con costo e rework per fase, e
alla vista Modello come ha lavorato il modello: contesto turno per turno, cache, ragionamento, latenza e `stop_reason`, per
ruolo. La proiezione di ADR-0029 non leggeva la storia dei ticket. Il nome delle istanze non dice niente del rework: in `merlo3`
il direttore ha dieci istanze su un solo ticket, una per turno, mentre la rifinitura ha tre istanze perché è stata rimandata
due volte.

**Decisione.**
- **La proiezione legge la storia dei ticket**: apertura e transizioni di `Action`, con chi e quando (`EventRecord`, schema 4).
  Non legge le note, che restano nel registro, né le prove, che hanno la loro tabella e serviranno alla vista Strumenti e QA. Un
  test tiene allineato l'elenco delle azioni a `Action`.
- **Il rework si legge dagli eventi, non dai nomi.** Un rimando del direttore è lavoro da rifare: ciò che il ticket costa dopo il
  primo rimando è *rifatto*. Una chiamata che finisce nell'istante del rimando appartiene al tentativo prima. Un ticket bloccato
  è costato *senza esito*. I passi indietro sono i rimandi, i blocchi e gli annullamenti, in ordine di tempo, con quante
  consegne c'erano state prima.
- **La fase di un ticket è quella del motore**, `phase.of(assignee, prompt)`. Le fasi si leggono in ordine di lavoro: dalla
  prima chiamata, o dall'apertura del primo ticket se non ne hanno.
- **La consegna al cliente non è una fase**: è il progetto. Il suo stato, i ticket ancora da finire e l'ultimo passo dicono dove
  si è fermato. Un ticket consegnato ma non accettato non ha finito.
- **Quali risposte non sono arrivate intere lo decide `insights`**: `max_tokens`, `refusal` e
  `model_context_window_exceeded`, perché il ciclo dell'agente non mette in cronologia una risposta troncata e blocca il ticket
  dopo un rifiuto. Il motore non ha un elenco canonico di questi motivi: quando ne avrà uno, `insights` lo userà.
- Le due viste hanno read model propri, `FlowReport` e `BehaviourReport`, e route proprie: `/api/projects/{name}/flow` e
  `/api/projects/{name}/behaviour`. `ProjectReport` resta il modello di `agency report`. I conti che le viste condividono
  stanno in `agency.insights.sums`.
- **Il contesto turno per turno è un piccolo multiplo per istanza**, con una scala sola per tutte, così le altezze si
  confrontano. Una linea da 2 px con un velo al 10%, il blu `series-1` della palette di riferimento, validato su carta e
  pannello nei due temi. Il puntatore e le frecce mostrano un turno; la tabella dei turni c'è per ogni istanza.
- La tabella dei turni nasce nel browser solo quando la si apre. Resa dal server, i turni sarebbero arrivati tre volte: HTML,
  payload di React e grafico. Su `merlo3` la pagina passa da 857 a 233 KB.

**Conseguenze.**
- Una proiezione dello schema 3 si rigenera da sola alla prima lettura.
- Senza JavaScript la tabella dei turni non si apre; il resto delle due viste si legge lo stesso.
- I numeri di `merlo3` dicono già dove guardare: la rifinitura ha fatto tre consegne, con 8,14 $ rifatti, e il suo contesto
  arriva a 267.966 token in 128 turni.
