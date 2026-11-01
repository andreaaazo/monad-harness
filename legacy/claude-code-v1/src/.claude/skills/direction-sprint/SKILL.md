---
name: direction-sprint
description: Sprint delle direzioni per i progetti importanti — brief pack congelato, tre (o più) esploratori isolati che sviluppano direzioni sostanzialmente diverse per concept, composizione, tipografia e linguaggio delle immagini, applicazioni comuni confrontabili, tavole anonime, misura della diversità, scelta del direttore creativo senza fusioni automatiche, carta della direzione. Da usare per identità, rebrand, campagne e siti di dimensione L.
---

# Sprint delle direzioni

Le direzioni esplorate in una sola testa si somigliano: ognuna eredita le idee della
precedente. Lo studio le fa sviluppare da esploratori separati (`direction-a`, `-b`, `-c`),
con lo stesso brief e senza vedersi: un hook (`isolation-guard.py`) lo impone.

**L'isolamento non basta.** Verificato sul lavoro dello studio: tre esploratori isolati con lo
stesso brief sono arrivati allo stesso concept (stessa metafora, stessi caratteri, stessa
palette), perché lo stesso modello davanti allo stesso brief converge sull'idea più probabile.
Per questo ogni esploratore riceve una **leva di partenza** diversa e paga la **tassa delle idee
ovvie**; la diversità si misura sulle schede (`concepts`), non solo sui pixel.

**Tre è il punto di partenza operativo, non un dogma.** Due bastano quando il brief è stretto
o il budget piccolo; quattro servono quando la categoria è molto affollata. Dopo ogni sprint
registra in `.agency/decisions.md` se le direzioni erano davvero diverse (`diversity`) e se la
scelta è caduta su quella più lontana dalla convenzione: è il dato per tarare il numero.

## Organizzatore (creative-director)

1. **Prerequisiti**: dossier con copertura completa (`facts.py coverage`), mondo del cliente
   inventariato (`client-world`), strategia approvata dal cliente (gate `strategy`).
2. **Brief pack** in `work/directions/brief-pack.md`: obiettivo, pubblico, criteri di scelta,
   fatti chiave citati [F-…], materiali del cliente da usare, vincoli, cosa evitare. Uguale per
   tutti: è un input con versione nei ticket, quindi gli hash dimostrano che è lo stesso.
3. **Applicazioni comuni** in `work/directions/apps.json`: 4–6 applicazioni scelte dal mondo
   del cliente (non generiche), con dimensioni esatte. Per progetti digitali: home desktop,
   home touch, pagina di contenuto denso, momento d'interazione chiave in sequenza, stesso
   momento in comportamento ridotto. Esempio per uno studio medico:
   lockup del segno, cartello d'ingresso, scheda paziente, home del sito, post di
   reclutamento. Almeno una applicazione difficile (molto piccola, molto densa o in movimento).
4. **Pre-mortem delle idee ovvie**: prima di lanciare, scrivi nel brief pack una sezione
   **Territori esclusi** con le 5–8 idee che chiunque (anche un modello) produrrebbe per primo per
   questo cliente e questa categoria, e i concept già esplorati in sprint precedenti. È un vincolo
   uguale per tutti, non un'indicazione di stile. Verificato: senza questa sezione la stessa idea
   "di default" (per uno studio di fisioterapia, il goniometro) è tornata in due sprint su due.
5. **Leve di partenza**: assegna a ogni esploratore un ingresso diverso al significato, scelto
   tra quelli che il dossier rende forti per questo cliente. Esempi:
   - *il gesto o il meccanismo* del prodotto (cosa fa il corpo, la macchina, il servizio);
   - *il luogo e la materia* (pietra, acqua, legno, luce del luogo, superfici reali);
   - *la parola* (il nome, le lettere, il lessico del cliente, la tipografia come idea);
   - *le persone e le situazioni d'uso* (momenti reali, ritmi, oggetti che usano);
   - *il sistema o la regola* (un principio generativo da cui nascono tutte le forme);
   - *la tensione con la categoria* (la convenzione più forte, rovesciata).
   La leva indica da dove partire, non come deve apparire: nessuna indicazione di stile. Le leve
   stanno nel ticket di ciascuno; il brief pack resta identico.
