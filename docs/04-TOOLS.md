# Strumenti

Verificato su questa macchina il 2026-10-31: 24 core, 60 GB di RAM, RTX 5080 Laptop con 16 GB di VRAM,
Docker 29.9, `bwrap`.

## Produzione

| Strumento | Versione | Mezzo | Master | Accesso | Comandi |
|---|---|---|---|---|---|
| VectorCraft | 0.18.0 | Vettoriale | `.vectorcraft` | CLI, MCP headless | 822 |
| EffectCraft | 0.18.0 | Motion | `.ecproj` | CLI, script | ~700 |
| PhotoCraft | 0.17.0 | Immagine | `.pcraft` | CLI, `serve`, MCP | ~900 |
| FigCraft | 0.12.1 | Interfaccia, impaginati | `.figcraft` | CLI, MCP | 615 |
| Blender | 5.2.3 LTS | 3D | `.blend` | `blender -b`, bpy | API Python |

Per EffectCraft e PhotoCraft il numero viene dalle righe del catalogo: è un ordine di grandezza. Tutti
e cinque girano in `bwrap` senza rete (`spikes/sandbox_craft.sh`).

**Lo strumento è obbligatorio per mezzo.** Il calcolo in `compute` serve a costruire, poi entra nel
master. Le consegne si esportano dal master.

**Esclusi:** `artcraft-launcher` non si esegue mai: ha già installato software da solo.

## Strumenti per gli agenti

Set fisso per ruolo, definito in `agency.tools`.

| Strumento | Ruoli | Scopo |
|---|---|---|
| `read_file`, `write_file`, `list_files` | Tutti, nel perimetro del ticket | File del progetto |
| `read_skill` | Tutti | Carica una skill |
| `view_image` | Tutti | Immagini; quelle grandi si riducono da sole |
| `render` | Tutti | Rende un output e lo registra |
| `craft_search`, `craft_describe`, `craft_run` | Secondo `craft` in `roles.json` | Comandi delle applicazioni |
| `export_master` | Autori | Consegne derivate dal master |
| `compute` | Autori | Python in sandbox, senza rete |
| `run_check` | Tutti, secondo i ruoli ammessi | Controlli QA registrati |
| `judge` | Revisori | Giudizio con confronto e motivazione |
| `web_search`, `web_fetch` | Da M2 | Strumenti server dell'API, 10 $ ogni 1.000 ricerche, accettati dai nostri modelli |
| `open_ticket` | Secondo `ORG` | Delega |
| `ask_client` | Agenti, passa dal router | Domande per il cliente |
| `deliver`, `block` | Assegnatario | Fine del lavoro |
| `draft_presentation`, `present_concepts` | Direttore, in presentazione | Compone le pagine, poi le manda al cliente solo se guardate (ADR-0017) |

Nessuna shell generica: ogni azione è tipizzata, e il sistema può vederla, autorizzarla e registrarla.

## Verifica

| Area | Strumenti | Origine |
|---|---|---|
| Vettori | `svg_audit`, `svg_parity`, `logo_proof` | Script dello studio |
| Immagini | `image_check`, `optical_check`, `pixel_diff`, OpenImageIO | Studio, M3 |
| Colore | `color` (OKLCH, APCA, WCAG, daltonismo) | Studio |
| Tipografia | `font_inspect`, `type_scale`, `font_library` | Studio |
| Stampa | `pdf_preflight`, Ghostscript, poppler | Studio |
| Interfacce | `figcraft_audit` | Studio |
| Motion | `motion_probe`, `lottie_check`, ffprobe | Studio |
| Token | `tokens_check` | Studio |
| 3D | `pack_render`, trimesh, bpy | Studio, M3 |
| Siti esistenti | `web_audit` (solo audit) | Studio |

I controlli oggi sono soprattutto 2D perché il lavoro dello studio è soprattutto 2D: trimesh e OpenImageIO
si sommano a questi, non li sostituiscono.

## Contesto

| Strumento | Uso | Traguardo |
|---|---|---|
| Pillow, ffmpeg | Anteprime, frame, fogli di contatto | M1 |
| Modello di scena | Struttura dei master | M3 |
| LanceDB + SigLIP | Ricerca visiva locale | M3 |
| OpenUSD | Solo se servirà scambiare scene (ADR-0007) | Non previsto |

## Server e interfaccia (M1.6)

Scelte in ADR-0020. Le versioni indicate sono verificate su questa macchina il 2026-11-01.

| Strumento | Uso | Stato |
|---|---|---|
| Django, Django Ninja | Server e API, `uv run agency-server` | Django 5.2.18 LTS, supportata fino ad aprile 2028; Django Ninja 1.7.1 |
| `django-stubs` | Tipi di Django per `pyright`, solo sviluppo | 5.2.9 |
| Alembic | Migrazioni del registro | 1.20.0 |
| `import-linter` | Confini tra moduli, in `make check` | 2.15 |
| mise | Versioni degli strumenti locali, da `mise.toml` (ADR-0034) | 2026.10.3, installato da Andrea |
| Node | Build ed esecuzione di Next.js, che chiede almeno la 20.9 | 22.22.1, da mise |
| pnpm | Dipendenze JavaScript, con quarantena di due settimane | 12.14.0, da mise |
| `openapi-typescript` | Tipi TypeScript da `schemas/openapi.json` (ADR-0032) | 7.13.0 |
| TypeScript | Tipi dell'interfaccia, `strict` | 5.9.3: `openapi-typescript` non supporta ancora la 6 e la 7 |
| Next.js | Interfaccia, in `web/`, server `output: 'standalone'` (ADR-0024, ADR-0033) | 16.4.2: al 2026-11-01 la 16.4.3, del 23 ottobre, era ancora in quarantena |
| React | Componenti delle pagine | 19.3.1, con `@types/react` 19.3.0 |
| Playwright | Prove di fumo del cruscotto, `make e2e` | 1.64.1, con Chromium `chromium-1248` già in cache. Se manca, Andrea lo installa: `mise exec -- pnpm --dir web exec playwright install chromium` |
| `node --test` | Prove unitarie dell'interfaccia, senza dipendenze | Quello di Node, che esegue TypeScript da sé |
| Task | Ingresso unico dei comandi | 3.54.0, da mise |
| Docker Compose | Server e servizi | 5.4.0 |

## Generazione (M4)

ComfyUI headless, solo esplorazione e texture (ADR-0009). Con 16 GB di VRAM il candidato è FLUX.2 Klein
4B, ma licenza e requisiti vanno verificati sulla fonte originale prima di usarlo.

## Da installare

`oiiotool` e `usdcat` non sono presenti. OpenImageIO arriva dal gruppo `qa` delle dipendenze Python;
OpenUSD non serve per ora.
