# Strumenti

**Il mezzo decide lo strumento.** Lo studio **progetta**: per siti e app consegna design, prototipi
e specifiche, mai codice di produzione.

| Mezzo (`--medium`) | Strumento obbligatorio | Master | Lavori |
|---|---|---|---|
| `vettoriale` | **VectorCraft** | `.vectorcraft` | logo, lettering, icone, illustrazione vettoriale, dieline, tavole |
| `motion` | **EffectCraft** | `.ecproj` | logo animato, sting, transizioni, compositing, Lottie |
| `immagine` | **PhotoCraft** | `.pcraft` | ritocco, trattamento, compositing, maschere, mockup fotografici |
| `interfaccia` | **FigCraft** | `.figcraft` | siti, app, componenti, prototipi; layout e presentazioni |
| `3d` | **Blender** | `.blend` | packaging e prodotto in scena |
| `nessuno` | — | — | strategia, testi, ricerca: con `--medium-why` |

Regole:

- **Il calcolo costruisce, il master conserva.** Uno script può calcolare coordinate, griglie e
  misure. Il risultato entra nel master: `vectorcraft-cli run --commands` (comandi nativi) oppure
  `vectorcraft-cli convert calcolo.svg logo.vectorcraft`. Da lì in poi si lavora e si corregge nel master.
- **Le consegne derivano dal master**: `master.py export <master> <file>` esporta con la CLI e
  registra il legame; per un export fatto dentro l'app, `master.py link`. Master cambiato dopo = export scaduto.
- `ticket.py deliver` apre ogni master con la sua CLI e rifiuta: master mancante o vuoto, export
  senza legame. Un'eccezione reale (foto originale del cliente) si scrive con `--no-master '<glob>=motivo'`.
- **Parallelo**: le CLI su file diversi lavorano insieme senza lock (provato in parallelo su tutte e
  quattro). L'MCP di un server ha un autore per volta.

```sh
.claude/scripts/py .claude/scripts/tools.py check     # stato (exit 1 se manca un tool core)
.claude/scripts/py .claude/scripts/tools.py plan      # come installare ciò che manca
```

Non eseguire launcher o programmi sconosciuti per "vedere cosa fanno": alcuni installano o
aggiornano software. Leggi prima `--help` di una CLI nota, `dpkg -L`, la documentazione.

## Applicazioni di design (MCP con lock, e CLI per lavoro senza finestra)

| App | Per | MCP (un autore per volta) | CLI |
|---|---|---|---|
| **FigCraft** | interfacce, siti, app, layout editoriali e presentazioni, componenti, variabili e temi, prototipi interattivi, handoff (dev mode, annotazioni, misure), lavagne | `mcp__figcraft__*` | `figcraft-cli run/export/render/info` (`run` su file propri: esplorazioni in parallelo) |
| **VectorCraft** | logo e lettering, icone, illustrazione vettoriale, tavole, stampati, brand book | `mcp__vectorcraft__*` | `vectorcraft-cli run/convert` |
| **EffectCraft** | motion, logo animato, studi d'interazione, compositing, Lottie | `mcp__effectcraft__*` | `effectcraft-cli render/render-frame/run` |
| **PhotoCraft** | fotoritocco, trattamento e compositing fotografico, maschere, deformazioni, riempimento in base al contenuto, mockup fotografici | `mcp__photocraft__*` | `photocraft-cli run/batch/convert` |
| **Blender** | packaging e prodotto in 3D, scene di contesto, materiali e luce | — | `blender -b -P <script>` (es. `production-3d`); GPU con `use_gpu`, vedi la skill |

## Capacità e strumenti di verifica

| Risultato | Strumenti possibili | Verifica |
|---|---|---|
| Osservare qualsiasi output | `render.py` (FigCraft, VectorCraft, PhotoCraft, EffectCraft, SVG, PDF, video, Lottie, Office, immagini) | render registrato + `evidence.py observe` |
| Design di interfacce | FigCraft | `figcraft_audit.py`, render dei frame, prova dei prototipi |
| Siti esistenti del cliente | browser headless | `web_audit.mjs` (audit, non sviluppo) |
| Caratteri | `font_library.py` (~1900 famiglie a licenza aperta), fonderie commerciali proposte al cliente | `font_inspect.py`, specimen renderizzato |
| Colore | `color.py` (OKLCH, APCA, WCAG, daltonismo) | `color.py matrix`, `cvd` |
| Vettori e segni | VectorCraft | `svg_audit.py`, `svg_parity.py`, `logo_proof.py`, `optical_check.py` |
| Fotografia | PhotoCraft, `photo_set.py` (ricetta e coerenza del set) | `photo_set.py measure`, foglio di contatto |
| 3D | Blender (`pack_render.py`) | autoverifica di fedeltà colore e alte luci + render guardato |
| Mockup | PhotoCraft (master), `mockup_compose.py` per la prospettiva, Blender per il 3D | proporzioni, `image_check.py`, render guardato |
| Motion | EffectCraft | `motion_probe.py`, `lottie_check.mjs` |
| Stampa | VectorCraft o FigCraft (PDF con abbondanze, CMYK), Ghostscript per la verifica | `pdf_preflight.py` |
| Mondo del cliente | `world_ingest.py` | fogli di contatto |
| Confronti tra versioni | `pixel_diff.py` | regione attesa |

Capacità **dimostrate** su lavori di prova, con le prove: [CAPABILITIES.md](CAPABILITIES.md). Un
eseguibile presente nel registro non dimostra da solo il livello della produzione.

## Installazione

| Livello | Come | Approvazione |
|---|---|---|
| Toolchain utente (Python in venv, Node con versioni fisse, Chromium) | `bash .claude/tools/setup_tools.sh` → `~/.local/share/design-agency` | parte dello studio |
| Tool di sistema | `bash .claude/tools/setup_tools.sh --system` stampa il comando | lo esegue l'utente |
| Font a licenza aperta | `font_library.py fetch … [--install]` (licenza registrata) | parte del progetto |
| Font, foto, risorse a pagamento | mai acquistati o scaricati senza licenza | decide il cliente |

## Limiti dichiarati

- Nessun generatore d'immagini: fotografia e illustrazione pittorica vengono dal cliente, da
  shooting commissionato, da stock con licenza, da 3D o da illustrazione vettoriale; PhotoCraft le
  tratta e le compone. Quando una direzione dipende da immagini che non esistono, si dice prima.
- Misure di laboratorio (`web_audit`, Lighthouse) non sono dati di campo.
- I controlli legali sono ricerche preliminari, non pareri.
