---
name: mockup
description: Crea mockup credibili e onesti — stampati, packaging, insegne, merch, schermi e dispositivi — con scena di fonte registrata, prospettiva corretta, proporzioni reali dell'artwork, luce e materiale della scena, verifica a dimensione piena. Da usare per "preparami un mockup", presentazioni di identità e verifiche di applicazione.
---

# Mockup

Un mockup mostra il lavoro nel mondo. È presentazione, non prova: non sostituisce i test
del logo né il preflight di stampa, e non deve nascondere un difetto.

## 1. Scena

| Fonte | Uso | Da registrare |
|---|---|---|
| Foto del cliente | applicazioni reali | permesso d'uso |
| Stock con licenza | presentazioni | fonte, ID, licenza, limiti (`legal-ip`) |
| Frame FigCraft esportati | interfacce e siti in dispositivi | file e frame |
| Scena 3D Blender (`production-3d`) | packaging e prodotti con luce e materiali reali | file di scena, verifica di fedeltà |
| Compositing PhotoCraft | stampati su superfici reali, insegne, merch, con maschere e deformazioni | file `.pcraft` con livelli |

La scena deve avere superfici con prospettiva leggibile, luce coerente e risoluzione
almeno pari all'uso finale. Scrivi in `work/mockup/sources.md` la fonte di ogni scena.

## 2. Superficie

- Individua i quattro angoli della superficie (in alto a sinistra, alto a destra, basso a
  destra, basso a sinistra) e controllali con
  `mockup_compose.py --scene s.jpg --show-quad "…" --out guida.png`. Guarda la guida.
- Superfici curve (bottiglie, tazze) o con pieghe forti: dividi in strisce o usa il 3D; un
  solo quadrilatero su una superficie curva è un errore.

## 3. Artwork

- Tavola dell'artwork con le **proporzioni fisiche reali** della superficie (es. A4 =
  210×297, biglietto 85×55). Lo script rifiuta scarti di proporzione oltre il 6%: se la stima
  è falsata da una prospettiva forte, verifica a occhio sulla guida prima di `--allow-stretch`.
- Risoluzione dell'artwork almeno pari ai pixel che occuperà nella scena.
- Solo artwork approvato; altrimenti il mockup è marcato come bozza.

## 4. Composizione

```sh
.claude/scripts/py .claude/skills/mockup/scripts/mockup_compose.py --scene s.jpg --art a.png \
    --quad "x1,y1 x2,y2 x3,y3 x4,y4" --out m.png --blend multiply|normal|screen [--shading 0.6] [--mask m.png] [--grain 0.3]
```

| Materiale | Blend | Note |
|---|---|---|
| carta, cartone, tessuto chiaro | `multiply` | pieghe e grana della scena passano attraverso l'inchiostro |
| superfici opache scure, plastica, metallo verniciato | `normal` + `--shading` | luce della scena trasferita |
| schermi | `normal`, `--shading` basso + riflesso della scena | il contenuto dello schermo è emissivo |
| stampa su vetro o pellicole | `screen` o maschera | verifica a occhio |

Più artwork nella stessa scena: applicali in sequenza sull'output. Ombre di contatto e
riflessi locali si aggiungono con maschere dalla scena, non dipinti a mano libera.

## 5. Verifica

Guarda il mockup a dimensione piena e al 200% sui bordi:
- prospettiva coerente con le linee della scena; nessuna deformazione dell'artwork;
- bordi senza aloni né scalettature; nessun pezzo di superficie scoperto;
- luce e ombre coerenti con la direzione della luce della scena;
- testo dell'artwork leggibile quanto lo sarebbe nella realtà, non di più.

Poi `image_check.py` sugli export (dimensioni, profilo, peso) e registra `mockup_aspect`,
`image_check`, `visual_review` in `evidence.py`.
