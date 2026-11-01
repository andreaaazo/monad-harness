# ADR-0017: il cliente riceve ciò che lo studio ha guardato

**Contesto.** Su `merlo3` il PDF nasceva dopo la fine del lavoro del direttore. Nessuno lo ha mai guardato: del motivo
si leggevano 58 caratteri su 541, il limite della proposta era interamente fuori pagina. Sulla tavola solo V aveva un
segno solo nel file, gli altri quattro avevano varianti, riduzioni o sfondi. Nella riduzione da 96 px V misurava 96×57
px, X 35×26 px, Y 29×41 px, e solo V ha superato il primo sguardo. Le condizioni non erano uguali per tutti.

**Decisione.**
- La presentazione ha due passi: `draft_presentation` compone le pagine vere, `present_concepts` manda al cliente
  l'ultima bozza. Il sistema rifiuta l'invio se una pagina, così com'è ora, non è stata guardata.
- Il testo scorre sulle pagine che servono: nessuna riga può uscire dal foglio.
- Lo schizzo contiene un solo segno, su fondo vuoto. Il sistema toglie un fondo chiaro uniforme e, se vede più segni
  separati, avvisa l'esploratore.
- L'avviso vale una volta per versione del file: è una stima, e una parola a lettere staccate può sembrare più segni.
  Sbagliare costa una chiamata e non blocca mai il lavoro (ADR-0015).
- Il direttore scrive solo ciò che ha visto o che risulta dalle consegne, e promette solo ciò che lo studio può fare.

**Conseguenze.** La presentazione costa qualche chiamata in più. Il PDF resta una scheda generata dal sistema: la
presentazione impaginata dallo studio arriva in M2.
