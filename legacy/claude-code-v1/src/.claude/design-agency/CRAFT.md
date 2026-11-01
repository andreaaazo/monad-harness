# Craft — MCP e CLI

Quale strumento per quale mezzo: [TOOLS.md](TOOLS.md). Qui, come operare.

I server `vectorcraft` ed `effectcraft` partono da `.claude/scripts/start-craft.sh`, che
confina letture e scritture alla radice del progetto (`--automation-read-root` e
`--automation-write-root`). Gli agenti autori ereditano i tool `mcp__vectorcraft__*` e
`mcp__effectcraft__*` della sessione; l'elenco non è fissato nei prompt [C4 in [SOURCES](SOURCES.md)].

## Lock (obbligatorio)

```sh
python3 .claude/scripts/craft_lock.py acquire vectorcraft <tuo-nome-agente> <documento> --ticket <T-…>
python3 .claude/scripts/craft_lock.py renew   vectorcraft <tuo-nome-agente>      # lavori lunghi
python3 .claude/scripts/craft_lock.py release vectorcraft <tuo-nome-agente>      # dopo aver salvato
```

L'hook `craft-guard.py` (PreToolUse) blocca ogni tool `mcp__vectorcraft__*` o
`mcp__effectcraft__*` senza un lock valido, e quello di un agente diverso dal titolare quando
l'hook conosce l'agente chiamante. Il router può forzare il rilascio solo dopo aver verificato
che il titolare ha finito e salvato.

## Prima di operare

1. Il server previsto è connesso (`/mcp`, o una chiamata di ispezione non mutante).
2. Leggi descrizioni e schemi dei tool **della sessione corrente**; se sono differiti,
   caricali con la ricerca tool del client. Non inventare nomi o payload.
3. Per i comandi del motore leggi il catalogo del server: parametri, unità, enum, default.
4. Ispeziona documento attivo, selezione, ID e risorse. Conferma di essere l'unico autore
   della connessione prima di aprire o modificare documenti.

## Durante

- Dopo un errore di schema, rileggi lo schema e ricostruisci il payload.
- Dopo un **timeout di scrittura**, ispeziona lo stato prima di ritentare: l'operazione
  potrebbe essere riuscita.
- Salva lo stesso master a milestone. EffectCraft parte senza `--autosave`.
- Mantieni i percorsi nella radice; un'operazione negata non si aggira con un'altra interfaccia.

## Controlli del mestiere

**VectorCraft**: unità del documento, indici delle tavole, ID, curve, testo e font,
maschere, bounding box, opzioni di export, viewBox degli SVG [S1]. Il master resta
editabile; outline e raster sono derivati dichiarati.

**EffectCraft**: base temporale del layer rispetto alla composizione, fps, offset,
pivot, property path dall'ispezione (non da stringhe fisse), alpha e formato. Rileggi
le proprietà dopo aver scritto i keyframe e dopo la riapertura.

**Entrambi**: salva → renderizza → osserva → esporta → riapri → verifica.

## Fuori dalla sessione MCP (CLI installate, versione 0.18.0 osservata il 2026-10-29)

- `vectorcraft-cli convert IN OUT --scale K` rasterizza un SVG o un master: è il renderer
  usato da `logo_proof.py`. `vectorcraft-cli commands` stampa il catalogo dei comandi.
- `effectcraft-cli commands --filter lottie` elenca `file.exportLottie` e `file.importLottie`.
  `effectcraft-cli render-frame` e `render` producono frame e video dalla riga di comando.

Queste CLI non condividono il documento attivo della sessione MCP: usale su file salvati.

Esempi verificati il 2026-10-31 (CLI su file diversi, anche in parallelo):

```sh
vectorcraft-cli run --commands passi.json --export work/source/segno.vectorcraft   # comandi nativi
vectorcraft-cli convert calcolo.svg work/source/segno.vectorcraft                  # geometria calcolata → master
vectorcraft-cli info work/source/segno.vectorcraft                                 # oggetti, tavole, font
figcraft-cli run passi.json --in a.figcraft --out a.figcraft
photocraft-cli run --new '{"width":2400,"height":1600}' --out work/source/foto.pcraft
photocraft-cli run foto.pcraft --cmd <id> --params '{…}' --out foto2.pcraft
effectcraft-cli run file.saveAs '{"path":"…/motion.ecproj"}'
```

`passi.json` di VectorCraft è una lista `[{"command":"path.create","params":{…}}]`: `shape.*`,
`path.create {anchors|d}`. Dopo: `.claude/scripts/py .claude/scripts/master.py export <master> <file>`.

## Renderer EffectCraft

`AGENCY_EFFECTCRAFT_RENDERER=auto` (default) aggiunge `--gpu` se la CLI lo offre;
`native` lascia la scelta al programma; `gpu` lo impone. Verifica sempre il backend reale.

## Diagnostica

`/design-preflight` controlla configurazione, eseguibili e flag di confinamento.
`claude mcp get <server>` mostra le configurazioni persistenti, che possono differire da
una sessione avviata con `start-agency.sh` (`--strict-mcp-config`). Un health check
riuscito non equivale a un export riuscito.
