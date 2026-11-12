# Design Agency Harness

Harness proprietario della design agency. Porta fuori da Claude Code CLI lo studio già costruito
(25 ruoli, 33 skill, governance a ticket e prove) e lo fa girare su un sistema nostro, sull'API
Anthropic a pagamento, con strumenti creativi headless e regole imposte dal sistema invece che dal
prompt.

Lo studio **progetta**: identità, stampa, packaging, motion, 3D, interfacce. Per siti e app consegna
design e specifiche, mai codice di produzione.

## Stato

**M1.5 chiuso, prossimo M1.6.** Per un logo lo studio esplora 5 direzioni in parallelo, pensando e disegnando,
sceglie internamente, sviluppa le proposte e presenta al cliente un PDF con la sua raccomandazione, poi rifinisce la proposta
scelta. Su `merlo3` il lavoro è arrivato al gate `concept` in 30 minuti e 13,29 $, e al gate `final` con 34,38 $.

M1.6 porta misure confrontabili e un cruscotto con Django e Next.js. M1.7 divide il motore in slice. Il progetto diventerà un SaaS
dopo il primo cliente reale. I dettagli sono nella [roadmap](docs/02-ROADMAP.md).

## Avvio

### Prerequisiti

Serve Linux con una sessione utente di systemd, e questi strumenti della macchina:

| Strumento | Perché | Su Debian e Ubuntu |
|---|---|---|
| git | il clone; quattro prove chiedono un clone git | `sudo apt install git` |
| [mise](https://mise.jdx.dev/getting-started.html) | Node, pnpm, uv e Task alle versioni esatte di `mise.toml` (ADR-0034); uv installa poi Python 3.13.15, da `.python-version` | come dice la guida di mise |
| bubblewrap (`bwrap`) | la sandbox degli strumenti, che 17 prove usano | `sudo apt install bubblewrap` |
| fontconfig (`fc-match`) | i font della presentazione, che 9 prove costruiscono | `sudo apt install fontconfig` |
| make | facoltativo: gli alias `make setup`, `make check` | `sudo apt install make` |

Chromium per le prove Playwright si installa dopo `task setup`, con la riga qui sotto. La chiave API non serve: le
prove non chiamano mai l'API. Gli strumenti dello studio (VectorCraft, EffectCraft, FigCraft, PhotoCraft, Blender,
ffmpeg, Ghostscript) servono al lavoro vero, non alle prove: quelle che chiedono VectorCraft si saltano, e così quelle
di Docker senza il client `docker`. `task doctor` dice cosa c'è sulla macchina.

mise va attivato nella shell una volta, poi si apre una shell nuova: con zsh
`echo 'eval "$(mise activate zsh)"' >> ~/.zshrc`, con bash `echo 'eval "$(mise activate bash)"' >> ~/.bashrc`. Senza
attivarlo, `make <comando>` e `mise exec -- task <comando>` fanno lo stesso.

### Dal clone alle prove verdi

```sh
git clone <percorso-o-url> design-agency-harness
cd design-agency-harness
mise trust        # una volta: permette a mise di usare il mise.toml della cartella
mise install      # Node 22.22.1, pnpm 12.14.0, uv 0.12.5, Task 3.54.0
task setup        # Python 3.13.15 e le dipendenze da uv.lock, web/ da pnpm-lock.yaml
mise exec -- pnpm --dir web exec playwright install chromium   # una volta per macchina
task check        # tutto il gate, circa due minuti: finisce con le prove Playwright e codice d'uscita 0
```

Senza mise attivo: `mise trust`, `make setup` (che esegue `mise install` e poi `task setup`), la riga di Chromium,
`make check`. `task setup` stampa anche il comando che attiva l'hook pre-commit, se non è già attivo:
`git config core.hooksPath .githooks` (ADR-0051).

### I comandi

