# ADR-0044: i file dell'harness fuori dalla sandbox

**Contesto.** ADR-0005 dà a ogni lavoro una sola cartella scrivibile, `/job`. Fino al 2026-11-06 l'harness teneva lì
anche i propri file, in `/job/.ops`:
- lo script di `compute`;
- il piano di `craft_run`;
- per la ripresa di `craft_run`, il risultato dei passi e il documento costruito.

Il codice che il modello fa girare con `compute` scrive in `/job`, quindi poteva riscrivere
`.ops/<operazione>.result.json` e `.ops/<operazione>.vectorcraft`. Alla ripresa `craft_run` trovava i due file, non
rifaceva i passi e copiava nel master il documento falso (SEC-001, riprodotto il 2026-11-06). Gli aiuti che non seguono
i link simbolici tolgono la fuga verso l'host, ma non questo: un file non ha bisogno di un link per essere falso. Il
difetto è di classe: l'harness, che è fidato, tiene il proprio stato in un albero che la sandbox, non fidata, può
scrivere.

**Decisione.** Tre tipi di file, ognuno al suo posto.
- Gli ingressi che l'harness scrive per la sandbox, cioè lo script di `compute` e il piano di `craft_run`, stanno in
  `.data/ops/<progetto>/<istanza>/in/`. La cartella è montata in sola lettura in `/ops`.
- Le uscite di uno strumento restano in `/job`, dove la sandbox scrive. `craft_run` esporta in
  `/job/.partial/<operazione>.vectorcraft`.
- Il registro della ripresa, cioè il risultato e il documento costruito, è una copia che l'harness fa in
  `.data/ops/<progetto>/<istanza>/`, con gli aiuti che non seguono i link. Quella cartella non entra in nessuna
  sandbox, e la ripresa legge solo da lì. Anche la copia del documento nel master passa dagli aiuti.

`DataLayout` è l'unico proprietario dei due percorsi (`ops_inputs` e `ops_records`). La sandbox dell'agente riceve
`/ops`. Senza `/ops`, `compute` e `craft_run` rifiutano con un messaggio al modello, e non ripiegano mai su `/job`. La
sandbox del gate del cliente non lo riceve, perché non esegue nulla: controlla solo gli hash e le prove.

**Conseguenze.**
- La sandbox può ancora scrivere ciò che vuole nelle proprie uscite, ma niente di ciò che l'harness rilegge dopo come
  suo.
- Un progetto fermo a metà di un `craft_run` con il vecchio schema rifà i passi una volta, perché il vecchio
  `/job/.ops` non si legge più. Se il master aveva già ricevuto quei passi, li riceve due volte. Oggi nessun progetto è
  in pausa: `merlo3` è chiuso e non riprende (ADR-0021), `merlo4` non è partito. Quindi non serve una migrazione. Dopo
  l'avvio di `merlo4`, un nuovo cambio di questo schema la richiederà.
- `list_files` nasconde `.partial` e il vecchio `.ops`, che può restare nelle cartelle di lavoro già esistenti.
- La garanzia vale finché `.data` non sta dentro la cartella di lavoro di un progetto. I valori predefiniti le tengono
  separate.
- Le richieste all'API non cambiano: `.ops` non compare in nessun prompt né in nessuno strumento, e le istantanee delle
  richieste restano identiche byte per byte.
- Resta un'occorrenza della stessa classe: il primo sguardo del critico (`reviews/valutazione.json`) sta nella
  cartella di lavoro e `select_concepts` lo legge come vincolo. È la Task 2.F24 di `docs/audit/PLAN.md`.
- Verifica: `tests/test_agent_flow.py`, con `test_compute_script_lives_outside_the_work_folder`,
  `test_craft_run_resume_reads_only_the_harness_record`, `test_resume_with_a_record_only_in_the_old_place_reruns_once`
  e `test_list_files_hides_the_partial_exports`.
