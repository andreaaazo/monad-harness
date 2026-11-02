# ADR-0027: il giudizio alla cieca

**Contesto.** Il giudizio alla cieca di Andrea è la misura principale della qualità (`docs/07-EVALS.md`), ma finora nessun
giudizio è stato salvato. ADR-0022 ha deciso che `judgments` lega il punteggio allo sha256 del file, ma non come resta cieco chi
giudica. Anche il test di sostituzione, criterio ereditato da M1.5, non ha un posto dove registrarsi.

**Decisione.**
- `agency judge FILE…` copia i file in `.data/blind/<confronto>/` con la sola lettera nel nome: `A.svg`, `B.svg`. Le copie sono
  nuove e non conservano la data dell'originale.
- Le lettere si estraggono a caso a ogni confronto. Non sono stabili come quelle della tavola dei critici: a una persona che
  giudica più volte, lettere ripetute direbbero col tempo chi è chi.
- La corrispondenza tra lettere e file resta in memoria finché il giudizio non è completo. L'origine si mostra solo dopo la
  registrazione. Se il giudizio si interrompe non si registra nulla, e le copie si cancellano in ogni caso.
- Per ogni lettera si chiedono il livello (ordinario, buono, eccellente), il test di sostituzione (con un altro nome reggerebbe
  lo stesso?) e il perché, obbligatorio. Con due file o più si chiede anche il migliore, obbligatorio: due livelli possono essere
  pari, e per dire che un segno ne batte un altro serve una scelta esplicita.
- Un confronto si fa alla pari: file che esistono, dello stesso tipo e con contenuti diversi. Altrimenti si rifiuta prima di
  mostrare qualcosa.
- `judgments` ha una riga per file, scritte insieme in una sola transazione, solo in aggiunta. `project` è vuoto per un file
  fuori dai progetti, come le consegne della CLI del punto 18: allora si registra il percorso intero.
- Chi giudica è `--judge`, di default l'utente del sistema.
- Il giudizio è una slice nuova, `agency.evaluation`, nella forma di ADR-0021: dipende solo dai contratti, e nel registro scrive
  l'ingresso, `agency judge`.

**Verifica (2026-11-02).** `tests/test_judgments.py`. Prova sui due `segno.svg` reali di `merlo` e `merlo3` con un registro
temporaneo: le copie anonime spariscono dopo il giudizio, l'origine compare solo alla fine, gli originali restano identici. Su
una copia del registro reale la migrazione `0003` aggiunge `judgments` e lascia identiche tutte le 3.814 righe.

**Conseguenze.**
- Lo strumento nasconde nome, ordine e data, non il contenuto. Un file che porta scritta la propria origine non è cieco: si
  confrontano file della stessa natura, per esempio gli SVG finali o i loro render.
- Fino al punto 7 di M1.6 il file giudicato può cambiare nel progetto dopo il giudizio. Lo sha256 dice quale versione è stata
  giudicata, ma il contenuto si recupera solo quando esisteranno gli artefatti per hash.
- In M1.6 l'API non scrive: i giudizi arrivano solo da `agency judge` (ADR-0019).
- Se il processo viene ucciso, senza un'interruzione da tastiera, la cartella anonima resta. Non dice da dove vengono i file e si
  può cancellare.
