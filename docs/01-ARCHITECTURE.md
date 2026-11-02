# Architettura

## Principio

**Il modello decide cosa fare; il sistema decide cosa è possibile.** Tutto ciò che è una regola sta nel
grafo, nei contratti o nel gateway. Il prompt tiene solo il mestiere: come si pensa e si giudica.

```text
 Cliente ─ agency CLI (poi interfaccia web)
              │
 ┌────────────▼─────────────────────────────────────────────┐
 │ PROCESSO   LangGraph: fasi, gate, interrupt, checkpoint   │
 └────────────┬─────────────────────────────────────────────┘
              │ ticket (contratto Pydantic)
 ┌────────────▼─────────────────────────────────────────────┐
 │ LAVORO     agente monouso: pacchetto di contesto + loop   │
 └───┬──────────────────────┬───────────────────────────────┘
     │ chiamate al modello  │ chiamate agli strumenti
 ┌───▼───────────┐   ┌──────▼──────────────────────────────┐
 │ GATEWAY       │   │ STRUMENTI  tipizzati, in sandbox     │
 │ budget, cache,│   │ Craft headless · Blender · QA ·      │
 │ fallback,     │   │ compute · render · ComfyUI (M4)      │
 │ usage         │   └──────┬──────────────────────────────┘
 └───┬───────────┘          │
     │ API Anthropic        │ artefatti per hash, master
 ┌───▼──────────────────────▼──────────────────────────────┐
 │ MEMORIA  registro SQLite · artefatti · checkpoint ·      │
 │          scena · LanceDB · tracce OpenTelemetry          │
 └──────────────────────────────────────────────────────────┘
```

## Processo: LangGraph

Un grafo per progetto. I nodi sono le fasi di `HANDOFFS` (scoperta, mondo, strategia, contratto
creativo, sprint, confronto, selezione, carta, sistema, applicazioni, robustezza, digitale,
produzione). Proporzione S/M/L: lo stesso grafo con rami diversi, scelti alla classificazione.

- **Gate del cliente**: `interrupt()`. Il processo si ferma e sopravvive a un riavvio. La ripresa porta
  le parole del cliente e gli hash dei file approvati.
- **Parallelo**: `Send` per sprint e ticket indipendenti.
- **Attenzione**: alla ripresa un nodo si riesegue da capo. Ogni effetto ha quindi un
  `operation_id` e controlla il registro prima di agire (ADR-0002).
- Il grafo tiene il **dove siamo**; il registro tiene il **cosa è successo**. Il registro è la verità:
  il checkpoint si può ricostruire, il registro no.

## Esplorazione prima della produzione

Il lavoro creativo ha due fasi con regole opposte (ADR-0011):

- **Esplorazione**: 5 esploratori in parallelo, ciascuno con una leva diversa e una sandbox propria. Si pensa
  disegnando: 3–5 miniature, si guarda, si sceglie, si ridisegna. Nessuna rifinitura e nessun controllo di finitura.
- **Primo sguardo**: il critico vede solo tavola e brief, scrive cosa si vede davvero e chi passa. Il sistema non lascia
  andare avanti chi non passa (ADR-0014).
- **Scelta interna**: critico e direttore scelgono 2 o 3 idee da soli. Il cliente non vede mai gli schizzi: non sa
  leggerli, e giudicherebbe il disegno invece dell'idea (ADR-0012).
- **Proposte**: ogni idea scelta si sviluppa in parallelo in una proposta forte, con le applicazioni reali del
  cliente, con il ciclo disegna, guarda, correggi. Il direttore prepara la presentazione: un PDF con idea, motivo, limite e raccomandazione, di cui guarda ogni pagina prima dell'invio.
- **Rifinitura**: inizia solo dopo il gate `concept`. Il finisher parte dal master approvato, con controlli completi,
  e non esplora più. Se il concetto cade, si torna agli schizzi, non al rework.

Così l'idea si giudica quando costa poco cambiarla, e il cliente sceglie su qualcosa che sa valutare. L'effort dipende dalla fase, non solo dal ruolo. I set di
strumenti seguono la stessa regola: chi cerca l'idea non può disegnare, chi disegna non può rifinire, il critico
vede solo la tavola anonima, e ogni esploratore vede solo la propria cartella.

Nessun limite dello studio ferma il lavoro: i vincoli sono modello e budget, scelti dal cliente (ADR-0015).

## Lavoro: agenti monouso

Un'istanza di agente vive per un solo ticket: riceve un pacchetto, lavora, consegna e sparisce.
Sparisce così il costo peggiore di Neima, gli agenti fermi con il contesto in pancia.

**La delega non blocca.** Un direttore lavora a due tempi:

1. **Pianifica**: apre i ticket e finisce.
2. **Rivede**: quando i figli hanno finito, il grafo avvia una nuova istanza con un pacchetto breve
   (esiti, tavole, difetti). Non esiste un direttore che aspetta.

