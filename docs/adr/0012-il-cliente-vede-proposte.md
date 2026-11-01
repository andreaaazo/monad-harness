# ADR-0012: il cliente vede proposte, non schizzi

**Contesto.** ADR-0011 metteva il gate del cliente sulla tavola degli schizzi. È sbagliato: in uno studio gli schizzi
restano interni. Un cliente non sa leggerli, giudica il disegno invece dell'idea, e può scartare un'idea forte per
uno schizzo debole. Il setup precedente lo faceva già bene: il cliente vedeva tavole confrontabili con la
raccomandazione dello studio. Decisione di Andrea, 2026-10-31.

**Decisione.** Tre momenti distinti.

1. **Dentro lo studio**: schizzi, tavola anonima, critica e scelta di 2 o 3 idee. Il sistema decide da solo.
2. **Davanti al cliente**: ogni idea scelta diventa una proposta pulita con le applicazioni reali. Il direttore
   prepara una presentazione in PDF con idea, motivo, limite e raccomandazione. Il gate `concept` è qui.
3. **Dopo la scelta**: il finisher rifinisce la proposta approvata partendo dal suo master.

**Tre ruoli da non confondere.** La scelta tra gli schizzi è dello studio. La scelta tra le proposte è del cliente:
nelle prove lo interpreta Andrea, perché il cliente è inventato. Il giudizio alla cieca è una misura del sistema e
non fa parte del flusso di un progetto.

**Regole.**
- Le proposte si sviluppano in parallelo, ciascuna in una sandbox propria, a effort `medium`, con un tetto.
- Le applicazioni le sceglie il direttore dal mondo del cliente, con la dimensione reale. Sono disegni vettoriali
  onesti, mai finte fotografie.
- Il direttore può scartare una proposta prima del cliente, o tornare all'esplorazione se nessuna regge.

**Conseguenze.** Il costo fino al cliente sale, perché si sviluppano più proposte. In cambio il cliente confronta
lavoro vero, e l'idea sbagliata cade prima della rifinitura. I tetti si tarano con la prima prova reale.
