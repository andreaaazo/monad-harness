# ADR-0057: l'albero dei pacchetti del motore

**Contesto.** ADR-0021 fissa i principi del monolite a slice, ma non disegna l'albero dei pacchetti. Oggi `agency.tools`
tiene insieme due cose diverse:
- la piattaforma su cui lavorano gli strumenti: sandbox, file, Craft, render, master, tavola;
- gli strumenti che il modello chiama, tutti in `tools/surface.py`, 1.130 righe.

`graph/workflow.py` tiene tutti i nodi dentro `build`, che ha complessità McCabe 65. Fra i pacchetti di `agency`
resta un solo ciclo, `tools → qa`, verificato con il contratto `acyclic_siblings` di import-linter 2.15. Il piano
`docs/superpowers/plans/2026-11-14-m1-7-slice-architecture.md` porta M1.7 dai punti 1 a 3. Andrea ha lasciato
all'esecuzione le quattro scelte che il piano gli chiedeva.

**Decisione.**
1. **`agency.tools` diventa `agency.workshop`**, quando gli strumenti degli agenti ne sono usciti. Dopo la divisione,
   «tools» vorrebbe dire tre cose: la piattaforma, il kit degli strumenti, gli strumenti del modello.
2. **Le slice stanno sotto un solo pacchetto, `agency.studio`:** `exploration`, `selection`, `proposal`,
   `presentation`, `refinement`, `delivery`. Sono le sei capacità di ADR-0021. Un pacchetto in più al primo livello,
   invece di sei, perché `pyproject.toml` elenca a mano ogni pacchetto di primo livello in cinque contratti.
3. **I livelli, dal basso.** Ognuno importa solo da quelli sotto:

   | Livello | Pacchetti |
   |---|---|
   | contratti | `contracts` |
   | piattaforma | `config`, `registry`, `ledger`, `gateway`, `telemetry`, `artifacts`, `workshop` |
   | controlli | `qa` |
   | kit degli strumenti | `toolkit` |
   | slice | `studio` |
   | agenti | `agents` |
   | processo | `process` |
   | ingressi | gli entry point |

   `evaluation` e `insights` restano sui soli contratti. `agents` sta sopra `studio`, perché il catalogo degli
   strumenti, in `agents.toolbox`, importa gli strumenti delle slice. I nodi delle slice raggiungono l'agente
   attraverso il protocollo `Runner`, senza importarlo. Così `Toolbox(context)` conserva il suo default, e i test
   che creano `AgentRunner` non cambiano.
4. **Gli script QA si montano solo quando gira un controllo.** `/opt/agency-qa` non sta più in ogni comando della
   sandbox: `qa.checks` aggiunge il montaggio con `Sandbox.with_mount`, e la sandbox non conosce più la cartella di
   `qa`. Nessun prompt e nessuna voce del registro nominano `/opt/agency-qa`.

L'albero alla fine dei punti 1–3:

| Pacchetto | Contiene |
|---|---|
| `agency.workshop` | sandbox, file, Craft, master, render, la tavola anonima |
| `agency.qa` | controlli, consegna, prove; gli script restano in `qa/scripts/` |
| `agency.toolkit` | il kit degli strumenti (`Tool`, `ToolContext`, `Refused`) e gli strumenti condivisi: file, Craft, revisione, chiusura |
| `agency.studio` | le sei slice, ognuna con i suoi strumenti e i suoi nodi; `shared.py` con lo stato del grafo, `Runner` e `Crew` |
| `agency.agents` | il ciclo dell'agente, i prompt, le trascrizioni, il catalogo e `Toolbox` |
| `agency.process` | la composizione del grafo e le sessioni |

Spariscono `agency.tools`, `agency.graph` e `agency.runtime`.

**Conseguenze.**
- **Cosa non cambia.** Restano identici:
  - nomi, descrizioni e schemi degli strumenti, compresi i nomi delle classi, che compaiono come `$defs` nelle
    richieste;
  - i nomi dei nodi e i nomi delle tracce.

  Gli snapshot delle richieste restano byte per byte quelli di M1.6.
- **Ogni spostamento cambia l'impronta.** `agency compare` mostrerà come cambiati tutti i file spostati.
- **Una sandbox vede meno.** I comandi di `compute`, `craft_run` e `render` non vedono più gli script QA.
- **`board.py` resta nella piattaforma.** Lo usano due slice: l'esplorazione con `submit_concept` e la selezione con
  `make_board`.
- **Il contratto `acyclic_siblings` vale da subito su tutto `agency`.** È anche il primo contratto della specifica
  di M1.8 (§6.5).
- **I punti 4–6 di M1.7 restano da pianificare.** Dominio, applicazione, livelli imposti e piramide dei test si
  pianificano quando le slice esistono.
