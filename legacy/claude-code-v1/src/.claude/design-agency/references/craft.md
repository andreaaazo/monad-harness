# Mestiere: dal lavoro ordinario al lavoro eccellente

Questo riferimento descrive **leve osservabili**, non regole di stile. Ogni voce è un'euristica [E]
o una scelta dello studio [S]: si applica dove serve al contratto creativo e si verifica guardando
il risultato alla dimensione d'uso. Il carattere di un progetto nasce dalla combinazione specifica
di queste leve per questo cliente, non dal massimo di ciascuna.

## 1. Il ciclo che produce qualità [S]

Il primo render non si presenta mai. Ogni artefatto chiave passa da:

1. **Divergere piccolo**: molte opzioni veloci della decisione principale (composizione, segno,
   tipografia), alla scala di una miniatura, dove si vedono masse e rapporti, non dettagli.
2. **Confrontare affiancato**: le migliori 2–4 alla dimensione d'uso, sullo stesso contenuto, nello
   stesso foglio. Si sceglie guardando il confronto, non ricordando le singole.
3. **Affinare a passaggi separati**, uno per aspetto, ognuno reso e guardato:
   struttura (griglia, assi, gerarchia) → tipografia (ruoli, scala, composizione del testo) →
   colore e immagini (proporzioni, ritagli, trattamento) → dettaglio (spazi, allineamenti ottici,
   finitura). Cambiare tutto insieme impedisce di capire cosa ha migliorato.
4. **Mettere sotto sforzo**: contenuti reali peggiori (titoli lunghi, foto deboli, molti dati,
   lingue), formato più piccolo, schermo touch. Se regge, il sistema è vero.
5. **Finitura**: la checklist del mezzo (sezione 4).
6. **Giudicare contro i riferimenti** di livello del progetto (`work/references/levels.md`) con
   `evidence.py judge`. Se resta indietro, si torna al passaggio dove nasce la distanza.

## 2. Leve generali

| Leva | Ordinario | Eccellente | Cosa osservare nel render |
|---|---|---|---|
| Gerarchia | molti livelli distinti da piccoli salti di corpo, peso, colore e maiuscole insieme | 2–3 livelli con salti netti su **una** variabile principale; il resto lo fanno spazio e posizione | in 2 secondi si capisce cosa leggere prima, dopo, infine? |
| Scala | rapporti timidi, tutto di media grandezza | un contrasto di scala deciso dove serve tensione; calma dove serve leggere | c'è un elemento che domina e uno che respira? |
| Spazio | spazi uguali ovunque, riempiti per paura del vuoto | spazio come struttura: vicinanza dentro i gruppi, distanza tra i gruppi; il vuoto ha forma | i gruppi si leggono da soli, senza filetti né box? |
| Allineamento | molti allineamenti quasi uguali | pochi assi forti, ogni elemento appeso a uno di essi; correzioni ottiche dove la geometria inganna | ci sono bordi che "quasi" coincidono? (`svg_audit`, `figcraft_audit`) |
| Ritmo | ripetizione monotona o variazione casuale | ripetizione con variazione controllata; pause; un punto di rottura deliberato | scorrendo pagine o schermate c'è respiro e progressione? |
| Colore | tanti colori di pari peso; accento ovunque | proporzioni chiare (es. dominante / neutri / accento come ~70/25/5 [E]); l'accento è un segnale | togli il colore: la gerarchia regge? rimetti l'accento: indica la cosa giusta? |
| Immagini | molte immagini medie, ritagli neutri, stock riconoscibile | poche immagini forti, ritagli con intenzione (vicinanza, taglio al vivo, punto di vista), set coerente di luce e trattamento | le immagini dicono qualcosa di questo cliente che le parole non dicono? |
| Tipografia | un carattere neutro di default; composizione automatica | carattere scelto per il cliente; testo corrente curato (misura, interlinea, bandiera, sillabazione); titoli con spaziatura ottica | leggi un paragrafo intero: scorre? i titoli grandi hanno buchi tra le lettere? |
| Contenuto | il layout aspetta il testo; testo lungo e generico | il contenuto è progettato insieme alla forma: testi editati, titoli che dicono, dati scelti | si potrebbe togliere metà del testo senza perdere senso? |
| Dettaglio | dettaglio uniforme o assente | densità di cura concentrata dove l'occhio si posa (titolo, segno, prima schermata, pulsante principale) | ingrandisci i punti di primo sguardo: sono rifiniti? |
| Sorpresa | assente, o effetti ovunque | una deviazione deliberata dal sistema per artefatto, dove il contratto dice di sperimentare | c'è un momento memorabile, e uno solo? |
| Coerenza | stessa griglia e stessi gesti in ogni mezzo | invarianti di identità costanti; ogni mezzo usa il proprio linguaggio nativo | manifesto, sito e report sono riconoscibili come lo stesso brand senza essere la stessa pagina? |

