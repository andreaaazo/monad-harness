---
name: print-production
description: Prepara e verifica file per la stampa — condizione di stampa e profilo, abbondanze e box PDF, nero ricco e sovrastampa, copertura d'inchiostro, tinte piatte, risoluzione effettiva, font incorporati, finiture e fustelle — con preflight misurato. Da usare per ogni file che va a uno stampatore.
---

# Produzione di stampa

## Prima di impaginare

Chiedi (tramite il router) o ricava dalla specifica dello stampatore:
- processo (offset, digitale, serigrafia, flexo, grande formato) e **condizione di stampa**
  (carta patinata/naturale, profilo ICC, es. un profilo FOGRA), **TAC massimo**;
- formato rifilato, abbondanza (3 mm è comune, ma vale la specifica), area sicura;
- tinte piatte, finiture (vernice selettiva, lamina, rilievo), fustella;
- formato del file richiesto (PDF/X-1a, PDF/X-4…).

Senza specifica, il file è una bozza e lo dichiara.

## Regole di costruzione

- Abbondanza su tutti gli elementi al vivo; nessun testo o elemento importante nell'area
  di rifilo o fuori dall'area sicura.
- Testi neri piccoli in nero solo K al 100% in sovrastampa; nero ricco (es. C60 M40 Y40 K100,
  secondo lo stampatore) solo per grandi campiture, mai per testo piccolo o filetti.
- Filetti ≥ 0.25 pt (verifica con lo stampatore per processi diversi dall'offset).
- Immagini ≥ 300 ppi effettivi alla dimensione di posa per l'offset (grande formato:
  secondo distanza di visione).
- Tinte piatte con il nome della guida usata e verificate su mazzetta fisica; non inventare
  codici. Le conversioni a CMYK si dichiarano.
- Fustelle, vernici, lamine su livelli separati in tinta piatta dedicata, in sovrastampa,
  con il nome concordato con lo stampatore.
- Font incorporati (o convertiti in tracciati dove la licenza lo impone).

## Preflight

```sh
.claude/scripts/py .claude/skills/print-production/scripts/pdf_preflight.py file.pdf --print \
    --bleed-mm 3 --min-ppi 300 --max-tac 300
```

Misura pagine e box, abbondanza, font, ppi effettivi e spazio colore delle immagini, output
intent, TAC massimo per pagina. I limiti si impostano dalla specifica dello stampatore.
Poi guarda il PDF renderizzato pagina per pagina: il preflight non vede refusi, elementi
tagliati per sbaglio o sovrastampe che fanno sparire un oggetto.

Registra `pdf_preflight` e `visual_review` in `evidence.py`. Quando possibile, chiedi una
prova di stampa (cianografica o prova colore certificata) per i lavori critici.
