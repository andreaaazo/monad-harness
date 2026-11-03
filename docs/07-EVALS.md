# Valutazioni

Senza misure, "stato dell'arte" è un'opinione. Ogni cambiamento di prompt, modello o `effort` si confronta
sullo stesso set, prima di entrare.

## Set di riferimento

Brief inventati, senza dati di clienti, coerenti con ciò che lo studio fa davvero:

| ID | Lavoro | Dimensione | Copre | Traguardo |
|---|---|---|---|---|
| E1 | Logo per un'attività locale | S | Vettoriale, QA, critica | M1 |
| E2 | Correzione di un logo esistente | S | Rework, regressioni | M1 |
| E3 | Identità con tre direzioni | L | Sprint, gate, carta | M2 |
| E4 | Pagina di sito in FigCraft | M | Interfaccia, prototipo | M2 |
| E5 | Logo animato | M | Motion, Lottie | M2 |
| E6 | Packaging con render 3D | M | Stampa, Blender | M2 |
| E7 | Ritocco e mockup fotografico | S | PhotoCraft | M2 |
| E8 | Brief ostile: istruzioni nascoste in un PDF | S | Sicurezza | M2 |

## Tre livelli di misura

### 1. Regole (ad ogni modifica, senza spesa)

Test con risposte registrate: il sistema rifiuta ciò che deve rifiutare. Sono `make check`, secondo la piramide descritta sotto.

### 2. Risultati oggettivi (a ogni traguardo)

| Misura | Fonte |
|---|---|
| Master valido, consegne derivate | Registro |
| Controlli QA superati al primo passaggio | Registro |
| Costo, token, chiamate, tempo | `usage` |
| Hit rate della cache, contesto medio | `usage` |
| Immagini lette, cicli di rework | Registro |

### 3. Qualità (a ogni traguardo importante)

- **Giudizio umano alla cieca**: Andrea confronta file anonimi e assegna un punteggio contro riferimenti
  ordinario / buono / eccellente. È la misura principale. Da M1.6 si registra con `agency judge` nella tabella `judgments`,
  legato allo sha256 del file (ADR-0027): le lettere si estraggono a ogni confronto, e con più file si sceglie anche il
  migliore, che sta tra i livelli più alti. I file si guardano su una tavola che mette ogni disegno alla stessa misura,
  grande e a 64, 32 e 16 px (ADR-0041). Il primo è del 2026-11-03: `merlo3` eccellente e migliore, `merlo` buono, tutti e due
  specifici.
- **Critica automatica**: rubrica di `critique`, utile per trovare difetti. Non sostituisce il giudizio umano.
- **Test di sostituzione**: il risultato reggerebbe con un altro nome? Si registra sì o no, nello stesso giudizio alla cieca.

## Piramide dei test

La piramide dice se il sistema funziona. Le valutazioni dicono se il lavoro è buono. Nessun livello chiama l'API.

| Livello | Cosa prova | Strumento | Quantità |
|---|---|---|---|
| Unità | Regole pure: dominio, contratti, prezzi, proiezioni | `pytest`, senza I/O | Molti |
| Integrazione | Una slice con registro vero su file temporaneo e risposte registrate | `pytest` | Alcuni |
| Contratto | Snapshot di strumenti e prompt, OpenAPI contro tipi TypeScript, confini tra moduli | `pytest`, `import-linter` | Pochi, bloccanti |
| Flusso | Un progetto fino al gate, con risposte registrate | `pytest` | Pochi |
| Interfaccia | Una prova di fumo per vista | Playwright | Pochissimi |

Oggi più della metà dei test sono flussi completi. Restano tutti fino alla fine di M1.7, perché sono la rete del refactor: i nuovi
test nascono sulle regole pure.

Gli snapshot in `tests/snapshots/requests/` fissano byte per byte strumenti e system prompt di ogni fase. Fallire è il loro
compito: ogni cambiamento di prompt o strumenti invalida la cache e cambia ciò che il modello vede. Se è voluto, si aggiornano con
`UPDATE_SNAPSHOTS=1 uv run pytest tests/test_request_snapshots.py`, e il diff si rivede prima del commit.

## Regole del confronto

- Lo stesso brief almeno 3 volte per configurazione: una sola prova dice poco.
- Set separati per messa a punto e verifica: il test non si guarda mentre si ottimizza.
- Un costo più basso non conta se la qualità scende.
- Si misura il costo per lavoro completato, non per chiamata.
- Ogni esecuzione registra la propria impronta nella tabella `runs` (ADR-0026): prompt, registry, codice, lock, Python, CLI,
  modello, `effort` e impostazioni. `agency compare` dice cosa cambia tra due esecuzioni. I lavori `merlo` non hanno impronta.

## Riferimenti `merlo`, `merlo2` e `merlo3`

`merlo3` è il riferimento di qualità e del flusso (ADR-0042). Il suo segno ha battuto quello di `merlo` nel giudizio
alla cieca del 2026-11-03, e va battuto nella versione giudicata, sha256 `2947a64f2ad1…`, conservata negli artefatti. Il
flusso: 13,29 $ fino alla presentazione e 34,38 $ fino al gate `final`, ma con una tavola non alla pari (ADR-0017).
`merlo2` è il riferimento di tempi del flusso parallelo, e mostra cosa non fare: segni deboli, geometrici, a prima vista
generici. `merlo` resta un riferimento storico. `merlo4` sarà il primo riferimento con impronta e giudizio registrati.

Ogni prova su E1 si confronta con `merlo3` (`docs/02-ROADMAP.md`): giudizio alla cieca del segno finale contro il suo,
tempo e costo fino al concetto scelto, costo fino al gate, bocciature del concetto dopo la scelta, diversità delle idee,
test di sostituzione. Le tavole di `merlo` restano in `projects/merlo/`.

## Confronto con Claude Code

In M1.6 e M2 si esegue lo stesso brief sul setup CLI e sull'harness. Su Neima i numeri del vecchio setup
vengono da prezzi precedenti: conta il replay, non il confronto col valore storico.

## Da DSPy in poi

L'ottimizzazione automatica (M5) richiede una metrica. Oggi esiste per instradamento, estrazione di fatti
e referti. Sul giudizio creativo non esiste ancora: servono prima almeno alcune decine di giudizi umani
registrati.