```sh
task               # tutti i comandi, una riga ciascuno
task check         # il gate prima di dichiarare finito un lavoro; la CI, quando ci sarà, eseguirà lo stesso
task check:fast    # i controlli veloci, circa 10 s: gli stessi dell'hook pre-commit
task check:clean   # setup e check su una copia di ciò che git ha nell'indice, per i file mai aggiunti
task lint          # Ruff, regole e formato, senza toccare i file
task format        # Ruff corregge e formatta ciò che sa sistemare da solo
task imports       # i confini tra moduli, con import-linter
task types         # pyright
task test          # le prove di Python
task web           # l'interfaccia senza server: tipi dallo schema, TypeScript, difese, prove unitarie
task e2e           # le prove Playwright, sulla build di produzione
task schemas       # rigenera schemas/openapi.json e i tipi TypeScript
task doctor        # gli strumenti della macchina
```

`make` da solo elenca i comandi; `make check`, `make test` e gli altri sono `mise exec -- task …`. Gli editor leggono
`.editorconfig`, pyright e Ruff leggono `pyproject.toml`.

### Una prova sola

```sh
task test -- tests/test_ledger.py                        # un file
task test -- tests/test_ledger.py::test_verify_exits_1_on_a_broken_chain   # una prova
task test -- -k chain                                    # le prove con quella parola nel nome
task e2e -- e2e/run.spec.ts                              # un file Playwright, dopo la build
pnpm --dir web exec node --test src/lib/format.test.ts   # un file di prove unitarie dell'interfaccia
```

Con `make` gli argomenti non passano: senza mise attivo si scrive `mise exec -- task test -- tests/test_ledger.py`.

### Errori comuni

| Cosa vedi | Cosa fare |
|---|---|
| la shell non trova `task` (`command not found`), o `"uv": executable file not found in $PATH` | mise non è attivo nella shell: attivalo come sopra, o usa `make …` e `mise exec -- task …` |
| mise dice che `mise.toml` non è fidato (`not trusted`) | `mise trust` nella cartella del clone |
| ``The lockfile at `uv.lock` needs to be updated`` | `pyproject.toml` è cambiato e `uv.lock` no. I comandi di Task non riscrivono mai il lock: se la modifica è tua, esegui `uv lock` nella shell e versiona i due file insieme |
| `web/node_modules manca: esegui task setup` | `task setup` |
| `browserType.launch: Executable doesn't exist at …` | manca Chromium per Playwright: esegui la riga di Chromium qui sopra; `task doctor` dice quale cartella manca |
| `the sandbox tests need a working bwrap sandbox, and it fails here: …` | la fine della riga dice perché. Installa bubblewrap e guarda `task doctor`, righe `bwrap` e `limiti sandbox`. Intanto puoi lavorare senza quelle prove, con `task test -- -m "not sandbox"`, o per tutto il gate con `PYTEST_ADDOPTS='-m "not sandbox"' task check`; un gate così non è verde |
| `No such file or directory: 'fc-match'` nelle prove della presentazione | `sudo apt install fontconfig` |
| `systemd-run non crea lo scope` con `$DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined` | la shell non ha la sessione utente di systemd, che dà alla sandbox i limiti di memoria e processi (ADR-0046). Succede con `sudo -u`, `su`, `env -i` o in un container: apri una sessione di login normale, da terminale o SSH, dove `systemctl --user status` risponde |
| `pre-commit: the fast checks failed, so nothing was committed` | correggi ciò che il controllo riporta sopra; `task format` sistema lint e formato |
| `AGENCY_DATA_DIR deve essere un percorso assoluto` | la cartella del registro si indica con un percorso che comincia con `/` (ADR-0045) |
| `AGENCY_DATA non si usa più` | il nome è `AGENCY_DATA_DIR` |
| `Il registro … non esiste` con `task docker:up` | avvia prima un progetto con `agency run`, o indica un registro che c'è con `AGENCY_DATA_DIR` |

## Uso

