# ADR-0010: OpenTelemetry subito, Langfuse self-hosted

**Contesto.** Servono tracce per capire costi e comportamento, senza far uscire materiali.

**Decisione.** Span OpenTelemetry da M1, costi anche in SQLite. Langfuse in self-hosting da M4.

**Perché.**
- Il budget non può dipendere dalla telemetria: i costi nel registro sono la fonte.
- Langfuse richiede Postgres, ClickHouse, Redis e storage S3: non serve prima di avere traffico vero.
- La versione cloud è esclusa dai vincoli sui materiali del cliente.

**Conseguenze.** Per default le tracce non contengono il testo dei materiali. Il pacchetto `langfuse` è
opzionale, nel gruppo `telemetry`.
