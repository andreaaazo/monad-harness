---
title: L'harness segue i link che la sandbox lascia nella cartella del lavoro
date: 2026-11-13
category: security-issues
module: agency.contracts.files
problem_type: security_issue
component: infrastructure
symptoms:
  - "compute scrive lo script del modello in una cartella dell'host attraverso un .ops diventato link (SEC-001)"
  - "un'immagine dell'host compare nella presentazione per il cliente attraverso un link nascosto (SEC-003)"
  - "agency restore scrive una versione dentro un link lasciato in projects/, raggiunto con .. o con un alias"
  - "una FIFO lasciata nel lavoro blocca l'harness per sempre a una lettura"
root_cause: missing_validation
resolution_type: code_fix
severity: critical
tags: [sandbox, symlink, no-follow, toctou, path-traversal, fifo, bwrap]
---

# L'harness segue i link che la sandbox lascia nella cartella del lavoro

## Problema

Il codice che gira nella sandbox (`compute`, i Craft, Blender) può scrivere qualunque cosa nella sua `/job`, cioè
`projects/<progetto>/work`, compresi link simbolici e FIFO. L'harness gira fuori dalla sandbox, con i permessi
dell'operatore. Ogni volta che leggeva, scriveva, creava cartelle, calcolava hash o elencava file in quella cartella
con le API normali (`Path.open`, `mkdir(parents=True)`, `shutil.copyfile`, `glob`, `resolve()`), seguiva quei link
fuori dal perimetro. L'audit ne ha trovati oltre trenta, un caso per volta (SEC-001, SEC-003, da 2.F1 a 2.F27), e la
revisione finale altri cinque nelle due righe di comando che ricevono un percorso digitato (R2, R5, R9, R11).

## Sintomi

- `compute` scriveva lo script in `work/.ops`; trasformato `.ops` in un link verso `migrations/versions`, la
  migrazione successiva eseguiva il codice del modello fuori dalla sandbox (SEC-001, critico).
- La presentazione rifaceva un `glob` della cartella della proposta e prendeva un `.zz.png` nascosto che puntava a
  un'immagine dell'host (SEC-003).
- `agency restore` e `agency judge` seguivano un link sotto `projects/` raggiunto con `elsewhere/../projects/...`,
  con `~/alias/...` o con `op/..` dopo un link dell'operatore.
- Una FIFO al posto di un file faceva aspettare `read_under` per sempre (2.F21).

## Cosa non ha funzionato

- **Risolvere e poi aprire** (`inside(work, path)` e poi `open`): tra il controllo e l'uso un link scambiato viene
  seguito, e `resolve()` segue proprio i link che si vogliono rifiutare.
- **`O_NOFOLLOW` sull'ultimo componente soltanto**: un link in una cartella intermedia redirige lo stesso.
- **Ragionare sul testo del percorso** (`os.path.normpath`, poi il kernel): R2 e R5 hanno deciso "dentro o fuori
  `projects/`" dal testo e poi hanno passato il percorso al kernel, che legge `..` dopo aver seguito i link. Ogni
  correzione ha aperto un caso nuovo (`..` dopo un link, un alias, `..` dopo un file) e ha cambiato senza volerlo
  messaggi e comportamenti fuori dal perimetro.
- **Rifare il `glob` di una cartella** che la sandbox può scrivere: elenca anche ciò che nessuno ha consegnato.

## Soluzione

Una sola regola, imposta dal codice e non dai prompt: nella cartella del lavoro l'harness tocca i file solo
attraverso gli aiuti di `agency.contracts.files`, che aprono la radice fidata e poi ogni componente con `O_NOFOLLOW`
dal descrittore del precedente.

```python
from agency.contracts.files import read_under, replace_under, sha256_under, glob_under, ensure_dir_under

# mai (work / relative).read_text()
data = read_under(work, "proposals/r1/a/scheda.json", limit=MAX_TEXT_FILE_BYTES)
replace_under(work, "reviews/valutazione.json", payload)  # scrive accanto e rinomina: nessun link seguito
digest = sha256_under(work, relative)  # mai file_sha256(work / relative)
files = glob_under(work, "exports/**/*.svg")  # non entra in cartelle-link e non le elenca
```

- `open_under` apre con `O_NONBLOCK` e rifiuta in lettura tutto ciò che non è un file regolare: una FIFO o un
  dispositivo sono rifiutati subito.
- Le letture che decodificano o interpretano passano un `limit` (`MAX_TEXT_FILE_BYTES`, `MAX_IMAGE_FILE_BYTES`,
  `MAX_DOCUMENT_BYTES`): la sandbox può scrivere file fino a 2 GiB.
- I file che l'harness scrive per la sandbox e poi rilegge come fidati non stanno in `/job`: gli ingressi in
  `.data/ops/<progetto>/<istanza>/in`, montata in sola lettura in `/ops`, e i record di ripresa nella cartella sopra
  (ADR-0044). Lo stesso vale per i dati che decidono qualcosa, come le valutazioni del critico: stanno nel registro,
  non in un file che l'agente può riscrivere (2.F24).
- Si costruiscono gli elenchi da ciò che è stato consegnato (`ledger.delivered`), non dal contenuto della cartella.
- Per un percorso **digitato dall'operatore** (`agency judge`, `agency restore`) si usa `land(path, root)`: percorre
  il percorso un componente alla volta come farebbe il kernel, segue i link fuori da `projects/` (lo spazio
  dell'operatore), rifiuta ogni link che si trova in `projects/` o sotto, comunque lo si raggiunga, e si ferma su un
  file. Poi si agisce sull'arrivo (`Landing`), mai di nuovo sul percorso digitato: sotto `projects/` con gli aiuti
  `*_under`, fuori sul percorso reale (`landing.real`).

## Perché funziona

Un descrittore di cartella aperto con `O_NOFOLLOW` resta quella cartella anche se intanto il nome viene scambiato
con un link: non esiste più una finestra tra controllo e uso. Rifiutare per posizione del link (in `projects/` o
sotto), e non per forma del testo, chiude tutte le grafie insieme: alias, `..` dopo un link, `//`, link relativi.

## Prevenzione

- Prima di scrivere `work / ...` o di passare un percorso del lavoro a `open`, `mkdir`, `shutil`, `glob`, `resolve` o
  `file_sha256`, usare l'aiuto `*_under` corrispondente. Una ricerca utile in revisione:
  `rg -n "inside\(|\.resolve\(\)|shutil\.|\.glob\(" src/agency`.
- Ogni lettore nuovo entra nella tabella parametrizzata di `tests/test_safe_files.py`
  (`test_harness_readers_refuse_a_planted_symlink`, `test_a_planted_fifo_is_refused_at_once`).
- Una correzione di questo perimetro si verifica confrontando vecchio e nuovo comportamento su ogni classe di
  percorso (dentro, fuori, con `..` prima e dopo la cartella, con un link dell'operatore, su un file esistente, su un
  link pendente): R2, R5 e R9 hanno ciascuno cambiato un caso che nessuno aveva chiesto di cambiare.

## Problemi correlati

- ADR-0044 (i file dell'harness fuori dalla sandbox), ADR-0046 (i limiti della sandbox).
- `docs/audit/SUMMARY.md` (SEC-001, SEC-003) e `docs/audit/PLAN.md` (Task 2.1-2.3, 2.F1-2.F27, R2, R5, R9, R11).
- Resta aperto: una cartella di progetto che è essa stessa un link fuori da `projects/` porta il suo lavoro fuori
  dalla radice protetta (`docs/audit/PLAN.md`, "Fourth review round").
