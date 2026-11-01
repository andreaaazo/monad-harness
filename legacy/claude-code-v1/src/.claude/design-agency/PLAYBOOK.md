# Processo dello studio

Ciclo di vita di un progetto d'identità. Per gli altri servizi e per chi fa cosa:
[SERVICES](SERVICES.md) (catalogo e flussi), [ORG](ORG.md) (reparti), [ROUTING](ROUTING.md)
(ticket e deleghe), [QA](QA.md) (livelli e prove).

Alternanza di divergenza e convergenza ispirata al Double Diamond [D1 in
[SOURCES](SOURCES.md)]; fasi, ruoli e gate sono scelte dello studio. Per un incarico
piccolo si usa solo la fase pertinente.

## Struttura di un lavoro

Nella radice del progetto cliente (si crea solo ciò che ha contenuto):

```text
.agency/STATE.md, .agency/decisions.md     # stato e decisioni (templates/state.md, decisions.md)
work/brief.md  strategy.md  direction.md  construction.md  spec.md
work/tokens.json  work/source/  work/exports/  work/proofs/  work/review.md  work/delivery.md
```

## Fasi

| # | Fase | Skill | Autore | Gate di uscita |
|---|---|---|---|---|
| 1 | Brief | [templates/brief.md](templates/brief.md) | coordinatore | requisiti verificabili, assunzioni scritte |
| 2 | Strategia | `brand-strategy` | `art-director` | frase di differenza, convenzioni di categoria, criteri |
| 3 | Concept | `concept-divergence` | `art-director` | 2–3 territori per idea; scelta registrata in decisions |
| 4 | Logo | `logo-design` | `identity-designer` | test superati e osservati; critica senza maggiori |
| 5 | Sistema | `color-system`, `type-system`, `design-tokens` | `identity-designer` | coppie misurate, specimen visto, token validi |
| 6 | Motion | `motion-identity` | `motion-designer` | chiusura sul master, probe OK, variante ridotta |
| 7 | Guidelines e applicazioni | `brand-guidelines` | `identity-designer` | applicazioni reali, valori da un'unica fonte |
| 8 | Critica | `critique` | `critic` | READY |
| 9 | Consegna | [templates/delivery.md](templates/delivery.md) | coordinatore | solo file esistenti, limiti dichiarati |

Dopo le fasi 3 e 4, se l'utente non ha delegato la scelta, presenta e attendi
l'approvazione. Una direzione cambiata dopo la fase 5 invalida le prove che ne dipendono:
consulta la mappa delle dipendenze in `spec.md`.

## Regole di produzione

- Ogni autore riceve file e documento assegnati; un solo autore per server Craft.
- Prima di una chiamata mutante in Craft: documento giusto, schema live, ID interessati
  ([CRAFT.md](CRAFT.md)). Salva lo stesso master a milestone.
- VectorCraft → EffectCraft: passa file salvati, dimensioni, bounding box, colori, nomi
  dei livelli, pivot e intenzioni di movimento; verifica cosa sopravvive all'import.
- Aggiorna `.agency/STATE.md` a ogni gate e registra le decisioni.

## Correzioni

Il coordinatore rimanda all'autore i difetti; il critico ricontrolla le aree cambiate e
le regressioni plausibili. Se due iterazioni non migliorano il risultato, diagnostica il
limite e cambia approccio (idea, costruzione o strumento) invece di ripetere.
Non abbassare un requisito per ottenere un `PASS`.