6. **Ticket in parallelo**, uno per esploratore:
   `ticket.py new --from creative-director --to direction-a --type produzione --title "Direzione A — leva: <leva>" --request-file work/directions/brief-pack.md --inputs work/directions/brief-pack.md work/directions/apps.json work/context/dossier.md --medium vettoriale interfaccia --outputs work/directions/a/direction.md 'work/directions/a/src/*.vectorcraft' 'work/directions/a/src/*.figcraft' 'work/directions/a/apps/*.png' --accept 'direction.md=facts_check+direction_lint' '*.png=visual_review+optical_check' '*.vectorcraft=master_open' '*.figcraft=master_open' --after-gate strategy`. Il mezzo segue le applicazioni comuni: dichiara solo quelli usati.
   Lancia i tre agenti **nello stesso messaggio**, ognuno con il proprio ticket. Non dare a
   nessuno indicazioni di stile che gli altri non hanno.
7. **Verifica**, con `--record-by creative-director`:
   - `direction_board.py check`: tutte le applicazioni, dimensioni esatte, sezioni, citazioni;
   - `direction_board.py lint`: scheda completa, licenze, cliché tipografici giustificati;
   - `direction_board.py concepts`: concept, caratteri, colori, leva, linguaggio delle immagini;
   - `direction_board.py diversity`: somiglianza visiva grossolana delle applicazioni.
   Se due direzioni convergono, rimanda indietro la meno argomentata con una leva diversa e
   l'istruzione di cambiare concept, non dettagli. Registra l'esito in `decisions.md`.
8. **Tavole anonime**: `direction_board.py boards`. Le direzioni diventano X/Y/Z.

## Esploratore (direction-a, -b, -c)

- Leggi brief pack, dossier, mondo del cliente, `apps.json`. Nient'altro dello sprint.
- **Parti dalla tua leva** (nel ticket). Prima di tutto scrivi le **3 idee più ovvie** per questo
  brief: sono quelle a cui arriverebbero anche gli altri esploratori. Scartale, o dimostra con
  la leva perché la tua versione non è quella ovvia. Confronta con
  `.claude/design-agency/references/anti-patterns.md`: un carattere o una palette di default
  si giustifica nella scheda o si cambia.
