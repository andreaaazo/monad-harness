# Studio di design per Claude Code

Template di progetto per uno studio completo: strategia, naming e voce, logo e identità,
rebrand, mockup, packaging, editoria e stampa, campagne e social, illustrazione e icone,
design di siti e app (FigCraft, senza codice), motion, fotografia e 3D, presentazioni.
Nessun dato di cliente è incorporato.

## Avvio

```sh
bash .claude/tools/setup_tools.sh                 # toolchain utente (una volta per macchina)
bash .claude/scripts/start-agency.sh              # Claude dalla radice, solo gli MCP locali
```

Al primo avvio in un progetto **accetta la finestra di fiducia**: finché la cartella non è
attendibile, Claude Code ignora i permessi di `.claude/settings.json` e chiede conferma per
ogni script dello studio. Poi: `/design-preflight`, quindi `/design-agency <richiesta>`.

## Organizzazione

| Documento | Contenuto |
|---|---|
| `.claude/CLAUDE.md` | Router e regole per tutti: standard (contratto, calibrazione, ciclo di qualità, onestà), cliente, personalizzazione, principi, proporzione (~2.400 token) |
| [ORG](ORG.md) | Reparti, livelli di delega (0–3), chi può chiedere a chi, autori Craft |
| [SERVICES](SERVICES.md) | Catalogo dei servizi: ingresso, team, skill, livello QA, flussi |
| [CLIENT](CLIENT.md) | Lavoro con il cliente: domande, gate, presentazioni, feedback, iterazioni |
| [HANDOFFS](HANDOFFS.md) | Contratti di passaggio per fase: input con versione, output, accettazione, chi accetta |
| [ROUTING](ROUTING.md) | Ticket, messaggio di delega, formato dell'esito, escalation |
| [QA](QA.md) | Livelli L1–L4, controlli per deliverable, registro delle prove con hash |
| [TOOLS](TOOLS.md) | Strumenti disponibili e capacità; chi lavora sceglie lo strumento |
| [CAPABILITIES](CAPABILITIES.md) | Capacità dimostrate su lavori di prova, con prove e limiti |
| [CRAFT](CRAFT.md) | VectorCraft ed EffectCraft: lock, schemi live, controlli |
| [SOURCES](SOURCES.md) | Standard, ricerca, tradizione del mestiere, contratti software |
| [PLAYBOOK](PLAYBOOK.md) | Ciclo di vita di un progetto d'identità |
| `references/` | [mestiere: ordinario → eccellente](references/craft.md), [anti-pattern](references/anti-patterns.md), [casi studio](references/case-studies.md), [lezioni dello studio](references/lessons.md) |

**25 agenti** in 5 reparti (`.claude/agents/`, inclusi gli esploratori `direction-a/-b/-c`), **33 skill** (`.claude/skills/`), con
script di misura dentro le skill.

## Governance

