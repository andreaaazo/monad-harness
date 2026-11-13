# ADR-0046: i limiti della sandbox

**Contesto.** ADR-0005 isola i comandi con `bwrap`: una cartella scrivibile, nessuna rete, nessun segreto. Non limitava
però le risorse (SEC-005, riprodotto il 2026-11-07). Dentro la sandbox `RLIMIT_AS`, `RLIMIT_DATA` e `RLIMIT_FSIZE`
erano illimitati, `/tmp` e `/dev/shm` mostravano i 30,5 GiB liberi dell'host, e il processo stava nello stesso scope
cgroup dell'operatore: `/proc/self/cgroup` dava lo stesso percorso del chiamante, e né il chiamante né la sandbox
avevano `memory.max`. In 60 secondi il codice di `compute` poteva riempire la RAM con l'heap o con le tmpfs, e
l'OOM killer dell'host poteva colpire l'harness o il desktop di chi lavora.

La Task 2.18 ha tolto ciò che non chiedeva misure: 2 GiB per `/tmp`, 256 MiB per `/home` e `prlimit --fsize` di 2 GiB.
Resta il tetto di memoria e di processi di tutto il comando, che si fissa solo conoscendo quanto serve davvero.

**Misura.** Il 2026-11-08, a 0 $, ogni comando dentro `systemd-run --user --scope -p MemoryAccounting=yes -p
TasksAccounting=yes`, con `memory.peak` e `pids.peak` letti dal cgroup prima che lo scope finisse. Una sola esecuzione
per riga, su questa macchina (24 core). `memory.peak` conta anche la cache delle pagine dei file letti, quindi
sopravvalutare è la direzione sicura. Il master è la copia di `merlo3/work/source/segno.vectorcraft` (360 KB), gli altri
documenti sono stati fatti con le stesse CLI. Scena del 3D: un cubo con sei texture di rumore da 4096 × 4096 px
(incomprimibile, il caso peggiore per un'arte di stampa), resa con Cycles su CPU, senza denoise.

| Strumento | Comando | Ingresso | Memoria al picco | Task al picco |
|---|---|---|---|---|
| VectorCraft | `info` | `segno.vectorcraft` | 6 MiB (21 MiB a freddo) | 2 |
| VectorCraft | `convert … .png --scale 3` (`render`) | `segno.vectorcraft` → 2400 × 1800 px | 308 MiB | 10 |
| VectorCraft | `convert … .png --scale 10` | `segno.vectorcraft` → 8000 × 6000 px | 560 MiB | 10 |
| VectorCraft | `convert … .svg` (`export_master`) | `segno.vectorcraft` | 8 MiB | 2 |
| VectorCraft | `convert … .pdf` | `segno.vectorcraft` | 11 MiB | 2 |
| VectorCraft | `run --in --commands --export` (`craft_run`) | `segno.vectorcraft`, 2 passi | 8 MiB | 2 |
| FigCraft | `info --json` | A4 a 300 dpi, tre forme e un testo | 12 MiB | 2 |
| FigCraft | `export … .png --scale 2` | lo stesso | 362 MiB | 2 |
| FigCraft | `render`, `run` | lo stesso | 163 MiB, 97 MiB | 26 |
| PhotoCraft | `info` | 4000 × 3000 px, un livello | 4 MiB | 2 |
| PhotoCraft | `info` | A2 a 300 dpi (4961 × 7016 px), due livelli | 7 MiB | 2 |
| PhotoCraft | `convert … .png` | lo stesso | 327 MiB | 50 |
| PhotoCraft | `run … gaussianBlur` | lo stesso | 723 MiB | 38 |
| EffectCraft | `info --project --json`, `exec` | un montaggio 1920 × 1080 | 3 MiB | 2 |
| EffectCraft | `render-frame` | lo stesso | 20 MiB | 26 |
| Controlli | `svg_audit` | `segno.svg` | 11 MiB | 2 |
| Controlli | `svg_parity` | `segno.svg` | 168 MiB | 57 |
| Controlli | `logo_proof proof` | `segno.svg` | 120 MiB | 11 |
| Controlli | `optical_check` | resa 2400 × 1800 px | 273 MiB | 25 |
| Controlli | `optical_check` | resa 8000 × 6000 px | 2.777 MiB | 25 |
| Blender 5.2.3 | `-b --python` e6, 4 campioni | 6 × 4096² px, resa 4961 × 3508 px (A3 a 300 dpi) | 2.586 MiB | 51 |
| Blender 5.2.3 | lo stesso, 1 campione | lo stesso | 2.392 MiB | 51 |
| Blender 5.2.3 | lo stesso, 1 campione | 6 × 4096² px, resa 7016 × 4961 px (A2 a 300 dpi) | **3.956 MiB** | 51 |

Il picco dipende dalla scena e dalla risoluzione, non dai campioni (2.392 contro 2.586 MiB). Il massimo misurato è
quello di Blender sul formato più grande, 3.956 MiB. I task al massimo sono 57 (`svg_parity`, con i suoi renderer in
parallelo). Le CLI di FigCraft, PhotoCraft e EffectCraft sono qui per completezza: oggi l'harness le usa solo con
`info` (`master.problem`), perché `export_master` esporta solo VectorCraft (M1). `blender` non lo esegue ancora
nessuno strumento dell'harness: la riga è la stima per E6 (`docs/07-EVALS.md`), da rifare quando uno strumento lo
lancia.

**Decisione.**
- **Ogni comando gira in uno scope cgroup proprio**, con
  `systemd-run --user --scope --quiet -p MemoryMax=8589934592 -p MemorySwapMax=0 -p TasksMax=512 -- bwrap …`. Lo scope
  è dell'utente: `user@1000.service` delega già i controller `memory` e `pids`, e non serve nessun privilegio.
- **`MemoryMax` è 8 GiB** (`MEMORY_MAX_BYTES`): il doppio del massimo misurato (2 × 3.956 MiB = 7,73 GiB), arrotondato
  per eccesso al GiB intero. La macchina ha 60 GB, quindi un comando fuori controllo costa al più 8 GiB e non la
  macchina. Il tetto di 2 GiB di `/tmp` (Task 2.18) rientra nel conto: le pagine che una tmpfs tiene sono addebitate
  allo scope che le ha scritte. Una `/tmp` piena (2 GiB) e una `/home` piena (256 MiB) sommate al picco massimo
  misurato fanno 6,1 GiB, sotto gli 8 GiB: un lavoro lecito non incontra prima il tetto di memoria.
  Provato il 2026-11-08 con un tetto di 64 MiB solo in una copia di prova: 128 MiB scritti in `/dev/shm`, 128 MiB in
  `/tmp` e 128 MiB di heap vengono tutti uccisi dallo scope.
- **`MemorySwapMax=0`**: niente swap, così il tetto è il tetto e il computer non si blocca a paginare.
- **`TasksMax` è 512** (`TASKS_MAX`), contati come thread. Il massimo misurato è 57, cioè nove volte meno. Blender usa
  un thread per core più qualche altro (51 su 24 core): su una macchina con molti più core il margine si accorcia, e il
  valore va riguardato.
- **Se lo scope non si può creare, la sandbox non parte.** `Sandbox.run` alla prima chiamata di ogni istanza lancia una
  sonda, `systemd-run --user --scope --quiet -p … -- true`, con gli stessi limiti. Se `systemd-run` manca, non risponde
  entro 15 s o esce con errore, `run` alza `SandboxUnavailable` con il motivo, e il comando non parte mai fuori dai
  tetti. A sonda riuscita il codice d'uscita di un comando è sempre il suo. La sonda sta prima del comando proprio
  perché il codice del modello può scrivere ciò che vuole su stdout, stderr e codice d'uscita: leggere l'esito dello
  scope da lì si potrebbe falsificare.
- **`SandboxUnavailable` è un `RuntimeError`.** `Toolbox.call` ha già un ramo per i `RuntimeError`: lo strumento
  risponde al modello con il testo dell'errore e `is_error`, senza traccia e senza «non è riuscito», e il tracciamento
  segna il rifiuto. Non c'è un punto nuovo dove catturarla.
- **`agency doctor` fa lo stesso controllo** con la stessa funzione (`scope_problem`), come riga obbligatoria
  `limiti sandbox`: se va bene dice `scope systemd con 8 GiB di memoria e 512 task`, altrimenti `ERR` e il motivo.

**Conseguenze.**
- **La sandbox ora chiede una sessione utente di systemd** (bus utente raggiungibile, `XDG_RUNTIME_DIR` e
  `DBUS_SESSION_BUS_ADDRESS` validi) con i controller `memory` e `pids` delegati. Un lavoro di cron, una
  shell senza il bus dell'utente o un container senza systemd non la hanno: là la sandbox si rifiuta di partire, e
  `agency doctor` dice perché. Il ripiego senza tetti non esiste, di proposito.
- Un comando che supera gli 8 GiB viene ucciso dal kernel (codice 137 o -15) e il modello vede l'uscita del comando,
  non un messaggio sul tetto. Se lo strumento che lo lancia dovesse spiegarlo, sarà un'altra unità.
- `SandboxUnavailable` esce da `Sandbox.run` anche fuori da `Toolbox.call` (per esempio nei controlli di consegna): se
  il progetto debba fermarsi invece di continuare con un rifiuto per ogni strumento lo decide Andrea
  (`docs/audit/PLAN.md`, Task 2.F43).
- Il valore va misurato di nuovo quando un lavoro reale con Blender (M2) o un master molto più grande lo avvicini:
  l'ADR che alza `MEMORY_MAX_BYTES` porta la sua tabella.
- `/dev/shm` resta senza una dimensione propria, ma è tenuta dentro gli 8 GiB dallo scope (Task 2.F39).
