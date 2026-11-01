# STATE — <progetto>

<!-- Massimo 60 righe. Fonte autorevole per riprendere il lavoro. Aggiornare a ogni milestone. -->

- project_id: <slug-stabile>   schema: 1   revisione: <n>   aggiornato: <AAAA-MM-GG>
- Fase: strategia | concept | logo | sistema | motion | guidelines | critica | consegna
- Obiettivo corrente: <una frase>

## Ticket e server
- Ticket aperti: `python3 .claude/scripts/ticket.py list --open` — principali: <T-…>
- Budget: `.claude/scripts/py .claude/scripts/budget.py status`
- Lock Craft: `python3 .claude/scripts/craft_lock.py status`
- Cliente: `python3 .claude/scripts/client.py status` — in attesa di: <domande / feedback / approvazione di gate>
- Gate previsti: <understanding, brief, strategy, direction, design, prototype, final> — approvati: <…>

## Riferimenti approvati
- Brief: `work/brief.md` (v<n>)
- Strategia / direzione: `work/strategy.md`, `work/direction.md` — approvate da <utente|studio> il <data>
- Decisioni: `.agency/decisions.md`

## Master
| File | Revisione/stato | Salvato |
|---|---|---|
| `work/source/<file>` | <cosa contiene> | sì/no |

<!-- Vuota con lavoro visivo in corso = allarme: `master.py check <file>` su ogni master. -->

## Ultimo passo completato e verificato
- <cosa, con prova>

## In corso / esito incerto
- <operazione interrotta o timeout: verificare il file prima di ripetere>

## Difetti e domande aperte
- <ID, severità, dove>

## Prossima azione
- <azione concreta> — completata quando <criterio>

## File minimi da leggere per riprendere
- <percorsi>
