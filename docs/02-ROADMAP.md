# Roadmap

Ogni traguardo finisce con un lavoro reale e con criteri verificabili, non con infrastruttura. Non si
passa al successivo con un criterio aperto. I tetti di spesa sono stime iniziali per le prove dal vivo:
si aggiornano con i dati di M1.

| # | Traguardo | Risultato | Tetto API | Stato |
|---|---|---|---|---|
| M0 | Fondamenta | Repo, contratti, registro, documenti, backup | 0 $ | **fatto** |
| M1 | Prova verticale | Un logo S dall'inizio alla fine, confrontato con la CLI | 40 $ | **chiuso**, confronto passato a M1.6 |
| M1.5 | Esplorazione a schizzi | Idee in parallelo, schizzi veloci, scelta del concetto, poi produzione | 40 $ | **chiuso**, 38,83 $ spesi, criteri non verificati passati a M1.6 e M2 |
| M1.6 | Misure e cruscotto | Dati confrontabili, `insights`, API Django, cruscotto Next.js | 30 $ | **chiuso**, 0 $ spesi, `merlo4` e confronto con la CLI passati a M1.9 |
| M1.7 | Architettura a slice | Motore diviso in slice, dipendenze imposte | 0 $ | **in corso**, punti 1–7 fatti, manca la revisione finale |
| M1.8 | Quality gate di Python | Un comando decide, niente soppressioni, hook che lo applicano da soli | 0 $ | |
| M1.9 | Prova reale | `merlo4` misurato e giudicato, confronto con la CLI | 30 $ + CLI | |
| M2 | Parità | Tutto lo studio, con replay di un'identità | 200 $ | |
| M3 | Contesto visivo e parallelo | Scena, ricerca visiva, istanze per lavoro | 60 $ | |
| M4 | Osservabilità e generazione | Langfuse, ComfyUI isolato, scheduler GPU | 60 $ | |
| M5 | Ottimizzazione | Taratura misurata di effort, modelli e prompt | 100 $ | |
| M6 | Passaggio definitivo | Primo cliente reale, interfaccia, CLI in pensione | da definire | |
| M7 | SaaS | Più clienti paganti, separati tra loro, sullo stesso sistema | da definire | |

M1.5 viene prima della parità perché cambia il modo in cui nasce ogni lavoro creativo: i ruoli si portano
una volta sola, sul flusso definitivo. M3 e M4 possono invertirsi. Gli altri sono in sequenza.

M1 e M1.5 sono chiusi il 2026-11-01 per decisione di Andrea, con alcuni criteri non verificati. Quei criteri non sono segnati
come fatti: passano a M1.6, dove si misurano su `merlo4`, oppure a M2. Il 2026-11-13 M1.6 si è chiuso allo stesso modo, e quelli
ancora aperti sono passati con `merlo4` a M1.9. In M1.9 gli obiettivi di costo si misurano ma non bloccano M2.

M1.6 e M1.7 vengono prima della parità perché M2 porta tutto lo studio sul motore: senza misure si lavorerebbe alla cieca, e
dopo dividere il codice costerebbe molto di più. Una prova dal vivo parte solo su richiesta, anche con il tetto in tabella. M7
viene dopo il primo cliente reale (ADR-0023).

M1.8 e M1.9 sono nati il 2026-11-13 per decisione di Andrea ([ADR-0055](adr/0055-il-quality-gate-prima-di-merlo4.md)).
`merlo4` non parte ora: arriva dopo il refactor e il gate, e misura il motore su cui si costruisce M2. M1.6 si è chiuso senza
prove dal vivo.

Fra M1.6 e M1.7 c'è stato l'audit deep-review, dal 2026-11-04 al 2026-11-13, entrato in `main` con `ceec412`. Non è un
traguardo: ha corretto 101 problemi, senza altri cambiamenti visibili all'utente, con gli ADR da 0044 a 0054. Il risultato è in
[`docs/audit/99-result.md`](audit/99-result.md). Ciò che ha rimandato passa a M1.7.

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
2. [x] **Risposte registrate**: registratore per ripetere nei test le chiamate senza spendere, collegato con
   `--record` dopo l'audit ([ADR-0048](adr/0048-le-esecuzioni-si-registrano-e-si-ripetono.md)).
