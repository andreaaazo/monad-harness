# ADR-0062: docstring complete nei file che cambiano

**Contesto.** Durante l'audit la risposta a Q14 escludeva una campagna di docstring e la regola Ruff `D1`: porte,
contratti e moduli della piattaforma ricevevano le docstring nei loro task (`docs/audit/PLAN.md`, Phase 3).

Il quality gate di M1.8 chiede invece, in ogni file Python che cambia:
- una docstring per ogni modulo, classe e funzione, secondo Ruff `D` con la convenzione Google;
- ogni argomento, ritorno, `yield` ed eccezione documentati, secondo pydoclint (§6.3).

**Decisione.** Per i file che cambiano, la risposta a Q14 si rovescia: il gate chiede docstring complete in tutto il
file, non solo nelle righe toccate (§7.5). Per i file che nessuno tocca resta com'era: nessuna campagna.

**Conseguenze.**
- Ogni modifica a un file vecchio porta con sé le docstring di tutto il file. È il costo voluto della §12: è il
  meccanismo che porta il repository verso `full` verde.
- `full` le chiede ovunque, ma fino alla fine della pulizia fa solo rapporto
  ([ADR-0060](0060-il-quality-gate-parametri-decisioni-e-ordine.md), D3).
- Il codice del gate le ha fin dal primo file.
