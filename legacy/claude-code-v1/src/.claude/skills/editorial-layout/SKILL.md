---
name: editorial-layout
description: Impaginazione editoriale — formato, gabbia e griglia, gerarchia, stili di paragrafo e carattere, composizione di testi lunghi, immagini e didascalie, ritmo delle pagine, file per stampa e schermo. Da usare per brand book, brochure, report, poster, cataloghi, cancelleria, libri.
---

# Impaginazione editoriale

## Struttura

- **Formato** dal contenuto e dall'uso (tenuto in mano, a parete, a schermo); per la stampa
  verifica i formati standard dello stampatore per evitare sfridi.
- **Gabbia**: margini (interno più piccolo dell'esterno nei libri rilegati; piede più ampio
  della testa), colonne, intercolonna, righe di base [B2]. La griglia di base nasce
  dall'interlinea del corpo testo.
- **Gerarchia**: al massimo 3–4 livelli evidenti per pagina; ogni livello con un solo mezzo
  principale (corpo, peso, colore, spazio) per non confondere.

## Stili

Stili di paragrafo e carattere dai token tipografici: titoli, lede, corpo, didascalie, note,
numeri di pagina, testatine, tabelle. Nessuna formattazione locale fuori dagli stili.

## Testo

- Misura del corpo intorno a 45–75 caratteri [B1]; giustificato solo con sillabazione
  della lingua corretta e controllo dei rivoli; altrimenti a bandiera con ritmo curato.
- Niente vedove e orfane; niente righe di una parola a fine paragrafo nei titoli.
- Punteggiatura tipografica della lingua, cifre tabellari nelle tabelle, maiuscoletto vero.

## Immagini

Allineate alla griglia; ritagli motivati; didascalie vicine e coerenti; risoluzione per la
stampa ≥ 300 ppi effettivi alla dimensione di posa (verificata da `pdf_preflight.py`).

## Ritmo

Guarda il documento come sequenza (foglio di miniature di tutte le pagine): alternanza di
densità, pagine di respiro, aperture di capitolo riconoscibili.

## Verifica

- Render di ogni pagina e foglio di miniature; guarda pagina per pagina al 100%.
- Per la stampa: `print-production` e `pdf_preflight.py --print`.
- Rilettura finale dei testi impaginati (`proof_read`): il testo impaginato non è quello del
  file di copy finché non lo rileggi.
