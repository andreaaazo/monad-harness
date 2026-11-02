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

```sh
make setup      # dipendenze dal lock (Python 3.13, uv)
make check      # lint, confini tra moduli, tipi, test
make doctor     # strumenti della macchina
cp .env.example .env   # poi inserisci ANTHROPIC_API_KEY

uv run agency run progetto brief.md --budget 30   # lavora fino al gate del cliente
uv run agency report progetto           # costi e stato dei ticket
uv run agency decide progetto --approve --choice X --text "…"   # gate del concetto
uv run agency decide progetto --approve --text "…"              # gate finale
uv run agency budget progetto 40        # alza il budget se è finito
uv run agency resume progetto           # riprende dopo un'interruzione
uv run agency runs progetto             # esecuzioni con la loro impronta, e cosa cambia dall'una all'altra
uv run agency compare 3 7               # cosa cambia tra due esecuzioni, anche di progetti diversi
uv run agency judge a.svg b.svg         # giudizio alla cieca: file anonimi, poi il voto, poi l'origine
uv run agency artifacts progetto        # versioni conservate per hash: consegne, presentazioni, giudizi
uv run agency restore 2947a64f x.svg    # riporta una versione in un file nuovo, senza sovrascrivere
uv run agency insights                  # proiezione per report e cruscotto, senza scrivere il registro
uv run agency migrate                   # aggiorna il registro, dopo averne fatto una copia
```

Modello ed effort si scelgono con `--model` e `--effort`: sono, con il budget, gli unici vincoli al lavoro. I file di un progetto stanno in
`projects/<nome>/work/`. Per ora `agency run` sa fare solo loghi.

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
src/agency/     pacchetto dell'harness
registry/       ruoli, controlli, organizzazione: dati, non codice
docs/           progetto e decisioni
tests/          test; verificano anche che il backup resti intatto
spikes/         collaudi riproducibili delle ipotesi
legacy/         setup Claude Code v1 congelato, sola lettura
```