3. [x] **Loop dell'agente**: solo in aggiunta, strumenti strict, `deliver`, tutti gli `stop_reason`.
4. [x] **Sandbox**: `agency.workshop.sandbox` su `bwrap`.
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

## M1.6 — Misure e cruscotto (chiuso)

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
17. [ ] **`merlo4`**: preparato il 2026-11-03, non avviato. Passato a M1.9 ([ADR-0055](adr/0055-il-quality-gate-prima-di-merlo4.md)).
18. [ ] **Confronto con la CLI** sullo stesso brief: passato a M1.9.

### Le viste

| Vista | Domanda | Contenuto |
|---|---|---|
| Run | Quanto è costato e quanto è durato? | Costo, tempo, budget, timeline delle istanze |
| Fasi | Dove si è fermato o è tornato indietro? | Dalle idee alla consegna, costo e rework per fase |
| Modello | Come ha lavorato? | Contesto turno per turno, cache, ragionamento, latenza e `stop_reason`, per ruolo |
| Strumenti e QA | Dove sbaglia? | Rifiuti con motivo, passaggi al primo colpo, ticket bloccati |
| Confronto | È meglio di prima? | Due esecuzioni affiancate, differenze di impronta, giudizi |
| Replay | Cosa è successo davvero? | Un'istanza turno per turno, con le immagini |

Una vista nuova entra solo se `merlo4`, in M1.9, mostra una domanda a cui queste non rispondono.

### Criteri di uscita

- [x] Gli snapshot di strumenti e system prompt stanno nei test e bloccano `make check`: `tests/test_request_snapshots.py`
- [x] `agency verify` passa su una copia del registro migrata: provato il 2026-11-02, con tutte le 3.814 righe identiche
  (`tests/test_migrations.py`)
- [x] Ogni nuova esecuzione registra la propria impronta, e due esecuzioni mostrano cosa è cambiato: `tests/test_runs.py` e
  `tests/test_flow_project.py`, a mano con `agency runs <progetto>` e `agency compare <n> <n>`
- [x] Ogni nuova chiamata registra in `usage` esecuzione, fase, effort, durata, TTFT e ragionamento: `tests/test_gateway.py` e
  `tests/test_flow_project.py`. Il TTFT dal vivo si vedrà con `merlo4`: i test lo misurano su uno stream simulato
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
- [ ] `merlo4` è arrivato al gate `final` ed è stato letto per intero nel cruscotto. Passa a M1.9

**Ereditati da M1 e M1.5:**

- [x] **Il segno scelto batte quello di `merlo` nel giudizio alla cieca di Andrea**: `merlo3` eccellente e migliore, `merlo`
  buono, il 2026-11-03 (punto 16). `uv run agency report merlo3`
- [ ] Stesso brief su CLI e harness: qualità non inferiore alla cieca. Passa a M1.9
- [ ] Stesso brief su CLI e harness: costo inferiore. Passa a M1.9
- [x] Il test di sostituzione passa: il segno scelto dice ciò che rende unico il cliente. Nello stesso giudizio Andrea ha detto
  che il segno di `merlo3`, con un altro nome, non reggerebbe. Nel perché ci legge il merlo, e nel cerchio vuoto la ruota e la
  chiave inglese dell'officina: la riparazione che in M1.5 diceva solo l'adesivo
- [ ] Presentazione pronta entro 45 minuti e 12 $, con 2 o 3 proposte confrontabili. Passa a M1.9
- [ ] Lavoro completo fino al gate `final` entro 22 $. Passa a M1.9

**Fuori da M1.6:** scritture dall'interfaccia, account, multi-tenancy, Langfuse, refactor del motore.

### Chiusura (2026-11-13)

Andrea ha chiuso M1.6 senza spesa: tutto il lavoro che non chiede prove dal vivo è fatto e verificato, punto per punto, con il
modo di rifarlo. `merlo4`, il confronto con la CLI e i criteri che li aspettavano passano a M1.9, dopo il refactor di M1.7 e il
gate di M1.8 ([ADR-0055](adr/0055-il-quality-gate-prima-di-merlo4.md)). Come per M1 e M1.5, quei criteri non sono segnati come
fatti.

---

## M1.7 — Architettura a slice