| Meccanismo | File | Cosa garantisce |
|---|---|---|
| Ticket | `scripts/ticket.py` → `.agency/tickets/` | ogni delega tracciata con mittente, destinatario, padre, esito; `--after-gate` rifiuta il lavoro oltre un gate non approvato |
| Registro cliente | `scripts/client.py` → `.agency/client.jsonl` | domande e risposte testuali, presentazioni a round, feedback, approvazioni legate all'hash dei file |
| Contratto creativo | `templates/creative-contract.md`, `scripts/contract_lint.py` | ogni incarico importante definisce percezione, cosa del cliente emerge, decisione caratterizzante, dove sperimentare, cosa resta familiare, come si giudica; aggettivi senza forma osservabile segnalati |
| Giudizio di qualità | `evidence.py judge` | qualità percettiva solo con confronto visivo (riferimento, alternativa, versione precedente) e motivazione; scade se cambia il termine di confronto |
| Scoperta del cliente | `client.py ready` | fine dell'ascolto solo con comprensione confermata dal cliente, dossier coperto, nessuna domanda bloccante; domande senza un numero massimo |
| Contratto di passaggio | `scripts/ticket.py` (v3) | input con hash, mezzo, output (file o glob) ciascuno con un controllo o un'esenzione motivata; stato del lavoro e verdetto separati; consegna sempre verificata, accettazione con i controlli indipendenti; `lineage` per file |
| Master per mezzo | `scripts/master.py` | vettori VectorCraft, motion EffectCraft, immagini PhotoCraft, interfacce FigCraft, 3D Blender: il master si apre con la CLI, le consegne derivano dal master e scadono se cambia |
| Firma e indipendenza | `design-agency/checks.json`, hook `identity-guard.py`, `evidence.py` | nomi dei controlli da registro; firma confrontata con l'agente reale; l'autore non firma i controlli indipendenti; un FAIL non si copre con il PASS altrui; registri non scrivibili a mano |
| Budget di contesto | `design-agency/budgets.json`, hook `budget-guard.py`, `scripts/budget.py` | limiti per ruolo su web e immagini, immagini oltre 1600 px e riletture bloccate, avviso sulle chiamate, risvegli limitati; il router estende con un motivo |
| Dossier con provenienza | `scripts/facts.py` → `.agency/facts.jsonl` | ogni fatto è CLIENTE (solo con id reale di `client.py`), FONTE (file o URL con data) o IPOTESI (con ragionamento e verifica); copertura dei temi obbligatori; citazioni [F-…] controllate |
| Osservazione | `scripts/render.py`, `evidence.py observe`, hook `observe-reminder.py` | ogni output reso in PNG con hash della sorgente; revisione visiva solo su render della versione attuale, con descrizione di ciò che si è visto |
| Sprint isolato | hook `isolation-guard.py`, `direction_board.py` | esploratori che non vedono le altre direzioni; schede, cliché, diversità di concept e visiva, tavole anonime |
| Registro prove | `scripts/evidence.py` → `.agency/evidence.jsonl` | ogni PASS legato all'hash del file; un file cambiato rende la prova STALE e blocca il gate |
| Lock Craft | `scripts/craft_lock.py` + hook `hooks/craft-guard.py` | un solo autore per server; chiamate MCP Craft bloccate senza lock o di un altro titolare |
| Stato | hook `hooks/session-start.sh` | `.agency/STATE.md` e indice delle decisioni all'avvio |
| Coerenza del setup | `scripts/validate_agency.py` | documenti, organigramma, catalogo, frontmatter, script e percorsi citati coerenti |

## Script di misura

