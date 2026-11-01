---
name: illustration-iconography
description: Sistemi di icone e illustrazione di marca — griglia e keyline, tratto, terminali, raggi, livello di dettaglio, metafore coerenti, versioni per dimensione, regole di stile riproducibili e audit del set. Da usare per set di icone, pittogrammi, illustrazioni, pattern figurativi, diagrammi.
---

# Illustrazione e iconografia

## Icone: regole prima dei pezzi

In `work/icons/rules.md`:
- **griglia** (es. 24×24 con 2 px di margine) e **keyline**: cerchio, quadrato, rettangoli
  verticale e orizzontale di area visiva equivalente (il cerchio è più grande del quadrato);
- **tratto**: spessore unico o due spessori, a pixel interi alla dimensione base;
  terminali e giunzioni (tondi, piatti, smussati) coerenti con il carattere del brand;
- **raggi**: pochi valori, derivati dalla geometria del logo;
- **dettaglio**: numero massimo di elementi per icona; niente dettagli sotto 1 px a 16 px;
- **metafore**: un glossario (azione → metafora) per non avere due icone diverse per lo
  stesso concetto; evita metafore obsolete o culturalmente ambigue;
- **stile**: outline, pieno o duotono; stati (attivo/inattivo) definiti dal sistema.

## Produzione

1. 4–6 icone campione che stressano le regole (una tonda, una diagonale, una densa, una
   astratta, una con testo o numero). Critica, poi il set.
2. Costruzione con le stesse unità; SVG con `viewBox` della griglia, tratti espansi solo
   nel deliverable (conserva il sorgente con tratti vivi se il set deve restare modificabile).
3. Versioni ottiche se servono (16 px con meno dettaglio, 32 px pieno).

## Audit del set

- `svg_audit.py` su ogni icona (quasi-allineamenti, transform, nodi).
- Foglio di contatto a 16/24/32/48 px su chiaro e scuro (`logo_proof.py sheet --mono`):
  peso ottico uniforme, allineamento alla griglia, nessuna icona che "salta" per massa.
- Area d'inchiostro per icona (pixel neri sul totale a 24 px): scarti grandi indicano
  icone otticamente più pesanti.

## Illustrazione

Regole: costruzione delle forme, prospettiva (frontale, isometrica, libera), palette e
quantità di colori, luce e ombre (piatte, a bande, nessuna), texture, figura umana
(proporzioni, volti sì/no, diversità), livello di dettaglio per dimensione. Tre pezzi
campione prima del set; ogni pezzo nuovo si confronta affiancato con i campioni approvati.
