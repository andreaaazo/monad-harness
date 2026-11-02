# Decisioni architetturali

Ogni decisione ha contesto, scelta e conseguenze. Si rovescia con un nuovo ADR, non modificando quello
vecchio. Date: 2026-10-31.

| ADR | Decisione | Stato |
|---|---|---|
| [0001](0001-registro-sqlite.md) | Registro su SQLite + SQLModel, niente Kitsu | Accettata, da rivedere prima di M7 (0023) |
| [0002](0002-langgraph-processo.md) | LangGraph solo per il processo | Accettata |
| [0003](0003-loop-proprio.md) | Loop proprio sulla Messages API, niente smolagents | Accettata |
| [0004](0004-indice-comandi.md) | Tre strumenti e un indice per i comandi Craft | Accettata |
| [0005](0005-sandbox-bwrap.md) | Sandbox `bwrap` e istanze per lavoro | Accettata |
| [0006](0006-niente-litellm.md) | Anthropic diretto, niente LiteLLM | Accettata |
| [0007](0007-openusd-rimandato.md) | Master nativi, OpenUSD rimandato | Accettata |
| [0008](0008-dspy-separato.md) | DSPy tardi e in ambiente separato | Accettata |
| [0009](0009-comfyui-limitato.md) | ComfyUI solo per esplorazione e texture | Accettata, rivedibile |
| [0010](0010-osservabilita.md) | OpenTelemetry subito, Langfuse self-hosted | Accettata, cruscotto anticipato da 0019 |
| [0011](0011-esplorazione-a-schizzi.md) | Esplorazione a schizzi prima della produzione | Accettata, gate cambiato da 0012, istanze da 0014 |
| [0012](0012-il-cliente-vede-proposte.md) | Il cliente vede proposte, non schizzi | Accettata |
| [0013](0013-cinque-direzioni-interne.md) | Cinque direzioni interne | Accettata |
| [0014](0014-pensare-disegnando.md) | Pensare disegnando, primo sguardo, nessun blocco a metà | Accettata |
| [0015](0015-modello-e-budget-del-cliente.md) | Modello e budget li sceglie il cliente | Accettata, avvisi tolti da 0016 |
| [0016](0016-nessun-avviso-agli-agenti.md) | Gli agenti non sanno nulla del budget | Accettata |
| [0017](0017-il-cliente-riceve-ciò-che-lo-studio-ha-guardato.md) | Il cliente riceve ciò che lo studio ha guardato | Accettata |
| [0018](0018-un-contratto-impossibile-non-si-apre.md) | Un contratto impossibile non si apre | Accettata |
| [0019](0019-cruscotto-lato-di-lettura.md) | Il cruscotto è un lato di lettura separato | Accettata |
| [0020](0020-django-react-taskfile-docker.md) | Django e React per il server, Taskfile e Docker attorno | Accettata, Vite sostituito da Next.js in 0024 |
| [0021](0021-monolite-modulare-a-slice.md) | Monolite modulare a slice, con Clean Architecture | Accettata |
| [0022](0022-schema-prima-del-codice.md) | Lo schema viene prima del codice | Accettata |
| [0023](0023-il-progetto-diventa-un-saas.md) | Il progetto diventa un SaaS | Accettata, rovescia un non-obiettivo di `00-PROJECT.md` |
| [0024](0024-nextjs-per-l-interfaccia.md) | Next.js per l'interfaccia | Accettata, rovescia la scelta di Vite in 0020 |
| [0025](0025-il-registro-si-aggiorna-solo-su-richiesta.md) | Il registro si aggiorna solo su richiesta | Accettata |
| [0026](0026-l-impronta-di-un-esecuzione.md) | L'impronta di un'esecuzione | Accettata, allarga la lista di 0022 |
| [0027](0027-il-giudizio-alla-cieca.md) | Il giudizio alla cieca | Accettata |
