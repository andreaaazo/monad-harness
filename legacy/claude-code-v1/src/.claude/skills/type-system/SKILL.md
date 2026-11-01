---
name: type-system
description: Sceglie e calibra il sistema tipografico di un brand — caratteri e licenze, abbinamenti, scala modulare, interlinea su griglia di base, misura della riga, ruoli, scala fluida per il web, specimen con testi reali. Da usare per definire o verificare la tipografia di un'identità.
---

# Sistema tipografico

Il carattere è la voce del brand e l'asset che compare più spesso. Le regole di base
vengono dalla tradizione tipografica [B1][B13]; i numeri si derivano dal contenuto e dal supporto.

## Scelta dei caratteri

**Non scegliere tra i caratteri installati sulla macchina**: sono pochi e portano sempre agli
stessi. Cerca nella libreria (≈1900 famiglie a licenza aperta) e, se il progetto lo giustifica,
proponi al cliente caratteri commerciali di fonderia con licenza da acquistare.

```sh
S=.claude/skills/type-system/scripts/font_library.py
.claude/scripts/py $S search --category serif --subset latin-ext --min-styles 4 --avoid-popular 100
.claude/scripts/py $S fetch "Famiglia A" "Famiglia B"            # work/fonts/<slug>/ con LICENSE-RECORD.json
.claude/scripts/py $S specimen "Famiglia A" "Famiglia B" --text "<nome del cliente>" --text2 "<descrittore reale>"
```

[E] `--avoid-popular` allarga lo sguardo oltre le scelte di default, ma la scelta si fa per
**adeguatezza, non per rarità**: confronta sempre nello specimen anche un candidato convenzionale
ben composto, sugli stessi testi, e scegli sul risultato. Lo specimen è renderizzato: guardalo con Read.

- Parti dalle tensioni della strategia: costruzione (geometrica, umanista, grottesca,
  contrasto, larghezza), dettagli (terminali, aperture, altezza della x), comportamento
  ai pesi estremi.
- Verifica: copertura dei glifi per tutte le lingue del brand (accenti, ß, ł, virgolette,
  numeri tabellari e proporzionali, frazioni), pesi e corsivi necessari, varianti
  ottiche, qualità del kerning, rendering a schermo piccolo.
- **Licenza**: desktop, web, app, logo, modifiche; fonderia e versione. Registrala.
- Un carattere di default (vedi [anti-patterns](../../design-agency/references/anti-patterns.md))
  richiede una ragione scritta.
- Abbinamenti: per contrasto chiaro o per famiglia. Allinea l'altezza della x tra i due
  a corpi di uso comune e controlla che colore e ritmo stiano insieme.

## Scala

```sh
.claude/scripts/py .claude/skills/type-system/scripts/type_scale.py --base 16 --ratio major-third --steps -2:6 --grid 4
.claude/scripts/py .claude/skills/type-system/scripts/type_scale.py --base 16 --ratio 1.2 --max-base 18 --max-ratio perfect-fourth --viewport 360:1440 --css
```

- Scala modulare: corpi legati da un rapporto [B9]. Rapporti piccoli (1.125–1.25)
  per interfacce dense, ampi (1.333–1.618) per editoriale ed espressivo.
- Interlinea relativa decrescente con il corpo, agganciata alla griglia di base.
- I passi estremi si correggono a vista con contenuti reali: registra le deviazioni.
- Per il web, scala fluida con `clamp()` tra due viewport.

## Leggibilità

- Misura del testo corrente intorno a 45–75 caratteri per riga [B1]; più corta per
  colonne strette o testo grande.
- Tracking: negativo leggero per i titoli grandi, positivo per maiuscoletto e corpi molto
  piccoli, zero per il testo corrente salvo motivo.
- Contrasto del testo misurato con `color-system` sui corpi e pesi reali.

## Ruoli

Display, titoli, lede, corpo, didascalia, etichetta, dati. Per ciascuno: carattere,
peso, corpo, interlinea, tracking, maiuscole/minuscole, cifre. Diventano token
`typography` composti (`design-tokens`).

## Specimen

Renderizza uno specimen con testi veri del brand, nelle lingue reali e con le stringhe
più lunghe, a dimensione d'uso. Guardalo. Controlla vedove e orfane, rientri, cifre
in tabella, sostituzione del font di fallback.