La gerarchia è un dato (`ORG`: chi può aprire ticket verso chi), quindi non c'è limite di profondità
imposto dal client. I disaccordi diventano ticket `disaccordo`.

### Ciclo di una chiamata

Loop scritto da noi sulla Messages API (ADR-0003), con queste regole imposte dall'API:

- **Solo in aggiunta.** Mai modificare turni già inviati: gli account creati dopo il 2026-08-31 ricevono
  400 sulla cronologia alterata. Promemoria: messaggi `system` in coda, non modifiche.
- Thinking adattivo sempre attivo; si regola con `output_config.effort` per ruolo.
- Streaming, con `eager_input_streaming` sui nostri strumenti e validazione dell'input prima di eseguire.
- `tool_choice` forzato vietato: la consegna è lo strumento `deliver` con `strict: true`, chiesto dal
  prompt. Se l'agente finisce senza, un richiamo e poi errore.
- `stop_reason` sempre controllato: `refusal`, `max_tokens`, `pause_turn` hanno un ramo proprio.
- `fallbacks: "default"` attivo sui rifiuti di Opus 5.5 e Sonnet 5.5.
- Risultati paralleli sempre in un solo messaggio utente.

## Gateway del modello

Unico modulo che importa `anthropic` e unico che conosce la chiave. Per ogni chiamata:

1. **Autorizza**: stima il costo con `count_tokens` e lo confronta con il budget del progetto.
2. **Compone**: strumenti → system → messaggi, in ordine stabile, con i breakpoint di cache.
3. **Chiama**, con retry distinti per errori transitori e definitivi.
4. **Registra** `usage` in SQLite e nella traccia, per ticket, ruolo e fase.

Se il budget finirebbe, la chiamata non parte: il lavoro resta salvato e riprende quando il cliente alza il tetto.
Gli agenti non sanno nulla di budget e spesa: nessun avviso, nessuna quota (ADR-0016).

## Contesto: pacchetti compilati

È la leva principale. L'harness compila il pacchetto di ogni ticket; l'agente non esplora alla cieca.

| Livello | Contenuto | Cache |
|---|---|---|
| Strumenti | Set fisso del ruolo | Sì, stabile |
| Sistema | Ruolo, regole, indice delle skill | Sì, 5 min |
| Pacchetto | Ticket, contratto, fatti pertinenti, riferimenti, scena dei master | Sì |
| Lavoro | Turni e risultati, solo in aggiunta | Automatica |

- **Skill a richiesta**: nel sistema c'è solo l'indice, `read_skill` carica il resto.
- **Risultati brevi**: gli strumenti rispondono con esiti e percorsi. Il dettaglio resta nei file.
- **Modello di scena**: un JSON comune estratto da `info` di ogni Craft o da bpy: l'agente legge la
  struttura del master senza aprire immagini.
- **Immagini**: 1200 px di default, zoom sui dettagli, fogli di contatto. L'API accetta fino a 2576 px sul
  lato lungo, che costano di più: si usano solo per verifiche di dettaglio.
- **Compaction e context editing** restano la rete di sicurezza. Con agenti monouso non dovrebbero servire.

## Strumenti

Sono funzioni tipizzate, non una shell: l'harness vede ogni azione e può autorizzarla, registrarla e
parallelizzarla. Il set è fisso per tutta l'istanza, perché cambiarlo invaliderebbe la cache.

**I comandi Craft non diventano tool.** Sono migliaia (822 VectorCraft, 615 FigCraft, ordine di
grandezza simile gli altri): sarebbero decine di migliaia di token. Tre strumenti fissi li coprono:

| Strumento | Cosa fa |
|---|---|
| `craft_search(app, query)` | Cerca nell'indice dei comandi, BM25 + embedding, versionato per CLI |
| `craft_describe(app, command)` | Restituisce lo schema esatto |
| `craft_run(app, document, steps)` | Valida ed esegue una sequenza sul documento del ticket |

L'indice si rigenera da `commands` a ogni aggiornamento di una CLI.

### Sandbox e istanze

Ogni lavoro gira in `bwrap`: `/usr` in sola lettura, una sola cartella scrivibile, nessuna rete, nessuna
chiave. Collaudato il 2026-10-31 con tutti e cinque gli strumenti (`spikes/sandbox_craft.sh`).

Un'istanza MCP headless per lavoro sostituisce il lock di server: VectorCraft espone `mcp --headless`
con 33 tool (`command_run`, `command_batch`, `doc_inspect`, `render_preview`…). Due istanze partono in
parallelo. Il lavoro concorrente reale va collaudato in M3; fino ad allora bastano le CLI.

`compute` esegue Python in sandbox per calcolare geometria e misure. Non è una shell di lavoro: il
risultato entra nel master.

## Prove e QA

I controlli sono funzioni pure su file, con le soglie dello studio, e riusano gli script esistenti. Il
sistema, non l'agente, registra l'esito con firma e hash. Da `registry/checks.json`:

