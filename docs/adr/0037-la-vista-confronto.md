# ADR-0037: la vista Confronto

**Contesto.** La roadmap chiede alla vista Confronto se il lavoro è meglio di prima: due esecuzioni affiancate, le differenze di
impronta e i giudizi. Ogni esecuzione (`run`, `resume`, `decide`) registra la sua impronta (ADR-0026), e `agency compare` ne
mostra le differenze. I giudizi alla cieca possono mettere insieme file di progetti diversi (ADR-0027). `merlo`, `merlo2` e
`merlo3` hanno lavorato prima delle impronte: oggi un confronto vero mostra i numeri, ma non le impronte né i giudizi.

**Decisione.**
- **Si confrontano due progetti**, cioè il lavoro su un brief: `merlo3` contro `merlo4`. Ogni progetto è la sequenza delle sue
  esecuzioni. Ogni chiamata dice a quale esecuzione appartiene; quelle di prima delle impronte non appartengono a nessuna, e la
  vista le conta a parte.
- **I numeri di ogni lato vengono dalle viste Run, Fasi, Modello e Strumenti e QA**: il confronto non ricalcola niente. Le fasi si
  affiancano per nome, nell'ordine di lavoro del progetto di dopo.
- **Le impronte confrontate sono l'ultima di prima e la prima di dopo**, con `contracts.run.changes`, la stessa regola di
  `agency compare`: dicono cosa è cambiato fra la fine dell'uno e l'inizio dell'altro. Ogni esecuzione dice anche quante
  differenze ha dalla precedente. Un'impronta di una forma che il contratto non conosce più resta nell'elenco ma non si
  confronta: la si dice, non la si indovina.
- La proiezione legge le esecuzioni (schema 6) e tiene l'impronta come il JSON del registro.
- **Un giudizio alla cieca conta quando contiene file di tutti e due i progetti**, e si mostra con tutti i suoi voti, anche su
  file di altri progetti o esterni.
- La differenza è sempre dopo meno prima, e la vista non colora meglio o peggio: per il costo è meglio meno, per i controlli al
  primo colpo più, e il giudizio sul lavoro resta di chi legge, insieme ai voti alla cieca.
- Un progetto senza la sua riga, di prima di M1.5, ha modello ed effort *non registrati*, che è diverso da predefiniti.
- La route è `/api/compare?before=…&after=…`: 400 per un progetto confrontato con sé stesso, 404 per uno sconosciuto. La pagina è
  `/compare`, fuori dai progetti, con una scelta che è un modulo GET e funziona senza JavaScript. Senza una scelta confronta i due
  progetti che hanno lavorato per ultimi.

**Conseguenze.**
- Il primo confronto completo sarà `merlo3` contro `merlo4`: il giudizio alla cieca di `merlo3` contro `merlo` (punto 16)
  comparirà qui appena registrato.
- I progetti di M1 hanno fasi con il nome del ruolo: affiancati a quelli di M1.5 compaiono come fasi diverse, e la pagina lo dice.