```sh
cp .env.example .env   # poi inserisci ANTHROPIC_API_KEY: la legge solo il gateway

uv run agency run progetto brief.md --budget 30   # lavora fino al gate del cliente; il tetto si dichiara sempre
uv run agency run progetto brief.md --budget 30 --record   # lo stesso, e registra le risposte per ripeterle nei test
uv run agency report progetto           # costi, fasi e ticket; con --json il modello del cruscotto
uv run agency decide progetto --approve --choice X --text "…"   # gate del concetto
uv run agency decide progetto --approve --text "…"              # gate finale
uv run agency budget progetto 40        # alza il budget se è finito
uv run agency resume progetto           # riprende dopo un'interruzione
uv run agency verify                    # rifà il conto della catena di hash del registro e delle versioni conservate
uv run agency runs progetto             # esecuzioni con la loro impronta, e cosa cambia dall'una all'altra
uv run agency compare 3 7               # cosa cambia tra due esecuzioni, anche di progetti diversi
uv run agency judge a.svg b.svg         # giudizio alla cieca: file anonimi e tavola, poi il voto, poi l'origine
uv run agency artifacts progetto        # versioni conservate per hash: consegne, presentazioni, giudizi
uv run agency restore 2947a64f x.svg    # riporta una versione in un file nuovo, senza sovrascrivere
uv run agency insights                  # proiezione per report e cruscotto, senza scrivere il registro
uv run agency migrate                   # aggiorna il registro, dopo averne fatto una copia
task dashboard                          # cruscotto su http://127.0.0.1:3000, con l'API su :8000; sola lettura
task dashboard:dev                      # lo stesso, con l'interfaccia ricaricata a ogni modifica
task docker:up                          # il cruscotto in Docker, sempre su http://127.0.0.1:3000; task docker:down lo toglie
```

Modello ed effort si scelgono con `--model` e `--effort`: sono, con il budget, gli unici vincoli al lavoro. Il registro
sta in `.data/`, o nella cartella assoluta di `AGENCY_DATA_DIR`; i file di un progetto in `projects/<nome>/work/`.
Nessuna delle due cartelle è versionata. Per ora `agency run` sa fare solo loghi.

## Documentazione

| Documento | Contenuto |
|---|---|
| [Progetto](docs/00-PROJECT.md) | Obiettivi, requisiti, metriche di successo, rischi, decisioni aperte |
| [Architettura](docs/01-ARCHITECTURE.md) | Livelli, ciclo dell'agente, flussi, confini di fiducia |
| [Roadmap](docs/02-ROADMAP.md) | Traguardi M0–M7 con criteri di uscita verificabili |
| [Modello dati](docs/03-DATA-MODEL.md) | Registri, artefatti, checkpoint, scena |
| [Strumenti](docs/04-TOOLS.md) | Cosa è disponibile, per chi, in che modo |
| [Costi](docs/05-COSTS.md) | Modelli, prezzi, cache, budget, telemetria |
| [Sicurezza](docs/06-SECURITY.md) | Modello delle minacce e difese |
| [Valutazioni](docs/07-EVALS.md) | Come si misura se il sistema migliora |
| [Parità](docs/PARITY.md) | Ogni elemento del setup precedente e dove arriva |
| [Decisioni](docs/adr/README.md) | Le scelte architetturali con il loro perché |

## Struttura

```text
src/agency/       il motore; i pacchetti, uno per riga, in docs/01-ARCHITECTURE.md
web/              il cruscotto Next.js in TypeScript, che legge tutto dall'API Django (ADR-0024); e2e/ le prove Playwright
schemas/          openapi.json, generato da task schemas e versionato (ADR-0032)
registry/         ruoli, controlli, organizzazione: dati, non codice
prompts/          i testi dei ruoli, delle skill e dell'organizzazione
evals/            i brief delle valutazioni (docs/07-EVALS.md)
docker/           le immagini e il Compose del cruscotto (ADR-0040)
docs/             progetto, decisioni in adr/, audit in audit/
tests/            le prove di Python; verificano anche che il backup resti intatto
spikes/           collaudi riproducibili delle ipotesi
legacy/           setup Claude Code v1 congelato, sola lettura
.githooks/        l'hook pre-commit (ADR-0051)
Taskfile.yml      i comandi (ADR-0039); Makefile ne è l'alias
mise.toml         le versioni degli strumenti; .python-version quella di Python
```
