# Organigramma

Claude Code consente a un subagente di delegare ad altri subagenti fino a **tre livelli
sotto la sessione principale** (limite: `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`) e al massimo
20 subagenti attivi insieme (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`) [C1 in [SOURCES](SOURCES.md)].
Lo studio usa quei livelli come gerarchia:

```text
livello 0  router (sessione principale) — accoglie, instrada, gate, risponde al cliente
livello 1  direttori — pianificano il lavoro del reparto e lo approvano
livello 2  specialisti — producono
livello 3  consulenze e QA — misurano, verificano, rispondono a domande puntuali
```

Al livello 3 il tool `Agent` non è disponibile: chi ci lavora non delega e, se serve
altro, lo scrive nel blocco `RICHIESTE` del proprio esito.

## Reparti

| Reparto | Direttore (L1) | Specialisti (L2) |
|---|---|---|
| Strategia | `strategy-director` | `brand-strategist`, `researcher`, `copywriter` |
| Creativo | `creative-director` | `art-director`, `critic`; nello sprint `direction-a`, `direction-b`, `direction-c` |
| Design | `design-director` | `identity-designer`, `typographer`, `illustrator`, `editorial-designer`, `packaging-designer`, `mockup-artist`, `motion-designer` |
| Digitale | `digital-director` | `ux-designer`, `ui-designer` (design e prototipi, nessun codice) |
| Produzione e qualità | `production-director` | `production-manager`, `qa-inspector`, `legal-reviewer` |

`creative-director` è anche il responsabile dei programmi multi-reparto (dimensione L):
coordina gli altri direttori e firma la qualità creativa finale.

## Responsabilità

| Reparto | Risponde di | Non decide |
|---|---|---|
| Strategia | dossier e provenienza dei fatti, strategia, naming e voce, criteri di successo | la forma visiva |
| Creativo | sprint delle direzioni, scelta e carta della direzione, qualità creativa finale | fattibilità tecnica e conformità |
| Design | esecuzione di segno, sistema, applicazioni, brand book, motion; coerenza con la carta | posizionamento, scelta della direzione |
| Digitale | architettura, design di interfacce e siti, prototipi, accessibilità del design, handoff | identità e direzione; non scrive codice |
| Produzione e qualità | verifiche tecniche indipendenti, licenze e diciture, pacchetti, gate finale | il gusto |

## Diritti di decisione

| Materia | Decide | Consulta | Veto |
|---|---|---|---|
| Fatti, pubblico, posizionamento, criteri | `strategy-director` | cliente, `researcher` | — |
| Numero e brief delle direzioni, scelta e carta della direzione | `creative-director` | `critic`, `strategy-director` | il cliente sceglie al gate `direction` |
| Esecuzione dentro la carta (forme, spazi, correzioni ottiche) | `design-director` | specialisti, `critic` | `creative-director` se viola la carta |
| Soluzioni di interfaccia, interazioni, accessibilità del design | `digital-director` | `ui-designer`, `ux-designer`, `qa-inspector` | `production-director` su requisiti obbligatori |
| Producibilità, conformità, licenze, diciture | `production-director` | `legal-reviewer`, `production-manager` | **veto** su ciò che non è producibile o conforme |
| Gusto tra opzioni ugualmente valide, budget, tempi, rischio accettato | **cliente** | studio con raccomandazione | — |

Un veto blocca solo con una prova (misura, norma, specifica del fornitore) e una proposta
alternativa; senza prova è un'opinione e si tratta come disaccordo.

## Disaccordi

1. Chi rileva il disaccordo apre un ticket `--type disaccordo` verso chi decide la materia
   (tabella sopra), con `work/disputes/D-<n>.md` dal modello `templates/dispute.md`: domanda in
   una frase, posizioni con prove, criteri applicabili, opzioni.
2. Chi decide sceglie entro un passaggio, scrive la decisione e il motivo; il router la registra
   in `.agency/decisions.md`. Il lavoro che dipende dalla decisione resta fermo fino ad allora.
3. Se la materia è del cliente, o se il disaccordo è tra due direttori con pari diritto, il
   `creative-director` (materia creativa) o il router (il resto) prepara le opzioni e il router le
   presenta al cliente con la raccomandazione dello studio.
4. Una decisione si riapre solo con un fatto nuovo, non con la stessa argomentazione.

## Chi può chiedere a chi

| Da | Può aprire ticket verso | Per |
|---|---|---|
| router | chiunque | instradamento |
| `creative-director` | direttori, `art-director`, `critic` | programmi L, direzione, critica |
| direttori | specialisti del proprio reparto; altri direttori per lavoro trasversale; `qa-inspector`, `critic` | produzione e verifiche |
| specialisti | `qa-inspector`, `researcher`, `copywriter`, `typographer`, `legal-reviewer`, `critic` come consulenze; altri specialisti solo per un'informazione puntuale | dati, testi, misure, pareri |
| `qa-inspector`, `critic`, `legal-reviewer` | nessuno (lavorano su file salvati e restituiscono `RICHIESTE`) | indipendenza del giudizio |
| `direction-a`, `direction-b`, `direction-c` | nessuno (niente tool `Agent`; un hook impedisce di vedere le altre direzioni) | esplorazione indipendente |

Una richiesta di **produzione** a un altro reparto passa dal suo direttore o dal router,
così il carico e i server Craft restano coordinati. Le **consulenze** possono andare dirette.

## Server Craft

| Server | Autori tipici | Regola |
|---|---|---|
| `figcraft` | `ui-designer`, `ux-designer`, `editorial-designer`, `identity-designer` | un titolare per volta con `craft_lock.py` |
| `vectorcraft` | `identity-designer`, `typographer`, `illustrator`, `editorial-designer`, `packaging-designer` | idem |
| `effectcraft` | `motion-designer` | idem |
| `photocraft` | `mockup-artist`, `editorial-designer`, `packaging-designer`, `illustrator` | idem |

Il mezzo decide lo strumento e il master (TOOLS.md): chi assegna il lavoro lo scrive nel ticket con
`--medium`. I direttori, i revisori, la strategia e il QA non hanno gli MCP Craft (`disallowedTools`) e lavorano su file salvati, export e CLI. Gli
esploratori dello sprint usano solo le CLI su file propri, per lavorare in parallelo.

## Costi

Ogni livello aggiunto costa contesto e token. Il router usa il punto d'ingresso più basso
che basta; i direttori delegano solo ciò che richiede una competenza diversa dalla loro;
gli esiti restano brevi e i dettagli vivono nei file.
