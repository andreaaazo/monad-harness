# Protocollo di delega

## Ticket

Ogni delega ha un ticket, aperto da chi delega:

```sh
python3 .claude/scripts/ticket.py new --from <mittente> --to <agente> --type produzione|consulenza|revisione|ricerca|qa|consegna \
        --title "<cosa>" --request-file <file> --inputs <file…> --outputs <file o glob…> --accept <controlli…> \
        --medium vettoriale|motion|immagine|interfaccia|3d|nessuno [--medium-why "…"] [--parent T-0001] [--qa L1|L2|L3|L4]
python3 .claude/scripts/ticket.py deliver T-0004 --by <destinatario> --note "<una riga>"     # chi ha fatto il lavoro
python3 .claude/scripts/ticket.py deliver T-0005 --by qa-inspector --verdict READY|REVISE|NOT_VERIFIED --note "…"
python3 .claude/scripts/ticket.py accept T-0004 --by <mittente>                              # chi l'ha chiesto
python3 .claude/scripts/ticket.py rework T-0004 --by <mittente> --reason "<cosa cambiare>"
python3 .claude/scripts/ticket.py block T-0004 --by <agente> --reason "<cosa manca>"
python3 .claude/scripts/ticket.py tree        # chi ha chiesto cosa a chi
```

Due domande, due campi, nessuna interpretazione:

| Domanda | Campo | Valori |
|---|---|---|
| A che punto è il lavoro? | stato | `open`, `delivered`, `accepted`, `rework`, `blocked`, `cancelled` |
| Cosa ha trovato il revisore? (solo `qa`, `revisione`) | verdetto | `READY`, `REVISE`, `NOT_VERIFIED` |

Una revisione che boccia è un ticket `delivered` con verdetto `REVISE`: chi l'ha aperto la accetta e
manda il lavoro rivisto in `rework`. Chi accetta è chi ha aperto il ticket, dopo aver letto l'esito e
guardato gli output. Le azioni si firmano: `ticket.py` rifiuta chi non ne ha il diritto.

I campi obbligatori del contratto per ogni fase sono in [HANDOFFS.md](HANDOFFS.md). `--accept` prende
nomi di `checks.json`, o `req:<nome>` per un requisito del progetto, validi per tutti gli output
(`critique`) o per tipo di file (`'*.png=visual_review+optical_check'`, `'direction.md=facts_check'`).
**Ogni output ha almeno un controllo**, o un'esenzione motivata (`--exempt '<file>=motivo'`); le
cartelle non sono output: si dichiarano i file o un glob, che alla consegna deve trovare file.

## Messaggio di delega

Il destinatario non conosce la conversazione. Il prompt contiene sempre:

```text
TICKET   T-0004 (padre T-0002) · da design-director · tipo produzione · QA L3
CONTESTO 2–5 righe: progetto, fase, decisione approvata da rispettare
CONTRATTO work/creative-contract.md (versione) e riferimenti di livello del mezzo (work/references/levels.md)
INPUT    percorsi dei file da leggere (brief, strategia, direzione, token, master)
MEZZO    vettoriale, motion, immagine, interfaccia, 3d o nessuno: strumento obbligatorio (TOOLS.md)
OUTPUT   percorsi esatti da creare o modificare; master Craft assegnato e consegne derivate
VINCOLI  lingua, formati, dimensioni, licenze, cose da non toccare
CRITERI  requisiti verificabili (R1…), con il metodo di prova
VISIVI   immagini annotate, esempi approvati, dettagli da preservare (percorsi; anche come --inputs):
         un riassunto testuale conserva le intenzioni ma perde ciò che rende interessante una soluzione
LIVELLO  profondità attuale (1, 2 o 3): al livello 3 non si delega
```

## Esito

Ogni agente restituisce, in questo ordine e in forma breve:

```text
ESITO      delivered | blocked — una riga (registrato con ticket.py deliver o block)
VERDETTO   READY | REVISE | NOT_VERIFIED — solo per qa e revisione
FILE       percorsi creati o modificati
DECISIONI  scelte fatte e motivo; assunzioni
PROVE      controlli eseguiti → stato, con percorso della prova (registrate in evidence.py)
DIFETTI    aperti, con severità e posizione
RICHIESTE  "a <agente>: <cosa serve>" — solo se non hai potuto delegare tu
DOMANDE CLIENTE  per ognuna: domanda · perché cambia la soluzione · opzioni · raccomandazione ·
           bloccante sì/no · quale parte del lavoro resta ferma
PROSSIMO   l'azione successiva consigliata
```

**Massimo 12 righe.** I dettagli restano nei file: chi delega legge i file, non un riassunto lungo.
L'esito è un passaggio di consegne: chi riprende il lavoro parte da lì, senza la tua conversazione.

## Regole

- **Profondità**: router 0 → direttori 1 → specialisti 2 → consulenze 3. Non saltare
  livelli verso l'alto: una richiesta a un altro reparto passa dal direttore o dal router.
- **Parallelismo**: in parallelo ricerca, copy, consulenze e revisioni di file salvati.
  In sequenza tutto ciò che scrive sullo stesso file o sullo stesso server Craft.
- **Craft**: prima di qualsiasi tool `mcp__vectorcraft__*` o `mcp__effectcraft__*`,
  `craft_lock.py acquire <server> <tuo-nome> <documento> --ticket <T>`; a fine lavoro,
  salva e `release`. Un hook blocca le chiamate senza lock o di un altro titolare.
- **Timeout di scrittura**: ispeziona lo stato prima di ritentare.
- **Escalation**: dopo due iterazioni senza miglioramento, o in caso di conflitto tra
  reparti, l'agente registra `ticket.py block` con la diagnosi; decide il direttore, poi il router,
  poi il cliente se la scelta è sua.
- **Domande al cliente**: solo il router parla con il cliente (`CLIENT.md`). Gli agenti
  mettono le domande in `DOMANDE CLIENTE`, non inventano le risposte e non proseguono il
  lavoro che ne dipende: lo consegnano fino al punto in cui la risposta serve, con
  `ESITO blocked` se non c'è altro da fare.
- **Gate del cliente**: un ticket di una fase successiva a un gate si apre con
  `--after-gate <gate>`; `ticket.py` lo rifiuta se il cliente non ha approvato le versioni
  attuali dei file.
- **Agenti monouso**: un agente consegna e finisce. Risvegliarlo con `SendMessage` riscrive tutto il
  suo contesto nella cache, e dopo pochi minuti di pausa costa come ricominciare da capo: per un
  seguito apri un ticket nuovo con INPUT brevi e l'esito precedente. Due risvegli al massimo
  (`budget-guard.py`); chi delega non controlla a intervalli: viene avvisato quando l'agente finisce.
- **Budget**: `budgets.json` per ruolo. Al limite l'agente consegna ciò che ha e chiede in
  `RICHIESTE`; solo il router estende (`budget.py extend <agente> web|images <n> --by router --why "…"`).
