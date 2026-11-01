Materiale da revisionare: $ARGUMENTS

Se sei la sessione principale, affida la revisione all'agente `critic` con brief,
percorsi e criteri di accettazione; altrimenti esegui tu i passi sotto.
Non modificare i master. Scrivi il report in `review.md` nella cartella del lavoro
usando `read_skill("org", "review.md")`.

## 1. Primo sguardo (prima di leggere le motivazioni dell'autore)

Guarda gli artefatti e il brief. Scrivi in tre righe: cosa comunica, a chi, cosa
lo rende diverso. Solo dopo leggi `direction.md` e le note dell'autore e confronta.

## 2. Livello richiesto: confronto con i riferimenti

Il critico rischia di condividere il gusto medio dell'autore e di scambiare un lavoro ordinato per
eccellente. Per questo il progetto ha `work/references/levels.md` (`client-world`, `research`):
per il mezzo in esame (tipografia, composizione, fotografia, ritmo, interazione) esempi di lavoro
**ordinario, buono ed eccellente**, con dove sta il salto concreto.

Confronta il risultato con i riferimenti selezionati nelle stesse condizioni d'uso. Indica dove
raggiunge il livello richiesto e dove resta indietro, citando elementi visibili. Distingui problemi
di **concept**, **composizione** ed **esecuzione**. Identifica anche gli **elementi riusciti da
preservare** durante la revisione. L'assenza di errori non basta a dichiarare raggiunta
l'ambizione creativa.

## 3. Proteggere il carattere

Prima di prescrivere correzioni, identifica ciò che dà carattere al lavoro. Per ogni problema,
distingui un difetto osservabile da una preferenza. Proponi la modifica con il maggiore beneficio
atteso e segnala cosa potrebbe peggiorare. Dopo la revisione confronta entrambe le versioni
(render affiancati, `pixel_diff.py`) e dì se il carattere è rimasto. Una successione di critiche
può eliminare tutte le irregolarità interessanti e lasciare una composizione innocua: è un esito
da evitare quanto un difetto.

## 4. Rubrica creativa comune

| Criterio | Domanda |
|---|---|
| Idea | C'è un'idea riconoscibile e coerente con la strategia, o solo uno stile? |
| Distintività | È confondibile con un concorrente? Contiene cliché di [anti-patterns](../../design-agency/references/anti-patterns.md) non giustificati? Per un brand nuovo: è differenziabile e capace di caricarsi di significato? |
| Specificità | Test di sostituzione: con un altro nome, altre immagini, un altro settore, reggerebbe uguale? Le scelte determinanti hanno la catena fatto → interpretazione → ipotesi → alternativa → confronto? |
| Appropriatezza | Parla al pubblico e alla categoria giusti, con la personalità giusta? |
| Semplicità | Ogni elemento serve? Si può descrivere a voce e ridisegnare a memoria? |
| Sistema | Logo, colore, tipo, motion e voce nascono dalla stessa idea? Il sistema genera applicazioni nuove? |
| Mestiere | Regge il confronto con i riferimenti di livello del contratto creativo, nelle stesse condizioni d'uso? |
| Contratto creativo | Produce la percezione dichiarata, fa emergere ciò che doveva, la decisione caratterizzante è visibile? |

Per ogni criterio: giudizio motivato con riferimento a una posizione precisa.
Niente voti medi: un punto debole grave non si compensa con altri buoni.

## 5. Rubrica per servizio (in profondità)

| Ambito | Qualità da esaminare |
|---|---|
| Identità | differenziabilità, appropriatezza, comportamento del sistema in mezzi diversi, riduzione, potenziale di apprendimento |
| Web e app | composizione per breakpoint, sequenza narrativa, interazioni (chiariscono, interessano, lasciano il controllo), contenuto reale, esperienza touch, stato ridotto, accessibilità |
| Editoria | tipografia del testo corrente, ritmo tra le pagine, leggibilità, rapporto testo-immagini, gerarchia dei dati |
| Campagna | forza del messaggio, relazione copy-immagine, efficacia in ogni formato, tenuta nel formato più difficile |
| Motion | timing, pause, continuità, dove va l'attenzione, relazione con il contenuto, chiusura sul segno |
| Packaging | riconoscimento a distanza di scaffale, gerarchia delle informazioni, sistema di varianti, producibilità |
| Fotografia e immagini | coerenza del set, luce, punto di vista, trattamento, relazione con la direzione |

"Si può ridisegnare a memoria?" vale per un simbolo, non per una pagina o un sito: usa la riga
dell'ambito giusto.

## 6. Rubrica tecnica

Esegui o verifica gli script pertinenti e **guarda** le immagini prodotte:
- logo: `svg_audit.py`, `logo_proof.py proof` (riduzione, mono, negativo, blur);
- colore: `color.py matrix` sulle coppie reali, per ogni tema;
- tipografia: specimen alla dimensione d'uso, glifi delle lingue, licenze registrate;
- token: `tokens_check.py`, coerenza tra token, brand book ed export;
- motion: `motion_probe.py`, frame chiave, chiusura sul master statico, variante ridotta;
- consegna: file apribili, dimensioni, font incorporati o in tracciati, nomi coerenti.

Accessibilità: criteri e ambito in [references/accessibility.md](references/accessibility.md).

## 7. Difetti

| Severità | Significato |
|---|---|
| Bloccante | Inutilizzabile, contenuto essenziale errato, flash a rischio, licenza mancante |
| Maggiore | Requisito obbligatorio fallito; idea debole o confondibile; difetto visibile all'uso |
| Minore | Difetto localizzato che non compromette l'uso |
| Preferenza | Alternativa estetica senza violazione dimostrata |

Ogni difetto: severità, tipo (concept / composizione / esecuzione), file e posizione, evidenza,
impatto, correzione verificabile. Una deviazione da un'euristica non è un difetto se l'effetto
osservato è buono; un requisito violato lo è sempre.
Niente critiche vaghe ("più premium", "più moderno"): indica la forma concreta.

## 8. Esito

Registra il giudizio con `judge`, sempre con un termine di confronto reale e la motivazione.