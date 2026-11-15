# ADR-0058: porte, tipi e livelli del motore

**Contesto.** Il primo piano di M1.7 ha diviso il motore in slice ([ADR-0057](0057-l-albero-dei-pacchetti-del-motore.md)).
Mancano i punti 4–7:
- dominio e applicazione dentro le slice;
- i livelli e le regole sulle librerie imposti da `import-linter`;
- la piramide dei test;
- i tipi espliciti.

Del principio 2 di [ADR-0021](0021-monolite-modulare-a-slice.md) i punti 1–6 coprono solo una parte, e restano fuori
tre cose:
- le fasi e le rotte sono stringhe libere;
- i nodi restituiscono un `dict` qualsiasi;
- il registro dei ruoli è un `dict[str, dict]` letto come variabile globale.

Il registro SQLite esce dal suo pacchetto in due modi: con le righe SQLModel e con gli interni di `ledger.store`
(`now`). La CLI e il suo renderer stanno fuori dagli ingressi (STR-007).

Il [secondo piano](../superpowers/plans/2026-11-15-m1-7-plan-b-domain-ports-types.md) li porta a termine. Andrea ha
lasciato all'esecuzione le scelte qui sotto.

**Decisione.**
1. **Le porte stanno in `agency.contracts`**, come `Protocol`, insieme ai record che portano:
   - `contracts.ledger` per il registro;
   - `contracts.sandbox` per la sandbox;
   - `contracts.artifact.ArtifactStore` c'è già.

   La porta del modello resta `gateway.transport.Transport`. I contratti sono il livello più basso: ogni livello
   dipende da una porta senza dipendere dall'adattatore che c'è dietro.
2. **La porta del registro è divisa per argomento:** `Tickets`, `Operations`, `Concepts`, `Gates`, `Proofs`, `Usage`,
   `KeptArtifacts`, `Runs`. `LedgerPort` le compone. Ogni modulo usa la porta più stretta che gli basta: il gateway, per
   esempio, solo `Usage`. I record sono modelli pydantic immutabili, chiamati `<Tipo>Entry`, con gli stessi campi della
   riga. Il nome evita lo scontro con i `*Record` di `insights.domain` e con `contracts.gate.Gate`.
3. **Solo le radici di composizione importano `agency.ledger`:** `agency.process.session` e `agency.entrypoints.cli`.
   Lo impone un contratto `forbidden`. Così «il registro solo dietro la sua porta» si può verificare.
4. **Fasi e rotte sono tipi `Literal`, non `StrEnum`:**
   - `DirectorMode` in `contracts.phase`;
   - `Route` ed `END_ROUTE` in `studio.shared`.

   Il checkpoint conserva le stringhe di oggi, e i progetti in pausa riprendono. Il serializzatore di LangGraph può
   invece salvare modulo e classe di un enum.
5. **I due nodi raggiunti da `Send` ricevono `TicketTask = Mapping[str, str]`, non un `TypedDict`.** LangGraph trasforma
   un `TypedDict` in uno schema d'ingresso, e lo schema aggiunge un canale al checkpoint. Un alias di `Mapping` non è una
   classe, e LangGraph lo ignora. Lo prova un test sulla forma del grafo, che fissa canali e schemi d'ingresso.
6. **Le regole dello studio sono un valore tipizzato, passato a chi lo usa.** `contracts.registry.StudioRules` lo
   carica `agency.registry.load_rules()` nelle radici di composizione, e lo ricevono `AgentRunner`, `ToolContext` e
   `qa.delivery`. Le ricerche nella libreria dei prompt restano funzioni di `agency.registry`, perché leggono file al
   momento della chiamata.
7. **La CLI passa in `agency.entrypoints.cli`,** con `render.py` (da `telemetry/report.py`) e `doctor.py`.
   L'impronta di un'esecuzione passa in `agency.process.fingerprint`, perché la usa solo la sessione. A
   `agency.telemetry` resta solo OpenTelemetry.
8. **Dentro una slice:**
   - `domain.py` tiene le regole pure, e importa solo `agency.contracts`;
   - `application.py` tiene la logica dei nodi senza LangGraph, e importa solo `contracts`, `studio.shared`, il suo
     `domain`, `toolkit.base` e `workshop.files`;
   - `tools.py` e `nodes.py` sono gli adattatori.

   Una query usata da due slice sta in `studio.shared`; una regola usata da una slice sta nel suo `domain`. I tipi
   rivolti a LangGraph (`Node`, `TaskNode`, `Router`) stanno in `agency.studio.graph`. Non si crea una porta attorno a
   codice interno senza un confine da proteggere.
9. **`agency.context`,** vuoto fino a M3, sta nel livello della piattaforma.
10. **In questo piano i test di flusso possono cambiare anche gli argomenti dei costruttori che rendono esplicita
    una dipendenza:** `rules=`, e le porte al posto delle classi concrete. Non cambiano mai un'asserzione, una
    risposta registrata o un turno scritto.

**Conseguenze.**
- **I test di flusso cambiano i costruttori.** Il criterio di uscita 3 di M1.7 lo dice.
- **Il checkpoint non cambia.** Valori di rotte e fasi, nomi dei nodi e canali del grafo restano gli stessi, e un
  progetto messo in pausa prima del secondo piano riprende dopo.
- **La catena degli hash lega gli stessi byte.** Un registro scritto attraverso i record passa `agency verify` come
  prima. Un test con l'orologio fissato registra l'hash prima del cambio e lo confronta dopo.
- **Le regole sulle librerie diventano contratti:**
  - `langgraph` solo nel processo e negli adattatori del grafo di `studio`;
  - `sqlmodel`, `sqlalchemy` e `alembic` solo nel registro;
  - dominio e applicazione senza framework.
- **La factory `select` resta a complessità 11 fino a M1.8**, che porta la soglia a 8 e la divide.
