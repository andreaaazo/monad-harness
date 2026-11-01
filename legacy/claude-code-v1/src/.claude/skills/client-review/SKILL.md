---
name: client-review
description: Presenta il lavoro al cliente a ogni gate e gestisce il ciclo di feedback — presentazione con lavoro renderizzato, criteri, alternative e raccomandazione; domande chiare; registrazione testuale del feedback; traduzione in modifiche concrete; chiarimento dei punti ambigui; approvazione esplicita legata ai file. Da usare quando il router deve mostrare qualcosa al cliente, ricevere un commento o chiedere una decisione.
---

# Revisione con il cliente

Protocollo completo: `.claude/design-agency/CLIENT.md`.

## Preparare una presentazione

1. **Cosa si decide**: una frase ("scegliere il territorio su cui disegnare il logo").
2. **Promemoria**: obiettivo e criteri del brief in 3 righe; risposte del cliente che hanno
   guidato il lavoro.
3. **Il lavoro**: immagini reali (render, fogli di prova, mockup onesti, screenshot) con il
   percorso di ogni file. Per ogni opzione: idea in una frase, come risponde ai criteri,
   compromessi. Opzioni mostrate alle stesse dimensioni e sulle stesse applicazioni.
4. **Raccomandazione** dello studio, con il motivo.
5. **Assunzioni** fatte dallo studio da quando il cliente ha parlato l'ultima volta.
6. **Domande** finali, numerate, con opzioni.

Il lavoro presentato deve aver superato il QA del suo livello: niente bozze spacciate per
definitive. Se è una bozza, dillo.

Registra: `python3 .claude/scripts/client.py present --round <N> --title "<cosa>" --files <file…> --questions <Q-…>`.

## Durante il feedback

- Copia le parole del cliente così come sono: `client.py feedback P-… --text "…"`.
- Traduci in `work/feedback/round-<N>.md` (modello `.claude/design-agency/templates/feedback.md`),
  includendo **ciò che funziona e va preservato**: le iterazioni che correggono solo difetti
  tendono a rendere ogni versione più convenzionale.
- Feedback vago → traduzione con varianti:

| Il cliente dice | Possibili significati da verificare |
|---|---|
| "più moderno" | meno ornamento? carattere più recente? palette più satura? più spazio? movimento? |
| "più premium" | meno elementi, più spazio, materiali/finiture, tipografia più raffinata, colore più profondo |
| "non mi convince" | quale parte? idea, forma, colore, tono? rispetto a cosa? |
| "più visibile" | dimensione, contrasto, posizione, colore, distanza di lettura |

  Chiedi quale significato intende, idealmente con 2–3 varianti rapide affiancate.
- Feedback in conflitto con requisiti o strategia → mostra la prova (misura, criterio,
  rischio), proponi un'alternativa che rispetti l'intenzione, chiedi la decisione.

## Chiudere un gate

Solo con parole esplicite che scelgono o approvano:

```sh
python3 .claude/scripts/client.py approve --gate <gate> --files <file approvati> --text "<parole del cliente>"
python3 .claude/scripts/client.py gate <gate>
```

Poi `.agency/decisions.md` (scelta, motivo, alternative scartate) e ticket della fase
successiva con `--after-gate <gate>`.

## Consegna finale

La presentazione finale riepiloga: cosa è stato consegnato (file reali), esito QA, decisioni
prese insieme, limiti, cosa resta da fare (stampa, sviluppo, registrazione del marchio).
Chiedi conferma esplicita che il lavoro è accettato e registra il gate `final`.