**Domanda a cui rispondere:** il motore può crescere fino a tutto lo studio senza che ogni ruolo nuovo tocchi gli stessi file?

Viene prima di `merlo4`, che passa a M1.9 ([ADR-0055](adr/0055-il-quality-gate-prima-di-merlo4.md)). Non ha prove dal vivo, né
prima né dopo il refactor ([ADR-0056](adr/0056-m1-7-senza-prova-dal-vivo.md)). Il comportamento del motore lo fissano gli
snapshot di strumenti e system prompt e i test di flusso con risposte registrate. La prima misura dal vivo del motore diviso è
`merlo4`, in M1.9. Principi e confini in [ADR-0021](adr/0021-monolite-modulare-a-slice.md), l'albero dei pacchetti in
[ADR-0057](adr/0057-l-albero-dei-pacchetti-del-motore.md). I punti 1–3 seguono il
[piano](superpowers/plans/2026-11-14-m1-7-slice-architecture.md), i punti 4–7 il
[secondo piano](superpowers/plans/2026-11-15-m1-7-plan-b-domain-ports-types.md). L'audit ha
rimandato qui alcuni problemi trovati; il codice e gli ID sono in `docs/audit/SUMMARY.md`.

### Lavoro, in ordine

1. [x] **Cicli**: spezzare quello tra `qa` e `tools`, l'unico rimasto tra i pacchetti di `agency`, insieme al montaggio QA
   della sandbox (STR-004). Quello tra `agents` e `tools` l'ha tolto l'audit (`73881ee`). Fatto il 2026-11-14: gli script
   QA si montano solo nei controlli, gli strumenti degli agenti sono in `agency.agents.toolbox`, e il contratto
   `acyclic_siblings` vieta ogni ciclo in `agency`, a ogni livello. Si rifà con `uv run lint-imports`.
2. [x] **`tools/surface.py`**: 1.130 righe dopo l'audit, divise per slice una alla volta (SIM-012). Fatto il 2026-11-14:
   il kit e gli strumenti condivisi in `agency.toolkit`, quelli di ogni fase nella sua slice di `agency.studio`, catalogo e
   `Toolbox` in `agency.agents.toolbox` (163 righe). Gli snapshot delle richieste sono identici:
   `uv run pytest tests/test_request_snapshots.py`.
3. [x] **`graph/workflow.py`**: i nodi passano alle slice, `process` compone il grafo. `build` ha complessità McCabe 63
   (SIM-012), e l'import di `langchain_core` passa al livello del processo (SIM-004). Fatto il 2026-11-15: i nodi stanno
   nelle slice di `agency.studio`, come factory che ricevono il `Crew`; `agency.process` compone il grafo (`graph.py`) e
   apre le sessioni (`session.py`). `build` scende da 65 a 2; tra grafo e slice resta sopra 10 solo la factory `select`
   (11), che M1.8 divide. `langchain_core` lo importa solo `process/session.py`. Si rifà con
   `uv run ruff check --select C901 --config "lint.mccabe.max-complexity = 10" src/agency/process src/agency/studio` e
   `grep -rn langchain_core src`.
4. [x] **Dominio e applicazione**: regole pure, casi d'uso e porte fuori dai framework. La CLI passa in `entrypoints/cli/`
   con il suo renderer (STR-007). Fatto il 2026-11-15:
   - ogni slice ha `domain.py`, con le regole pure, e `application.py`, con i nodi senza LangGraph; `tools.py` e `nodes.py`
     sono gli adattatori;
   - le porte stanno in `agency.contracts`: il registro (`LedgerPort` e le porte per argomento, con record al posto delle
     righe), la sandbox (`SandboxPort`), gli artefatti (`ArtifactStore`); il modello resta dietro `Transport`;
   - la CLI, con il renderer e `doctor`, sta in `agency.entrypoints.cli`, e l'impronta delle esecuzioni in `process`.

   Si rifà con `uv run lint-imports` e `uv run pytest tests/test_domain_*.py`.
