# ADR-0003: loop proprio sulla Messages API

**Contesto.** Il loop decide firma, budget, cache e sicurezza. Le opzioni: Tool Runner dell'SDK, Claude
Agent SDK, Managed Agents, smolagents, loop proprio.

**Decisione.** Loop manuale con l'SDK `anthropic`.

**Perché.**
- **Claude Agent SDK**: ripropone Claude Code, il cui comportamento vogliamo controllare.
- **Managed Agents**: esegue in container Anthropic; a noi servono Craft locali e materiali in casa.
- **Tool Runner**: è beta e nasconde punti in cui vogliamo intervenire. Si può rivalutare.
- **smolagents**: secondo runtime sopra LangGraph; la documentazione dice che l'esecutore locale non è un
  confine di sicurezza, e nel 2026 ha avuto CVE su quell'area.

**Conseguenze.** Dobbiamo reggere noi stream, errori, rifiuti e cronologia solo in aggiunta. Il rischio è
perdere la messa a punto di Claude Code: M1 serve a misurarlo prima di andare oltre.
