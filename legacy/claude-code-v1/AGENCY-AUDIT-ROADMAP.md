# Audit e roadmap della design agency

Data: 29 ottobre 2026. Workspace esaminato: `claude-config-ui`.

Durante l'audit il setup è stato spostato dalla radice a `src/` e il percorso MCP della memoria è passato da `memory.jsonl` a `memory.json`. La verifica finale e i riscontri sotto riflettono questo aggiornamento. I percorsi `.claude/` e `.mcp.json` indicati nel documento sono relativi alla radice del setup, attualmente `src/`, salvo diversa indicazione.

Questo documento distingue lo stato osservato dalle proposte. La configurazione esistente non è stata modificata.

## Valutazione

Il setup contiene un buon protocollo di produzione e controllo qualità, ma non costituisce ancora un'agenzia operativa completa. Le priorità sono: rendere veritiera la documentazione, isolare i progetti, dimostrare la ripresa del lavoro, quindi sviluppare e valutare le competenze creative.

L'obiettivo economico consigliato è **minimizzare i token complessivi per un risultato accettato**, mantenendo una soglia di qualità. Una ricerca o una review aggiuntiva può costare meno di rifare un'identità dopo averla applicata a decine di asset.

## Evidenze dell'audit

| Priorità | Riscontro | Evidenza e conseguenza |
|---|---|---|
| P0 | Implementazione incompleta rispetto alla consegna dichiarata | `HANDOFF.md:36–43` descrive agenti, script, hook e `.claude/settings.json`. Questi percorsi sono assenti nel workspace. Non si possono considerare operative quelle automazioni. |
| P0 | Comando di avvio e preflight incompleti | README e skill preflight richiamano `start-agency.sh` e `validate_agency.py`, entrambi assenti. |
| P0 | Stato cliente incluso nel setup riutilizzabile | `.claude/PROGRESS.md` contiene Monad, Tiempos, palette, artboard, percorsi esterni, approvazioni e una prossima azione relativa al brand book. |
| P0 | Persistenza ancora da dimostrare | Il percorso attuale `.claude/memory.json` è coerente tra configurazione e guide; il grafo non è presente qui e mancano gli hook descritti. Il precedente disallineamento `.json`/`.jsonl` è stato risolto durante l'audit. |
| P0 | Runtime fuori dal requisito del server disponibile | Node osservato: `22.22.1`. Pacchetto memory in cache: `2.0.1`, con `engines.node >=24`. Il comando non seleziona una versione compatibile. Questo è un disallineamento verificato, non la prova che ogni operazione fallisca. |
| P1 | Confinamento dei tool descritto ma non configurato qui | Le due CLI supportano root di lettura/scrittura; `.mcp.json` non passa questi flag. L'istruzione testuale di restare nella cartella non implementa il confinamento dichiarato in CRAFT.md. |
| P1 | Storico non verificabile in questo workspace | `git status` restituisce “not a git repository”. La directory `.git` visibile non contiene un repository utilizzabile. La disponibilità dello storico non va data per acquisita. |
| P1 | Distribuzione affidata a una procedura manuale | Non c'è `.gitignore` nel setup; HANDOFF elenca esclusioni da applicare copiando i file. Senza un elenco di distribuzione verificato si può trasportare lo stato del cliente. |
| P1 | Riproducibilità delle dipendenze insufficiente | Context7 usa `@latest`; memory e sequential-thinking non fissano una versione. Un avvio successivo può risolvere un pacchetto diverso. |
| P1 | Ruoli presenti solo come descrizioni | Otto nomi in CLAUDE.md, nessuna definizione in `.claude/agents/`; anche `~/.claude/agents/` è assente. Non risultano agenti locali configurati per quei ruoli. |
| P2 | Copertura creativa generale | Quattro skill locali; i fondamenti trattano bene diversi controlli ma non articolano processi completi per strategia di marca, logo, identità verbale, motion identity e governance dei token. |
| P2 | Piccola ambiguità nelle fonti | `SOURCES.md` assegna `M1` sia a Carbon Motion sia al server memory. Rendere gli identificatori univoci. |

Le due configurazioni JSON locali sono sintatticamente valide. I link Markdown relativi esaminati risolvono; questo controllo da solo non scopre gli script mancanti citati nei blocchi di codice. La separazione in `src/` richiede anche di distinguere la directory sorgente del template dalla radice in cui verrà installato e avviato.

