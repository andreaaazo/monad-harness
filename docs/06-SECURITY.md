# Sicurezza

Sistema locale con un solo operatore, ma con tre fonti non fidate: risposte del modello, materiali del
cliente, contenuti del web. Resta locale fino a M6, quando il cliente dovrà raggiungere l'interfaccia, e con un solo operatore
fino a M7 (ADR-0023).

## Minacce e difese

| Minaccia | Esempio | Difesa |
|---|---|---|
| Prompt injection | Un PDF del cliente dice di inviare file altrove | Niente rete nelle sandbox, nessuno strumento di invio, azioni tipizzate; i contenuti esterni sono marcati come dati |
| Firma falsa | Un agente si spaccia per il QA | L'attore lo imposta l'harness; gli schemi non hanno il campo |
| Autoapprovazione | L'autore giudica il proprio lavoro | Controlli indipendenti eseguiti da un'altra istanza |
| Alterazione dei registri | Modifica di una prova | Trigger, catena di hash, nessuno strumento scrive i registri |
| Fuga della chiave | La chiave finisce in un log o in una risposta | Solo nel gateway, `SecretStr`, assente dall'ambiente delle sandbox, `.env` fuori dalla portata di ogni strumento |
| Fuga fuori dal perimetro | Path traversal | `bwrap` per ciò che gira in sandbox. Gli strumenti che girano nell'harness non hanno quella difesa: passano da `inside()` o da un elenco chiuso (`read_skill`, `list_files`) |
| Dipendenza compromessa | Il caso LiteLLM di marzo 2026 | Quarantena di due settimane, lock con hash, poche dipendenze, anche per JavaScript |
| Scrittura dal cruscotto | Una richiesta altera il registro | API solo `GET` in M1.6, connessione `mode=ro`, nessun modello Django sul registro |
| Cruscotto esposto in rete | Materiali del cliente leggibili da fuori | Django e Next.js solo su loopback, porta pubblicata su `127.0.0.1`, verificato da un test |
| DNS rebinding | Una pagina web fa puntare un suo nome a `127.0.0.1` e legge il cruscotto dal browser | Django: `ALLOWED_HOSTS` solo loopback, controllato su ogni richiesta (ADR-0031). Next.js: `src/proxy.ts` rifiuta ogni `Host` non loopback prima di pagine, `/api` e file statici, perché il suo proxy riscrive l'`Host` verso Django (ADR-0033). Test per entrambi |
| Copie dei materiali fuori dal progetto | Next.js salva immagini o risposte in `.next/cache`, o un browser tiene in cache le pagine | `images.unoptimized`, `cache: 'no-store'` su ogni lettura, pagine sempre dinamiche, `Cache-Control: no-store` anche sulle pagine statiche. Verificato da un test |
| Custom node maligno | Codice in ComfyUI | Container senza uscita, niente Manager, nodi bloccati per hash |
| Costo fuori controllo | Un loop che non finisce, o una scelta sbagliata al gate | Budget preventivo, tetto nella Console, `agency decide` che rifiuta una scelta inesistente |
| Comando distruttivo | Sovrascrive un master | Artefatti per hash: ogni versione consegnata resta, e `agency restore` la riporta |

## Sandbox

Profilo collaudato per i Craft:

```sh
bwrap --ro-bind /usr /usr --ro-bind /etc /etc --symlink usr/bin /bin --symlink usr/lib /lib \
      --symlink usr/lib64 /lib64 --proc /proc --dev /dev --tmpfs /tmp \
      --bind <cartella-del-lavoro> /job --chdir /job \
      --unshare-net --unshare-pid --die-with-parent
```

Provato: i Craft e Blender funzionano; le altre cartelle non esistono; rete assente; `/usr` non scrivibile.
`/etc` è montato per i font e la configurazione di sistema: in M1 va ridotto al necessario.

## Dati del cliente

I materiali restano in `projects/<slug>/`. Possono uscire solo verso l'API Anthropic, necessaria per il
lavoro. La vecchia regola "mai a servizi esterni" va quindi scritta con precisione: **l'unico servizio
esterno ammesso è l'API Anthropic**, e il cliente deve saperlo.

- **Ricerche web**: solo informazioni pubbliche, mai dettagli riservati nelle query.
- **Telemetria**: Langfuse solo locale. Per default le tracce non contengono il testo dei materiali.
- **Programmatic tool calling e code execution dell'API**: non si usano con i file del cliente, perché
  girano in un container Anthropic.
- **Prima del primo cliente reale**: verificare retention e regione dei dati (`inference_geo` esiste) e
  scriverle nel contratto. È una decisione aperta in `00-PROJECT.md`.

## Supply chain

- `exclude-newer` in `pyproject.toml`: nessun pacchetto più recente di due settimane. Va aggiornato a mano.
- `uv.lock` versionato.
- Immagini Docker bloccate per digest, pesi dei modelli per hash.
- DSPy dipende da LiteLLM: non entra nell'ambiente principale (ADR-0008).
- Le dipendenze JavaScript hanno la stessa quarantena di due settimane, con `minimumReleaseAge` di pnpm e lock versionato.

## Cruscotto e server

- Django e Next.js non ricevono la chiave né `.env`, e non eseguono il grafo (ADR-0019, ADR-0024). Il server di Django non importa
  `agency.config`, che legge `.env`, e all'avvio toglie la chiave dal proprio ambiente (ADR-0031).
- Docker pubblica solo la porta di Next.js, su `127.0.0.1`: una porta pubblicata senza indirizzo ascolta su tutte le interfacce.
- Fuori da Docker, `next dev` parte con `-H 127.0.0.1` e il server standalone con `HOSTNAME=127.0.0.1`: di suo ascolta su
  `0.0.0.0`. I processi di Next.js e Django non ricevono la chiave: un test la mette nell'ambiente di chi li avvia e la cerca in
  `/proc`.
- `.data` e `projects/` entrano solo nel container di Django, senza mount `:ro`, fragile con WAL: la sola lettura sta nella
  connessione.
- La telemetria di Next.js resta spenta con `NEXT_TELEMETRY_DISABLED=1`, build compresa.
- Le trascrizioni contengono i materiali del cliente: il cruscotto resta su questa macchina fino a M6.

## Verso il SaaS

Con M7 cade il presupposto di un solo operatore (ADR-0023). Prima del primo cliente del SaaS servono autenticazione e permessi,
isolamento dei dati tra clienti, sandbox fuori da questa macchina, segreti fuori dai file, e un modello delle minacce riscritto.
Chiave API, materiali del cliente e sandbox non cambiano regole: cambiano le difese attorno.

## Regole operative

- Nessun servizio ascolta su interfacce diverse da loopback, fino all'ADR che in M6 deciderà come il cliente raggiunge
  l'interfaccia.
- Nessun launcher sconosciuto: `doctor` interroga solo CLI note.
- `.env` non si versiona.
