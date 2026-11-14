# Progetto

## Perché

Lo studio funziona dentro Claude Code CLI, ma ne eredita i limiti. La prova Neima ha mostrato dove
si rompe:

- **Le regole dipendono dal modello.** Gli hook leggono il testo dei comandi, sono aggirabili e
  arrivano dopo la decisione. Il direttore ha potuto scrivere "non servono" sui Craft.
- **Il contesto non si controlla.** Media di ~190.000 token per chiamata, di cui 36–52k fissi.
- **L'attesa costa.** Il 71% delle scritture in cache è arrivato dopo pause oltre i 5 minuti, per
  agenti fermi ad aspettare i loro sotto-agenti.
- **Il processo non è durevole.** Lo stato sta in file e nella memoria della sessione.

Un harness nostro trasforma queste regole da istruzioni a proprietà del sistema.

## Obiettivo

Un sistema che prende una richiesta di design di qualsiasi tipo, lavora con il cliente a tappe e
consegna master editabili, con ogni affermazione di qualità legata a una prova, a un costo noto in
anticipo. Almeno pari al setup precedente in ciò che fa, migliore in ciò che garantisce.

Oggi gira su questa macchina, per questo studio. Dopo il primo cliente reale diventa un SaaS completo, stabile e forte
(ADR-0023).

## Requisiti

Ereditati dallo studio, non negoziabili:

1. **Parità completa**: tutto ciò che è in `docs/PARITY.md` arriva o viene dismesso con un motivo.
2. **Personalizzazione**: mondo del cliente, fatti con provenienza (cliente, fonte, ipotesi), test di
   sostituzione.
3. **Cliente a tappe**: scoperta senza limite di domande, gate approvati con parole esplicite e legati
   all'hash dei file.
4. **Strumento per mezzo**: vettori VectorCraft, motion EffectCraft, immagini PhotoCraft, interfacce
   FigCraft, 3D Blender. Le consegne derivano dal master.
5. **Prove**: misura, requisito e giudizio distinti; revisione indipendente dall'autore.
6. **Sprint isolato** con esploratori che non si vedono e scelta senza fusioni.
7. **Niente codice** di siti e app.
8. **L'idea si giudica prima della rifinitura**: esplorazione a schizzi in parallelo, in cui si pensa disegnando e
   guardando. Un segno deve reggere al primo sguardo, senza spiegazioni. La scelta tra gli schizzi è dello studio; il cliente vede solo proposte
   sviluppate, nel loro contesto, con la raccomandazione. Solo dopo la sua scelta si rifinisce.

Nuovi con l'harness:

9. **Identità imposta**: un agente non dichiara chi è.
10. **Modello e budget del cliente**: sono gli unici vincoli al lavoro. Ogni chiamata è autorizzata prima di partire;
    a budget finito il lavoro si ferma salvato e riparte quando il cliente lo alza.
11. **Durabilità**: un processo interrotto riprende senza rifare lavoro né duplicare effetti.
12. **Riproducibilità**: ogni artefatto risale a input, ruolo, modello, prompt e strumenti.
13. **Misurabilità**: ogni cambiamento si confronta su un set di valutazione.
14. **Struttura che regge la crescita**: modular monolith in vertical slices, explicit over implicit, Clean Architecture,
    Schema-First Design e testing pyramid (ADR-0021, ADR-0022).

## Non obiettivi

- Scrivere codice di produzione per i siti e le app dei clienti. Il nostro prodotto non rientra in questa regola.
- Essere un prodotto multi-tenant o un servizio pubblico prima di M7: fino ad allora gira su questa macchina, per questo
  studio (ADR-0023).
- Supportare più provider dal primo giorno (ADR-0006).
- Generare logo, tipografia o asset finali di marca con modelli d'immagine (ADR-0009).
- Sostituire il giudizio umano sul lavoro creativo.

## Metriche di successo

Il riferimento è Neima: 112,6 $, ~3,6 ore, 737 chiamate, 0 master Craft, un solo gate superato.
I prezzi di allora non sono quelli di oggi, quindi il confronto vero si fa con il replay di M2.

