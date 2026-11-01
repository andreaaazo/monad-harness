---
name: color-system
description: Costruisce la palette di un brand in OKLCH — colori primari, rampe percettivamente uniformi, neutri tinti, ruoli semantici, coppie di contrasto misurate in APCA e WCAG, note per stampa. Da usare per creare, estendere o verificare una palette.
---

# Sistema colore

Il colore è un asset distintivo [B11] e un sistema di ruoli. Si progetta in uno spazio
percettivo e si verifica con misure, perché l'interazione tra colori inganna l'occhio [B8].

## Strumento

```sh
S=.claude/skills/color-system/scripts/color.py
.claude/scripts/py $S info "#HEX"                        # OKLCH, luminanza, croma massima in sRGB
.claude/scripts/py $S ramp --hue H --chroma C --lightness 0.97,0.92,…,0.2 [--names 50,100,…]
.claude/scripts/py $S contrast "#TESTO" "#SFONDO"        # APCA Lc e rapporto WCAG
.claude/scripts/py $S matrix palette.json                # tutte le coppie testo×sfondo
```

APCA è implementato secondo APCA-W3 0.0.98G-4g [K2]; WCAG 2 secondo la formula
normativa [A1]. Le conversioni OKLab sono quelle di Ottosson [K3].

## Processo

1. **Colore primario dalla strategia.** Da dove viene (materiale, luogo, prodotto,
   contrasto con la categoria)? Registra la tinta e il motivo. Controlla con `info`
   quanta croma è disponibile a quella chiarezza in sRGB.
2. **Rampe.** Per ogni tinta, una rampa a chiarezza OKLCH esplicita: passi uniformi
   alla vista si ottengono con passi di L, non schiarendo in HSL. La croma cala verso
   gli estremi (`--chroma-curve taper`), dove sRGB ne contiene poca. Lo script
   riduce la croma a L e tinta costanti se serve e segnala `gamut_mapped`.
   La tinta può ruotare di pochi gradi lungo la rampa se a vista serve
   (i gialli scuri tendono all'oliva): annota la rotazione.
3. **Neutri tinti.** Grigi con croma bassa (≈0.005–0.02) nella tinta del brand o
   nella sua complementare, invece di grigi puri.
4. **Ruoli.** Nomi semantici (`surface`, `text`, `text-muted`, `accent`, `border`,
   `focus`, stati) mappati sulle primitive. L'accento è raro per definizione.
5. **Contrasto per coppie reali.** Scrivi `palette.json` con i ruoli testo e sfondo,
   lancia `matrix`. Riporta APCA (Lc con segno: positivo scuro su chiaro, negativo
   chiaro su scuro) e WCAG. Per il web la conformità si dichiara su WCAG 2.2 [A1][A2];
   APCA guida le scelte di leggibilità per corpo e peso.
6. **Temi.** Il tema scuro non è l'inversione del chiaro: le superfici salgono di
   chiarezza con l'elevazione, l'accento spesso scende di croma, il testo non è bianco puro.
   Rimisura tutte le coppie.
7. **Daltonismo.** Nessuna informazione affidata solo alla tinta [A3]; controlla che
   le coppie di stato differiscano anche in chiarezza (ΔL OKLCH ben visibile).
8. **Stampa.** CMYK e tinte piatte dipendono da carta, processo e fornitore: chiedi le
   condizioni di stampa e il profilo prima di fissare equivalenze. Non inventare codici
   di tinte piatte; proponi candidati da verificare su mazzetta fisica.

## Deliverable

Primitive e ruoli in token (`design-tokens`), tabella delle coppie misurate con metodo,
tavola colore renderizzata e osservata su chiaro e scuro, note di stampa con stato.
