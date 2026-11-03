# Roadmap

Ogni traguardo finisce con un lavoro reale e con criteri verificabili, non con infrastruttura. Non si
passa al successivo con un criterio aperto. I tetti di spesa sono stime iniziali per le prove dal vivo:
si aggiornano con i dati di M1.

| # | Traguardo | Risultato | Tetto API | Stato |
|---|---|---|---|---|
| M0 | Fondamenta | Repo, contratti, registro, documenti, backup | 0 $ | **fatto** |
| M1 | Prova verticale | Un logo S dall'inizio alla fine, confrontato con la CLI | 40 $ | **chiuso**, confronto passato a M1.6 |
| M1.5 | Esplorazione a schizzi | Idee in parallelo, schizzi veloci, scelta del concetto, poi produzione | 40 $ | **chiuso**, 38,83 $ spesi, criteri non verificati passati a M1.6 e M2 |
| M1.6 | Misure e cruscotto | Dati confrontabili, `insights`, API Django, cruscotto Next.js, `merlo4` misurato | 30 $ | in corso |
| M1.7 | Architettura a slice | Motore diviso in slice, dipendenze imposte, E2 dal vivo | 10 $ | |
| M2 | Parità | Tutto lo studio, con replay di un'identità | 200 $ | |
| M3 | Contesto visivo e parallelo | Scena, ricerca visiva, istanze per lavoro | 60 $ | |
| M4 | Osservabilità e generazione | Langfuse, ComfyUI isolato, scheduler GPU | 60 $ | |
| M5 | Ottimizzazione | Taratura misurata di effort, modelli e prompt | 100 $ | |
| M6 | Passaggio definitivo | Primo cliente reale, interfaccia, CLI in pensione | da definire | |
| M7 | SaaS | Più clienti paganti, separati tra loro, sullo stesso sistema | da definire | |

M1.5 viene prima della parità perché cambia il modo in cui nasce ogni lavoro creativo: i ruoli si portano
una volta sola, sul flusso definitivo. M3 e M4 possono invertirsi. Gli altri sono in sequenza.

M1 e M1.5 sono chiusi il 2026-11-01 per decisione di Andrea, con alcuni criteri non verificati. Quei criteri non sono segnati
come fatti: passano a M1.6, dove si misurano su `merlo4`, oppure a M2. In M1.6 gli obiettivi di costo si misurano ma non bloccano
M1.7.

M1.6 e M1.7 vengono prima della parità perché M2 porta tutto lo studio sul motore: senza misure si lavorerebbe alla cieca, e
dopo dividere il codice costerebbe molto di più. Una prova dal vivo parte solo su richiesta, anche con il tetto in tabella. M7
viene dopo il primo cliente reale (ADR-0023).

---

## M0 — Fondamenta (fatto)

- [x] Repo con `uv`, lock, dipendenze con quarantena di due settimane
- [x] Backup congelato in `legacy/claude-code-v1/` con manifest verificato dai test
- [x] Contratti `TicketSpec`, stati, verdetti, tabella delle transizioni
- [x] Registro SQLite solo in aggiunta, con trigger e catena di hash
- [x] `agency doctor`, `agency verify`
- [x] Registri `roles`, `checks`, `budgets`; matrice di parità generata dal backup
- [x] Collaudo: Craft e Blender in `bwrap` senza rete, MCP headless paralleli
- [x] Documenti e ADR

**Prerequisiti di M1, a carico di Andrea:** chiave API e tetto mensile nella Console. Fatto il 2026-10-31.

---

## M1 — Prova verticale (chiuso)

**Domanda a cui rispondere:** il nostro loop produce lavoro almeno pari a Claude Code, spendendo meno?
Se la risposta è no, ci si ferma qui e si capisce perché, prima di portare il resto.

**Percorso:** brief → `design-director` pianifica → `identity-designer` produce → `qa-inspector` e
`critic` verificano → `design-director` rivede → consegna.

### Lavoro, in ordine

1. [x] **Gateway**: chiamata con streaming, `usage`, retry, rifiuti, costo per ticket, tetto preventivo.
2. [x] **Risposte registrate**: registratore per ripetere nei test le chiamate senza spendere.
3. [x] **Loop dell'agente**: solo in aggiunta, strumenti strict, `deliver`, tutti gli `stop_reason`.
4. [x] **Sandbox**: `agency.tools.sandbox` su `bwrap`.
5. [x] **Indice Craft**: `craft_search`, `craft_describe`, `craft_run` per VectorCraft.
6. [x] **Porting**: `master`, `render`, `evidence`, `svg_audit`, `svg_parity`, `logo_proof`, `optical_check`.
7. [x] **Pacchetto di contesto**: ticket + ruolo + skill a richiesta.
8. [x] **Grafo minimo**: pianifica, produci, verifica, rivedi, con checkpoint e un gate.
9. [x] **Telemetria**: span OpenTelemetry e rapporto di costo per ticket.
10. [ ] **Valutazione**: E1 eseguito sull'harness (`merlo`), confronto con la CLI passato a M1.6.

### Criteri di uscita

