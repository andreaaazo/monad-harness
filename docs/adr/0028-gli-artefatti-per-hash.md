# ADR-0028: gli artefatti per hash

**Contesto.** `03-DATA-MODEL.md` descriveva gli artefatti per hash da M1, e `06-SECURITY.md` li indicava come difesa contro un
comando che sovrascrive un master, ma non erano mai stati costruiti (ADR-0022). Il registro salvava gli hash delle consegne, delle
presentazioni e dei giudizi, non i contenuti: un file sovrascritto nel progetto non si recuperava più, e un giudizio alla cieca
restava legato a un hash senza file (ADR-0027).

**Decisione.**
- Si conserva ciò che esce dal lavoro di un'istanza o arriva a una persona: ogni consegna (`deliver`, `submit_concept`), il PDF
  che il cliente riceve (`present_concepts`) e ogni file giudicato (`agency judge`). Non si conserva ogni scrittura intermedia.
- Il contenuto sta in `.data/artifacts/<ab>/<sha256>`, in sola lettura. Un file entra prima in `.incoming/`, con l'hash calcolato
  mentre lo si copia, e prende il suo nome solo quando è completo e scritto su disco. Lo stesso contenuto si conserva una volta.
- La tabella `artifacts`, solo in aggiunta, dice da dove viene ogni versione: progetto, percorso, ticket, esecuzione, motivo
  (consegna, presentazione, giudizio), tipo MIME e dimensione. Così ogni artefatto risale a input, ruolo, modello, prompt e
  strumenti, attraverso il ticket e l'impronta dell'esecuzione (ADR-0026).
- L'ordine è sempre: prima il contenuto, poi la riga, poi l'evento che lo usa. Una riga dice sempre la verità su un contenuto che
  esiste. La stessa versione dello stesso file per lo stesso motivo si registra una volta sola, quindi una ripresa a metà ripete il
  passo senza duplicare nulla.
- La consegna registra gli hash di ciò che è stato conservato, non di una lettura separata.
- `agency judge` conserva le copie anonime dopo aver verificato che abbiano ancora l'hash letto all'inizio: si conserva
  esattamente ciò che si è guardato. Se una copia cambia durante il giudizio, non si registra nulla.
- Il tipo MIME viene dalla tabella interna di Python, mai da quella del sistema: lo stesso file ha lo stesso tipo su ogni
  macchina.
- `agency restore` riporta una versione in un file nuovo: non sovrascrive mai, e controlla l'hash della copia. Vuole almeno 8
  cifre dell'hash, non ambigue. `agency verify` controlla anche che ogni versione registrata ci sia e abbia ancora il suo hash.
- La porta `ArtifactStore` sta nei contratti, con `FileStore` come unico adattatore. Il deposito si passa a chi lo usa (sessione,
  agente, strumenti), non si ricava dalla configurazione: con il SaaS ogni cliente avrà il suo.
- Il proprietario è `agency.artifacts`, nella piattaforma, non `agency.tools`: lo usano gli strumenti, il giudizio e i comandi.

**Verifica (2026-11-02).** `tests/test_artifacts.py`, più i test sui giudizi e sul flusso completo: ogni hash consegnato di ogni
ticket ha il suo contenuto, e il PDF del gate `concept` è quello conservato. Su una copia del registro reale la migrazione `0005`
lascia identiche tutte le 3.814 righe. Sui due `segno.svg` reali di `merlo` e `merlo3` il ripristino è identico all'originale.

**Conseguenze.**
- I lavori precedenti a M1.6 non hanno artefatti. Nessuno si ricostruisce a posteriori.
- Il deposito non cancella mai. Un'interruzione tra il deposito e il registro lascia un contenuto che nessuna riga cita: occupa
  spazio e basta. Una tra la riga e l'evento lascia una versione conservata che nessun evento usa: è vera, e una consegna ripresa
  completa il passo.
- Il deposito è un dato che non si ricostruisce, come il registro: entra nei backup di M5 e nell'isolamento per cliente di M6.
- I file intermedi di un'istanza, come schizzi scartati e prove di render, restano solo in `projects/<slug>/work/`.
