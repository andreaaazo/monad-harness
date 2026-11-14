# Costi

Prezzi dal riferimento API aggiornato al 2026-10-06. Vanno ricontrollati prima di ogni stima importante.

## Modelli

| Modello | Input $/M | Output $/M | Lettura cache $/M | Contesto | Uso |
|---|---|---|---|---|---|
| `claude-opus-5-5` | 4,00 | 20,00 | 0,20 | 1M | Default di tutti i ruoli |
| `claude-sonnet-5-5` | 2,00 | 10,00 | 0,20 | 1M | `legal-reviewer`, `researcher`, `qa-inspector` |

Scrittura in cache: ~1,25× l'input a 5 minuti, 2× a 1 ora. I modelli più economici si valutano solo in
M5, con le valutazioni e con una decisione esplicita.

`effort` per ruolo in `registry/roles.json` è un valore di partenza: `high` per direttori, critica e autori
del segno, `medium` per gli altri. Opus 5.5 ha default `medium`, quindi va sempre impostato.

Prima di una cascata di modelli si misura l'alternativa più semplice: lo stesso modello a `effort` più
basso. Spesso regge, e un solo modello condivide la stessa cache.

## Effort per fase (M1.5)

| Fase | Effort | Perché |
|---|---|---|
| Esplorazione | `high` | Si pensa disegnando: è qui che si decide il valore del lavoro |
| Proposta | `high` | Il segno deve reggere davanti al cliente |
| Scelta, critica, rifinitura | `high` | Giudizio e costruzione |

`max` non si usa: consuma troppo. `high` è il massimo. `medium` si prova con `AGENCY_EXPLORER_EFFORT` e
`AGENCY_PROPOSAL_EFFORT`, e si tiene solo se la qualità regge. Si resta su Opus 5.5: cambiare modello richiede una
decisione esplicita.

## Modello e budget li sceglie il cliente

Sono gli unici vincoli al lavoro (ADR-0015). Si scelgono per progetto e restano salvati:

```sh
uv run agency run progetto brief.md --budget 30 --model claude-opus-5-5 --effort high
uv run agency budget progetto 40
```

Senza `--model` e `--effort` valgono le impostazioni per ruolo di `registry/roles.json`. `--budget` invece è obbligatorio,
e non ha un default né nelle impostazioni né nell'ambiente (ADR-0043). Il budget ferma il lavoro prima di superarlo, e il
lavoro riprende quando il cliente lo alza. Il tetto si può alzare anche mentre il progetto lavora, e vale dalla chiamata
successiva.

Gli agenti non ricevono nessuna informazione su budget e spesa: nessun avviso e nessuna quota (ADR-0016). Il loro
obiettivo è la qualità più alta. Il costo lo governa il cliente, non la fretta dei designer.

Su `merlo2` idee e schizzi separati sono costati 0,39 $ a direzione, senza qualità. Su `merlo3` l'esploratore che
disegna è costato da 1,18 $ a 2,48 $ a direzione, 8,59 $ in tutto, con un salto netto di qualità.

## `merlo3`: il costo del flusso definitivo

Brief E1, 2026-11-01: 13,29 $ in 365 chiamate e 30 minuti fino al gate `concept`, con una sola proposta. Il 65% è
esplorazione. Da questi dati, sempre a `high`, una presentazione costerebbe circa 17,5 $ con 2 proposte e 21,7 $ con 3.
È una stima, non una misura.

Fino al gate `final`: 34,38 $ in 811 chiamate. Dopo il gate `concept` sono 21,09 $ in 446 chiamate, di cui 3,10 $ di revisioni
bloccate (ADR-0018). L'obiettivo di 22 $ per l'intero lavoro non è raggiunto.

| Tipo di lavoro | Costo |
|---|---|
| Produzione | 15,69 $ |
| Schizzi | 8,59 $ |
| Proposta | 4,22 $ |
| Revisione | 3,37 $ |
| Consegna | 1,72 $ |
| QA | 0,79 $ |

## `merlo`: il primo dato reale

Brief E1, 2026-10-31: 15,91 $ in 363 chiamate, senza arrivare al gate.

| Istanza | Costo | Esito |
|---|---|---|
| Designer, giro 1 | 4,14 $ | Concetto bocciato |
| Designer, giro 2 | 2,44 $ | Trovato il concetto |
| Designer, giri 3 e 4 | 6,61 $ | Rifinitura di un concetto ancora debole, interrotta dal tetto |
| Critico, QA, direttore | 2,71 $ | Revisioni e decisioni |

Cache al 97%. Il 98% del tempo è generazione del modello; strumenti 2%, nostro codice meno dello 0,2%. Il tempo
si riduce con meno passi e meno ragionamento dove non serve, non ottimizzando il codice.

## Dove sono finiti i soldi di Neima

| Voce | Quota | Risposta dell'harness |
|---|---|---|
| Scritture in cache | 44% | Agenti monouso e delega non bloccante |
| Letture in cache | 40% | Contesto più piccolo: paghi meno a ogni chiamata |
| Output | 16% | `effort` per ruolo |

Il 71% delle scritture è arrivato dopo pause oltre i 5 minuti, ~35 $. Bash ha messo in contesto ~1,3M
caratteri, le immagini 792k: risultati brevi degli strumenti e pacchetti compilati sono la leva maggiore.

## Regole di cache

- L'ordine è strumenti → system → messaggi. Ogni byte cambiato invalida ciò che segue.
- Set di strumenti fisso per istanza, sistema senza timestamp, JSON ordinato.
- Cambiare modello a metà invalida la cache: i modelli si cambiano solo tra istanze.
- TTL 5 minuti per i loop normali. TTL 1 ora solo quando una pausa tra 5 e 60 minuti è prevedibile, ad
  esempio un render Blender lungo.
- Una lettura rinnova il timer. Il tempo si misura dall'inizio della richiesta.
- Un breakpoint esplicito sul prefisso statico + caching automatico sulla coda.
- `usage.cache_read_input_tokens` a zero tra richieste simili segnala un'invalidazione silenziosa.

## Altri strumenti di risparmio

| Leva | Risparmio | Quando |
|---|---|---|
| Batch API | 50% | Valutazioni e lavori non interattivi |
| Context editing | Toglie risultati vecchi | Rete di sicurezza |
| Programmatic tool calling | Risultati intermedi fuori dal contesto | Da valutare: gira nel container Anthropic, quindi non con i file del cliente |

## Sviluppo

Le prove dal vivo si pagano. I test usano risposte registrate; ogni prova dal vivo dichiara un tetto
prima di partire e riporta il costo. I tetti per traguardo sono in `02-ROADMAP.md`.

Spesa finora: M1 15,91 $ su 40 $, M1.5 38,83 $ su 40 $, M1.6 0 $ su 30 $. Il lavoro di M1.7 e M1.8 non spende nulla
(ADR-0056). M1.9 spende per `merlo4` (30 $) e per la prova sulla CLI, che ha un tetto proprio.
