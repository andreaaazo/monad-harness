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
| Django, Django Ninja | Server e API | Da aggiungere con `uv add`, ultima LTS di Django |
| Alembic | Migrazioni del registro | Da aggiungere con `uv add` |
| `import-linter` | Confini tra moduli | Da aggiungere con `uv add` |
| Node | Build del frontend | 22.22.1 |
| pnpm | Dipendenze JavaScript, con quarantena | Da installare |
| React, Vite, TypeScript | Cruscotto, in `web/` | Da aggiungere |
| Playwright | Prove di fumo del cruscotto | Da aggiungere |
| Task | Ingresso unico dei comandi | 3.54.0 |
| Docker Compose | Server e servizi | 5.4.0 |

## Generazione (M4)

ComfyUI headless, solo esplorazione e texture (ADR-0009). Con 16 GB di VRAM il candidato è FLUX.2 Klein
4B, ma licenza e requisiti vanno verificati sulla fonte originale prima di usarlo.

## Da installare

`oiiotool` e `usdcat` non sono presenti. OpenImageIO arriva dal gruppo `qa` delle dipendenze Python;
OpenUSD non serve per ora.