5. [x] **`import-linter` bloccante** su tutto il pacchetto, con le regole di ADR-0021 ancora mancanti: `langgraph` solo nel
   processo e nei nodi, `sqlmodel` solo nel registro, il registro solo dietro la sua porta (STR-003). Fatto il 2026-11-15:
   i livelli di ADR-0057, `langgraph` e l'ORM sono contratti, e solo la sessione e la CLI arrivano al registro SQLite. I
   contratti sono tredici, e un test controlla ogni lista scritta a mano: `uv run lint-imports` → 13 kept.
6. [x] **Piramide dei test**: nuovi test sulle regole pure. I test di flusso restano: sono la rete del refactor. I quattro file
   di test sopra le 500 righe e `globals.css` si dividono con le slice (STR-013). Fatto il 2026-11-15:
   - 32 test unitari sulle regole pure delle slice (`tests/test_domain_*.py`);
   - `test_agent_flow.py` e `test_sketch_flow.py` sono diventati 16 file, uno per slice o per argomento;
     `test_hardening.py`, `test_safe_files.py` e `test_insights.py` sono diventati 15 file, nessuno sopra le 500 righe;
   - `globals.css` è diviso in sette fogli, importati da `layout.tsx` nell'ordine di prima.

   Restano sopra le 500 righe sette file di test che l'audit non nominava: `test_ledger.py` (1.033), `test_server.py`
   (759), `test_qa_gates.py` (691), `test_migrations.py` (678), `test_judgments.py` (599), `test_gateway.py` (589),
   `test_artifacts.py` (575).
7. [x] **Tipi espliciti** (principio 2 di ADR-0021). Fatto il 2026-11-15:
   - `DirectorMode` e `Route` sono `Literal`, così nel checkpoint restano le stringhe di prima; i nodi restituiscono
     `ProjectUpdate`, e i due nodi paralleli ricevono `TicketTask`. Un test fissa canali e schemi d'ingresso del grafo:
     `uv run pytest tests/test_gate_sandbox.py -k channels`;
   - le regole dello studio sono `StudioRules`, tipizzate, caricate da `load_rules` e passate a chi le usa:
     `uv run pytest tests/test_registry.py -k "typed_rules or global"`.

### Criteri di uscita

Verificati il 2026-11-15, ciascuno con il comando che lo riproduce.

- [x] `tools/surface.py` non esiste più, e non ci sono cicli tra pacchetti: `test ! -d src/agency/tools` e
  `uv run lint-imports` → `acyclic_siblings` KEPT
- [x] Gli snapshot di strumenti e system prompt sono identici a quelli di M1.6: `git diff --quiet 38f1f16 HEAD --
  tests/snapshots` e `uv run pytest tests/test_request_snapshots.py` → 12 passed
- [x] I test di flusso passano senza cambiare un'asserzione, una risposta registrata o un turno scritto
  ([ADR-0058](adr/0058-porte-tipi-e-livelli-del-motore.md)). Confrontati test per test con l'inizio di M1.7 (`38f1f16`),
  154 dei 156 hanno ogni `assert` identico, e nessuno è stato aggiunto o tolto. I due restanti cambiano dentro
  l'asserzione, senza cambiare cosa verificano:
  - `test_the_reminder_offers_every_closing_tool_but_reject_concept` legge da `Tool.closes` l'insieme che prima leggeva
    da `CLOSE_ALWAYS`, perché il refactor ha spostato proprio quel dato;
  - `test_each_phase_has_only_its_tools` passa `RULES` a `tools_for`, perché le regole ora si passano.
- [x] Dominio e applicazione non importano framework: `uv run lint-imports` → i due contratti di ADR-0058 KEPT
- [x] Fasi, rotte e ruoli sono tipi: `git grep -nE "mode: str|route: str" src/agency` non trova niente, e
  `uv run pytest tests/test_explicit_types.py tests/test_registry.py tests/test_gate_sandbox.py` → 58 passed
- [x] Ogni principio di ADR-0021 è verificato uno per uno: la tabella qui sotto

### ADR-0021, principio per principio