| Metrica | Riferimento | Obiettivo a M2 |
|---|---|---|
| Costo per un'identità fino al gate `direction` | 112,6 $ | ≤ 50 $ |
| Contesto medio per chiamata | ~190.000 token | ≤ 60.000 token |
| Contesto fisso di uno specialista | 36–52k token | ≤ 6.000 token |
| Produzioni visive con master valido | 0% | 100% |
| Output senza controllo | presenti | 0 |
| Prove firmate dall'autore su controlli indipendenti | presenti | impossibili |
| Ripresa dopo interruzione | manuale | automatica, senza doppi effetti |
| Costo previsto noto prima di iniziare | no | sì, con tetto |

Il primo dato reale è `merlo`, sul brief E1: 15,91 $ senza finire, concetto trovato dopo 36 minuti e 8,02 $, contesto
medio 67.111 token. Da qui gli obiettivi di M1.5 in `02-ROADMAP.md`. I valori sopra restano obiettivi di partenza. La qualità si misura a parte, alla cieca
(`docs/07-EVALS.md`): un sistema più economico ma peggiore non è un successo.

## Rischi principali

| Rischio | Effetto | Risposta |
|---|---|---|
| Qualità inferiore a Claude Code, che ha anni di messa a punto del loop | Tutto il progetto | Confronto in M1.9 sullo stesso brief, prima di investire nella parità |
| Costruire infrastruttura invece di design | Mesi senza risultati | Prova verticale subito; ogni traguardo finisce con un lavoro reale. M1.7 e M1.8 non ne hanno uno: M1.9 li chiude con `merlo4`, prima della parità (ADR-0055) |
| Il SaaS assorbe il lavoro prima che la qualità sia dimostrata | Prodotto solido su un risultato creativo debole | M7 parte solo dopo un cliente reale servito in M6 |
| Il refactor cambia il motore senza che si veda | Cache invalidata, risultati peggiori | Snapshot di strumenti e prompt e test di flusso con risposte registrate durante M1.7; `merlo4` in M1.9 lo misura dal vivo contro `merlo3` (ADR-0055, ADR-0056) |
| Costi di sviluppo fuori controllo | Spesa senza valore | Tetti per traguardo, test con risposte registrate |
| API e SDK cambiano | Rotture | Un solo gateway da aggiornare; versioni bloccate |
| Le CLI Craft cambiano | Catalogo e strumenti superati | Indice versionato per CLI, test di contratto |
| Prompt injection da materiali e web | Azioni non volute | Niente rete né chiave nelle sandbox, azioni tipizzate (`06-SECURITY.md`) |
| 16 GB di VRAM condivisi | Blocchi e rallentamenti | Scheduler GPU in M4 |
| Gli esploratori convergono sulla stessa idea | Lo schizzo parallelo non aggiunge nulla | Leve diverse, territori esclusi, diversità misurata (`merlo` non lo ha ancora provato) |
| Lo schizzo veloce tradisce l'idea | Si scarta un concetto buono per un disegno debole | Scheda dell'idea accanto alla tavola; alternativa con una sola istanza |

## Decisioni aperte

| Decisione | Chi | Quando | Default se non si decide |
|---|---|---|---|
| Creare la chiave API e fissare il tetto mensile nella Console | Andrea | prima di M1 | M1 non parte |
| Dati del cliente verso l'API: retention e regione, e cosa dire nel contratto | Andrea | prima del primo cliente reale | solo progetti di prova |
| Uso di ComfyUI oltre esplorazione e texture | Andrea, con parere legale | M4 | vietato (ADR-0009) |
| Remote Git e posizione dei backup | Andrea | quando serve | solo locale |
| Isolamento dei dati per cliente, e registro su SQLite o Postgres | Andrea | prima di M7 | SQLite, una macchina (ADR-0001) |
| Dove girano i lavori del SaaS: sandbox, Craft, Blender, GPU | Andrea | prima di M7 | questa macchina |
| Licenze dei Craft per l'uso da parte di un servizio | Andrea | prima di M7 | nessun uso da parte di un servizio |
| A chi si vende, piani e fatturazione | Andrea | prima di M7 | nessuna vendita |