Sono presenti 15 file Markdown, circa 7.469 parole. CLAUDE.md ha 84 righe e circa 825 parole: la sua dimensione, da sola, non è il problema principale. Il totale dei documenti **non equivale al contesto caricato a ogni turno**.

Versioni locali osservate: Claude Code `2.1.312`, VectorCraft `0.18.0`, EffectCraft `0.18.0`. Ho verificato presenza, versione e help delle CLI; non ho eseguito una sessione Claude autenticata, chiamate Craft di produzione o il test memory tra due processi. Questi controlli restano `NOT_VERIFIED`.

Nella configurazione globale letta compaiono marketplace aggiuntivi e una preferenza di effort alto per un modello. Il registro `installed_plugins.json` è vuoto; directory in cache e marketplace scaricati non provano che i relativi plugin siano attivi. Non ho aperto credenziali o trascrizioni private. Le impostazioni lette non provano da sole il modello effettivamente usato da una sessione.

## Elementi da conservare

- Brief con requisiti verificabili e distinzione tra fatti, ipotesi e preferenze.
- Esplorazione di direzioni diverse prima della produzione costosa.
- Master editabili, export osservati e riapertura dei file.
- Reviewer che esamina gli artefatti e localizza i difetti.
- Stati `PASS`, `FAIL`, `NOT_VERIFIED`, `NOT_APPLICABLE` e severità separate.
- Un solo autore per connessione Craft condivisa; nessuna apertura concorrente che cambi il documento attivo.
- Salvataggi a milestone e nessun backup o commit automatico.
- Distinzione tra standard applicabili e scelte estetiche dello studio.

## Architettura proposta

Separare quattro responsabilità:

| Livello | Contenuto | Caricamento |
|---|---|---|
| Core dell'agenzia | Regole brevi, instradamento, contratti degli agenti, procedura di recupero | Sempre, in forma minima |
| Competenze | Workflow, rubriche, riferimenti, esempi e procedure dei tool | Solo per la fase e il ruolo attivi |
| Progetto | Identità del progetto, brief, decisioni, token, asset, stato e prove | Solo il progetto assegnato |
| Runtime | Cache, lock, file temporanei, diagnostica tecnica | Solo quando necessari |

Struttura indicativa: i percorsi del lavoro possono essere diversi e vanno dichiarati nel manifest.

```text
.claude/
  CLAUDE.md                 # nucleo breve e instradamento
  settings.json             # hook condivisibili, realmente implementati
  agents/                   # pochi ruoli con contratti verificabili
  skills/                   # competenze caricate su richiesta
  design-agency/            # riferimenti e template
  scripts/                  # avvio, diagnostica, validazione
  hooks/                    # recupero e verifica dello stato
  memory.json               # indice MCP locale in JSONL; escluso dal template
  runtime/                  # cache e temporanei; esclusi dal template
.mcp.json
.agency/
  project.yaml              # ID stabile, scope, percorsi, profilo di tool
  STATE.md                  # stato corrente e prossima azione
  decisions.md              # decisioni, ragioni, approvazioni, superamenti
  evidence.json             # indice delle prove e delle revisioni degli asset
work/
  brief.md
  strategy.md
  direction.md
  tokens.json
  source/
  exports/
  proofs/
  delivery.md
```

`project.yaml` contiene uno schema versionato, un ID stabile indipendente dal nome della cartella, il nome visualizzato, lingue, obiettivi, percorsi e deliverable. Il core non contiene nomi di cliente, font, palette o dimensioni specifiche. Le preferenze trasversali dell'utente sono separate dalle preferenze del cliente.

I percorsi proposti sono una convenzione dello studio. Non creare tutti i file per ogni microintervento: materializzarli quando esiste contenuto utile.

La prima distribuzione può essere un template versionato con installazione ripetibile. Il plugin è un'opzione successiva, quando il contratto è stabile: nella documentazione corrente alcuni campi degli agenti, fra cui `mcpServers` e hook, vengono ignorati negli agenti distribuiti tramite plugin e richiedono un adattamento. [Documentazione subagent](https://code.claude.com/docs/en/sub-agents).

## Roadmap ordinata

### 1. P0 — Allineare realtà e documentazione

Produrre un inventario con tre stati: implementato, pianificato, verificato. Correggere HANDOFF e README; implementare soltanto launcher, agenti e controlli necessari alla prima pipeline funzionante. Scegliere una combinazione Node/server memory supportata, versionare le dipendenze e mantenere un unico percorso della memoria. Quello attuale, `.claude/memory.json`, può restare: il contenuto è JSONL anche se il suffisso è `.json`. Un'eventuale rinomina deve essere una migrazione esplicita.

