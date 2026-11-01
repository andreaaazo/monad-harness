---
name: design-tokens
description: Struttura il design system del brand in token DTCG — primitive, ruoli semantici, componenti, temi chiaro/scuro, alias — e ne verifica la validità e le dipendenze. Da usare per consegnare colori, tipografia, spaziature, raggi e motion come dati riutilizzabili.
---

# Design token

Formato di riferimento: Design Tokens Format Module 2025.10 del W3C Community Group [T1]
(un Community Group Report, non una Recommendation W3C).

## Livelli

1. **Primitive** — i valori: `color.violet.500`, `space.4`, `radius.2`, `duration.short`.
2. **Semantici** — i ruoli, come alias: `color.text.default → {color.neutral.900}`.
   Le applicazioni usano solo questi.
3. **Componenti** (solo se servono) — `button.background → {color.accent.default}`.

Temi: stesso albero semantico, file per tema (`tokens.light.json`, `tokens.dark.json`)
che rimappano gli alias sulle primitive.

## Forma dei valori (2025.10)

```json
{
  "color": { "$type": "color",
    "violet": { "500": { "$value": { "colorSpace": "oklch", "components": [0.62, 0.17, 290], "hex": "#816ADB" } } } },
  "space": { "$type": "dimension", "4": { "$value": { "value": 16, "unit": "px" } } },
  "duration": { "$type": "duration", "short": { "$value": { "value": 160, "unit": "ms" } } },
  "easing": { "$type": "cubicBezier", "brand-out": { "$value": [0.2, 0, 0, 1] } }
}
```

Alias: `"$value": "{color.violet.500}"`. `$description` per ogni ruolo non ovvio.

## Scale

- Spaziature: una scala che nasce dal contenuto (es. dall'interlinea del corpo o
  dall'unità `u` del logo), non multipli di 8 per abitudine.
- Raggi, spessori, ombre ed elevazione: pochi valori, coerenti con la geometria del marchio.
- Motion: durate ed easing da `motion-identity`.

## Verifica

```sh
.claude/scripts/py .claude/skills/design-tokens/scripts/tokens_check.py tokens.json [--list]
```

Controlla tipi, alias, cicli e forma dei valori. Poi:
- ogni coppia testo/sfondo semantica rimisurata con `color-system` per ogni tema;
- mappa delle dipendenze in `spec.md`: quali applicazioni e prove usano quali token,
  così una modifica invalida solo le prove interessate;
- se esporti verso CSS o un'app Craft, verifica il risultato importato: un JSON valido
  non prova che lo strumento di destinazione lo legga correttamente.
