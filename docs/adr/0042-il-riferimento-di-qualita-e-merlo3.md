# ADR-0042: il riferimento di qualità di E1 è `merlo3`

**Contesto.** `docs/07-EVALS.md` aveva fissato `merlo` come riferimento di qualità per E1: il segno da battere. Il
2026-11-03 il primo giudizio alla cieca di Andrea (punto 16 di M1.6, confronto `123b003a`) ha dato `merlo3` eccellente,
specifico e migliore, e `merlo` buono. `merlo3` era già il riferimento del flusso definitivo, con 13,29 $ fino alla
presentazione e 34,38 $ fino al gate `final`. Decisione di Andrea, 2026-11-03, prima di `merlo4`.

**Decisione.**
- Il segno da battere su E1 è `exports/segno.svg` di `merlo3`, nella versione giudicata: sha256 `2947a64f2ad1…`,
  conservata in `.data/artifacts/` con origine `giudizio`.
- Una prova su E1 si chiude con un giudizio alla cieca contro quel segno: il segno finale della prova e quello di `merlo3`,
  sulla tavola di ADR-0041. Per `merlo4` si fa dopo il gate `final`.
- Si confronta la versione giudicata, non il file del momento. Se `projects/merlo3/work/exports/segno.svg` non ha più
  quell'hash, si recupera con `agency restore 2947a64f2ad1 <file>` e si giudica il file recuperato.
- Tempo e costo si confrontano con `merlo3`, che era già il riferimento del flusso: fino al concetto scelto, fino alla
  presentazione e fino al gate `final`.
- `merlo` resta un riferimento storico, con le sue tavole in `projects/merlo/`. Non è più il segno da battere.

**Conseguenze.**
- Il criterio ereditato «il segno scelto batte quello di `merlo`» è chiuso dal punto 16. Il confronto di `merlo4` misura
  altro: se il flusso, con impronta e con ADR-0017 e ADR-0018 attivi dall'inizio, regge il livello raggiunto.
- È una prova sola su un brief solo: un giudizio di `merlo4` contro `merlo3` è indicativo, non una media (`07-EVALS.md`).
- Quando un segno batte `merlo3` in un giudizio registrato, il riferimento si sposta con un ADR nuovo, come questo.
