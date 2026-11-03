# ADR-0041: la tavola del giudizio e il migliore coerente

**Contesto.** Il punto 16 di M1.6 è il primo giudizio alla cieca vero, `merlo3` contro `merlo`, con `agency judge`
(ADR-0027). La prova generale del 2026-11-03, su una copia migrata del registro e con i due `segno.svg` reali, ha trovato due
problemi:
- Aperti da soli, i due file non sono alla pari. Il `segno.svg` di un progetto è 98 × 118,5 px, quello dell'altro 800 × 600 px:
  un browser li mostra a quelle misure, con il loro `<title>` nella scheda, `simbolo` e `0 simbolo`. Anche nello stesso
  riquadro il disegno riempie il 91% della tela nel primo e il 76% nel secondo, che sembrerebbe più piccolo di un quinto.
- Il migliore era libero. `A eccellente`, `B ordinario` e «il migliore: B» si registravano. Un giudizio così non dice quale
  segno vince, e il criterio principale di M1.6 legge proprio il migliore.

**Decisione.**
- **Nella cartella anonima `agency judge` mette una tavola**, `tavola.png`, accanto ad `A.svg`, `B.svg`. Ogni lettera ha lo
  stesso quadrato su fondo bianco. Il lato più lungo del disegno è di 480 px, misurato sul disegno e non sulla tela. Sotto
  compare lo stesso disegno a 64, 32 e 16 px, ciascuno reso alla sua scala e non ridotto, poi solo la lettera. Le lettere
  stanno tre per riga.
- La tavola si disegna dalle copie anonime, che hanno l'hash letto all'inizio, e quindi mostra esattamente ciò che si giudica.
  È un PNG senza testo: né titolo, né percorso, né misura della tela. I rendering intermedi stanno nella cartella anonima e
  spariscono prima delle domande.
- Gli SVG li rende `vectorcraft-cli`, il renderer dello studio, che `agency doctor` già richiede. Nel suo ambiente ci sono solo
  `PATH` e `HOME`. Se manca, un confronto di SVG si rifiuta prima di mostrare qualcosa: mostrarli diversi sarebbe peggio che non
  mostrarli. PNG, JPEG e WebP li misura Pillow, sulla parte non trasparente. Gli altri tipi, come il PDF, non hanno una tavola:
  il comando lo dice, e i file si guardano come sono.
- Si rifiutano prima delle domande due casi: un disegno vuoto, e uno così piccolo nella sua tela che renderlo a 480 px
  vorrebbe dire una tela oltre i 16.384 px.
- **Il migliore sta tra i livelli più alti.** `Judgment` rifiuta un migliore con un livello più basso di un'altra lettera: un
  eccellente non perde da un buono. A pari livello decide la scelta, come in ADR-0027. Nell'intervista una scelta che
  contraddice i livelli si spiega e si richiede. Per cambiare un livello si interrompe con Ctrl-C, e non si registra nulla.
- ADR-0027 voleva `agency.evaluation` dipendente solo dai contratti. Ora lo verifica `import-linter`: la slice non importa né il
  motore né il registro.

**Conseguenze.**
- La misura uguale è il lato più lungo nello stesso quadrato: un segno largo occupa meno area di uno alto. È la convenzione dei
  fogli di miniature di `logo_proof`, non una misura ottica.
- Il fondo è solo bianco. Un segno pensato in negativo, bianco su trasparente, sulla tavola non si vedrebbe: in quel caso si
  giudica un render su fondo.
- Come in ADR-0027, lo strumento non nasconde il contenuto. Ora toglie anche misura e titolo, ma non il colore: un nero puro e
  un nero `#141414` restano diversi.
- La tavola non si conserva. Si rifà dai file, che sono conservati per hash, ma con un'altra versione di `vectorcraft-cli`
  potrebbe cambiare di qualche pixel.
- Verificato il 2026-11-03 con `vectorcraft-cli` 0.18.0, sulla copia migrata del registro vero e sui due `segno.svg` reali:
  - la tavola esce in 0,3 s, e tutti e due i disegni hanno il lato più lungo di 480 px;
  - la scelta incoerente viene spiegata e richiesta;
  - i giudizi compaiono in `/api/compare?before=merlo&after=merlo3`;
  - nella cartella anonima non resta nulla.

  I voti di quella prova erano finti, e stavano solo nella copia, cancellata dopo. Prove: `tests/test_board.py` e
  `tests/test_judgments.py`.
