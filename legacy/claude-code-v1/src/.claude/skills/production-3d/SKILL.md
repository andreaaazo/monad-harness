---
name: production-3d
description: Produzione 3D in Blender per packaging, prodotti e scene di contesto — geometria in misure reali, grafiche mappate senza deformazioni, materiali e finiture, luce da studio calibrata, camera e inquadratura calcolate, render con autoverifica di fedeltà del colore e alte luci. Da usare per mockup di packaging, visualizzazioni di prodotto e scene quando la fotografia non c'è.
---

# Produzione 3D

## Packaging a scatola

```sh
blender -b -P .claude/skills/production-3d/scripts/pack_render.py -- \
    --size 120x60x180 --front work/pack/fronte.png --side work/pack/lato.png --back work/pack/retro.png \
    --out work/mockup/pack.png --res 2400x1800 --samples 128 --finish matte|satin|gloss --light 0.5 --look faithful
```

- Dimensioni in mm reali; ogni grafica deve avere le proporzioni della sua faccia (lo script lo
  verifica e si ferma). Le grafiche arrivano dalla dieline approvata, non da una bozza.
- `--look faithful` mantiene i colori del file (packaging, verifica); `photographic` dà un aspetto
  più fotografico ma schiarisce e desatura.
- A fine render lo script misura **fedeltà del colore del fronte** (ΔE OK tra grafica e render) e
  **alte luci bruciate**: ΔEok < 0.06 e < 1% di pixel bruciati è il punto di partenza dello studio;
  sopra, abbassa `--light`, cambia finitura o esposizione e rifai. Poi **guarda** il render.
- Registra `render_check` (misura) e `visual_review` (render osservato) sull'immagine.

## Dispositivo di render

`pack_render.py` usa la GPU quando c'è e altrimenti la CPU; la riga `DISPOSITIVO` dell'output dice
quale ha usato. Ogni script di scena dedicato fa lo stesso, dopo `read_factory_settings`:

```python
sys.path.insert(0, ".claude/skills/production-3d/scripts")
from cycles_device import use_gpu
use_gpu(scene)
```

`DISPOSITIVO CPU` su una macchina con GPU di solito significa build sbagliata: quella apt non ha i
kernel GPU. Installa quella ufficiale con `bash .claude/tools/setup_tools.sh --blender`.

## Oltre la scatola

Bottiglie, buste, flaconi, forme fustellate aperte, materiali speciali (lamina, rilievo,
vernice selettiva) richiedono uno script di scena dedicato o il lavoro manuale in Blender: la
capacità non è ancora dimostrata (`CAPABILITIES.md`). Dichiaralo prima di prometterlo al cliente.

## Regole

- Luce e camera motivate dall'uso del render (scaffale, e-commerce, editoriale), non di default.
- Un render è una presentazione, non una prova di stampa: i colori finali si verificano con il
  preflight e con la prova dello stampatore.
