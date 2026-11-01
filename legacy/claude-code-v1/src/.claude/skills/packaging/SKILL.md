---
name: packaging
description: Progetta packaging ed etichette — dieline del fornitore, architettura delle informazioni sulle facce, impatto sullo scaffale, sistema di varianti, diciture obbligatorie e minimi di leggibilità, codici a barre, materiali e finiture, file di stampa e mockup di verifica. Da usare per scatole, etichette, buste, linee di prodotto.
---

# Packaging

## Input obbligatori

- **Dieline del fornitore** (mai disegnata a stima): facce, pieghe, incollaggi, fustella,
  direzione della fibra.
- Materiale e processo di stampa (cartoncino, kraft, plastica, vetro; offset, flexo, digitale).
- Contenuti e diciture obbligatorie della categoria e del mercato (testi dal cliente,
  verificati da `legal-ip`).
- Contesto di vendita: scaffale fisico, e-commerce (immagine piccola), entrambi.

## Architettura delle facce

1. Faccia principale: riconoscimento del brand → variante/prodotto → beneficio chiave.
2. Facce secondarie: informazioni, istruzioni, diciture, codice a barre.
3. Sistema di varianti: cosa resta fisso (brand, griglia, posizione dei blocchi) e cosa
   cambia (colore, illustrazione, nome); prova con tutte le varianti affiancate.

## Leggibilità e diciture

- Nell'UE, per gli alimenti, le informazioni obbligatorie hanno un'altezza minima della x di
  1.2 mm (0.9 mm se la superficie maggiore è sotto 80 cm²) [P1]. Altre categorie hanno norme
  proprie: verificale per mercato e categoria.
- Contrasto sufficiente tra testo e fondo, anche su materiali come il kraft (misura il colore
  reale del supporto, non il bianco).

## Codici a barre

EAN/UPC dal sistema GS1 del cliente; dimensione e zone di rispetto secondo le specifiche
GS1 [P2] (per EAN-13 la dimensione nominale è 37.29 × 25.93 mm a ingrandimento 100%);
barre scure su fondo chiaro, orientamento rispetto alla direzione di stampa, niente
troncature dell'altezza senza conferma del fornitore. Verifica con lettore quando possibile.

## Scaffale

Mockup di verifica (`mockup`) sulla dieline montata o in 3D; confronto affiancato con 4–6
concorrenti a distanza di scaffale (immagine ridotta a ~10% della dimensione reale) e a
dimensione e-commerce (~300 px). Il brand e la variante devono restare riconoscibili.

## File

Dieline, abbondanza, area sicura e finiture su livelli separati in tinte piatte dedicate in
sovrastampa; un PDF per variante; `print-production` e `pdf_preflight.py --print`.
Registra `pdf_preflight`, `dieline_check`, `legal_text`, `barcode`, `visual_review`.
