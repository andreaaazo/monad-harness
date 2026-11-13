# ADR-0051: il controllo gira da solo

**Contesto.** Il gate di ADR-0039, `task check`, girava solo quando qualcuno se ne ricordava. Girava sempre sulla
cartella di lavoro, mai su ciò che git ha davvero (DX-009 di `docs/audit/60-dx.md`). Il 2026-11-03 la regola
`projects/` del `.gitignore` nascondeva le pagine del cruscotto: le prove passavano perché i file erano sul disco, ma
il commit non li aveva (`tests/test_repository.py`). Il repository non ha un remoto, e dove tenere remoto e backup è
ancora una decisione aperta in `docs/00-PROJECT.md`: oggi una CI non avrebbe dove girare.

**Decisione.** In due tempi, come dice la risposta a Q11 di `docs/audit/SUMMARY.md`.
- **Un hook pre-commit versionato, `.githooks/pre-commit`.** Esegue `mise exec -- task check:fast`, cioè lock,
  Ruff, confini, pyright, tipi dallo schema, TypeScript e difese dell'interfaccia, in circa 10 s. Se un controllo
  fallisce il commit non si fa, e il messaggio dice cosa fare. Lo attiva Andrea, una volta sola, con
  `git config core.hooksPath .githooks`. `task setup` stampa questo comando finché l'hook non è attivo, ma non
  cambia la configurazione di git. `git commit --no-verify` lo salta per un solo commit.
- **`task check` comincia con `task check:fast`**, poi esegue le prove di Python, le prove unitarie dell'interfaccia
  e Playwright. L'hook esegue quindi esattamente l'inizio del gate, senza una seconda lista di comandi. Rispetto a
  ADR-0039 cambia solo l'ordine: le difese dell'interfaccia vengono prima delle prove.
- **`task check:clean`** copia l'indice di git (`git checkout-index --all --prefix=`) in una cartella temporanea.
  Lì esegue `task setup` e `task check`, poi cancella la cartella, anche se un controllo fallisce. L'indice è `HEAD`
  più ciò che è in stage, cioè il contenuto del prossimo commit. Nella copia manca ogni file che c'è solo sul disco,
  ignorato o non aggiunto. Nessuno dei due comandi scrive la storia o l'indice di git.
- **Due alternative scartate:**
  - il framework pre-commit, perché scarica gli hook da GitHub a revisioni arbitrarie e scavalca le due settimane di
    quarantena (ADR-0006, ADR-0034);
  - l'intero gate nell'hook, perché un commit che dura 80 s si salta con `--no-verify`.
- **La CI arriva con il remoto**, al più tardi prima di M6, che chiede backup fuori dalla macchina e quindi un
  remoto. Esegue `task setup` e `task check` su un clone pulito, come `check:clean`. Con il remoto, `check:clean`
  diventa anche l'hook `pre-push`. Lì le prove Craft si saltano. Le prove della sandbox girano dove bwrap funziona;
  altrove si escludono esplicitamente con `-m "not sandbox"` (Q10).

**Conseguenze.**
- L'hook controlla la cartella di lavoro, non solo ciò che è in stage, quindi conta anche un file modificato e non
  aggiunto. Ciò che entra davvero nel commit lo controlla `check:clean`.
- `check:clean` ricrea `.venv` e `web/node_modules` dalla cache di uv e dallo store di pnpm, e rifà la build
  dell'interfaccia: dura quanto `task check`, più l'installazione.
- Le prove di `tests/test_taskfile.py` non lanciano il gate una seconda volta. Eseguono l'hook con un `mise` finto,
  e `check:clean` con un `task` finto passato come variabile `TASK_EXE`. Da quel `task` finto controllano che la
  copia non sia la cartella di lavoro: nella copia mancano `.git`, `.venv` e `.task`.
