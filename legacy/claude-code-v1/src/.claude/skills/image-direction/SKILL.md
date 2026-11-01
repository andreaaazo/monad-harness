---
name: image-direction
description: Direzione fotografica e d'immagine — linguaggio fotografico del brand, moodboard motivato, brief per shooting, criteri di selezione, trattamento e color grading, fonti e licenze delle immagini. Da usare quando un'identità, una campagna o un sito usano fotografia o immagini.
---

# Direzione d'immagine

## Linguaggio

Dalla strategia e dalla direzione, definisci per la fotografia del brand: soggetti, punto
di vista e distanza, luce (dura/morbida, naturale/artificiale, direzione), colore e grading,
composizione e spazio per il testo, gesti e casting, cosa non mostrare mai.
Ogni regola con un esempio e un controesempio. Casting e soggetti rappresentano le persone reali
del pubblico e del cliente, senza stereotipi; niente immagini "di riempimento" che potrebbero stare
nel sito di chiunque.

## Moodboard

10–20 immagini di riferimento in `work/image/mood/`, ognuna con fonte e una riga sul
perché. Il moodboard spiega una regola, non è un collage di cose belle. Sono riferimenti:
non si usano come asset.

## Fonti delle immagini finali

| Fonte | Condizione |
|---|---|
| Fotografie del cliente | diritti e liberatorie confermati dal cliente |
| Shooting commissionato | brief di shooting (lista scatti, formati, luce, casting, consegna) |
| Stock | licenza registrata (fonte, ID, tipo di licenza, limiti d'uso) con `legal-ip` |
| 3D o illustrazione | prodotti dallo studio |

Lo studio non ha un generatore d'immagini: non presentare mai immagini di stock o
composizioni come fotografie del cliente o dei suoi prodotti.

## Coerenza e trattamento del set

```sh
S=.claude/skills/image-direction/scripts/photo_set.py
.claude/scripts/py $S measure work/client/foto          # firma di ogni foto, foto fuori set
.claude/scripts/py $S treat work/client/foto --recipe work/image/ricetta.json --out work/image/trattate
.claude/scripts/py $S match work/client/foto --out work/image/allineate
.claude/scripts/py $S sheet work/image/trattate --out work/image/foglio.png    # guardalo
```

La misura allinea luminosità, contrasto, croma e temperatura; non rende coerenti luce, soggetto e
punto di vista: quello è art direction (e a volte significa scartare o riscattare una foto).
Fotoritocco, maschere, rimozioni, riempimenti e compositing: **PhotoCraft** (MCP con lock o
`photocraft-cli run/batch`). Dimostrato su un set di prova: vedi `CAPABILITIES.md`.

## Trattamento

Grading e ritaglio coerenti, documentati come ricetta riproducibile (curve, saturazione,
temperatura, grana), applicati con script (Pillow/ImageMagick) per la coerenza del set.
Controlla con `image_check.py` profilo colore e risoluzione per il supporto.
