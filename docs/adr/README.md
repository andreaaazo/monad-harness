# Decisioni architetturali

Ogni decisione ha contesto, scelta e conseguenze. Si rovescia con un nuovo ADR, non modificando quello
vecchio. Date: 2026-10-31.

| ADR | Decisione | Stato |
|---|---|---|
| [0001](0001-registro-sqlite.md) | Registro su SQLite + SQLModel, niente Kitsu | Accettata, da rivedere prima di M7 (0023); la catena copre verdetti e consegne (0047) |
| [0002](0002-langgraph-processo.md) | LangGraph solo per il processo | Accettata |
| [0003](0003-loop-proprio.md) | Loop proprio sulla Messages API, niente smolagents | Accettata |
| [0004](0004-indice-comandi.md) | Tre strumenti e un indice per i comandi Craft | Accettata |
| [0005](0005-sandbox-bwrap.md) | Sandbox `bwrap` e istanze per lavoro | Accettata; i file dell'harness stanno fuori da `/job` (0044); i limiti di risorse in 0046 |
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
| [0028](0028-gli-artefatti-per-hash.md) | Gli artefatti per hash | Accettata |
| [0029](0029-la-proiezione-di-insights.md) | La proiezione di insights | Accettata; dalle trascrizioni solo strumenti e rifiuti (0036), il Replay le legge senza copiarle (0038) |
| [0030](0030-il-rapporto-passa-da-insights.md) | Il rapporto passa da insights | Accettata |
| [0031](0031-il-server-del-cruscotto.md) | Il server del cruscotto | Accettata |
| [0032](0032-schemi-e-tipi-generati.md) | Schemi e tipi generati | Accettata, `npx` sostituito da mise in 0034 |
| [0033](0033-il-cruscotto-next-js.md) | Il cruscotto Next.js | Accettata, aggiunge due difese a 0024 |
| [0034](0034-mise-per-gli-strumenti-locali.md) | mise per gli strumenti locali | Accettata, rovescia `npx` di 0032 |
| [0035](0035-le-viste-fasi-e-modello.md) | Le viste Fasi e Modello | Accettata, i motivi dei passi indietro entrano con 0036 |
| [0036](0036-la-vista-strumenti-e-qa.md) | La vista Strumenti e QA | Accettata |
| [0037](0037-la-vista-confronto.md) | La vista Confronto | Accettata |
| [0038](0038-la-vista-replay.md) | La vista Replay | Accettata, rovescia le trascrizioni nella proiezione di 0029 |
| [0039](0039-taskfile-come-ingresso-unico.md) | Taskfile come ingresso unico | Accettata |
| [0040](0040-il-cruscotto-in-docker.md) | Il cruscotto in Docker | Accettata, il nome della variabile dell'host passa a 0045 |
| [0041](0041-la-tavola-del-giudizio.md) | La tavola del giudizio e il migliore coerente | Accettata, aggiunge a 0027 |
| [0042](0042-il-riferimento-di-qualita-e-merlo3.md) | Il riferimento di qualità di E1 è `merlo3` | Accettata, sostituisce `merlo` in `07-EVALS.md` |
| [0043](0043-il-tetto-si-dichiara-all-avvio.md) | Il tetto di spesa si dichiara all'avvio | Accettata, toglie il budget di default a 0015 |
| [0044](0044-i-file-dell-harness-fuori-dalla-sandbox.md) | I file dell'harness fuori dalla sandbox | Accettata, estende 0005 |
| [0045](0045-una-radice-dei-dati-e-env-solo-per-i-segreti.md) | Una radice dei dati, e `.env` solo per i segreti | Accettata, si attua in tre passi (Task 2.15–2.17 di `docs/audit/PLAN.md`) |
| [0046](0046-i-limiti-della-sandbox.md) | I limiti della sandbox | Accettata, estende 0005: tetto di memoria e di task in uno scope cgroup |
| [0047](0047-la-catena-copre-verdetti-e-consegne.md) | La catena copre verdetti e consegne | Accettata, estende 0001: eventi di versione 2 e `agency verify` che rifà il conto |
| [0048](0048-le-esecuzioni-si-registrano-e-si-ripetono.md) | Le esecuzioni si registrano e si ripetono | Accettata, sostituisce il registratore di M1: chiave per richiesta, `--record`, ripetizione nei test |
| [0049](0049-la-catena-copre-cio-che-decide-la-consegna.md) | La catena copre ciò che decide la consegna | Accettata, estende 0047: contratto dei ticket, idee, gate e prove legati nella catena |
| [0050](0050-la-catena-copre-anche-i-costi.md) | La catena copre anche i costi | Accettata, estende 0049: chiamate pagate e progetti legati nella catena, `operations` solo in aggiunta |