- [ ] Stesso brief S eseguito su CLI e harness: qualità non inferiore nel giudizio alla cieca di Andrea (passato a M1.6)
- [ ] Costo harness inferiore a quello della CLI sullo stesso brief (passato a M1.6)
- [x] Un lavoro completo fino al gate del cliente: `merlo3`, gate `concept` e `final`
- [x] Nessun campo `by` negli schemi degli strumenti: la firma è impossibile da falsificare (test)
- [x] Un output senza controllo non si può consegnare (test)
- [x] Master `.vectorcraft` valido e SVG derivato (test su file reale e `merlo`)
- [x] Budget superato → lavoro fermo prima della spesa, senza perdere nulla (`merlo`, 15,91 $ su 16 $). Da M1.5 è
      davvero ripartibile: si alza il budget e si riprende
- [x] Processo ucciso a metà → riprende senza doppi effetti (test e ripresa reale di `merlo`)
- [x] Tentativo di scrivere fuori dalla cartella o di usare la rete → bloccato dalla sandbox (test)
- [x] Hit rate della cache misurato e riportato: 97% su `merlo`
- [x] Specialista con contesto fisso ≤ 6.000 token: 4.203 per `identity-designer`

### Risultato di `merlo` (brief E1, 2026-10-31)

| Misura | Valore |
|---|---|
| Spesa | 15,91 $ in 363 chiamate, fermata dal tetto di 16 $ |
| Tempo di lavoro | ~71 minuti, per il 98% generazione del modello |
| Designer | 13,20 $, l'83% del totale, su quattro giri |
| Primo concetto valido | scelto dopo 36 minuti e 8,02 $ |
| Contesto medio | 67.111 token per chiamata (obiettivo a M2: ≤ 60.000) |
| Esito | Terza versione non revisionata; critica: "corretto, ma ancora ordinario" sul riparare |

**Lezione:** il sistema regge, ma l'idea veniva giudicata solo dopo averla costruita e rifinita. Il primo giro
ha speso 4,14 $ su un concetto bocciato. Da qui nasce M1.5.

**Fuori da M1:** cliente reale, sprint, altri Craft oltre VectorCraft, LanceDB, Langfuse.

**Chiusura (2026-11-01).** Il sistema regge, ma la domanda di questo traguardo non ha ancora una risposta misurata: il confronto
con la CLI non è stato fatto. Si risponde in M1.6.

---

## M1.5 — Esplorazione a schizzi (chiuso)

**Domanda a cui rispondere:** giudicando idee su schizzi veloci, prima di rifinire, troviamo un concetto più
forte, prima e spendendo meno?

Come in uno studio vero: **si pensa disegnando, con schizzi rapidi finché un'idea non è scelta**. Il cliente non vede
mai gli schizzi: vede proposte forti, nel loro contesto, con la raccomandazione dello studio. Scelte motivate in
[ADR-0011](adr/0011-esplorazione-a-schizzi.md), [ADR-0012](adr/0012-il-cliente-vede-proposte.md),
[ADR-0013](adr/0013-cinque-direzioni-interne.md), [ADR-0014](adr/0014-pensare-disegnando.md),
[ADR-0015](adr/0015-modello-e-budget-del-cliente.md), [ADR-0016](adr/0016-nessun-avviso-agli-agenti.md) e
[ADR-0017](adr/0017-il-cliente-riceve-ciò-che-lo-studio-ha-guardato.md).

### Il flusso

```text
DENTRO LO STUDIO    brief → 5 esploratori in parallelo, che pensano disegnando → tavola anonima
                    → primo sguardo del critico → scelta di 2 o 3 idee → proposte in parallelo con le applicazioni
DAVANTI AL CLIENTE  presentazione con raccomandazione → gate `concept`
DOPO LA SCELTA      il finisher rifinisce la proposta scelta → QA e critica → gate `final`
```

| Fase | Chi | Effort | Regole |
|---|---|---|---|
| Piano | `design-director` | `high` | Risorse del cliente, leve, cliché da evitare, applicazioni reali. Il sistema rifiuta gli esclusi che vietano una risorsa |
| Esplorazione | Un esploratore per leva, fino a 5, in una sola istanza con la vista | `high` | 3–5 miniature, guarda, sceglie, ridisegna la migliore. Poi la scheda: idea, fatto del cliente, test di sostituzione |
| Tavola | Sistema | — | Anonima, stesse condizioni, stessa dimensione d'uso, piccola e grande |
| Primo sguardo | `critic` | `high` | Vede solo tavola e brief. Scrive cosa si vede davvero e chi passa: chi non passa non può andare avanti |
| Scelta interna | `design-director` | `high` | 2 o 3 idee tra quelle che passano, senza fusioni e senza fermarsi: è una decisione dello studio |
| Proposta | Un `identity-designer` per idea, in parallelo | `high` | Forte e convincente, con le applicazioni. Ciclo disegna, guarda, correggi. Mai finte fotografie |
| Presentazione | `design-director` | `high` | Documento PDF: idea, motivo, limite di ogni proposta, raccomandazione. Scarta ciò che non regge e guarda ogni pagina prima di mandarla |
| Gate `concept` | Cliente | — | Sceglie una proposta. Nelle prove il cliente lo interpreta Andrea |
| Rifinitura | Finisher | `high` | Parte dal master approvato, niente nuove esplorazioni, controlli completi |

### Lavoro, in ordine

