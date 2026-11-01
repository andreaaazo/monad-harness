# ADR-0016: gli agenti non sanno nulla del budget

**Contesto.** ADR-0014 e ADR-0015 prevedevano avvisi al 75% e al 90% del budget e quote indicative per tipo di lavoro.
Servivano a lasciare una riserva per prove e consegna. Da ADR-0015 un lavoro fermato dal budget riparte senza perdere
nulla, quindi quel motivo non esiste più: restava solo la fretta. Decisione di Andrea, 2026-11-01.

**Decisione.** Agli agenti non arriva nessuna informazione su budget e spesa. Niente avvisi, niente quote, nessuna frase
che inviti a sbrigarsi. L'obiettivo di un designer è la qualità più alta. Se il budget finisce, finisce: il lavoro
resta salvato e il cliente decide se alzarlo.

**Conseguenze.** Il budget può finire a metà di un lavoro, con un master non ancora verificato. Il cliente vede la spesa
nel report e può fermare o alzare il tetto quando vuole. Il controllo dei costi passa dalla scelta di modello, effort e
budget, non dalla pressione sugli agenti.