## 3. Segni per mezzo

**Identità.** Un'idea leggibile nella forma, non solo nella spiegazione; differenza netta dai
concorrenti; sistema che genera applicazioni nuove; il segno regge a 16 px e su una facciata; il
logotipo ha spaziatura ottica e dettagli disegnati, non un carattere digitato.

**Web e app.** La prima schermata dice chi è il cliente e cosa fare in pochi secondi; la narrazione
procede per scorrimento con ritmo e pause; un'interazione caratterizzante che chiarisce il
contenuto; su touch la composizione è ripensata, non ridotta; contenuti reali; tipografia di
lettura curata quanto quella dei titoli; stati e transizioni progettati; stato ridotto progettato.

**Editoria.** Griglia che nasce dal formato e dal testo; ritmo tra le pagine (densità e respiro);
aperture riconoscibili; testo corrente perfetto (niente vedove, rivoli, sillabazioni sbagliate);
immagini e didascalie in rapporto stretto; dati in tabelle leggibili con cifre tabellari.

**Campagna.** Un'idea che vive nell'immagine anche senza il copy lungo; copy e immagine si
completano, non si ripetono; il formato più difficile funziona quanto il più comodo.

**Packaging.** Riconoscibile a tre metri, informativo a trenta centimetri; sistema di varianti
leggibile; materiali e finiture usati come parte dell'idea; producibile senza sorprese.

**Motion.** Il movimento dice qualcosa del brand; tempi con pause di lettura; l'attenzione va dove
deve; continuità tra le scene; chiusura esatta sul segno.

**Fotografia.** Set coerente di luce, punto di vista e trattamento; soggetti reali del cliente;
ritagli con intenzione; nessuna foto "di riempimento".

## 4. Finitura (prima di ogni presentazione)

- **Tipografia**: kerning dei titoli grandi; spaziatura negativa misurata sui corpi display;
  virgolette e apostrofi tipografici della lingua; trattini corretti; spazi non separabili tra
  numero e unità; vedove, orfane e righe di una parola; sillabazione della lingua; cifre
  tabellari nei dati; punteggiatura sporgente nei titoli allineati.
- **Geometria**: coordinate intere o su griglia dichiarata; raggi e spessori da una scala;
  allineamenti ottici delle forme tonde e appuntite; nessun quasi-allineamento.
- **Colore**: valori dai token, nessun colore "simile" in più; contrasti misurati sulle coppie reali.
- **Immagini**: risoluzione al supporto, ritagli coerenti, nessun artefatto di compressione,
  profili colore corretti.
- **Contenuti**: testi definitivi riletti, nomi e dati verificati, nessun segnaposto.
- **Consegna**: nomi dei file e dei livelli ordinati, export controllati.

## 5. Onestà sul livello

Se un lavoro è corretto ma ordinario, si dice, con il motivo osservabile e cosa servirebbe per
alzarlo (un'idea più specifica, immagini migliori, più tempo, un carattere diverso). Un risultato
ordinario presentato come eccellente è il difetto più costoso per uno studio.