1. [x] **Contratti**: scheda dell'idea e ticket di schizzo, con controlli leggeri propri.
2. [x] **Effort per fase**: dipende dal ticket, non solo dal ruolo.
3. [x] **Parallelo**: esploratori con `Send` di LangGraph, limite di concorrenza, sandbox separate.
4. [x] **Leve e territori esclusi**: dal metodo dello sprint, per evitare che le idee convergano.
5. [x] **Tavola anonima** generata dal sistema, con lettere al posto degli autori.
6. [x] **Nuovi nodi del grafo**: esplorazione, selezione, gate `concept`, produzione.
7. [x] **Finisher**: prompt e strumenti senza esplorazione; un concetto bocciato torna agli schizzi, non al rework.
8. [x] **Budget per fase**: superato. Tetti, limiti e quote sono stati rimossi da ADR-0015 e ADR-0016.
9. [x] **Scelta interna**: critica e direttore scelgono da soli, senza gate del cliente.
   Dopo `merlo2` il primo sguardo è un vincolo del sistema, non un'istruzione.
10. [x] **Proposte in parallelo**: ogni idea scelta diventa una proposta con le sue applicazioni reali.
    Il numero di esploratori è configurabile, e si parte da 5.
11. [x] **Presentazione al cliente**: PDF con idea, motivo, limite e raccomandazione; gate `concept` su questo.
12. [x] **Esploratori che pensano disegnando**: una sola istanza con vista, 3–5 miniature, skill di mestiere.
13. [x] **Limiti**: gli unici vincoli sono modello e budget, scelti dal cliente per progetto (ADR-0015).
14. [ ] **Valutazione**: confronto con `merlo` e con la CLI passato a M1.6.

### Decisioni da prendere con la prima prova

- Quanti esploratori: si parte da 5 (ADR-0013), meno se il brief non regge tante leve vere. Se la quarta e la
  quinta idea risultano copie delle prime, si torna a 3 con `AGENCY_EXPLORERS=3`.
- Quante proposte: 2 o 3. Il direttore può portarne una sola se le altre non reggono.
- Effort `medium` su esplorazione e proposte: si prova con `AGENCY_EXPLORER_EFFORT` e `AGENCY_PROPOSAL_EFFORT`, e si
  tiene solo se la qualità regge.

### Criteri di uscita

I valori sono obiettivi iniziali, rispetto a `merlo`. Alla chiusura i criteri aperti sono passati a M1.6 o a M2.

- [x] Esploratori realmente in parallelo, verificato dalle tracce: 5 insieme su `merlo3`
- [x] Almeno 3 idee su 5 diverse nel concetto, non solo nello stile: 4 su `merlo3`
- [x] Il cliente non vede schizzi e la scelta interna non chiede nulla al cliente (test e `merlo3`)
- [ ] **Il segno scelto batte quello di `merlo` nel giudizio alla cieca di Andrea**: è il criterio principale. Non verificato,
  passa a M1.6
- [x] Il primo sguardo legge una figura o un'immagine forte, non una forma geometrica o un'icona generica
- [ ] Presentazione pronta entro 45 minuti e 12 $, con 2 o 3 proposte confrontabili. Non raggiunto: `merlo3` ha fatto 30 minuti
  e 13,29 $ con una proposta sola. Passa a M1.6
