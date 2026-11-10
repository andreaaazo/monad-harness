# Modello dati

Ogni dato ha un solo proprietario.

| Dato | Dove | Proprietario | Se si perde |
|---|---|---|---|
| Ticket ed eventi | `.data/ledger.sqlite` | `agency.ledger` | Perdita grave: va nei backup |
| Prove, fatti, cliente, consumi | `.data/ledger.sqlite` | i rispettivi moduli | Perdita grave |
| Copie prima delle migrazioni | `.data/backups/` | `agency.ledger.schema` | Si perde il ritorno indietro |
| Copie anonime e tavola di un confronto | `.data/blind/<confronto>/` | `agency.evaluation` | Nulla: si cancellano alla fine del giudizio |
| Checkpoint del grafo | `.data/checkpoints.sqlite` | LangGraph | Ricostruibile dal registro |
| Artefatti, da M1.6 | `.data/artifacts/<ab>/<sha256>` | `agency.artifacts` | Perdita grave |
| Master di lavoro | `projects/<slug>/work/` | l'agente del ticket | Da M1.6 recuperabile dagli artefatti |
| Trascrizioni delle istanze | `.data/runs/<slug>/` | `agency.agents` | Perdita grave: servono a ripresa e replay |
| Cassette delle esecuzioni registrate con `--record` | `.data/cassettes/<slug>/<esecuzione>.jsonl`, una riga per ogni risposta del modello (ADR-0048) | `agency.gateway` | Quell'esecuzione non si ripete più nei test |
| Ingressi delle sandbox e registro della ripresa | `.data/ops/<slug>/<istanza>/`; gli ingressi in `in/`, montata in sola lettura in `/ops` (ADR-0044) | `agency.tools` | Un `craft_run` interrotto rifà i passi, anche se il master li aveva già ricevuti |
| Indice dei comandi Craft | `.data/craft-index/` | `agency.tools.craft` | Rigenerabile |
| Indice visivo | `.data/lancedb/` | `agency.context` | Rigenerabile |
| Proiezioni del cruscotto | `.data/insights.sqlite`; in Docker in memoria (ADR-0040) | `agency.insights` | Rigenerabile |
| Tracce | `.data/traces.jsonl`, Langfuse da M4 | telemetria | Accettabile |
| Utenti e organizzazioni, da M6 | database di Django | `agency.entrypoints.server` | Perdita grave |

`.data/` e `projects/` non sono versionati.

Tutti e due stanno nella radice del checkout da cui gira il codice, la stessa di `prompts/` e `registry/`, da qualunque
cartella parta il comando: ogni worktree ha i suoi. `AGENCY_DATA_DIR` e `AGENCY_PROJECTS_DIR` li spostano, ma solo con
un percorso assoluto; uno relativo ferma il motore e il server con la stessa riga. Il motore e il server risolvono la
radice in un solo punto, `data_root()` di `agency.contracts.layout` (ADR-0045).

## Registro: solo in aggiunta

`events` non si può modificare: lo impediscono i trigger SQLite, e la catena di hash rileva chi li
aggira. Gli stessi trigger proteggono `usage`, `evidence`, `renders`, `derivations`, `gates`, `runs`, `judgments`,
`artifacts` e, dalla revisione 0008, `operations`.
`tickets` tiene lo stato attuale dei ticket; per stato, verdetto e consegna è una proiezione della storia degli eventi,
che è la verità. Dalla revisione 0006 ogni evento nuovo è di
versione 2 e lega nella catena lo stato del suo ticket dopo l'evento: stato, verdetto e hash consegnati, in
`payload_json`. Gli eventi precedenti restano di versione 1 e si verificano con la loro formula, e la migrazione ha
aggiunto un evento `baseline` per ticket con lo stato di quel momento (ADR-0047). Dalla revisione 0007 l'evento di un
ticket lega anche lo sha256 del suo contratto (`spec_json`) e dei suoi hash d'apertura (`inputs_json`), e ogni
scrittura di un'idea (`concepts`) o di un gate (`gates`) aggiunge un evento con ticket `-` che lega la riga intera;
l'evento di una prova (`evidence`) lega anche la prova. La migrazione 0007 ha legato così le righe di quel momento
(ADR-0049). Dalla revisione 0008 anche ogni chiamata pagata (`usage`) e ogni scrittura di un progetto (`projects`)
aggiungono un evento che lega la riga intera: la chiamata sul suo ticket, con lo stato del ticket, il progetto con
ticket `-`. La migrazione 0008 ha legato così le righe di quel momento, e un secondo record di ripresa con lo stesso
id non riscrive il primo (ADR-0050). `agency verify` ricontrolla la catena e confronta ogni ticket con lo stato e il
contratto legati dal suo ultimo evento, e ogni idea, gate, prova, chiamata pagata e progetto con l'ultimo evento che
la lega: una differenza, o un ticket o una riga legati che mancano, è un registro alterato.

