# ADR-0056: M1.7 senza prova dal vivo, E2 in M2

**Contesto.** Il set di `docs/07-EVALS.md` ha una riga E2, «Correzione di un logo esistente». C'è dal primo commit
(`51c511c`) e la tabella la assegna a M1. Nello stesso commit la roadmap metteva in M1.7 «E2 dal vivo», con un tetto di
10 $, per coprire il rework. ADR-0055 l'ha ripresa: proponeva di registrare E2 prima del refactor e usarlo come golden
master. La verifica del 2026-11-14 dice che E2 non si può eseguire:
- **Il motore non parte da un logo esistente.** Un progetto riceve solo `brief.md` (`src/agency/runtime.py`), e
  `agency run` non accetta altri file. Il flusso comincia sempre dall'esplorazione: la strada senza esplorazione
  (`explore=False`) esiste solo nei test.
- **E2 non ha un brief.** In `evals/briefs/` c'è solo `E1.md`. Nessun ADR motiva E2. Non viene dal backup: in `legacy/`
  non c'è un set E1–E8, e `eval_kit.py` non contiene brief.
- **E2 descrive la skill `rebrand` del vecchio studio**, «da usare quando il brand esiste già». In `docs/PARITY.md` è
  «da portare» in M2, insieme ai materiali del cliente.
- **Il rework che il motore fa davvero sta dentro un lavoro E1.** È fatto di:
  - revisioni dopo critica e QA;
  - modifiche chieste dal cliente al gate `final`;
  - un concetto bocciato che torna agli schizzi;
  - una consegna rifiutata all'accettazione.

  `merlo3` è passato dalle revisioni r1–r3.

**Decisione.** Decisione di Andrea, 2026-11-14.
- **M1.7 non ha una prova dal vivo.** Il suo tetto passa da 10 $ a 0 $. La rete del refactor sono due:
  - gli snapshot di strumenti e system prompt, byte per byte (`tests/test_request_snapshots.py`);
  - i test di flusso con risposte registrate.
- **Rovescia la parte di ADR-0055 su E2 e sul golden master.** M1.7 non ha un golden master registrato dal vivo, e la
  decisione prima del punto 2 non c'è più. La cassetta di `merlo4` (ADR-0048) arriva con M1.9, sul motore già diviso.
- **Il criterio di E2 passa a M1.9.** Hit rate della cache e contesto fisso non devono peggiorare: si misurano su
  `merlo4` contro `merlo3`.
- **E2 passa a M2 in `docs/07-EVALS.md`.** Chiede che un progetto riceva i materiali del cliente oltre al brief, e la
  skill `rebrand`. Il brief si scrive allora.

**Conseguenze.**
- **Nessuna prova dal vivo fino a M1.9.** Fra oggi e M1.9 il motore non si prova dal vivo. Un cambiamento che snapshot e
  flussi non vedono si scopre solo con `merlo4`.
- **Un peggioramento di `merlo4` non dice da solo la sua causa.** `merlo4` è una prova sola. Se va peggio di `merlo3`,
  `agency compare` dice cosa è cambiato nell'impronta, non se la causa è il refactor, il gate o la varianza.
- **La spesa fino a M1.9 è 0 $.**
- **In M1 e M1.5 il set ha avuto solo E1.** E2 non è mai stato eseguito.
- **Il resto di ADR-0055 resta valido:** M1.8, M1.9 e l'ordine M1.7, M1.8, M1.9, poi M2.