| Principio | Come è nel codice | Comando | Risultato (2026-11-15) |
|---|---|---|---|
| Modular monolith in vertical slices | Un solo pacchetto. Le sei capacità sono slice di `agency.studio` (`exploration`, `selection`, `proposal`, `presentation`, `refinement`, `delivery`), `insights` è la slice di lettura, la piattaforma è condivisa | `uv run lint-imports` | «the slices do not import each other» KEPT |
| Explicit over implicit | Stato del grafo in `ProjectState` e `ProjectUpdate`, fasi in `DirectorMode`, rotte in `Route`, gate in `ConceptGate` e `FinalGate`, regole in `StudioRules`. Strumenti e slice elencati a mano. Il `Crew` porta runner, registro, regole e sandbox ai nodi | `uv run pytest tests/test_explicit_types.py tests/test_registry.py tests/test_gate_sandbox.py` | 58 passed. Restano `dict[str, Any]` solo per il JSON grezzo prima della convalida, la catena degli hash, il `.env` e il risultato di LangGraph: nessuno è uno stato o un contratto |
| Clean Architecture | I livelli di ADR-0057. Il dominio dipende solo dai contratti, l'applicazione non importa framework né adattatori. Porte ai confini: modello (`Transport`), registro (`LedgerPort`), sandbox (`SandboxPort`), artefatti (`ArtifactStore`), lettura (le porte di `insights`) | `uv run lint-imports` e `uv run pytest tests/test_ledger.py tests/test_qa_gates.py -k "ledger_port or sandbox_port"` | 13 kept; il registro SQLite e la sandbox bwrap soddisfano le loro porte, metodo per metodo (pyright) |
| Schema-First Design | Lo schema OpenAPI generato e i tipi TypeScript che ne derivano (ADR-0022) | `pnpm --dir web run api:check` | esce con 0 |
| Testing pyramid | 32 test sulle regole pure delle slice, più quelli di `insights`; 47 test di flusso per slice; 18 flussi completi (`test_flow_gates.py`, `test_recording.py`); 24 prove Playwright per le viste | `make check` | 1.284 test Python e 24 Playwright passano |
| Confini delle librerie | `anthropic` solo nel gateway; `langgraph` solo nel processo, nei nodi e in `studio.graph`; l'ORM solo nel registro; Django solo nel server | `uv run lint-imports` | i quattro contratti KEPT |

**Fuori da M1.7:** ruoli nuovi, comandi dal cruscotto, multi-tenancy, il quality gate (M1.8).

---

## M1.8 — Quality gate di Python

**Domanda a cui rispondere:** un solo comando può dire se il Python che cambia è pulito, provato e senza scorciatoie, prima che
M2 porti sul motore il resto dello studio?

Lo stato finale è nella [specifica](quality-gate/SPEC.md): cinque proprietà, P1–P5, e i criteri di accettazione A1–A9. La
specifica non dà l'ordine di costruzione, lo dà questa roadmap. Il codice esistente non si sistema in blocco: chi tocca un file
lo ripulisce tutto, e così il repository va verso `full` verde. Motivi e conflitti con le decisioni già prese in
[ADR-0055](adr/0055-il-quality-gate-prima-di-merlo4.md).

### Parametri proposti

I parametri della §2 della specifica, da confermare al punto 1.

| Parametro | Valore proposto | Da dove |
|---|---|---|
| `<RUNNER>` | `uv run` | `CLAUDE.md` |
| `<ENV_PY>` | `.venv/bin/python` | uv |
| `<PY>` | `3.13` | `requires-python`; `.python-version` fissa 3.13.15 |
| `<PKGS>` | `agency`, in `src/agency` | `pyproject.toml` |
| `<TESTS>` | `tests` | `pyproject.toml` |
| `<BASE_BRANCH>` | nessuno finché non c'è un remoto | ADR-0051 |
| `<T_SUITE>` | da misurare con `coverage run`. Senza, pytest dura 84,6 s dentro `make check` | `docs/audit/99-result.md` |

### Decisioni da prendere prima di scrivere il gate

- **D1–D5 della specifica (§3).**
  - D1: pyright va sostituito da basedpyright. Ruff oggi usa sette famiglie di regole e righe da 110. `[tool.pytest.ini_options]`
    diventa `[tool.pytest]`, con pytest 9.
  - D2: i sette contratti di import-linter di oggi reggono già.
  - D3: la CI aspetta il remoto.
  - D4: i candidati sono `legacy/` e `src/agency/qa/scripts/`.
