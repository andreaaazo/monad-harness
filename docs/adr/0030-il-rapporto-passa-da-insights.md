# ADR-0030: il rapporto passa da insights

**Contesto.** ADR-0019 vuole che `agency report --json` usi gli stessi modelli del cruscotto. Il rapporto leggeva il registro con
`Ledger()` e costruiva dei `dict`, quindi testo, JSON e cruscotto avrebbero avuto tre calcoli diversi degli stessi numeri.

**Decisione.**
- `agency report` rigenera la proiezione e legge il rapporto da lì, come farà il cruscotto. Non apre `Ledger()`: legge il
  registro in sola lettura, anche mentre il motore lavora.
- Il rapporto è un modello Pydantic, `ProjectReport` in `agency.insights.views`. Il testo e `--json` nascono dallo stesso
  modello, e l'API del cruscotto restituirà lo stesso.
- I modelli di lettura sono propri, non le tabelle della proiezione (ADR-0022). Il calcolo è una funzione pura: dagli stessi
  dati, lo stesso rapporto.
- La proiezione contiene ciò che il rapporto legge: chiamate, progetti, ticket, gate, idee e giudizi. Le parole del cliente ai
  gate restano nel registro.
- Il rapporto aggiunge una sezione per fase: chiamate, costo, durata media, TTFT mediano e ragionamento, con il numero di
  chiamate misurate. Le medie valgono solo sulle chiamate misurate.

**Verifica (2026-11-02).** `tests/test_report_views.py`. Su copie del registro reale migrato e delle tracce, `agency report
--json` dà 15,91 $ su `merlo` e 13,29 $ in 365 chiamate e 30 minuti fino al gate `concept` di `merlo3`. Il testo nuovo è uguale
al vecchio riga per riga per `merlo`, `merlo2` e `merlo3`, con in più la sezione per fase.

**Conseguenze.**
- Ogni rapporto rilegge registro e tracce per intero: oggi meno di un secondo, ma il tempo cresce con i dati. Quando servirà, la
  proiezione si aggiornerà solo per ciò che è cambiato.
- Uno schema nuovo della proiezione si rigenera, non si migra: lo schema è passato alla versione 2.
