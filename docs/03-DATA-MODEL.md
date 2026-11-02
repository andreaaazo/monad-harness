# Modello dati

Ogni dato ha un solo proprietario.

| Dato | Dove | Proprietario | Se si perde |
|---|---|---|---|
| Ticket ed eventi | `.data/ledger.sqlite` | `agency.ledger` | Perdita grave: va nei backup |
| Prove, fatti, cliente, consumi | `.data/ledger.sqlite` | i rispettivi moduli | Perdita grave |
| Copie prima delle migrazioni | `.data/backups/` | `agency.ledger.schema` | Si perde il ritorno indietro |
| Checkpoint del grafo | `.data/checkpoints.sqlite` | LangGraph | Ricostruibile dal registro |
| Artefatti, da M1.6 | `.data/artifacts/<sha256>` | `agency.tools` | Perdita grave |
| Master di lavoro | `projects/<slug>/work/` | l'agente del ticket | Da M1.6 recuperabile dagli artefatti |
| Trascrizioni delle istanze | `.data/runs/<slug>/` | `agency.agents` | Perdita grave: servono a ripresa e replay |
| Indice dei comandi Craft | `.data/craft-index/` | `agency.tools.craft` | Rigenerabile |
| Indice visivo | `.data/lancedb/` | `agency.context` | Rigenerabile |
| Proiezioni del cruscotto | `.data/insights.sqlite` | `agency.insights` | Rigenerabile |
| Tracce | `.data/traces.jsonl`, Langfuse da M4 | telemetria | Accettabile |
| Utenti e organizzazioni, da M6 | database di Django | `agency.entrypoints.server` | Perdita grave |

`.data/` e `projects/` non sono versionati.

## Registro: solo in aggiunta

`events` non si può modificare: lo impediscono i trigger SQLite, e la catena di hash rileva chi li
aggira. Gli stessi trigger proteggono `usage`, `evidence`, `renders`, `derivations`, `gates` e `runs`.
`tickets` è una vista di comodo dello stato; la verità è la storia degli eventi. `agency verify`
ricontrolla la catena.

### Tabelle

| Tabella | Traguardo | Contenuto |
|---|---|---|
| `projects` | M1.5 | Budget, modello ed effort scelti dal cliente |
| `tickets` | M0 | Contratto, stato, verdetto |
| `events` | M0 | Chi ha fatto cosa, quando, con quale hash precedente |
| `evidence` | M1 | File, hash, controllo, esito, firma, prova, input confrontati |
| `artifacts` | M1.6 | Hash, percorso, tipo, ticket di origine |
| `renders` | M1 | Prova di render di una versione precisa di un file |
| `derivations` | M1 | Master → export, con entrambi gli hash |
| `usage` | M1 | Chiamata, ticket, ruolo, modello, token per tipo, costo. Da M1.6 anche esecuzione, fase, effort, durata, TTFT, ragionamento |
| `operations` | M1 | `operation_id` degli effetti, per la ripresa senza duplicati |
| `concepts` | M1.5 | Scheda dell'idea, leva, schizzo, lettera anonima, esito della selezione |
| `gates` | M1.5 | Decisione del cliente: parole testuali, scelta, hash dei file |
| `runs` | M1.6 | Ogni `run`, `resume` e `decide` con la sua impronta: prompt, registry, codice, lock, Python, CLI, modello, effort e impostazioni (ADR-0026) |
| `judgments` | M1.6 | Punteggio alla cieca, chi l'ha dato, sha256 del file giudicato |
| `client_log` | M2 | Domande, risposte, presentazioni, feedback, approvazioni |
| `facts` | M2 | Fatto, provenienza, fonte |

## Schema e migrazioni

Lo schema viene prima del codice (ADR-0022). I modelli Pydantic sono l'unica fonte: da lì si generano l'OpenAPI in
`schemas/openapi.json` e i tipi TypeScript, e un test fallisce se divergono. L'API espone modelli di lettura propri, mai tabelle.

Lo schema nasce dalle migrazioni in `src/agency/ledger/migrations/`, e un test verifica che coincida con i modelli. Ogni modifica è
una migrazione Alembic, provata su una copia del registro vero: dopo deve passare `agency verify`. Un registro esistente non si
aggiorna mai aprendolo: si esegue `agency migrate`, che fa una copia e lavora in una sola transazione (ADR-0025). Le righe storiche
non si riscrivono, e le colonne nuove restano vuote su quelle vecchie. I dati delle chiamate vecchie arrivano nella proiezione di
`insights`, collegando `usage` alle tracce con `request_id`.

Django non possiede il registro (ADR-0020). Quando nasceranno utenti e organizzazioni avrà un database proprio, con le sue
migrazioni. `checkpoints.sqlite` lo gestisce LangGraph.

## Ticket

Contratto in `agency.contracts.ticket`. Regole principali:

- `status`: `open`, `delivered`, `accepted`, `rework`, `blocked`, `cancelled`. Le transizioni sono solo
  quelle di `TRANSITIONS`.
- `verdict`: `READY`, `REVISE`, `NOT_VERIFIED`, solo per qa e revisione.
- Una produzione dichiara il mezzo; `nessuno` richiede il motivo.
- Ogni output ha un controllo o un'esenzione motivata. Le cartelle non sono output.
- L'attore arriva dall'harness: non è un campo compilato dall'agente.

## Master e derivazioni

| Mezzo | Master | Apertura verificata con |
|---|---|---|
| Vettoriale | `.vectorcraft` | `vectorcraft-cli info` |
| Motion | `.ecproj` | `effectcraft-cli info` |
| Immagine | `.pcraft` | `photocraft-cli info` |
| Interfaccia | `.figcraft` | `figcraft-cli info` |
| 3D | `.blend` | intestazione del file, poi bpy |

Un export è valido solo se `derivations` lega la sua versione a quella attuale del master.

## Modello di scena (M3)

Struttura comune estratta da ogni master, per dare agli agenti la forma del documento senza immagini:

```json
{
  "master": "work/source/segno.vectorcraft",
  "sha256": "…",
  "kind": "vector",
  "canvases": [{"id": "1", "name": "Tavola 1", "size": [1000, 1000]}],
  "nodes": [{"id": "12", "type": "path", "name": "segno", "bbox": [0, 0, 100, 100], "style": {}}],
  "fonts": [],
  "warnings": []
}
```

Lo schema definitivo si fissa in M3, dopo aver visto cosa espone davvero ogni `info`.