- Una direzione è una posizione: **concept** (una frase), **composizione** (struttura, ritmo,
  scala, rapporto pieno/vuoto), **tipografia** (caratteri con licenza verificata, ruoli, scala),
  **colore** (OKLCH, ruoli, misure), **linguaggio delle immagini** (fotografia, illustrazione,
  materia, trattamento), **movimento** (una frase), **voce** (un testo d'esempio).
  Le quattro dimensioni principali (concept, composizione, tipografia, immagini) devono
  derivare dalla stessa idea.
- Usa il mondo del cliente: prodotto, materiali, linguaggio, documenti, foto, utenti,
  situazioni d'uso. Ogni scelta dichiara il fatto su cui si basa [F-…]; ciò che è ipotesi è
  marcato come tale.
- Applicazioni esportate da master in `src/`, ciascuno nel suo strumento (TOOLS.md): vettori in
  VectorCraft (`vectorcraft-cli run --commands`), interfacce e impaginati in FigCraft
  (`figcraft-cli run --in/--out`), immagini in PhotoCraft (`photocraft-cli run`), 3D in Blender.
  Sono CLI su file tuoi: nessun lock, si lavora in parallelo. Testi veri del cliente, dimensioni
  esatte, export con `master.py export`, rese con `render.py --sheet` e **guardate**. Correggi ciò che vedi.
- Controlli L1 obbligatori (parte del contratto del ticket), dalla radice del progetto:

  ```sh
  .claude/scripts/py .claude/scripts/master.py check work/directions/<x>/src/<master> --record-by direction-<x>
  .claude/scripts/py .claude/scripts/master.py export work/directions/<x>/src/<master> work/directions/<x>/apps/A1.png -- --scale 2
  .claude/scripts/py .claude/scripts/render.py work/directions/<x>/apps/A1.png --out work/directions/<x>/proofs
  # apri il render con Read e guardalo, poi:
  .claude/scripts/py .claude/scripts/evidence.py observe work/directions/<x>/apps/A1.png --by direction-<x> --seen "<cosa hai visto>"
  .claude/scripts/py .claude/skills/visual-qa/scripts/optical_check.py work/directions/<x>/apps/A1.png --out work/directions/<x>/proofs/A1_optical.png --record-by direction-<x>
  .claude/scripts/py .claude/skills/color-system/scripts/color.py contrast "#TESTO" "#FONDO"
  .claude/scripts/py .claude/skills/type-system/scripts/font_inspect.py work/fonts/<slug>/<file>.ttf --langs it,de
  python3 .claude/scripts/facts.py check work/directions/<x>/direction.md --record-by direction-<x>
  .claude/scripts/py .claude/skills/direction-sprint/scripts/direction_board.py lint --record-by direction-<x>
  ```

  Ripeti render, observe e optical_check per ogni applicazione. Gli script delle skill stanno
  in `.claude/skills/<skill>/scripts/`, quelli comuni in `.claude/scripts/`.
- Caratteri dalla libreria (`font_library.py search … --avoid-popular 100`, poi `fetch` e
  `specimen` sui testi del cliente), non da quelli installati sulla macchina.
- File temporanei solo dentro `work/directions/<x>/`, mai in `/tmp`.

## Dati dello studio sul numero di direzioni

| Sprint | Configurazione | Esito |
|---|---|---|
| 1 | 3 esploratori isolati, stesso brief | 3/3 stesso concept (goniometro), stessi caratteri e palette; isolamento verificato |
| 2 | + leve di partenza, tassa delle idee ovvie, libreria di caratteri | 3 concept diversi; A–B ancora con caratteri e palette condivisi (rilevato da `concepts`); il goniometro torna sulla leva "gesto" |

Conclusione operativa: tre direzioni valgono solo se `concepts` e `diversity` passano. Se due
convergono, non aggiungere esploratori: rilancia quello convergente con un'altra leva e con il
concept convergente tra i territori esclusi. Aggiorna questa tabella dopo ogni sprint reale.

## Scelta (creative-director, con il critico)

1. Il `critic` giudica le tavole **anonime** con la rubrica di `critique` e i criteri del brief
   pack, prima di leggere i `direction.md`.
2. Il creative-director legge giudizio, tavole e `direction.md`, poi `direction_board.py reveal`.
3. Scrive `work/directions/selection.md` dal modello: per ogni direzione punti di forza,
   debolezze, rischio, aderenza ai criteri con prove; la scelta e il perché.
4. **Niente fusione automatica del "meglio di tutte"**: si sceglie **una** direzione, che resta
   intera. Un elemento di un'altra direzione si adotta solo se è compatibile con il concept
   scelto, e la motivazione va scritta. Ciò che si perde rinunciando alle altre si dichiara.
5. Presenta al cliente le direzioni (tavole confrontabili) con la raccomandazione
   (`client-review`, gate `direction`). Il cliente può scegliere un'altra direzione: si registra.
6. Dopo l'approvazione scrivi la **carta della direzione** `work/direction/charter.md` dal
   modello: principi, invarianti, cosa la direzione non fa mai. Ogni lavoro successivo si
   confronta con la carta; il critico segnala le derive.
