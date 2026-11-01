# ADR-0008: DSPy tardi e in ambiente separato

**Contesto.** DSPy ottimizza prompt contro una metrica, e GEPA ha un proposer per input multimodali.

**Decisione.** Non in M1–M4. In M5 solo dove la metrica è deterministica, e in un ambiente Python separato.

**Perché.**
- Senza un set di valutazione e una metrica, ottimizza il nulla.
- Sul giudizio creativo non abbiamo ancora dati umani.
- `dspy` 3.4.1 richiede `litellm` (verificato col resolver il 2026-10-31): nell'ambiente principale
  rientrerebbe ciò che ADR-0006 esclude. L'ambiente separato non contiene la chiave di produzione.

**Conseguenze.** I prompt ottimizzati tornano in `prompts/` come file normali, con il confronto registrato.