| Script | Cosa misura |
|---|---|
| `skills/color-system/scripts/color.py` | OKLCH, rampe in gamut, APCA, WCAG, matrice coppie, daltonismo (`cvd`) |
| `skills/type-system/scripts/type_scale.py` | scala modulare, griglia, `clamp()`, token |
| `skills/type-system/scripts/font_inspect.py` | licenza dichiarata, embedding, metriche, copertura per lingua, feature, shaping |
| `skills/design-tokens/scripts/tokens_check.py` | DTCG 2025.10, alias, cicli |
| `skills/logo-design/scripts/svg_audit.py` | nodi, quasi-allineamenti, segmenti minuscoli, attributi non da master |
| `skills/logo-design/scripts/logo_proof.py` | fogli di prova renderizzati; foglio miniature |
| `skills/mockup/scripts/mockup_compose.py` | mockup in prospettiva con luce della scena; rifiuta artwork deformati |
| `skills/print-production/scripts/pdf_preflight.py` | box, abbondanza, font, ppi effettivi, spazio colore, output intent, TAC |
| `skills/visual-qa/scripts/image_check.py` | dimensioni, alpha, ICC, ppi alla stampa, peso |
| `skills/visual-qa/scripts/pixel_diff.py` | SSIM, area cambiata, regressioni fuori regione |
| `skills/web-qa/scripts/web_audit.mjs` | breakpoint, overflow, axe WCAG 2.2, target, font, console, LCP/CLS, reduced-motion, Lighthouse |
| `skills/motion-identity/scripts/motion_probe.py` | metadati video, screening flash, raccordo del loop |
| `skills/motion-identity/scripts/lottie_check.mjs` | rendering reale con lottie-web, feature a rischio, frame campione |
| `skills/client-world/scripts/world_ingest.py` | inventario dei materiali del cliente: palette misurate, testi, font dei PDF, lessico, fogli di contatto |
| `skills/type-system/scripts/font_library.py` | ricerca in ~1900 famiglie a licenza aperta escludendo le più popolari, download con licenza registrata, specimen sui testi del cliente |
| `skills/visual-qa/scripts/optical_check.py` | baricentro visivo vs centro geometrico, bbox e ottico; equilibrio; peso ottico di un set |
| `skills/visual-qa/scripts/svg_parity.py` | stesso SVG in VectorCraft, librsvg, Inkscape, cairosvg |
| `skills/direction-sprint/scripts/direction_board.py` | completezza, schede, catene delle decisioni, test di sostituzione, cliché, diversità di concept e visiva (euristiche), tavole anonime |
| `skills/web-design/scripts/figcraft_audit.py` | design FigCraft: font mancanti, testo minimo, contrasto sui fondi, target interattivi, coordinate e allineamenti |
| `skills/production-3d/scripts/pack_render.py` | packaging 3D in Blender con autoverifica di fedeltà del colore e alte luci |
| `skills/image-direction/scripts/photo_set.py` | coerenza di un set fotografico, ricetta di trattamento, allineamento |
| `scripts/eval_kit.py` | valutazione ripetibile: setup completo vs essenziale, deliverable anonimi, schede di voto, punteggi |
| `scripts/tools.py` | stato della toolchain e piano di installazione |

## Installare in un progetto

Copia `.claude/` (senza `runtime/` e `settings.local.json`) e `.mcp.json` nella radice del
progetto; se `.mcp.json` esiste, aggiungi i due server senza sovrascrivere gli altri.
Controllo del template prima di distribuirlo: `python3 .claude/scripts/validate_agency.py --template`.

## Verifica

```sh
.claude/scripts/py .claude/scripts/selftest.py         # 170 test: script, contratti, stati, firme, budget, master, dossier, scoperta, sprint, design, prove, produzione, contratto creativo, giudizio, setup
python3 .claude/scripts/validate_agency.py --env --template
```

## Stato al 2026-10-30

| Componente | Stato |
|---|---|
| Setup: 33 skill, 25 agenti, documenti, organigramma, catalogo, percorsi, sintassi | verificato da `validate_agency.py` |
| Toolchain e app: FigCraft, VectorCraft, EffectCraft, PhotoCraft, Blender + 35 tool | presenti; launcher MCP confinati alla radice |
| Script, contratti, dossier, scoperta, prove (misura / requisito / giudizio con confronto), contratto creativo, riferimenti visivi nei ticket, design FigCraft, 3D, foto | `selftest.py`: 170/170 |
| Design FigCraft via MCP in una sessione reale | verificato: lock, frame, interazione, salvataggio, `design_audit` automatico, render guardato, `observe`, ticket DONE |
| Scoperta del cliente senza tetto di domande | verificata al primo giro in una sessione reale |
| Fotoritocco PhotoCraft | dimostrato su un'area piccola (`CAPABILITIES.md`) |
| Render 3D e set fotografico | dimostrati su prove (`CAPABILITIES.md`) |
| Delega annidata, hook Craft, ciclo con il cliente, sprint isolato | verificati in sessioni reali nelle versioni precedenti |
| Catene delle decisioni, contratto creativo, critico calibrato e per servizio, mandato creativo degli specialisti, prova di robustezza | implementati e testati negli script; non ancora provati in una sessione reale |
| Valutazione con designer esperti (`eval_kit.py`) | pronta; non eseguita: richiede valutatori umani |
| Qualità creativa su un incarico reale completo | NOT_VERIFIED |
