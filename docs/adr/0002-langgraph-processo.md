# ADR-0002: LangGraph solo per il processo

**Contesto.** Lo studio è un processo lungo con pause di giorni per il cliente, rami S/M/L e lavoro parallelo.

**Decisione.** LangGraph per fasi, gate (`interrupt`), parallelo e checkpoint. Non per il loop dell'agente.

**Conseguenze.**
- Alla ripresa i nodi si rieseguono: ogni effetto ha un `operation_id` controllato sul registro.
- Il checkpointer SQLite basta su una macchina. Le fonti lo indicano per lo sviluppo e Postgres per la
  produzione: si rivaluta se emergono limiti.
- Il registro è la verità; il checkpoint è ricostruibile.