### Tabelle

| Tabella | Traguardo | Contenuto |
|---|---|---|
| `projects` | M1.5 | Budget, modello ed effort scelti dal cliente |
| `tickets` | M0 | Contratto, stato, verdetto, hash consegnati: per stato, verdetto, consegna e contratto è una proiezione degli eventi (ADR-0047, ADR-0049) |
| `events` | M0 | Chi ha fatto cosa, quando, con quale hash precedente. Dalla versione 2 anche lo stato del ticket dopo l'evento (ADR-0047), lo sha256 del suo contratto e l'idea, il gate o la prova scritti (ADR-0049) |
| `evidence` | M1 | File, hash, controllo, esito, firma, prova, input confrontati |
| `artifacts` | M1.6 | Versione conservata: hash, progetto, percorso, ticket, esecuzione, motivo, tipo MIME, dimensione (ADR-0028) |
| `renders` | M1 | Prova di render di una versione precisa di un file |
| `derivations` | M1 | Master → export, con entrambi gli hash |
| `usage` | M1 | Chiamata, ticket, ruolo, modello, token per tipo, costo. Da M1.6 anche esecuzione, fase, effort, durata, TTFT, ragionamento. Una riga per chiamata: le colonne dei token sono l'uso del tentativo che ha dato la risposta (il contesto che la corsa ha usato davvero), mentre `cost_usd` copre tutti i tentativi |
| `operations` | M1 | `operation_id` degli effetti, per la ripresa senza duplicati |
| `concepts` | M1.5 | Scheda dell'idea, leva, schizzo, lettera anonima, esito della selezione |
| `gates` | M1.5 | Decisione del cliente: parole testuali, scelta, hash dei file |
| `runs` | M1.6 | Ogni `run`, `resume` e `decide` con la sua impronta: prompt, registry, codice, lock, Python, CLI, modello, effort e impostazioni (ADR-0026) |
| `judgments` | M1.6 | Ogni file di un confronto alla cieca: livello, test di sostituzione, migliore, perché, chi giudica, sha256 (ADR-0027). Il migliore sta tra i livelli più alti (ADR-0041) |
| `client_log` | M2 | Domande, risposte, presentazioni, feedback, approvazioni |
| `facts` | M2 | Fatto, provenienza, fonte |

## Schema e migrazioni

Lo schema viene prima del codice (ADR-0022). I modelli Pydantic sono l'unica fonte: da lì si generano l'OpenAPI in
`schemas/openapi.json` e i tipi TypeScript, e un test fallisce se divergono. L'API espone modelli di lettura propri, mai tabelle.

Lo schema nasce dalle migrazioni in `src/agency/ledger/migrations/`, e un test verifica che coincida con i modelli. Ogni modifica è
una migrazione Alembic, provata su una copia del registro vero: dopo deve passare `agency verify`. Un registro esistente non si
aggiorna mai aprendolo: si esegue `agency migrate`, che fa una copia e lavora in una sola transazione (ADR-0025). Le righe storiche
non si riscrivono, e le colonne nuove restano vuote su quelle vecchie. I dati delle chiamate vecchie arrivano nella proiezione di
`insights`, collegando `usage` alle tracce con `request_id`: `agency insights` la rigenera, e ogni chiamata dice da dove vengono le
sue misure e se la sua fase è registrata o ricavata (ADR-0029). La proiezione contiene anche progetti, ticket, gate, idee,
giudizi, la storia dei ticket con il motivo dei soli passi indietro (ADR-0035), le prove dei controlli e, dalle trascrizioni in
`.data/runs/`, le chiamate agli strumenti con i loro rifiuti (ADR-0036), e le esecuzioni con la loro impronta (ADR-0037): è tutto
ciò che legge `agency report`, che passa da lì come il cruscotto (ADR-0030). Le trascrizioni intere non entrano nella
proiezione: la vista Replay legge quella di un'istanza quando la si apre, e ogni risposta del modello porta il suo `request_id`
(ADR-0038).

