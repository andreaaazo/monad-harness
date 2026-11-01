---
name: motion-identity
description: Progetta il movimento del brand — principi derivati dalla strategia, curve ed easing proprietari, tempi in frame, logo animato, transizioni, sting, varianti di durata e formato, export Lottie e video, versione ridotta. Da usare per qualsiasi animazione d'identità in EffectCraft.
---

# Motion identity

Il movimento è un asset distintivo come colore e forma [B11]: deve poter essere
riconosciuto anche senza logo. Nasce dalla stessa idea del segno statico.

## 1. Principi

Traduci le tensioni della strategia in 4 parametri, ognuno con valore e motivo:
- **massa**: leggero (accelera subito) ↔ pesante (parte lento, si ferma con inerzia);
- **energia**: calmo ↔ vivace (velocità di picco, quantità di overshoot);
- **direzione**: da dove entrano le cose e perché (lettura, gravità, gesto del prodotto);
- **ritmo**: regolare ↔ sincopato; durata delle pause.

I 12 principi dell'animazione [B7] (anticipazione, follow-through, archi, slow in/slow
out…) sono un vocabolario, non una lista da applicare a tutto. Nel contesto UI le
durate sono brevi e funzionali [M1]; un brand reveal ha tempi propri.

## 2. Curve e tempi

- 2–3 curve proprietarie come `cubic-bezier`, con nome e uso (`brand-out` per gli ingressi,
  `brand-in-out` per gli spostamenti). Il lineare è giusto per moti costanti (rotazioni).
- Tempi in frame alla frequenza del deliverable (24/25/30/60). Una piccola scala di
  durate (es. breve/media/lunga) che diventa token.
- Easing e durate entrano in `design-tokens`.

## 3. Storyboard prima di animare

Beat per beat: cosa si vede, cosa deve essere letto, quanto dura la pausa di lettura,
dove va l'attenzione. Styleframe per i momenti chiave, renderizzati e osservati.

## 4. Logo animato

- Costruzione dal master statico: l'animazione rivela la logica del segno
  (la sua costruzione, il suo gesto, la sua regola), non effetti generici.
- Chiude sulla forma **esatta** del master, nella posizione esatta.
- Versioni: sting (~2–4 s), ingresso breve per UI o social (≤1 s), loop se serve,
  stato statico finale. Formati richiesti dal brief (16:9, 9:16, 1:1).
- Audio, se previsto: sincronia verificata in playback.

## 5. Produzione e verifica

Segui `.claude/design-agency/CRAFT.md`. Poi su ogni render:

```sh
.claude/scripts/py .claude/skills/motion-identity/scripts/motion_probe.py render.mp4 [--loop]
```

- metadati: codec, fps, dimensioni, alpha, durata, audio;
- screening flash (WCAG 2.3.1 [A4]): `FLAG` blocca la consegna; `OK` è uno screening,
  non una certificazione;
- raccordo del loop: `CHECK` richiede di confrontare il primo frame con il raccordo.

Su ogni Lottie esportato (leggi anche gli avvisi dell'export: gli effetti non supportati
vengono saltati):

```sh
.claude/scripts/node .claude/skills/motion-identity/scripts/lottie_check.mjs anim.json --out proofs/lottie
```

Rende il file con lottie-web, segnala feature a rischio (espressioni, effetti, maschere,
testo, immagini) e salva frame campione da confrontare con il master.

Osserva i frame chiave come immagini e, quando possibile, il filmato a velocità reale.
Senza playback osservato, ritmo e sincronia sono `NOT_VERIFIED`.

## 6. Deliverable

- master `.ecproj`;
- Lottie (`file.exportLottie` in EffectCraft: verifica che effetti ed espressioni usati
  siano supportati, poi riapri il file esportato), MP4 H.264, ProRes 4444 o WebM con
  alpha se richiesto;
- variante statica e ridotta per `prefers-reduced-motion` [A6];
- specifica di movimento: curve, durate, direzioni, cosa non fare.
