# ADR-0052: le dipendenze le dichiara il codice che le importa

**Contesto.** Il codice importava tre pacchetti che `pyproject.toml` non dichiarava (SIM-004 di
`docs/audit/70-simplification.md`): `sqlalchemy` nel registro e nelle migrazioni, `langchain_core` in `runtime.py` e
`httpx2` nelle prove. Arrivavano solo perché li chiedevano altri pacchetti: alembic e sqlmodel il primo, langgraph il
secondo, anthropic il terzo. Un loro rilascio che li togliesse o li fissasse a un'altra versione avrebbe rotto questi
import, senza nessuna modifica qui. Al contrario, `pyproject.toml` dichiarava un esportatore OTLP e tre extra che
nessun file importava (SIM-002, SIM-003): li hanno tolti le Task 6.1 e 6.2 di `docs/audit/PLAN.md`.

**Decisione.**
- **`pyproject.toml` dichiara ogni pacchetto che il codice importa direttamente.** `sqlalchemy` e `langchain-core`
  sono dipendenze di esecuzione, `httpx2` di sviluppo. Ciascuna ha come limite inferiore la versione già nel lock e
  nessun limite superiore, così il resolver resta libero. Dichiarare `langchain-core` non rende legittimo il suo uso
  in `runtime.py`: quell'import passa al livello del processo con M1.7 (STR-003). Il manifesto dice ciò che il
  codice importa oggi.
- **`tests/test_dependencies.py` lo controlla a ogni `task check`.** Legge gli import di primo livello di
  `src/agency` e di `tests` e li collega ai pacchetti installati con `importlib.metadata.packages_distributions()`.
  - Un import del motore deve venire da una dipendenza di esecuzione, perché l'immagine dell'API installa solo
    quelle.
  - Un import delle prove può venire anche da una dipendenza di sviluppo.
  - Ogni dipendenza di esecuzione deve essere importata dal motore. Ogni dipendenza di sviluppo deve essere
    importata dalle prove, tranne gli strumenti che si usano senza import: ruff, pyright, import-linter e
    django-stubs.
  - Restano fuori la libreria standard, gli import relativi, i moduli del progetto e gli script QA importati dal
    setup precedente, che girano nel Python degli strumenti.
- **Nessun pacchetto nuovo per il controllo.** Uno strumento come deptry farebbe lo stesso lavoro, ma sarebbe un
  pacchetto in più sotto la quarantena di due settimane (ADR-0006).
- **Un pacchetto di un traguardo futuro lo dichiara il traguardo che lo importa per primo**, come per gli extra tolti
  dalla Task 6.2.

**Limite.** Il controllo guarda il nome di primo livello. Alcuni nomi li forniscono più pacchetti: `langgraph` viene
da langgraph, langgraph-checkpoint e langgraph-checkpoint-sqlite, `opentelemetry` da opentelemetry-api e
opentelemetry-sdk. Basta che uno di questi sia dichiarato. Così `langgraph.checkpoint.base` e
`langgraph.checkpoint.memory`, che vengono da `langgraph-checkpoint`, e `opentelemetry.trace`, che viene da
`opentelemetry-api`, restano dipendenze transitive. Un controllo per modulo li troverebbe, ma va deciso a parte:
dichiarerebbe due pacchetti in più.

**Conseguenze.**
- `uv add` e `uv remove` tengono verde la prova; un import nuovo senza la sua dichiarazione la fa fallire, con il
  comando da eseguire nel messaggio.
- La prova legge l'ambiente installato: ha bisogno di `task setup`, cioè delle dipendenze di sviluppo installate.
- Verificato il 2026-11-12: la prova fallisce senza le tre dichiarazioni, e passa con esse. Su una copia ferma sei
  mutazioni: `sqlalchemy` tolto, una dipendenza di esecuzione e una di sviluppo che nessuno importa, `httpx2` tolto,
  `ruff` tolto dagli strumenti, `httpx2` spostato tra le dipendenze di esecuzione.