Django non possiede il registro (ADR-0020). Quando nasceranno utenti e organizzazioni avrà un database proprio, con le sue
migrazioni. `checkpoints.sqlite` lo gestisce LangGraph.

## Vocabolario

Gli identificatori sono in inglese; i valori salvati e quelli che viaggiano sono parole italiane, o le sigle di
sempre. Stanno nelle righe del registro, nelle trascrizioni, nei record di ripresa e nella proiezione, arrivano al
modello negli schemi degli strumenti e all'interfaccia come enum di `schemas/openapi.json`. Sembrano da tradurre e
non lo sono: un valore salvato cambia solo con una migrazione, mai con una rinomina, e `tests/test_vocabulary.py`
li tiene fermi (CMT-008, Task 1.17).

| Tipo | Valori |
|---|---|
| `TicketType` | `produzione`, `consulenza`, `revisione`, `ricerca`, `qa`, `consegna`, `disaccordo`, `idea`, `schizzo`, `proposta` |
| `Medium` | `vettoriale`, `motion`, `immagine`, `interfaccia`, `3d`, `nessuno` |
| `Verdict` | `READY`, `REVISE`, `NOT_VERIFIED` |
| `Status` | `open`, `delivered`, `accepted`, `rework`, `blocked`, `cancelled` |
| `Action` | `deliver`, `accept`, `rework`, `block`, `resume`, `cancel` |
| `Level` | `ordinario`, `buono`, `eccellente` |
| `RunCommand` | `run`, `resume`, `decide` |
| `OutcomeState` | `delivered`, `handed_off`, `selected`, `no_concept`, `presented`, `concept_rejected`, `blocked` |
| `Compared` (API) | `entrambe`, `manca prima`, `manca dopo`, `nessuna` |
| `Alignment` (API) | `per richiesta`, `per ordine`, `nessuna` |
| `Lifecycle` (API) | `open`, `deliver`, `accept`, `rework`, `block`, `resume`, `cancel` |

Oltre alle azioni del ciclo di vita, il registro scrive in `events.action` anche `evidence`, `baseline` (le
migrazioni 0006-0008), `concept`, `gate`, `usage` e `project` (ADR-0047, ADR-0049, ADR-0050).

## Ticket

Contratto in `agency.contracts.ticket`. Regole principali:

- `status`: `open`, `delivered`, `accepted`, `rework`, `blocked`, `cancelled`. Le transizioni sono solo
  quelle di `TRANSITIONS`.
- `verdict`: `READY`, `REVISE`, `NOT_VERIFIED`, solo per qa e revisione.
- Una produzione dichiara il mezzo; `nessuno` richiede il motivo.
- Ogni output ha un controllo o un'esenzione motivata. Le cartelle non sono output.
- L'attore arriva dall'harness: non è un campo compilato dall'agente.

## Gate ed esiti

Contratti in `agency.contracts.gate` e `agency.contracts.outcome` (ADR-0021: niente `dict` come contratto).

- Un gate è `ConceptGate` (PDF, proposte, raccomandazione) oppure `FinalGate` (consegne del ticket principale). `Decision` è la
  risposta del cliente. Nel checkpoint di LangGraph restano dict semplici, con il campo `gate` di sempre: il tipo vive nel codice,
  e il formato salvato non dipende dal serializzatore.
- L'esito di un'istanza è `Outcome`: uno dei sette `OutcomeState` e una nota. Per selezione e presentazione la nota è il JSON degli
  argomenti dello strumento, che il grafo rilegge con lo stesso modello. Nelle trascrizioni resta `{"state", "note"}`.

## Master e derivazioni

| Mezzo | Master | Apertura verificata con |
|---|---|---|
| Vettoriale | `.vectorcraft` | `vectorcraft-cli info` |
| Motion | `.ecproj` | `effectcraft-cli info` |
| Immagine | `.pcraft` | `photocraft-cli info` |
| Interfaccia | `.figcraft` | `figcraft-cli info` |
| 3D | `.blend` | intestazione del file, poi bpy |

Un export è valido solo se `derivations` lega la sua versione a quella attuale del master.

Ogni versione consegnata, mostrata al cliente o giudicata resta in `.data/artifacts/` (ADR-0028). `agency artifacts <progetto>`
le elenca, `agency restore <hash> <file>` ne riporta una in un file nuovo, e `agency verify` controlla che ci siano tutte.

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
