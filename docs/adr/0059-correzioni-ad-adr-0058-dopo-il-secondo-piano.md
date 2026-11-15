# ADR-0059: correzioni ad ADR-0058 dopo il secondo piano di M1.7

**Contesto.** Il [secondo piano](../superpowers/plans/2026-11-15-m1-7-plan-b-domain-ports-types.md) di M1.7 ha messo
in opera [ADR-0058](0058-porte-tipi-e-livelli-del-motore.md). La revisione finale ha confrontato le decisioni con il
codice, e cinque non coincidono più: la 2, la 5, la 6, la 8 e la 10. In tre casi il codice ha trovato un modo diverso
di ottenere lo stesso scopo; in due le decisioni promettevano più di quanto il codice faccia. Questo ADR registra come
stanno le cose. ADR-0058 resta valido per tutto il resto.

**Decisione.**
1. **Decisione 2, le porte del registro.** Oltre alle otto porte per argomento ce n'è una nona, `Projects`, con
   `project()`: il gateway legge le scelte del cliente insieme ai consumi. Il gateway riceve quindi `Spending`, che
   unisce `Usage` e `Projects`, non solo `Usage`. Anche `Spending` sta in `agency.contracts.ledger`.
2. **Decisione 5, il carico dei nodi raggiunti da `Send`.** Non è `Mapping[str, str]`: per i tipi di LangGraph
   l'ingresso di un nodo deve essere un `TypedDict`, una dataclass o un `BaseModel`, e pyright rifiuta un `Mapping`. Il
   carico è il `TypedDict` `TicketPayload`, e il nodo lo riceve attraverso l'alias `type TicketTask = TicketPayload`:
   - pyright vede il `TypedDict`;
   - LangGraph ricava uno schema d'ingresso solo da una classe (`isinstance(hint, type)`), e un alias non lo è, quindi
     il checkpoint non riceve canali nuovi.

   Lo scopo della decisione resta, e lo fissa `test_the_graph_keeps_its_channels_and_branches`: se una versione di
   LangGraph cambiasse comportamento, il test fallirebbe.
3. **Decisione 6, chi carica e chi riceve le regole.** Le carica solo `agency.process.session.open_session`, che le
   passa all'`AgentRunner`, al `Crew` e alla `Session`. La CLI non usa le regole direttamente, quindi non le carica.
   Oltre ad `AgentRunner`, `ToolContext` e `qa.delivery`, le ricevono `qa.evidence` e `qa.checks`, che leggevano
   anch'essi le verifiche e i revisori del registro.
4. **Decisione 8, gli import di un'applicazione.** Oltre a quelli che la decisione elencava, un'`application.py` usa:
   - gli schemi degli strumenti della sua slice (`SelectConcepts`, `PresentConcepts`), in cui il direttore scrive le
     sue note;
   - `workshop.board` e il documento della presentazione, che disegnano con PIL;
   - `agency.qa`, per l'accettazione al gate finale.

   Il contratto conta gli import diretti. Vieta i framework (`langgraph`, ORM, `anthropic`, Django, OpenTelemetry, PIL),
   gli adattatori concreti (registro SQLite, gateway, processo, agenti, sandbox) e gli adattatori di LangGraph
   (`agency.studio.graph` e il `nodes.py` di ogni slice). Attraverso i moduli ammessi un'applicazione raggiunge PIL e
   OpenTelemetry, mai LangGraph. Portare gli schemi fuori da `tools.py`, con `Strict` nei contratti, toglierebbe anche
   il legame dall'applicazione all'adattatore: resta da fare.
5. **Decisione 10, i test di flusso.** Oltre agli argomenti dei costruttori, sono cambiati gli import, i bersagli di
   `monkeypatch`, i record al posto delle righe, il tipo di due helper e il valore `""` diventato `None` per «nessuna
   fase». Nessun test è stato aggiunto o tolto. Confrontati con l'inizio di M1.7, 154 test su 156 hanno ogni `assert`
   identico; nei due restanti l'asserzione cambia dentro l'espressione, senza cambiare cosa verifica: `Tool.closes` al
   posto di `CLOSE_ALWAYS`, e `RULES` passato a `tools_for`.

**Conseguenze.**
- Il criterio di uscita 4 di M1.7 dice «import diretti», e la tabella di ADR-0021 nella roadmap lo riporta.
- Prima della correzione un'applicazione poteva importare `agency.studio.graph` con tutti i contratti rispettati, come
  ha mostrato la revisione finale. Ora il contratto lo vieta, e una prova su una copia della repo lo ha confermato.
- Restano da fare, fuori da M1.7: gli schemi fuori da `tools.py`.
