# Sistema qualità

Ogni affermazione di qualità è una prova legata a un file preciso. Le prove si registrano
con `evidence.py`, che salva l'hash del file: **se il file cambia, la prova scade** e il
gate la rifiuta. Così una correzione non può ereditare il `PASS` della versione precedente.

```sh
python3 .claude/scripts/evidence.py record --file <file> --check <controllo> --result PASS|FAIL|NOT_VERIFIED|NOT_APPLICABLE \
        --by <agente> [--proof <immagine o report>] [--ticket T-…] [--note "…"]
python3 .claude/scripts/evidence.py gate <file…> --require <controllo1,controllo2,…>
```

## Livelli

| Livello | Chi | Cosa | Quando |
|---|---|---|---|
| L1 autocontrollo | autore | script della skill, render osservato, checklist del deliverable | sempre |
| L2 verifica tecnica | `qa-inspector` | misure indipendenti, render a dimensione d'uso, checklist completa, regressioni | ogni consegna al cliente |
| L3 critica creativa | `critic` (+ `creative-director` per direzioni) | idea, distintività, mestiere, sistema; primo giudizio prima delle motivazioni | lavoro creativo nuovo o direzioni |
| L4 produzione | `production-director` con `production-manager`, `legal-reviewer` | file di consegna, preflight, licenze, diciture, pacchetto completo | stampa, packaging, siti, identità finali |

Un livello include i precedenti.

## Chi firma

Ogni prova ha un firmatario (`--by`), il ruolo che sta davvero lavorando: un hook lo confronta con
l'identità dell'agente e blocca firme altrui, variabili e scritture dirette sui registri.
`design-agency/checks.json` è il registro dei controlli: tipo, indipendenza, ruoli ammessi.

- **Autore**: chi riceve il ticket di produzione del file. Non firma i controlli indipendenti
  (critica, giudizi, `proof_read`, `legal_text`): `evidence.py` lo rifiuta.
- **Ticket `qa` e `revisione`**: valgono solo le prove firmate dal destinatario del ticket. Le misure
  dell'autore non soddisfano il QA: si rifanno.
- **Un FAIL resta**: sulla stessa versione del file, un FAIL si cambia solo con la firma di chi l'ha
  dato. Per il resto si corregge il file, e la prova scade da sola.
- I requisiti del singolo progetto si chiamano `req:<nome>`; ogni altro nome viene rifiutato.

## Tre giudizi distinti

| Giudizio | Stato | Come si ottiene | Cosa NON dice |
|---|---|---|---|
| Misura disponibile | `MEASURED` | uno script ha misurato (ottica, diversità) | che il risultato sia buono |
| Requisito soddisfatto | `PASS` / `FAIL` | una soglia tecnica o normativa (contrasto, abbondanza, target) | che il design funzioni |
| Qualità percettiva raggiunta | `PASS` / `FAIL` con `evidence.py judge` | confronto visivo con riferimenti, alternative o la versione precedente, motivazione, limiti | — è un giudizio, con i limiti di chi lo dà |

`visual_review` (render visto e descritto) è un prerequisito del giudizio, non il giudizio.

## Controlli per deliverable

Nomi dei controlli da usare in `--check` e `--require`:

| Deliverable | Controlli richiesti |
|---|---|
| Logo / simbolo (SVG) | `svg_audit`, `svg_parity`, `logo_proof`, `distinctiveness`, `critique` |
| Palette | `contrast_matrix`, `cvd`, `palette_render` |
| Tipografia | `font_license`, `font_coverage`, `specimen_render` |
| Token | `tokens_check`, `contrast_matrix` (per tema) |
| Immagini di consegna | `image_check` |
| Mockup | `mockup_aspect`, `image_check`, `visual_review` |
| PDF di stampa | `pdf_preflight`, `visual_review`, `proof_read` |
| Packaging | `pdf_preflight`, `dieline_check`, `legal_text`, `barcode`, `visual_review` |
| Video / motion | `motion_probe`, `keyframe_review`, `playback_review` |
| Lottie | `lottie_check`, `keyframe_review` |
| Design di sito o app (FigCraft) | `design_audit` (`figcraft_audit.py`), `visual_review` di ogni frame, `prototype_review` (percorsi provati a passi su desktop e touch, stato ridotto), `copy_review` |
| Sito esistente del cliente (audit) | `web_audit` (tutti i breakpoint), `lighthouse` |
| Render 3D | `render_check` (autoverifica di `pack_render.py`: fedeltà colore, alte luci) + `visual_review` |
| Set fotografico | `photo_set` (misura di coerenza) + `visual_review` del foglio |
| Presentazione | `visual_review`, `proof_read`, `image_check` sugli export |
| Icone e SVG di consegna | `svg_audit`, `svg_parity` |
| Documenti di strategia, brief, direzioni, selezione | `facts_check` (registrato da `facts.py check --record-by`) |
| Dossier | `dossier_coverage` (registrato da `facts.py coverage --record-by`) |
| Sprint delle direzioni | `board_check`, `diversity`, `concept_diversity` su `apps.json`, `direction_lint` su ogni `direction.md` (registrati da `direction_board.py --record-by`); `board_review` sulle tavole |
| Composizioni principali (poster, hero, copertine, segno) | `optical_check` + `visual_review` |
| Ogni artefatto dopo la scelta della direzione | `charter_review` |
| Contratto creativo, direzioni, selezione | `contract_check` (`contract_lint.py --record-by`) |
| Sistema approvato | `stress_test`: un'applicazione nuova e sfavorevole (pagina tecnica, comunicazione operativa, documento denso; titoli lunghi, foto disomogenee, molti dati), giudicata con `evidence.py judge … --check stress_test` |
| Qualità percettiva di un artefatto chiave | `quality_judgement` (`evidence.py judge`, con confronto) |
| Qualsiasi lavoro creativo nuovo | `critique` (giudizio con confronto) |

Ogni produzione con un mezzo aggiunge `master_open` sul master (`master.py check --record-by`).

`visual_review`, `keyframe_review`, `playback_review`, `board_review`, `charter_review`,
`logo_proof`, `specimen_render`, `palette_render`, `mockup_review` sono **controlli di
osservazione**: `evidence.py` li accetta come PASS solo con `--proof` che sia un render della
versione attuale del file (`render.py` o `logo_proof.py`, registrati in `.agency/renders.jsonl`).
`keyboard_review`, `proof_read`, `copy_review` richiedono di aver letto o percorso il risultato
reale, con la trascrizione dei passaggi come prova.

## Checklist

Le checklist dettagliate stanno nelle skill: `logo-design` (test), `color-system`,
`type-system`, `mockup`, `print-production`, `packaging`, `web-qa`, `motion-identity`,
`presentation`, `visual-qa`. La critica segue `critique` e il modello
[templates/review.md](templates/review.md).

## Severità

| Severità | Significato | Effetto |
|---|---|---|
| Bloccante | inutilizzabile, errato, rischio (flash, licenza, dicitura obbligatoria mancante) | niente consegna |
| Maggiore | requisito obbligatorio fallito, idea debole o confondibile, difetto visibile all'uso | niente consegna finale |
| Minore | difetto localizzato che non compromette l'uso | da correggere o dichiarare |
| Preferenza | alternativa estetica senza violazione | a discrezione |

## Regressioni

Dopo ogni correzione: rigenera le prove interessate, `pixel_diff.py` tra prima e dopo per
dimostrare che è cambiato solo ciò che doveva, e ricontrolla le dipendenze (un token cambiato
invalida le coppie di contrasto e le tavole che lo usano).
