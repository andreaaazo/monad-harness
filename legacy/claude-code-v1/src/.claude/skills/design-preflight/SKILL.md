---
name: design-preflight
description: Controlla che lo studio sia operativo — validità del setup, toolchain, flag di confinamento delle CLI Craft, lock, server MCP della sessione; con "smoke" esegue anche una prova di produzione ed export su VectorCraft ed EffectCraft.
argument-hint: "[opzionale: smoke]"
disable-model-invocation: true
---

Richiesta: $ARGUMENTS

1. Esegui e riporta l'output completo:

   ```sh
   python3 .claude/scripts/validate_agency.py --env
   .claude/scripts/py .claude/scripts/tools.py check
   python3 .claude/scripts/craft_lock.py status
   ```

   Se mancano tool core: `tools.py plan` e il comando da proporre all'utente.

2. Verifica nella sessione che `vectorcraft` ed `effectcraft` siano connessi: acquisisci il
   lock come `router`, fai una chiamata di ispezione non mutante, rilascia il lock.
   Se la sessione non è partita da `start-agency.sh`, una voce MCP globale può prevalere: dillo.

3. Solo con `smoke`, in sequenza e in `.claude/runtime/preflight/`, ciascuno con il proprio lock:
   - VectorCraft: quadrato con un cerchio sottratto, salva, riapri, esporta SVG e PNG;
     `svg_audit.py` e `logo_proof.py proof`, guarda il foglio.
   - EffectCraft: composizione di 1 s con un livello animato, salva, renderizza MP4, esporta
     Lottie; `motion_probe.py` sul video, `lottie_check.mjs` sul Lottie, guarda i frame.

Riporta separatamente: configurazione, toolchain, collegamento, produzione, controlli non
eseguiti. Non installare nulla senza approvazione e non modificare configurazioni globali.
