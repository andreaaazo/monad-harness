# ADR-0011: esplorazione a schizzi prima della produzione

**Contesto.** Su `merlo` il designer ha esplorato, costruito e rifinito nella stessa istanza. L'idea è stata
giudicata solo a lavoro finito: 4,14 $ sul primo concetto bocciato, 8,02 $ e 36 minuti per trovarne uno valido, 6,61 $
per rifinirlo senza risolvere il suo limite. Il designer ha speso l'83% del progetto. Il tempo è quasi tutto
ragionamento del modello, quindi la leva è ragionare dove conta.

**Decisione.** Replichiamo il metodo di uno studio vero. Decisione di Andrea, 2026-10-31.

1. Esploratori in parallelo, ciascuno con una leva diversa e uno schizzo diverso.
2. Molto ragionamento sull'idea, produzione veloce dello schizzo. L'effort massimo usato è `high`: `max` consuma
   troppo, e `medium` resta da provare.
3. Scelta del concetto su tavole anonime, poi gate `concept` del cliente.
4. Solo dopo, un finisher costruisce e rifinisce. Non esplora più.

**Regole.**
- Idea e schizzo sono istanze separate, di partenza: l'effort cambia senza toccare la cache di un'istanza lunga.
- Lo schizzo sta comunque in VectorCraft, su un master proprio: la regola del mezzo non ha eccezioni.
- Niente fusioni: si sceglie un concetto, che resta intero.
- Un concetto bocciato torna agli schizzi. Il rework vale solo per difetti dentro un concetto approvato.

**Alternative scartate.** Dividere il designer per compiti: export e controlli pesano pochissimo, e passare il lavoro
tra agenti rifà il contesto. Più agenti sulla rifinitura dello stesso segno: curve e spessori dipendono l'uno
dall'altro e perderebbero coerenza.

**Conseguenze.**
- L'effort dipende dalla fase, non solo dal ruolo.
- Il parallelo entra in M1.5, prima di M2. Ciò che si costruisce serve poi allo sprint delle direzioni.
- Il costo non è detto che scenda: più agenti spendono di più, il risparmio viene dai giri di rifinitura evitati.
- Rischi: idee che convergono e schizzi che tradiscono l'idea. Sono criteri di uscita di M1.5.
