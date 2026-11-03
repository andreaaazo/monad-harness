# ADR-0036: la vista Strumenti e QA

**Contesto.** La roadmap chiede alla vista Strumenti e QA dove sbaglia lo studio: rifiuti con motivo, passaggi al primo colpo,
ticket bloccati. Tre fonti dicono di no: le prove dei controlli nella tabella `evidence`, gli strumenti che rifiutano una
richiesta, i ticket rimandati o bloccati con una nota. ADR-0035 teneva le note nel registro, e ADR-0029 rimandava le trascrizioni
alla vista Replay. Ma un no senza il suo motivo non dice dove guardare. In `merlo3` le due revisioni bloccate su tre non
bocciavano il lavoro: il contratto chiedeva `review/…`, mentre `write_file` lascia scrivere al revisore solo in `reviews/`. Lo
dicono solo la nota del blocco e il rifiuto dello strumento.

**Decisione.**
- **La proiezione legge le prove dei controlli** (`CheckRecord`): ticket, file, controllo, esito, chi firma e la nota, che per
  un FAIL è il motivo. FAIL è l'unico esito che boccia, come in `qa/evidence.py`. Un controllo passa *al primo colpo* su un
  file quando la sua prima prova su quel file, in quel ticket, non è FAIL.
- **La nota di un passo indietro entra nella proiezione** come `reason`: solo per rimandi, blocchi e annullamenti. Le note di
  aperture, consegne e accettazioni restano nel registro. Questo cambia ADR-0035 per i soli passi indietro.
- **Dalle trascrizioni entrano solo le chiamate agli strumenti** (`ToolCallRecord`): istanza, turno, strumento e, quando lo
  strumento ha detto no (`is_error`), il suo testo. Brief, messaggi e risposte restano fuori fino alla vista Replay. Questo
  anticipa in parte ADR-0029.
- Un rifiuto lungo tiene i primi 1.200 caratteri e la fine, per 2.000 in tutto: il motivo sta in testa ("consegna rifiutata:
  …") o, nell'uscita di un programma come `craft_run`, in fondo.
- **Il percorso delle trascrizioni ha un solo proprietario**, `DataLayout.transcripts`. Lo usa il motore per scriverle e
  `insights` per leggerle: prima il motore lo costruiva da sé. Ogni trascrizione ha la sua impronta, e una trascrizione che
  cresce rende vecchia la proiezione. Una riga tagliata da un motore che scrive si conta e si salta.
- La vista ha il suo read model, `QualityReport`, e la sua route, `/api/projects/{name}/quality`. I passi indietro, con il
  motivo, vengono dalla stessa funzione della vista Fasi.
- Nella pagina, le prove fallite stanno raggruppate per controllo e i rifiuti per strumento, chiusi con il loro numero nel
  titolo. Ogni motivo si legge su una riga e per intero a richiesta. Una riga lunga senza spazi va a capo dove serve: una prova
  verifica che nessuna vista, su un telefono, scorra in orizzontale.

**Conseguenze.**
- La proiezione passa allo schema 5 e si rigenera da sola. Con le trascrizioni di `merlo`, `merlo2` e `merlo3` (19 MB) la
  rigenerazione dura circa 0,15 s.
- I motivi possono citare file e parole del progetto. Restano in `.data/`, come il registro e le trascrizioni da cui vengono, e
  l'API li serve solo su loopback.
- Un rifiuto dello strumento non ha un istante: la trascrizione non lo scrive. Si colloca con l'istanza e il turno.