La v2 corrente del server memory dichiara Node >=24. Aggiornare il runtime oppure scegliere una release compatibile verificata; evitare la scelta implicita della versione tramite `npx` senza pin. [Manifest ufficiale memory](https://github.com/modelcontextprotocol/servers/blob/main/src/memory/package.json).

Verificare le root dei tool con gli help installati. Il comando memory usa la variabile dentro la shell del processo figlio: Claude Code documenta `CLAUDE_PROJECT_DIR` nell'ambiente dei server stdio; questa forma non va confusa con l'espansione `${VAR}` del file MCP. [Documentazione MCP](https://code.claude.com/docs/en/mcp).

**Uscita:** un avvio documentato funziona da una directory con spazi; il preflight segnala precisamente componenti assenti o incompatibili; nessun controllo dichiarato come eseguito senza prova.

### 2. P0 — Rendere il template indipendente dal cliente

Conservare lo stato Monad nel suo contesto cliente, fuori dal template distribuibile. Non cancellare la conoscenza durante la pulizia. Eliminare dal core i riferimenti operativi ad `assets/`, percorsi personali e specifiche del vecchio lavoro. Aggiungere manifest, esclusioni e regole di migrazione.

Distribuire i file dell'agenzia tramite un elenco esplicito; escludere memoria, fallback, runtime, impostazioni personali e asset. Integrare `.mcp.json` senza sovrascrivere server preesistenti. Eseguire il bootstrap due volte senza creare duplicati o perdere configurazione.

**Uscita:** due progetti nuovi con nomi, settori e lingue diversi partono senza riferimenti al precedente. Rinominare o spostare la cartella non cambia l'identità del progetto né rompe i percorsi relativi.

### 3. P0 — Dimostrare una ripresa affidabile

Raccomandazione: documenti del progetto come fonte autorevole; MCP come indice e sintesi del contesto utile. Mantenere MCP è compatibile con questa architettura. Evitare che grafo, auto memory, fallback e diario contengano quattro versioni indipendenti dello stesso stato.

Contratto iniziale per `STATE.md`:

```text
project_id / schema_version / state_revision
fase e obiettivo corrente
brief e decisioni approvate: riferimenti
master assegnato, revisione e stato di salvataggio
ultimo passaggio completato e verificato
lavoro interrotto / operazione con esito incerto
difetti o domande aperte
prossima azione concreta e relativo criterio di completamento
file minimi da leggere
revisioni delle prove / stato di sincronizzazione MCP
```

Conservare le alternative scartate e la loro motivazione in `decisions.md`, con un indice corto. Questo evita di riproporre una soluzione già rifiutata. Salvare le decisioni approvate esplicitamente dall'utente distinguendole dalle raccomandazioni autonome.

Al recupero: identificare il progetto, leggere lo stato breve, verificare file e revisioni, ispezionare la sessione Craft, aprire solo i riferimenti necessari e proseguire. Dopo un timeout di modifica controllare l'artefatto prima di ripetere l'operazione.

Scrivere lo stato a milestone; usare un singolo autore e scritture atomiche. Un eventuale lock transitorio protegge dagli aggiornamenti concorrenti, senza creare copie storiche degli asset. Registrare una revisione sincronizzata: se l'indice MCP è vecchio, ricostruirlo dai documenti autorevoli.

Gli hook proposti sono piccoli programmi deterministici: `SessionStart` recupera un indice limitato; `PreCompact` controlla il checkpoint disponibile; `Stop` interviene solo se esiste stato utile non salvato e rispetta la protezione dai loop. Un hook shell non può ricostruire da solo una decisione che nessuno ha registrato. `Stop` non copre tutte le interruzioni. [Riferimento hook](https://code.claude.com/docs/en/hooks).

**Uscita:** dopo nuovo processo, compattazione e interruzione simulata, Claude identifica progetto, master, ultimo punto sicuro e prossimo passo senza chiedere di raccontare nuovamente la storia. Un MCP indisponibile non impedisce di leggere lo stato locale.

### 4. P1 — Misurare e ridurre il costo del contesto

Memoria persistente e prompt cache svolgono funzioni diverse. La prima conserva fatti e decisioni; la seconda riutilizza temporaneamente prefissi già elaborati. La cache ha durata limitata, non sostituisce i file e non elimina lo spazio occupato nel contesto. Claude Code la gestisce automaticamente; stabilità di modello e configurazione favorisce il riuso. [Prompt caching](https://code.claude.com/docs/en/prompt-caching).

Le skill caricano il corpo quando invocate; le skill precaricate in un subagent entrano invece nel suo contesto iniziale. Gli import in CLAUDE.md non riducono il testo caricato. Usare descrizioni precise e riferimenti tematici, evitando il pre-caricamento di tutti i fondamenti in ogni ruolo. [Skill](https://code.claude.com/docs/en/skills), [memoria e istruzioni](https://code.claude.com/docs/en/memory).

Azioni:

- Lasciare nel core regole invarianti, instradamento e recupero; spostare il troubleshooting storico nella guida pertinente.
- Usare profili stabili per branding, motion e implementazione digitale; Context7 solo dove serve documentazione software. Sequential-thinking opzionale, da mantenere soltanto se migliora risultati misurati.
- Sfruttare la discovery differita; non scaricare cataloghi o documenti completi a ogni operazione. Gli schemi MCP sono differiti per default nella documentazione corrente, quindi cinque server configurati non implicano automaticamente cinque cataloghi completi nel prompt. [Gestione costi](https://code.claude.com/docs/en/costs).
- Affidare conteggi, dimensioni, hash, confronto dei token e metadati media a script; restituire sintesi ed errori, non log integrali.
- Usare agenti quando il lavoro isolato o la review giustificano il costo. Un ruolo professionale può essere una skill dello stesso agente.
- Richiedere risultati brevi dagli specialisti: file modificati, decisioni, prove, difetti, azione successiva. Conservare dettagli nei file pertinenti.
- Confrontare modelli/effort su incarichi uguali, preservando quelli più capaci per le decisioni creative difficili. Non ottimizzare il numero di token a scapito del risultato finale.

Obiettivi iniziali proposti, da calibrare e non considerare limiti ufficiali: core circa 800–1.200 token, stato 300–600, pacchetto di ripresa entro circa 2.500 token di testo personalizzato. Il conteggio esclude prompt di sistema e componenti del client. Misurare il costo reale di immagini, tool e subagent.

**Uscita:** baseline e confronto su almeno tre incarichi; nessuna percentuale di risparmio promessa prima delle misure. Rilevare `/context`, `/usage`, token complessivi, cache, numero di deleghe e cicli di revisione.

### 5. P1 — Sviluppare competenze creative specialistiche

Ogni competenza deve definire input minimi, passaggi, deliverable, errori tipici, criteri di review ed esempi annotati. Le seguenti sono proposte di progettazione dello studio.

| Competenza | Contenuti da sviluppare | Prove e risultati |
|---|---|---|
| Strategia e identità completa | Pubblico e contesto, categoria, differenziazione, promessa, prove, personalità, voce, messaggi, eventuale architettura di marca; ricerca distinta dalle ipotesi | Brief strategico, principi di marca e criteri con cui scegliere la direzione |
| Direzione artistica | Territori concettuali, tensione visiva, semantica, riferimenti motivati, composizione, fotografia, illustrazione, materia e trattamento editoriale | 2–3 direzioni sostanziali e applicazioni confrontabili, con ragioni della scelta |
| Logo e lettering | Esplorazione di segno e logotipo, spazio negativo, curve, kerning ottico, proporzioni, famiglie di lockup, adattamenti alle scale | Master, monocromia, positivo/negativo, dimensioni minime provate, uso reale e varianti necessarie |
| Colore, tipografia e scale | Ruoli semantici, gamut e supporti, contrasti per coppie, lingue e glifi, metriche dei font, licenze, gerarchie, spaziature e griglie | Token, specimen con contenuti reali, matrice di uso e verifiche sul supporto |
| Motion identity | Principi di movimento derivati dalla marca, storyboard, styleframe, animatic, ritmo, pause, easing, transizioni, comportamento del logo, audio se pertinente | Master, render osservati in playback, regole riutilizzabili, varianti di durata/formato e riduzione del movimento |
| Applicazioni e brand guidelines | Coerenza tra segno, linguaggio visivo, testi e movimento; esempi editoriali, digitali e fisici selezionati dal brief | Brand book, applicazioni convincenti, istruzioni per i futuri autori |
| Review e consegna | Verifica tecnica, critica creativa, tracciabilità delle decisioni, export e interoperabilità | Difetti localizzati, prove associate alla revisione corretta, pacchetto realmente apribile |

Per i loghi aggiungere una ricerca documentata di somiglianze visive; non trasformare il giudizio del modello in una verifica legale. Per colori destinati alla stampa chiedere le condizioni effettive di produzione prima di fissare equivalenze. Per il motion mantenere una grammatica comune con il sistema statico.

L'ambizione Awwwards può guidare cura, originalità e presentazione. La scelta concreta nasce dal posizionamento: un'identità sobria, una massimalista e una tecnica devono essere tutte possibili senza riscrivere il core.

**Uscita:** ogni competenza completa un brief campione con artefatti e review; nessuna skill consiste soltanto nell'invito a essere “premium” o “world class”.

### 6. P1 — Collegare token, asset e verifiche

Adottare un formato strutturato per i token, con primitive, ruoli semantici, eventuali componenti, temi, unità e alias. Il formato DTCG 2025.10 è un riferimento interoperabile; è un Community Group Report, non una Recommendation W3C. [DTCG](https://www.designtokens.org/tr/2025.10/).

Collegare ogni applicazione alla revisione dei token e della direzione approvata. Documentare quali valori sono esportabili automaticamente e quali richiedono un adapter Craft: la presenza di JSON non dimostra che le applicazioni lo importino.

Mantenere una mappa delle dipendenze per rifare soltanto gli output interessati: un colore modificato può invalidare contrasti, tavole e frame specifici; un cambio di font invalida impaginazione e misure. Una prova è valida per l'artefatto controllato, non per tutte le revisioni successive.

**Uscita:** una modifica controllata a un token genera una lista corretta di asset e verifiche da aggiornare; nessuna incoerenza nota tra guide, master ed export.

### 7. P2 — Valutare la qualità e l'universalità

Preparare un piccolo benchmark: tre identità in settori e linguaggi visivi diversi, un logo da rifinire, una breve motion identity, un sistema con almeno due temi e una sessione da riprendere.

Valutare separatamente adeguatezza al brief, distintività, coerenza del sistema, qualità tipografica/vettoriale, motion e applicabilità. Affiancare una review tecnica con condizioni di esclusione a una valutazione creativa comparativa: l'assenza di difetti tecnici non dimostra eccellenza artistica.

Confrontare le varianti sulle stesse applicazioni e con dimensioni comparabili. Ove possibile far giudicare la direzione senza mostrare prima l'autogiustificazione dell'autore. Usare feedback umano per calibrare le preferenze dello studio. La documentazione dei riferimenti deve spiegare che cosa funziona, in quale contesto e con quali limiti di riutilizzo.

**Uscita:** miglioramento verificato su qualità e token per consegna accettata; regressioni individuabili quando cambiano prompt, modelli o tool.

### 8. P2 — Distribuzione e manutenzione

Versionare il core e lo schema dello stato, con migrazioni esplicite. Aggiornare le dipendenze in un passaggio dedicato e ripetere i controlli interessati. Conservare piccoli esempi indipendenti dai clienti; promuovere nella conoscenza dello studio soltanto lezioni astratte utili.

**Uscita:** installazione pulita in un nuovo workspace, aggiornamento ripetibile di quello esistente, nessuna sovrascrittura di decisioni cliente o impostazioni personali.

## Verifiche di accettazione della prima release

1. Tutti i comandi documentati esistono; configurazioni e riferimenti sono validati.
2. Template installato due volte senza duplicazioni né perdita di impostazioni.
3. Due progetti distinti non si scambiano palette, approvazioni o prossime azioni.
4. Memoria letta dopo riavvio del processo e ripresa dopo compattazione.
5. Guasto MCP gestito con stato locale coerente, poi riconciliazione per revisione.
6. Interruzione dopo salvataggio e timeout di una modifica ripresi senza duplicare l'azione.
7. Un vettore e un motion di prova salvati, riaperti ed esportati; immagine osservata e video verificato in playback.
8. Correzione di un asset invalida le sole prove pertinenti e impedisce un `PASS` obsoleto.
9. Costo del flusso completo misurato, inclusi specialisti, immagini, verifiche e tentativi falliti.

## Primo intervento consigliato

Completare i punti 1–3 della roadmap prima di espandere la libreria creativa. Il risultato atteso è un'agenzia minima realmente avviabile, un template senza dati cliente e una ripresa dimostrata. Successivamente sviluppare la prima filiera completa: strategia → direzione → logo → sistema → motion → applicazioni → review → consegna.
