---
name: presentation
description: Progetta presentazioni — pitch deck e presentazioni di progetto al cliente — con struttura narrativa, griglia e stili dal brand, una idea per slide, dati leggibili, export verificati in PDF e immagini. Da usare per presentare un'identità, una campagna, un sito o un deck del cliente.
---

# Presentazioni

## Narrazione

- Una frase per tutta la presentazione: cosa deve pensare e decidere chi guarda alla fine.
- Struttura per la presentazione di un progetto dello studio: problema e obiettivo →
  cosa abbiamo capito (strategia) → l'idea → l'idea nel sistema (logo, colore, tipo, motion)
  → l'idea nel mondo (applicazioni) → cosa serve decidere.
- Mostra le alternative scartate solo se aiutano la decisione.

## Slide

- Formato 16:9 a 1920×1080 salvo diversa richiesta; griglia e margini costanti.
- Una idea per slide; il titolo è una frase che dice la conclusione, non un'etichetta.
- Corpo minimo leggibile in proiezione (indicativamente ≥ 24 px a 1920×1080 per il testo,
  da verificare sul supporto reale); niente paragrafi lunghi.
- Dati: un grafico per messaggio, con il numero importante evidenziato.
- Immagini del lavoro grandi e su fondo neutro; mockup onesti (`mockup`).

## Produzione

In FigCraft (frame 1920×1080, stili e componenti del brand) o VectorCraft (tavole); export PDF e
PNG per slide con `figcraft-cli export` o `vectorcraft-cli convert`.
Se il cliente chiede .pptx, converti o costruisci e verifica l'apertura con LibreOffice.

## Verifica

Foglio di miniature di tutte le slide per ritmo e coerenza; ogni slide al 100%; rilettura dei
testi (`proof_read`); `image_check.py` sugli export; font incorporati nel PDF
(`pdf_preflight.py` senza `--print`).