- **I conflitti di ADR-0055.** Vanno decisi:
  - il pre-commit contro `.githooks/` (ADR-0051);
  - `task check` e i test che lo fissano;
  - la quarantena di ADR-0006;
  - la risposta a Q14 dell'audit;
  - `.claude/` ignorata da git;
  - la memoria in `~/.claude/`;
  - l'ambiente della sandbox;
  - le prove saltate.

### Lavoro, in ordine

Il gate si costruisce in una sessione di manutenzione con gli hook spenti, perché il guard vieta di scrivere in `quality_gate/`.
Gli hook si accendono per ultimi. Il blocco della configurazione lo genera Andrea dal suo terminale.

1. [ ] **Parametri, decisioni e ADR**: parametri confermati, D1–D5 decise, un ADR per ogni decisione accettata che cambia.
2. [ ] **Dipendenze**: il gruppo `quality` pinnato con `==` dentro la quarantena (ADR-0006), il lock aggiornato. Si tolgono gli
   strumenti che il gate sostituisce (D1).
3. [ ] **Configurazione**: le tabelle della §6 in `pyproject.toml` e `.flake8`, con le sole eccezioni della §6.10.
4. [ ] **Nucleo**: modi `file`, `changed` e `full`, scoperta dei file, esecuzione e rapporto, con i controlli per file (§7). Solo
   `execution.py` lancia processi.
5. [ ] **Controlli di progetto**: contratti, codice morto, dipendenze, duplicazione, test, copertura e copertura delle righe
   cambiate, con i filtri del ratchet (§7.5).
6. [ ] **Anti-aggiramento**: soppressioni, configurazioni ombra, blocco della configurazione e modo `lock`, integrità di hook,
   versioni e test (§8).
7. [ ] **`BASELINE.md`**: conteggi e durate iniziali di `full`, regole più frequenti, copertura di oggi, contratti attivi e in
   attesa, eccezioni.
8. [ ] **Collegamenti**: l'hook di commit, secondo la decisione su ADR-0051. Gli alias `gate`, `gate-full`, `gate-mutation` e
   `gate-lock` nel Taskfile, con gli alias `make`. La parte Python di `task check` passa dal gate.
9. [ ] **Il gate rispetta se stesso**: zero violazioni, rami coperti al 100% e mutation ≥ 90% su `quality_gate/` (P5).
10. [ ] **Hook di Claude Code e regole degli agenti**: `.claude/settings.json`, `AGENTS.md`, `@AGENTS.md` in `CLAUDE.md` (§9,
    §10.4).
11. [ ] **Prove**: canarini, hook con JSON di esempio, tempi e pulizia (A4–A7). In `DEVIATIONS.md` ogni differenza dalla
    specifica, con la sua prova.
12. [ ] **Blocco**: Andrea genera `config.lock` con `make gate-lock` dal suo terminale, poi fa il commit con
    `QUALITY_GATE_LOCK_CHANGE_OK=1 git commit`.

### Criteri di uscita

Sono i criteri della §11 della specifica, ognuno con la sua prova.

- [ ] A1: ogni pacchetto della §5 pinnato con `==`, lock aggiornato, `tool-versions` passa
- [ ] A2: `full` esegue tutti i controlli ed esce 1 sul codice di oggi; `changed` su un albero pulito esce 0
- [ ] A3: `quality_gate/` senza violazioni, con righe e rami coperti al 100% e mutation sopra la soglia
- [ ] A4: ogni canarino della §11 fa fallire il suo controllo
- [ ] A5: ogni ingresso degli hook dà l'esito atteso
- [ ] A6: `hook guard` ≤ 300 ms, `file` ≤ 15 s, `staged` su 10 file ≤ 30 s, `changed` ≤ `<T_SUITE>` + 60 s
- [ ] A7: nessun canarino rimasto, nessun file applicativo o di test cambiato oltre le eccezioni decise al punto 1
- [ ] A8: `config.lock` generato da Andrea, `config-lock` passa
- [ ] A9: `DEVIATIONS.md` e `BASELINE.md` completi

**Fuori da M1.8:** ripulire il codice esistente, la CI (aspetta il remoto), regole di qualità per TypeScript (DX-008 dell'audit:
un ADR a parte).

---

## M1.9 — Prova reale

**Domanda a cui rispondere:** il motore diviso in slice e sotto il gate lavora almeno come `merlo3`, e come la CLI, spendendo
meno?

