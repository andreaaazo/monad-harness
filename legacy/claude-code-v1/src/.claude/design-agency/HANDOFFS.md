# Contratti di passaggio

Ogni passaggio di lavoro tra reparti è un ticket con **input con versione** (hash registrato
all'apertura), **mezzo**, **output** con percorsi esatti, **controlli di accettazione** e **chi
accetta**. `ticket.py deliver` rifiuta sempre la consegna se manca un output, se un output non ha
controlli, se un input è cambiato dopo l'apertura, se una prova non è fresca, se il master del mezzo
manca o non si apre, se un export non deriva dal master. `ticket.py accept` aggiunge i controlli
indipendenti, che firma un altro: l'autore non li può coprire.

I controlli oggettivi li registrano gli script stessi (`--record-by`): `facts_check`,
`dossier_coverage`, `board_check`, `diversity`, `direction_lint`, `concept_diversity`, `optical_check`. I controlli di osservazione (`visual_review`,
`board_review`, `keyframe_review`, …) richiedono un render della versione attuale (`render.py`).

## Identità, rebrand, programmi L

| # | Fase | Esegue | Input (versione nel ticket) | Output | Accettazione (`--accept`) | Accetta | Gate cliente |
|---|---|---|---|---|---|---|---|
| 0 | Scoperta | router | richiesta, risposte `client.py`, materiali | `work/context/understanding.md`, `work/brief.md` | `facts_check` | router | `understanding`, poi `brief` |
| 1 | Mondo e dossier | strategy-director → researcher, brand-strategist | `work/brief.md`, `work/client/` | `work/context/world/inventory.md`, `work/context/dossier.md`, `work/references/selection.md` | `dossier.md=dossier_coverage`, `selection.md=facts_check` | strategy-director | — |
| 2 | Strategia | brand-strategist | brief, dossier | `work/strategy.md` | `facts_check` | strategy-director | `strategy` |
| 2b | Contratto creativo | creative-director con strategy-director | strategia approvata, dossier, riferimenti di livello | `work/creative-contract.md` | `contract_check` | router | presentato al cliente con la strategia |
| 3 | Sprint delle direzioni | direction-a, -b, -c (in parallelo, CLI su file propri) | `work/directions/brief-pack.md`, `apps.json`, dossier | `work/directions/<x>/direction.md`, master in `…/src/`, `…/apps/<id>.png` esportati dai master | `direction.md=facts_check+direction_lint`, `*.png=visual_review+optical_check` | creative-director | — |
| 4 | Confronto | creative-director, critic | output delle direzioni | `work/directions/boards/*.png`, critica | `apps.json=board_check+diversity+concept_diversity`, `boards/*.png=board_review` | creative-director | — |
| 5 | Selezione | creative-director | tavole, critica, `direction.md` | `work/directions/selection.md` | `facts_check` | router | `direction` |
| 6 | Carta | creative-director | selezione approvata | `work/direction/charter.md` | `facts_check` | router | — |
| 7 | Segno e sistema | design-director → identity-designer, typographer, illustrator | carta, dossier | master `.vectorcraft`, SVG esportati, token, specimen | controlli di [QA](QA.md) per deliverable + `charter_review` | design-director | `design` |
| 8 | Applicazioni e brand book | design-director → editorial-designer, mockup-artist | sistema approvato, carta | tavole, mockup, brand book | QA per deliverable + `charter_review` | design-director | — |
| 8b | Prova di robustezza | design-director → specialista non coinvolto nella scelta | sistema approvato, carta, contenuti sfavorevoli reali | un'applicazione nuova non usata nello sprint (pagina tecnica, comunicazione operativa, documento denso) | `stress_test` (giudizio con confronto con le applicazioni approvate) | creative-director | — |
| 9 | Digitale | digital-director → ux-designer, ui-designer, motion-designer | sistema, token, contenuti | file FigCraft (pagine, componenti, variabili, prototipo), handoff | `*.figcraft=design_audit+visual_review+prototype_review+charter_review` | digital-director | `prototype` |
| 10 | Produzione | production-director | tutti i deliverable approvati | pacchetto, `delivery.md` | `evidence.py gate` completo | production-director | `final` |

## Servizi S e M

| Servizio | Input minimi | Output | Accettazione |
|---|---|---|---|
| Mockup | artwork approvato, scena con fonte | master `.pcraft` o `.blend`, `work/mockup/*.png` | `*.pcraft=master_open`, `*.png=mockup_aspect+image_check+visual_review` |
| Logo (M) | brief, dossier, strategia breve | master `.vectorcraft`, SVG esportati, `construction.md`, prove | `*.vectorcraft=master_open`, `*.svg=svg_audit+svg_parity+logo_proof+critique`, `construction.md=facts_check` |
| Stampato | testi definitivi, specifica dello stampatore | master, PDF esportato | `*.pdf=pdf_preflight+visual_review+proof_read` |
| Design di pagina o app | wireframe e direzione approvati, testi | file FigCraft con frame desktop e touch | `*.figcraft=design_audit+visual_review+prototype_review` |

## Regole

- **Riferimenti visivi**: ogni produzione dopo la scelta della direzione porta negli `--inputs`
  almeno un riferimento visivo (esempi approvati, immagini annotate, dettagli da preservare);
  `ticket.py` rifiuta i ticket solo testuali.

- **Mezzo**: ogni produzione dichiara `--medium`; lo strumento e il master sono obbligatori
  (TOOLS.md). `nessuno` richiede `--medium-why`. I controlli del master: `*.vectorcraft=master_open`
  (registrato da `master.py check --record-by <agente>`).
- **Copertura**: ogni output ha un controllo o `--exempt '<file>=motivo'`. Un pattern che non colpisce
  nessun output e una cartella in `--outputs` vengono rifiutati all'apertura.
- **Input superati**: se un input cambia durante il lavoro (es. il brief è stato aggiornato),
  la consegna è rifiutata; rifai il lavoro, o dichiara con `--input-change "<motivo>"`
  perché la modifica non lo tocca.
- **Discendenza**: `ticket.py lineage <file>` dice quali ticket hanno usato o prodotto ogni
  versione di un file; serve a capire cosa rifare quando un materiale cambia.
- **Chi accetta** legge gli output (e li guarda), non solo l'esito dichiarato.
