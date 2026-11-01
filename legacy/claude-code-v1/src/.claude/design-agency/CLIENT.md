# Lavorare con il cliente

Lo studio non prende un prompt e consegna. Lavora **con** il cliente: ascolta finché ha capito
davvero, presenta a tappe, ascolta il feedback, lo traduce in modifiche precise e itera fino
all'approvazione esplicita. Solo il **router** parla con il cliente; gli agenti gli passano le
domande. Registro: `python3 .claude/scripts/client.py …` → `.agency/client.jsonl`.

## 1. Scoperta: domande fino a quando lo studio ha capito

**Non c'è un numero massimo di domande.** Un set breve di domande generiche porta a risultati
generici. Lo studio fa giri di domande successivi, ognuno costruito sulle risposte precedenti,
finché non può descrivere il cliente, il suo mondo e il problema con parole sue e il cliente
conferma che è così.

Ogni giro:
1. **Ascolta le risposte e scava**: chiedi il perché, un esempio concreto, un caso recente, cosa
   è successo l'ultima volta, cosa direbbe un loro cliente, cosa non vogliono essere. Le risposte
   astratte ("moderno", "di qualità", "per tutti") si trasformano in domande concrete.
2. **Mostra stimoli** quando le parole non bastano: 3–6 riferimenti visivi o varianti rapide
   affiancate ("quale è più vicino? cosa vi piace e cosa no in ciascuno?"). Il gusto si scopre
   reagendo, non descrivendo.
3. **Mappa chi decide**: chi approva, chi influenza, chi userà e manterrà il sistema dopo la
   consegna (marketing, comunicazione interna, agenzie terze, sviluppatori), quali approvazioni
   interne servono. Con una grande azienda i gate passano da più persone: registra chi parla.
4. **Chiedi i materiali** del mondo del cliente (`client-world`): prodotto, materiali, linguaggio,
   documenti, fotografie, utenti, situazioni d'uso. Un materiale vale più di dieci risposte.
5. **Ordina** le domande per importanza e raggruppale per tema, così il cliente risponde con
   ordine; un giro può avere tante domande quante ne servono.
6. **Non chiedere ciò che puoi trovare** (sito, documenti, ricerca) né ciò che lo studio deve
   decidere per mestiere: lì si registra un'assunzione e la si dichiara.

Ogni domanda ha: perché la chiediamo (cosa cambia nella soluzione), opzioni concrete quando
aiutano, e la raccomandazione dello studio quando ne ha una. Registrala:
`client.py ask --from <agente> --question … --why … [--options "A|B"] [--blocking]`; la risposta
testuale con `client.py answer`, e ogni fatto che contiene con `facts.py add --kind client --ref A-…`.

### Quando la scoperta è finita

Quando lo studio pensa di aver capito, scrive `work/context/understanding.md`: il cliente, il suo
mondo, il pubblico, il problema, l'obiettivo, cosa deve restare, cosa non deve succedere, i
vincoli, chi decide, le norme del settore che toccano il design, come si misurerà il successo,
quali asset esistono e quali andranno prodotti — **con parole dello studio**, citando i fatti [F-…] e
segnando le ipotesi. Lo presenta e chiede: "abbiamo capito bene? cosa manca o è sbagliato?".
Le correzioni aprono un nuovo giro. Solo con conferma esplicita:
`client.py approve --gate understanding --files work/context/understanding.md --text "…"`.

```sh
python3 .claude/scripts/client.py ready     # PRONTO solo con comprensione confermata, dossier coperto, nessuna domanda bloccante
```

La strategia non parte prima di `ready`. Anche dopo, ogni domanda nuova che cambia la soluzione
si fa subito: la scoperta riprende ogni volta che emerge qualcosa di non capito.

## 2. Gate per dimensione

| Dimensione | Gate cliente |
|---|---|
| S (un artefatto) | `understanding` (anche breve), `final` |
| M (un reparto) | `understanding`, `direction`, `final` |
| L (più reparti) | `understanding`, `brief`, `strategy`, `direction`, `design`, `prototype` (se digitale), `final` |

Un gate si supera **solo con parole esplicite del cliente**, registrate testuali, e vale per le
versioni approvate dei file. I ticket della fase successiva si aprono con `--after-gate <gate>`.

## 3. Presentare

Con `client-review`: lavoro reale renderizzato, legato ai criteri e ai fatti, alternative
confrontabili, raccomandazione motivata, cosa serve decidere, assunzioni fatte.
`client.py present --round N --title … --files …`.

## 4. Feedback

1. Parole testuali: `client.py feedback P-… --text "…"`.
2. Traduzione in `work/feedback/round-N.md` (`templates/feedback.md`): parole del cliente →
   interpretazione → modifica concreta → responsabile → come lo mostreremo, e **cosa funziona e
   va preservato**.
3. Feedback ambiguo → domande e varianti rapide prima di modificare.
4. Feedback in conflitto con strategia, accessibilità, licenze o fattibilità → compromesso
   spiegato con prove, alternativa che rispetti l'intenzione, decisione del cliente registrata.
5. Al round successivo: prima/dopo, e ciò che non è cambiato.

## 5. Iterazioni

- Ogni round è numerato e mostra cosa è cambiato.
- Dopo 3 round sullo stesso gate senza convergenza, fermati e rivedi insieme al cliente criteri e
  obiettivo: di solito manca qualcosa nella comprensione, e si riapre la scoperta.
- Silenzio o risposte generiche ("ok", "vediamo", "va bene, però…") non sono approvazioni.

## 6. Riprendere

All'avvio l'hook mostra domande aperte, presentazioni in attesa e gate. Il router riparte da lì.
