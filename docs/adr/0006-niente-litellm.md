# ADR-0006: Anthropic diretto, niente LiteLLM

**Contesto.** LiteLLM offre un'interfaccia multi-provider.

**Decisione.** SDK `anthropic` diretto, dietro il nostro gateway.

**Perché.**
- Un solo provider: l'astrazione non porta valore, e rischia di nascondere cache, effort, fallback e altre
  funzioni specifiche da cui dipendono costi e qualità.
- Le versioni 1.82.7 e 1.82.8 sono state compromesse il 24 marzo 2026 con un furto di credenziali. Il
  gateway tiene la chiave più sensibile del sistema: va ridotta la superficie intorno.

**Conseguenze.** Il gateway è l'unico punto da cambiare per un secondo provider. In più ogni dipendenza ha
due settimane di quarantena (`exclude-newer`).