- controlli indipendenti eseguibili solo da un'istanza diversa dall'autore, nei ruoli ammessi;
- un FAIL resta sulla stessa versione finché non lo cambia chi l'ha dato o cambia il file;
- `deliver` verifica copertura, freschezza, master e derivazione; `accept` aggiunge i controlli
  indipendenti.

## Confini di fiducia

| Zona | Fidata | Cosa può fare |
|---|---|---|
| Harness | Sì | Tutto, inclusa la chiave |
| Risposte del modello | No | Solo proporre azioni tipizzate |
| Sandbox | No | Scrivere nella propria cartella |
| Materiali cliente e web | No | Sono dati, mai istruzioni |
| Server Django | Parziale | Leggere il registro con `mode=ro`, solo loopback, nessuna chiave |
| Server Next.js | Parziale | Chiamare l'API Django, solo loopback, nessuna chiave e nessun accesso ai dati |
| Servizi locali (Langfuse, ComfyUI) | Parziale | Solo rete locale, nessuna uscita per ComfyUI |

## Telemetria

OpenTelemetry dal primo giorno, con span per progetto, fase, ticket, chiamata e strumento. I costi stanno
anche in SQLite, così il budget non dipende dalla telemetria. Il cruscotto arriva in M1.6, Langfuse in self-hosting in M4.

Da M1.6 ogni chiamata registra in `usage` anche l'esecuzione, la fase, l'effort inviato, la durata, il TTFT e i token di
ragionamento. Il TTFT si conta fino al primo `content_block_delta`, come nelle tracce dell'SDK, così le chiamate vecchie si
confrontano con le nuove. La durata comprende i tentativi ripetuti. Un valore vuoto vuol dire non misurato, mai zero.

## Cruscotto e server

Il cruscotto è un lato di lettura separato dal motore (ADR-0019). Il server è Django con Django Ninja (ADR-0020), l'interfaccia
Next.js con TypeScript (ADR-0024). Taskfile è l'ingresso unico dei comandi.

```text
 Browser ─ Next.js ─ API Django ─ agency.insights ─ sola lettura ─┐
                                                                  ▼
 agency CLI ─ motore: grafo, agenti, strumenti ─ scrive ─ registro, tracce, trascrizioni
```

- Motore, Django e Next.js sono processi separati: nessun server esegue il grafo.
- Next.js è solo interfaccia: legge tutto dall'API Django, senza dati propri, regole dello studio o Server Action.
- Il server legge con `mode=ro` e non apre `Ledger()`, che all'apertura prende un lock di scrittura.
- `.data/insights.sqlite` è una proiezione rigenerabile: il registro resta la verità.
- In M1.6 l'API è solo `GET`. Da M2 i comandi dell'operatore passano da casi d'uso e li esegue un worker.
- Django non possiede il registro: nessun modello Django e nessun admin sulle sue tabelle.
- Docker contiene Django, Next.js e i servizi. Il motore resta sull'host, con `bwrap`, Craft, Blender e GPU.

## Struttura del codice

Cinque principi: modular monolith in vertical slices, explicit over implicit, Clean Architecture (ADR-0021), Schema-First Design
(ADR-0022) e testing pyramid (`07-EVALS.md`). Questa è la forma di arrivo: `insights` nasce così in M1.6, il motore ci arriva in
M1.7.

```text
src/agency/
  shared/        contratti ed errori comuni
  platform/      registro, gateway, sandbox, telemetria
  studio/        una slice per capacità
    exploration/  selection/  proposal/  presentation/  finishing/  delivery/
  process/       composizione del grafo
  insights/      slice di lettura per report e cruscotto
  entrypoints/   cli/ e server/ (Django)
web/             interfaccia Next.js in TypeScript
schemas/         OpenAPI generato e versionato
```

Le dipendenze puntano verso l'interno: `entrypoints`, poi `process`, poi `studio` e `insights`, poi `platform`, poi `shared`.
Dentro una slice il dominio tiene le regole pure, l'applicazione casi d'uso e porte, gli adattatori strumenti e nodi. Le slice non
si importano tra loro, e `import-linter` in `make check` lo impone.

| Libreria | Chi può importarla |
|---|---|
| `anthropic` | Solo il gateway |
| `langgraph` | `process` e i nodi delle slice |
| `sqlmodel`, `alembic` | Solo il registro |
| `django`, `ninja` | Solo `entrypoints/server` |

## Verso il SaaS

Fino a M7 il sistema resta su una macchina, con un operatore (ADR-0023). Multi-tenancy, worker fuori da questa macchina e
archiviazione si decidono prima di M7, con un ADR ciascuna. Registro dietro una porta e casi d'uso separati dagli ingressi tengono
aperte queste scelte.

## Cosa manca volutamente

Nessun Kitsu, smolagents, LiteLLM o OpenUSD. I motivi sono negli ADR. DSPy è rimandato a M5, in un
ambiente separato.
