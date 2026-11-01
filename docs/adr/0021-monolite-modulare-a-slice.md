# ADR-0021: monolite modulare a slice, con Clean Architecture

**Contesto.** Il progetto deve reggere M2 e poi un SaaS, e la struttura di oggi non lo permette. `tools/surface.py` ha 940 righe,
il 18% del codice, e contiene gli strumenti di tutte le fasi. `graph/workflow.py` tiene tutti i nodi dentro una sola funzione.
`agents` e `tools`, e così `qa` e `tools`, si importano a vicenda. M2 porta su questi file 25 ruoli, 33 skill e altri quattro
strumenti creativi.

**Decisione.** Cinque principi, imposti dal codice dove si può.

1. **Modular monolith in vertical slices.** Un solo pacchetto, un solo rilascio. Ogni capacità dello studio è una slice:
   esplorazione, selezione, proposta, presentazione, rifinitura, consegna. `insights` è la slice di lettura. Registro, gateway,
   sandbox e telemetria sono piattaforma condivisa. Le slice non si importano tra loro.
2. **Explicit over implicit.** Nessun `dict[str, Any]` come stato o contratto. Fasi e gate sono tipi, non stringhe. Strumenti e
   slice si elencano a mano, senza scoperta automatica. Le dipendenze si passano, non si raggiungono.
3. **Clean Architecture.** Le dipendenze puntano verso l'interno: dominio, applicazione, adattatori, ingressi. Il dominio ha solo
   regole pure, senza I/O né framework. L'applicazione ha casi d'uso e porte. Le porte stanno ai confini esterni: modello,
   registro, sandbox, artefatti e lettura. Non si crea una porta attorno a codice interno senza un confine da proteggere.
4. **Schema-First Design.** Lo schema viene prima del codice (ADR-0022).
5. **Testing pyramid.** Molti test sulle regole pure, integrazione sulle slice, pochi flussi completi, una prova di fumo per
   vista (`docs/07-EVALS.md`). La piramide dice se il sistema funziona. La qualità del design resta alle valutazioni.

`import-linter` in `make check` impone i confini: `anthropic` solo nel gateway, `langgraph` solo nel processo e nei nodi,
`sqlmodel` solo nel registro, `django` solo nel server.

**Conseguenze.**
- Il refactor del motore è M1.7, dopo `merlo4`: il comportamento si misura prima di toccarlo. `insights` nasce già in questa forma.
- Gli snapshot di strumenti e system prompt restano identici a ogni passo: un byte cambiato invalida la cache e cambia il
  comportamento, e i test non lo vedrebbero.
- Rinominare nodi o strumenti rompe la ripresa dei progetti in pausa, che si chiudono prima. `merlo3` è chiuso e non si riprende.
- ADR-0002 e ADR-0003 restano validi: LangGraph tiene il processo, il loop resta nostro.