Sono le prove dal vivo di M1.6, spostate dopo M1.7 e M1.8 ([ADR-0055](adr/0055-il-quality-gate-prima-di-merlo4.md)). Una prova
dal vivo parte solo su richiesta di Andrea.

### Lavoro, in ordine

1. [ ] **`merlo4`**: brief E1 dal vivo, tetto 30 $. Prima esecuzione con impronta, e con ADR-0017 e ADR-0018 attivi
   dall'inizio. Con i costi di `merlo3` il tetto è stretto: si rivede prima di partire. È una prova sola, quindi il risultato è
   indicativo: le 3 prove di `07-EVALS.md` costerebbero circa 100 $.
   - [x] Preparato il 2026-11-03, senza spesa. Il brief è identico a quello di `merlo` e `merlo3`. Il tetto si dichiara per forza
     all'avvio ([ADR-0043](adr/0043-il-tetto-si-dichiara-all-avvio.md)): l'ambiente di Andrea ne dava uno di 40 $.
   - [x] Il segno da battere è quello di `merlo3` ([ADR-0042](adr/0042-il-riferimento-di-qualita-e-merlo3.md)).
   - [ ] Preparazione da rifare dopo M1.8. `agency doctor` deve passare. L'impronta di partenza cambia, perché cambia il codice:
     quella del 2026-11-03 era 5 esploratori, effort `high` e `vectorcraft-cli` 0.18.0, che il 2026-11-14 sulla macchina è
     0.23.0. Il registro vero è già alla revisione 0009, letta il 2026-11-13.
   - [ ] Avvio, da Andrea, con il tetto che dichiara: `uv run agency run merlo4 evals/briefs/E1.md --budget <usd> --record`
   - [ ] Gate `concept` e gate `final` decisi da Andrea, con `agency decide merlo4`
   - [ ] Giudizio alla cieca del segno finale contro quello di `merlo3`, e lettura per intero nel cruscotto
2. [ ] **Confronto con la CLI** sullo stesso brief. Questa prova ha un tetto proprio, da dichiarare prima di partire.

### Criteri di uscita

- [ ] `merlo4` è arrivato al gate `final` ed è stato letto per intero nel cruscotto
- [ ] Il TTFT si legge dal vivo in `usage`: in M1.6 i test lo misuravano su uno stream simulato
- [ ] Hit rate della cache e contesto fisso non peggiori di `merlo3`, letti nel cruscotto. Era il criterio di E2 in M1.7
  ([ADR-0056](adr/0056-m1-7-senza-prova-dal-vivo.md))

**Ereditati da M1, M1.5 e M1.6:**

- [ ] Stesso brief su CLI e harness: qualità non inferiore alla cieca
- [ ] Stesso brief su CLI e harness: costo inferiore
- [ ] Presentazione pronta entro 45 minuti e 12 $, con 2 o 3 proposte confrontabili
- [ ] Lavoro completo fino al gate `final` entro 22 $

La qualità decide se si prosegue: se risulta inferiore alla CLI vale ancora la regola di M1, ci si ferma e si capisce perché. Gli
obiettivi di costo, compreso il confronto con la CLI, si misurano su `merlo4`: se restano lontani non bloccano M2, e si affrontano
con il contesto delle istanze lunghe, il primo lavoro di M2.

**Fuori da M1.9:** le 3 prove per brief di `07-EVALS.md`. Una prova sola dà un risultato indicativo.

---

## M2 — Parità

**Domanda:** tutto ciò che lo studio sapeva fare esiste ancora?

Si costruisce sulle slice di M1.7, sotto il gate di M1.8, dopo la prova reale di M1.9.

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
- Il campo `craft` di `registry/roles.json` è applicato (`tools` dichiara l'insieme di strumenti di ogni ruolo; `craft_*` rifiutano un'app che il ruolo non elenca). Resta da fare: un `app` per strumento, con enum nello schema, quando arrivano le altre app Craft.
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

La revisione finale del secondo piano di M1.7, con un revisore che non ha scritto il codice. Poi M1.7 si chiude, e il
prossimo è M1.8, il quality gate. Dopo M1.9, M2 parte dal contesto delle istanze lunghe, prima dei ruoli.
