---
name: visual-qa
description: Verifica tecnica indipendente di qualsiasi deliverable visivo — scelta dei controlli per tipo, esecuzione degli script dello studio, osservazione delle prove, localizzazione dei difetti, regressioni tra versioni, registrazione delle prove con hash. Da usare per il QA L2.
---

# QA visivo

## Procedura

1. Dal ticket: elenco dei file e tipo di deliverable. Controlli richiesti da
   `.claude/design-agency/QA.md`.
2. Esegui gli script **tu**, sui file salvati, anche se l'autore li ha già eseguiti.
3. **Guarda** ogni prova prodotta (Read sull'immagine): uno script che passa non vede refusi,
   tagli, squilibri o elementi fuori posto.
4. Per ogni difetto: file, posizione (coordinate, pagina, timecode, selettore), misura,
   soglia, impatto, severità.
5. Registra ogni controllo con `evidence.py record … --by qa-inspector --proof <prova>`.

## Script per tipo

| Deliverable | Script |
|---|---|
| SVG, logo, icone | `logo-design/scripts/svg_audit.py`, `logo-design/scripts/logo_proof.py`, `visual-qa/scripts/svg_parity.py` (stesso aspetto in VectorCraft, librsvg, Inkscape, cairosvg) |
| Equilibrio e centri ottici | `visual-qa/scripts/optical_check.py` (composizione o `--set` per icone e varianti) |
| Qualsiasi output da guardare | `../scripts/render.py` (render registrato della versione attuale) |
| Colore | `color-system/scripts/color.py matrix`, `color.py cvd` |
| Font | `type-system/scripts/font_inspect.py` |
| Token | `design-tokens/scripts/tokens_check.py` |
| Immagini | `visual-qa/scripts/image_check.py` |
| Confronto tra versioni | `visual-qa/scripts/pixel_diff.py` |
| PDF | `print-production/scripts/pdf_preflight.py` |
| Video | `motion-identity/scripts/motion_probe.py` |
| Lottie | `motion-identity/scripts/lottie_check.mjs` |
| Web | `web-qa/scripts/web_audit.mjs` |

I percorsi sono relativi a `.claude/skills/`. Python con `.claude/scripts/py`, Node con
`.claude/scripts/node`.

## Regressioni

Dopo una correzione: stessa prova sulla nuova versione e
`pixel_diff.py prima.png dopo.png --expect-region x,y,w,h --out diff.png`. Cambiamenti fuori
dall'area attesa sono regressioni da segnalare. Le prove della versione precedente non
valgono più (il gate le vede STALE).

## Report

`work/qa/<ticket>.md`: file e revisioni ispezionati, controlli con esito e prova, difetti,
controlli non eseguibili con il motivo. Niente voti medi.