- [x] Nessun lavoro fermato da un limite dello studio, e nessuna pressione sugli agenti: solo il budget del cliente ferma
  (dopo ADR-0018; nelle trascrizioni di r2, r3, QA e critica non c'è nessun riferimento al budget)
- [x] Budget finito → si alza con `agency budget` e il lavoro riprende senza rifare nulla
  (`test_budget_end_pauses_the_project_and_an_increase_resumes_it`; su `merlo3` il registro non mostra uno stop per budget)
- [x] Nessuna bocciatura del concetto dopo il gate `concept`
- [ ] Lavoro completo fino al gate `final` entro 22 $ (`merlo`: non finito a 15,91 $; `merlo3`: 34,38 $). Passa a M1.6
- [ ] Il test di sostituzione passa: il segno scelto dice ciò che rende unico il cliente (`merlo3`: passa contro le
  ciclofficine generiche, non contro un'altra con il nome di un uccello; «ripara» lo dice l'adesivo, non il simbolo).
  Passa a M1.6
- [ ] Confronto con `merlo` e con la CLI: qualità almeno pari nel giudizio alla cieca di Andrea, costo inferiore. Non fatto,
  passa a M1.6
- [ ] Contesto medio ≤ 60.000 token per chiamata: 56.457 fino alla presentazione, 81.014 sull'intero `merlo3`. Passa a M2

### Risultato di `merlo2` (brief E1, 2026-10-31)

| Misura | Valore |
|---|---|
| Spesa | 4,45 $ in 107 chiamate, ferma per il limite di strumenti |
| Tempo fino alle proposte | circa 14 minuti |
| Parallelo | 5 istanze sovrapposte, verificato dal registro |
| Idee e schizzi | 1,97 $, cioè 0,39 $ a direzione |
| Esito | Nessun PDF: entrambe le proposte bloccate. Segni deboli, geometrici |

**Lezione:** la macchina funziona, il risultato creativo no. Il valore stava nel ciclo disegna, guarda, correggi, e il
flusso lo aveva tolto proprio dove nascono le idee. La figura più forte del cliente era stata vietata come ovvia, la
selezione premiava le spiegazioni, e un limite di strumenti bloccava il lavoro a metà. Correzioni in ADR-0014.

### Risultato di `merlo3` (brief E1, 2026-11-01)

| Fase | Tempo | Costo |
|---|---|---|
| Esplorazione, 5 in parallelo | 11,3 minuti | 8,59 $ |
| Primo sguardo e scelta | 1,1 minuti | 0,23 $ |
| Proposta V | 16,4 minuti | 4,22 $ |
| Piano e presentazione | 0,7 minuti | 0,25 $ |
| **Totale fino al gate `concept`, 365 chiamate** | **30 minuti** | **13,29 $** |

Segno V: un solo tracciato, 23 nodi. A 16 mm il foro misura 5,2 mm, l'anello 1,6–1,8 mm, l'occhio 0,9 mm, al limite per
il vinile. Il master supera `svg_audit` e `svg_parity`. Al gate `concept` restavano 16,71 $ di budget.

**Lezione:** pensare disegnando ha dato il salto di qualità. Due difetti del sistema hanno falsato il risultato: il PDF
tagliava motivo e limite, e la tavola giudicava V più grande degli altri perché era l'unico file con un segno solo.
Corretti in ADR-0017, da riprovare su un lavoro reale. Fino a questo gate il lavoro ha ricevuto ancora le quote.

**Dopo il gate `concept`:** `merlo3` è il primo lavoro arrivato al gate `final`: 34,38 $ in 811 chiamate, di cui 21,09 $
dopo la scelta del cliente. La rifinitura è costata 15,69 $: r1 7,56 $, r2 3,20 $, r3 4,94 $. La r3 ha lasciato il simbolo
identico, byte per byte: ha allineato sorgenti, documento e tavole. La critica ha trovato due difetti veri, il flesso
nella gola e il becco troppo leggero, corretti nella r2. Le prime quattro revisioni sono rimaste bloccate per contratti
impossibili (3,10 $), corretti in [ADR-0018](adr/0018-un-contratto-impossibile-non-si-apre.md): la correzione ha
funzionato dal vivo su `T-0034` e `T-0035`.

**Lezione:** il processo produce lavoro buono e si corregge da solo, ma costa troppo dopo la scelta. Il contesto medio
sale da 56.457 a 101.111 token, con un picco di 267.966 sul designer, che da solo fa 19,91 $ su 34,38 $.

**Fuori da M1.5:** direzioni complete con tipografia, colore e immagini, altri mezzi oltre il vettoriale,
cliente reale.

### Chiusura (2026-11-01)

Andrea ha chiuso M1.5 e `merlo3`. Il flusso è arrivato dal vivo fino al gate `final`, con READY di critica e QA. Restano senza
risposta il giudizio alla cieca e il confronto con la CLI, e gli obiettivi di costo e di contesto non sono stati raggiunti.

Il registro non ha una decisione al gate `final`, e il grafo di `merlo3` resta fermo lì. Il lavoro non si riprende: il refactor
di M1.7 non deve preservarlo.

---

## M1.6 — Misure e cruscotto

**Domanda a cui rispondere:** sappiamo dire con i numeri come lavora il modello, e se una versione è meglio della precedente?

La maggior parte del breakdown esiste già nei dati: tutte le 1.281 chiamate si collegano alle tracce, con durata, TTFT, effort e
ragionamento. Mancano le due cose che dicono se il lavoro va bene: il giudizio alla cieca e l'impronta di ogni esecuzione. Quindi
prima i dati, poi l'interfaccia. Scelte motivate in [ADR-0019](adr/0019-cruscotto-lato-di-lettura.md),
[ADR-0020](adr/0020-django-react-taskfile-docker.md), [ADR-0022](adr/0022-schema-prima-del-codice.md) e
[ADR-0024](adr/0024-nextjs-per-l-interfaccia.md).

### Lavoro, in ordine

**Messa in sicurezza**

1. [x] **Primo commit**: `51c511c`, con lo stato di lavoro di `.claude/` escluso da `.gitignore`.
2. [x] **Snapshot**: definizioni degli strumenti e system prompt delle 11 fasi, byte per byte, in `tests/snapshots/requests/`.

**Dati**

3. [x] **Migrazioni**: Alembic sul registro e `agency migrate`, provati su una copia di quello vero
   ([ADR-0025](adr/0025-il-registro-si-aggiorna-solo-su-richiesta.md)).
4. [x] **`runs`**: impronta di ogni `run`, `resume` e `decide`, con `agency runs` e `agency compare`. Oltre a prompt, registry,
   lock, CLI, modello ed effort contiene codice, Python e impostazioni ([ADR-0026](adr/0026-l-impronta-di-un-esecuzione.md)).
5. [x] **`judgments`** e `agency judge`: livello, test di sostituzione, migliore e perché, legati allo sha256 del file giudicato,
   con lettere estratte a ogni confronto ([ADR-0027](adr/0027-il-giudizio-alla-cieca.md)).
6. [x] **`usage` più ricca**: esecuzione, fase, effort, durata, TTFT e ragionamento, con la migrazione `0004`. Le righe vecchie
   restano vuote, e vuoto vuol dire non misurato.
7. [x] **Artefatti per hash**: consegne, presentazioni e file giudicati in `.data/artifacts/`, con `agency artifacts`,
   `agency restore` e il controllo in `agency verify` ([ADR-0028](adr/0028-gli-artefatti-per-hash.md)).
8. [x] **Tipi espliciti**: gate, decisioni ed esiti in `agency.contracts`, `ToolContext.extra` diviso in campi propri, il grafo
   tipizzato. I checkpoint e le trascrizioni già salvati si leggono ancora, compreso il gate in pausa di `merlo3`.

**Lettura**

9. [x] **Slice `agency.insights`**: connessione `mode=ro`, proiezione rigenerabile in `.data/insights.sqlite` con `agency insights`,
   nella forma di ADR-0021. `import-linter` in `make check`: `insights` non importa il motore, e il motore non importa Django
   ([ADR-0029](adr/0029-la-proiezione-di-insights.md)).
10. [x] **`agency report --json`**: `ProjectReport`, lo stesso modello per il testo, il JSON e il cruscotto, con una sezione per
    fase ([ADR-0030](adr/0030-il-rapporto-passa-da-insights.md)).

**Cruscotto**

11. [x] **API Django** con Django Ninja: solo `GET`, solo loopback, senza chiave, in un processo separato dal motore,
    `uv run agency-server` ([ADR-0031](adr/0031-il-server-del-cruscotto.md)).
12. [x] **Schemi**: `schemas/openapi.json` versionato, tipi TypeScript generati con `openapi-typescript`, controlli contro le
    divergenze in `make check` ([ADR-0032](adr/0032-schemi-e-tipi-generati.md)).
13. [x] **Cruscotto Next.js** in TypeScript, con le sei viste qui sotto. È solo interfaccia: legge tutto dall'API Django, con le
    difese di ADR-0024 e le due aggiunte da [ADR-0033](adr/0033-il-cruscotto-next-js.md). In cinque parti:
    - [x] **Run**, con le fondamenta: client unico, server standalone, controllo dell'`Host`, prove Playwright e unitarie. Il
      tempo di lavoro è separato dalle attese del cliente, calcolate da `insights`
    - [x] **Fasi** e **Modello**: rework e passi indietro dalla storia dei ticket, contesto turno per turno su una scala sola
      ([ADR-0035](adr/0035-le-viste-fasi-e-modello.md))
    - [x] **Strumenti e QA**: controlli al primo colpo, prove fallite, rifiuti degli strumenti e passi indietro, ognuno con il
      suo motivo ([ADR-0036](adr/0036-la-vista-strumenti-e-qa.md))
    - [x] **Confronto**: due progetti affiancati con i numeri delle altre viste, l'impronta fra la fine dell'uno e l'inizio
      dell'altro, i giudizi alla cieca che li contengono entrambi ([ADR-0037](adr/0037-la-vista-confronto.md))
    - [x] **Replay**: un'istanza turno per turno, letta dalla sua trascrizione senza copiarla, con le misure di ogni chiamata
      e le immagini ([ADR-0038](adr/0038-la-vista-replay.md))
14. [x] **Taskfile**: ingresso unico per Python e frontend, `make` come alias, il cruscotto con `task dashboard`
    ([ADR-0039](adr/0039-taskfile-come-ingresso-unico.md)). I comandi di Docker arrivano con il punto 15.
15. [x] **Docker** per Django e Next.js, per ultimo, con `task docker:up`. Il motore resta sull'host
    ([ADR-0040](adr/0040-il-cruscotto-in-docker.md)).

**Prova reale**

16. [x] **`merlo3` contro `merlo`**: primo giudizio alla cieca registrato, senza spesa, il 2026-11-03 (confronto `123b003a`).
    `merlo3` eccellente e migliore, `merlo` buono, tutti e due specifici. I due `segno.svg` erano sulla tavola, alla pari, e il
    migliore non può contraddire i livelli ([ADR-0041](adr/0041-la-tavola-del-giudizio.md)). Si rilegge con
    `uv run agency report merlo3` e nella vista Confronto, `/compare?before=merlo&after=merlo3`.
17. [ ] **`merlo4`**: brief E1 dal vivo, solo su richiesta di Andrea, tetto 30 $. Prima esecuzione con impronta e con ADR-0017 e
    ADR-0018 attivi dall'inizio. Con i costi di `merlo3` il tetto è stretto: si rivede prima di partire. È una prova sola, quindi
    il risultato è indicativo: le 3 prove di `07-EVALS.md` costerebbero circa 100 $.
    - [x] Preparato il 2026-11-03, senza spesa. Il brief è identico a quello di `merlo` e `merlo3`. `agency doctor` passa.
      L'impronta di partenza è 5 esploratori, effort `high`, `vectorcraft-cli` 0.18.0. Il tetto si dichiara per forza
      all'avvio ([ADR-0043](adr/0043-il-tetto-si-dichiara-all-avvio.md)): l'ambiente di Andrea ne dava uno di 40 $.
    - [x] Il segno da battere è quello di `merlo3` ([ADR-0042](adr/0042-il-riferimento-di-qualita-e-merlo3.md)).
    - [ ] Avvio, da Andrea, con il tetto che dichiara: `uv run agency run merlo4 evals/briefs/E1.md --budget <usd>`
    - [ ] Gate `concept` e gate `final` decisi da Andrea, con `agency decide merlo4`
    - [ ] Giudizio alla cieca del segno finale contro quello di `merlo3`, e lettura per intero nel cruscotto
18. [ ] **Confronto con la CLI** sullo stesso brief. Questa prova ha un tetto proprio, da dichiarare prima di partire.

### Le viste

| Vista | Domanda | Contenuto |
|---|---|---|
| Run | Quanto è costato e quanto è durato? | Costo, tempo, budget, timeline delle istanze |
| Fasi | Dove si è fermato o è tornato indietro? | Dalle idee alla consegna, costo e rework per fase |
| Modello | Come ha lavorato? | Contesto turno per turno, cache, ragionamento, latenza e `stop_reason`, per ruolo |
| Strumenti e QA | Dove sbaglia? | Rifiuti con motivo, passaggi al primo colpo, ticket bloccati |
| Confronto | È meglio di prima? | Due esecuzioni affiancate, differenze di impronta, giudizi |
| Replay | Cosa è successo davvero? | Un'istanza turno per turno, con le immagini |

Una vista nuova entra solo se `merlo4` mostra una domanda a cui queste non rispondono.

### Criteri di uscita

- [x] Gli snapshot di strumenti e system prompt stanno nei test e bloccano `make check`: `tests/test_request_snapshots.py`
- [x] `agency verify` passa su una copia del registro migrata: provato il 2026-11-02, con tutte le 3.814 righe identiche
  (`tests/test_migrations.py`)
- [x] Ogni nuova esecuzione registra la propria impronta, e due esecuzioni mostrano cosa è cambiato: `tests/test_runs.py` e
  `tests/test_sketch_flow.py`, a mano con `agency runs <progetto>` e `agency compare <n> <n>`
- [x] Ogni nuova chiamata registra in `usage` esecuzione, fase, effort, durata, TTFT e ragionamento: `tests/test_gateway.py` e
  `tests/test_sketch_flow.py`. Il TTFT dal vivo si vedrà con `merlo4`: i test lo misurano su uno stream simulato
- [x] Un file giudicato resta recuperabile dal suo hash in `.data/artifacts/`: `tests/test_artifacts.py` e
  `tests/test_judgments.py`, a mano con `agency restore <hash> <file>`
- [x] `ToolContext.extra` e `graph: object` non esistono più, e gate ed esiti hanno tipi propri:
  `tests/test_explicit_types.py` e `make check`, che con `pyright` rifiuta l'uso dei vecchi `dict`
- [x] `agency report --json` riproduce i numeri di questa roadmap: 15,91 $ su `merlo`, 13,29 $ fino al gate `concept` di `merlo3`.
  Dopo `agency migrate`: `uv run agency report merlo --json` e `uv run agency report merlo3 --json`, campo `to_presentation`
- [x] `merlo3` si legge nel cruscotto dal brief alla consegna: provato il 2026-11-03 su una copia migrata del registro, in tutte
  le sei viste. Run: 2 h 1 min di lavoro e 16 h 20 min di attesa del gate `concept`. Fasi: tre consegne della rifinitura, 8,14 $
  rifatti. Modello: contesto fino a 267.966 token in 128 turni. Strumenti e QA: 83 controlli su 89 al primo colpo, e le revisioni
  bloccate dicono che il contratto chiedeva `review/…` mentre il revisore scrive solo in `reviews/`. Confronto con `merlo`: +18,47 $.
  Replay: dal compito di T-0021-a1-plan alla consegna di T-0021-a7, turno per turno con le immagini. Si rifà con `agency migrate`,
  `uv run agency-server` e `pnpm --dir web build && pnpm --dir web start`
- [x] L'API non può scrivere, e il registro resta intatto dopo l'uso del cruscotto: `tests/test_server.py`
- [x] OpenAPI e tipi TypeScript non divergono: `tests/test_schemas.py` per modelli e schema, `make web` per schema e tipi
- [x] `import-linter` in `make check`: `insights` non importa il motore, e il motore non importa Django. `make imports`
- [x] Django e Next.js ascoltano solo su loopback e non vedono né chiave né `.env` (test): `tests/test_server.py` per Django,
  `make e2e` per entrambi, con le connessioni dagli indirizzi di rete della macchina e una chiave finta cercata in `/proc` nei
  processi dei server. `make web` rifiuta un `.env` in `web/` e uno script che avvia Next.js senza togliere la chiave
- [x] Una pagina ostile che fa puntare il suo nome a `127.0.0.1` non legge il cruscotto: `make e2e`, che chiede pagine, `/api` e
  file statici con `Host: evil.example` e si aspetta 400
- [x] Next.js non invia telemetria e non lascia copie di immagini o dati in `.next/cache` (test): `make web` verifica che
  `next telemetry status` dica `Disabled` e che ogni script la spenga; `make e2e` verifica che il browser parli solo con Next.js
  e che nella build, server standalone compreso, non restino immagini, risposte in cache o dati del registro
- [x] Almeno un test Playwright per vista: `web/e2e/run.spec.ts`, `phases.spec.ts`, `model.spec.ts`, `quality.spec.ts`,
  `compare.spec.ts`, `replay.spec.ts`, con `make e2e`
- [x] `task check` esegue i controlli di Python e Next.js, e Docker Compose avvia Django e Next.js: `task check`, e `make check`
  che ne è l'alias (`tests/test_taskfile.py`); `task docker:up`, verificato il 2026-11-03 su un registro di prova e su una copia
  migrata di quello vero, con la configurazione provata da `tests/test_docker.py`
- [ ] `merlo4` è arrivato al gate `final` ed è stato letto per intero nel cruscotto

**Ereditati da M1 e M1.5:**

- [x] **Il segno scelto batte quello di `merlo` nel giudizio alla cieca di Andrea**: `merlo3` eccellente e migliore, `merlo`
  buono, il 2026-11-03 (punto 16). `uv run agency report merlo3`
- [ ] Stesso brief su CLI e harness: qualità non inferiore alla cieca
- [ ] Stesso brief su CLI e harness: costo inferiore
- [x] Il test di sostituzione passa: il segno scelto dice ciò che rende unico il cliente. Nello stesso giudizio Andrea ha detto
  che il segno di `merlo3`, con un altro nome, non reggerebbe. Nel perché ci legge il merlo, e nel cerchio vuoto la ruota e la
  chiave inglese dell'officina: la riparazione che in M1.5 diceva solo l'adesivo
- [ ] Presentazione pronta entro 45 minuti e 12 $, con 2 o 3 proposte confrontabili
- [ ] Lavoro completo fino al gate `final` entro 22 $

La qualità decide se si prosegue: se risulta inferiore alla CLI vale ancora la regola di M1, ci si ferma e si capisce perché. Gli
obiettivi di costo, compreso il confronto con la CLI, si misurano su `merlo4`: se restano lontani non bloccano M1.7, e si affrontano
con il contesto delle istanze lunghe, il primo lavoro di M2.

**Fuori da M1.6:** scritture dall'interfaccia, account, multi-tenancy, Langfuse, refactor del motore.

---

## M1.7 — Architettura a slice

**Domanda a cui rispondere:** il motore può crescere fino a tutto lo studio senza che ogni ruolo nuovo tocchi gli stessi file?

Viene dopo `merlo4`, così il comportamento del motore è misurato prima di toccarlo. Principi e confini in
[ADR-0021](adr/0021-monolite-modulare-a-slice.md).

### Lavoro, in ordine

1. [ ] **Cicli**: spezzare quelli tra `agents` e `tools` e tra `qa` e `tools`.
2. [ ] **`tools/surface.py`**: 940 righe divise per slice, una alla volta.
3. [ ] **`graph/workflow.py`**: i nodi passano alle slice, `process` compone il grafo.
4. [ ] **Dominio e applicazione**: regole pure, casi d'uso e porte fuori dai framework.
5. [ ] **`import-linter` bloccante** su tutto il pacchetto.
6. [ ] **Piramide dei test**: nuovi test sulle regole pure. I test di flusso restano: sono la rete del refactor.
7. [ ] **E2 dal vivo**, solo su richiesta di Andrea, tetto 10 $. Copre il rework.

### Criteri di uscita

- [ ] `tools/surface.py` non esiste più, e non ci sono cicli tra pacchetti (`make check`)
- [ ] Gli snapshot di strumenti e system prompt sono identici a quelli di M1.6
- [ ] I test di flusso passano con le sole modifiche agli import
- [ ] Dominio e applicazione non importano framework (`import-linter`)
- [ ] E2: hit rate della cache e contesto fisso non peggiori di `merlo4`, letti nel cruscotto

**Fuori da M1.7:** ruoli nuovi, comandi dal cruscotto, multi-tenancy.

---

## M2 — Parità

**Domanda:** tutto ciò che lo studio sapeva fare esiste ancora?

Si costruisce sulle slice di M1.7.

1. Ruoli (25) e skill (33) in `prompts/`, ripuliti di ciò che ora impone il sistema.
2. Grafo completo con rami S/M/L e tutti i gate del cliente.
3. Registro cliente: domande, risposte, presentazioni, approvazioni con hash.
4. Fatti con provenienza, dossier, copertura.
5. Sprint delle direzioni in sandbox separate: estende l'esplorazione di M1.5 a direzioni complete.
6. Tutti i controlli QA e i Craft restanti (EffectCraft, PhotoCraft, FigCraft, Blender).
7. Disaccordi, prova di robustezza, retrospettiva e lezioni.
8. Consulenza su domande del cliente senza aprire tutto il processo.

### Lavoro emerso da `merlo3`

- Presentazione impaginata dallo studio con il suo mezzo: oggi è una scheda generata dal sistema.
- `web_search_20260209` e `web_fetch_20260209`: accettati da `claude-opus-5-5` e `claude-sonnet-5-5` (verificato con
  `count_tokens`). Il gateway deve contare anche le ricerche, 10 $ ogni 1.000. Servono per ricerca e verifica legale.
- `CommandIndex` deve chiedere `--json` agli altri Craft: oggi legge solo VectorCraft.
- `craft_run`, `render` ed `export_master` per EffectCraft, PhotoCraft, FigCraft e Blender.
- Il campo `craft` di `registry/roles.json` va applicato: oggi gli strumenti dipendono solo dalla fase.
- Un'attivazione per ruolo: un ruolo senza prompt non riceve ticket, quindi ogni ruolo portato si abilita da solo.
- Un progetto bloccato va ripreso dal cliente: oggi se il direttore si ferma il lavoro finisce, e `agency resume` non lo riapre.
- `record_requirement` deve accettare `NOT_VERIFIED`: su `merlo3` il requisito dei 16 mm, non provato fisicamente, è stato
  registrato come `NOT_APPLICABLE` perché non c'era altro modo di dirlo.
- Comandi dal cruscotto per l'operatore: gate, budget e ripresa, eseguiti da un worker (ADR-0019).
- **Prima di tutto il resto, il contesto delle istanze lunghe:** il designer lavora con una media di 127.000 token. Con
  questo andamento il replay entro 50 $ e il contesto entro 60.000 token non sono raggiungibili. Va deciso anche un giro
  separato e più leggero per le correzioni che non toccano il disegno: la r3 è costata 4,94 $ a simbolo invariato.
- Le note del cliente al gate devono poter aggiungere consegne: la versione a 32 px e il lockup chiesti su `merlo3` sono
  solo nel master e in `proofs/`, perché gli output restano quelli fissati all'avvio.
- Il testo del lockup va convertito in tracciati, e la licenza del font va registrata prima della consegna.
- `qa-inspector` deve poter eseguire gli script dell'autore: su `merlo3` non ha potuto rilanciare `costruzione.py`.

### Criteri di uscita

- [ ] Ogni riga di `docs/PARITY.md` è `fatto` o `dismesso` con motivo
- [ ] Replay di un'identità comparabile a Neima fino al gate `direction`: ≤ 50 $
- [ ] Contesto medio ≤ 60.000 token per chiamata
- [ ] 100% delle produzioni visive con master valido
- [ ] Sprint: nessun esploratore può leggere le altre direzioni (test sulla sandbox)
- [ ] Set di valutazione completo, nessuna regressione rispetto alla CLI
- [ ] Un gate fermo per giorni riprende dal checkpoint

---

## M3 — Contesto visivo e parallelo

1. Modello di scena comune per tutti i master; `Scene-Extractor` con bpy.
2. LanceDB + SigLIP locali: mondo del cliente, riferimenti, materiali.
3. Diversità tra direzioni misurata con gli embedding, accanto alle misure attuali.
4. Istanze MCP headless per lavoro; dismissione di `craft_lock`.
5. Controlli 3D, immagini e video: trimesh, OpenImageIO, ffprobe.

### Criteri di uscita

- [ ] Due autori sullo stesso server Craft in parallelo su file diversi, senza interferenze
- [ ] La ricerca visiva trova il materiale giusto su un archivio di prova, con precisione misurata
- [ ] La diversità con embedding distingue meglio la convergenza già vista negli sprint di prova
- [ ] Il modello di scena riduce le immagini lette per ticket, misurato

---

## M4 — Osservabilità e generazione

Il cruscotto di costi è passato a M1.6 (ADR-0019). Langfuse si rivaluta con quei dati: se non serve più, lo toglie un ADR nuovo.

1. Langfuse self-hosted con Docker, immagini bloccate per digest.
2. ComfyUI in container senza uscita di rete, senza Manager, nodi e pesi bloccati per hash.
3. Scheduler GPU per Blender, ComfyUI e SigLIP.
4. Provenienza: ogni immagine generata è marcata; non può diventare master o consegna finale.

### Criteri di uscita

- [ ] Una traccia completa di progetto, dal brief alla consegna, consultabile in locale
- [ ] Nessun dato cliente esce verso servizi diversi dall'API Anthropic (verificato sul traffico)
- [ ] Container ComfyUI senza uscita di rete (test)
- [ ] Licenza del modello verificata sul testo originale e registrata
- [ ] Blender e ComfyUI sotto carico contemporaneo senza errori di memoria

---

## M5 — Ottimizzazione

Solo con dati veri. Ordine: prima i guadagni gratuiti, poi i compromessi.

1. Cache: posizione dei breakpoint, TTL per ruolo, invalidazioni silenziose.
2. Sweep di `effort` per ruolo.
3. Modelli per ruolo: solo se le valutazioni lo reggono, con decisione esplicita.
4. Batch API per valutazioni e lavori asincroni (50% di sconto).
5. DSPy/GEPA solo dove c'è una metrica deterministica, in ambiente separato (ADR-0008).

### Criteri di uscita

- [ ] Riduzione di costo misurata a parità di punteggio sul set di test
- [ ] Ogni cambiamento di prompt ha un confronto registrato

---

## M6 — Passaggio definitivo

1. Interfaccia per il cliente su Django e Next.js, con account e permessi: tavole, feedback, approvazioni legate all'hash.
2. ADR su come il cliente raggiunge l'interfaccia: esposizione del server e correzioni di sicurezza senza quarantena.
3. Backup e ripristino di registro, master e artefatti, provati davvero.
4. Decisione sui dati del cliente verso l'API, scritta nel contratto.
5. Un progetto reale completo.

### Criteri di uscita

- [ ] Un cliente reale servito dalla scoperta alla consegna
- [ ] Ripristino da backup provato su una macchina pulita
- [ ] Setup CLI ufficialmente in pensione; `legacy/` resta come riferimento

---

## M7 — SaaS

**Domanda:** lo studio può servire più clienti paganti, separati tra loro, senza il nostro intervento su ogni lavoro?

Si dettaglia dopo M6, con i dati del primo cliente reale. Motivi e decisioni aperte in
[ADR-0023](adr/0023-il-progetto-diventa-un-saas.md).

1. Organizzazioni, ruoli e permessi per più clienti in Django, sopra gli account di M6.
2. Isolamento dei dati per cliente: registro, artefatti, checkpoint e tracce.
3. Lavori in coda, con worker separati dal server e sandbox fuori da questa macchina.
4. Piani, fatturazione e costo per cliente.
5. Rilascio, monitoraggio, backup e risposta agli incidenti.
6. Privacy, conservazione dei dati e contratti.

### Criteri di uscita

- [ ] Due clienti sullo stesso sistema: nessuno dei due vede i dati dell'altro (test)
- [ ] Un lavoro di un cliente pagante va dal brief alla consegna senza interventi manuali
- [ ] Il costo per cliente è noto prima di iniziare e misurato alla fine
- [ ] Ripristino dopo un guasto provato sull'ambiente reale

---

## Primo passo concreto

Il punto 13 di M1.6, senza spesa: il cruscotto Next.js in `web/`, con le sei viste e le difese di ADR-0024, che legge tutto
dall'API Django. Dopo M1.7, M2 parte dal contesto delle istanze lunghe, prima dei ruoli.
