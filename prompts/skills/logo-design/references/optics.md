# Correzioni ottiche e qualità delle curve

La percezione non coincide con la geometria. Le correzioni sotto sono pratica
consolidata del disegno di caratteri e di marchi; i valori sono **punti di partenza
da calibrare a vista** alla dimensione d'uso, non costanti. Ogni correzione applicata
va annotata in `construction.md` come deviazione dalla costruzione.

## Misurare prima di correggere

`run_check` con `optical_check` su un PNG
mostra baricentro della massa, centro della bounding box, centro della tavola e centro ottico.
Per varianti e set di icone: `optical_check.py --set …` confronta peso ottico e centratura.
La misura indica dove guardare; la correzione si decide a occhio e si annota.

## Dimensione apparente

| Fenomeno | Correzione | Partenza |
|---|---|---|
| Una forma tonda o appuntita a parità di altezza sembra più piccola di una piatta | overshoot oltre baseline e altezza | ~1–3% dell'altezza per lato |
| Cerchio e triangolo sembrano più piccoli di un quadrato di uguale altezza | aumentare l'altezza o l'area | cerchio ~+5–10%, triangolo di più; confronta a vista |
| Un elemento centrato nella bounding box sembra fuori centro | centrare sul baricentro visivo | triangoli e frecce: spostare verso la massa |
| Il centro geometrico verticale sembra basso | centro ottico leggermente sopra | ~1–3% dell'altezza |

## Spessori

| Fenomeno | Correzione | Partenza |
|---|---|---|
| Orizzontali dello stesso spessore delle verticali sembrano più spesse | assottigliare le orizzontali | ~5–15% |
| Diagonali e curve sembrano più spesse nel punto di massima pendenza | modulare lo spessore lungo la curva | da valutare per forma |
| Le giunzioni (V, curve che si toccano, tratti che si incrociano) accumulano nero | alleggerire o aprire le giunzioni (ink trap ottico) | più marcato per le versioni ridotte |
| Chiaro su scuro sembra più spesso (irradiazione) | negativo leggermente più sottile | ~1–3% dello spessore; confronta affiancato |

## Spazio

- Lo spazio tra due forme si giudica per area, non per distanza minima: due tonde
  vicine lasciano più vuoto di due dritte alla stessa distanza.
- I vuoti interni (contatori) devono reggere alla dimensione minima: se si chiudono
  a 16–24 px, servono aperture più ampie o una versione ridotta.
- Le tangenze accidentali (due forme che quasi si toccano) creano tensione non voluta:
  o si toccano con decisione o si separano chiaramente.

## Curve e nodi

- Nodi agli estremi orizzontali e verticali della curva, con maniglie orizzontali o
  verticali. Pochi nodi, ognuno necessario.
- Le maniglie non si incrociano e non superano il punto di intersezione delle tangenti.
- Passaggio retta→curva: maniglia allineata alla retta (tangente continua, G1).
  Dove la forma deve risultare morbida e "tesa", serve curvatura continua (G2):
  maniglie più lunghe di quelle di un arco circolare, che per un quarto di cerchio
  sono ≈ 0.5523 × raggio. Le transizioni a raggio costante su un rettangolo producono
  un punto di discontinuità visibile nei riflessi e nelle forme grandi.
- Coordinate e maniglie su valori interi o su una griglia fine dichiarata;
  `svg_audit.py` segnala i quasi-allineamenti.
- Nel master consegnato le figure sono unite (nessuna sovrapposizione nascosta);
  la costruzione resta in un livello separato.

## Riduzione

Sotto una certa dimensione il dettaglio sparisce o si impasta. Una versione ridotta
(meno elementi, aperture più larghe, spessori maggiori) è normale nei sistemi
professionali, come i tagli ottici dei caratteri. Decidila dai test, non a priori.
