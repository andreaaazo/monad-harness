---
name: logo-design
description: Progetta, costruisce e verifica un logo o un sistema di marchio (simbolo, logotipo, monogramma, lockup, versioni ridotte). Da usare per un nuovo logo, un redesign, la rifinitura di un marchio esistente o il controllo di un logo a piccole dimensioni.
---

# Logo design

Un logo acquista significato dalla qualità di ciò che rappresenta, non il contrario [B4]:
il suo compito è essere **appropriato, distintivo e semplice** [B5], e tenere a ogni
dimensione e supporto. Memorabilità e riconoscibilità si costruiscono con l'uso
coerente nel tempo [B11][B12]; il lavoro dello studio è dare al brand un segno che
regga quell'uso. Ogni proprietà si dimostra con un test, non con un aggettivo.

## 1. Input

Servono, in `strategy.md` o nel brief:
- la frase di significato (cosa deve dire il segno, a chi);
- il nome esatto (maiuscole, accenti, lingue, eventuale descrittore);
- categoria e 5–10 concorrenti diretti, per il confronto di distintività;
- usi principali: app icon e favicon, firma digitale, insegna, stampa, ricamo,
  incisione, motion, co-branding;
- equity da conservare in un redesign (colore, forma, iniziale riconoscibile).

Se manca la strategia, esegui prima `brand-strategy` in forma breve.

## 2. Tipo di marchio

Scegli e motiva prima di disegnare.

| Tipo | Funziona quando | Rischio da controllare |
|---|---|---|
| Logotipo | il nome è breve o medio e va imparato | "il nome in un font": serve un'idea nel lettering |
| Monogramma | il nome è lungo o già abbreviato nell'uso | lettere in un contenitore senza idea |
| Simbolo astratto | molte linee di prodotto o mercati diversi | vuoto finché l'uso non lo carica: serve investimento |
| Pittogramma | un'immagine concreta è legata al nome o all'origine | cliché di categoria (foglia, cervello, globo) |
| Emblema | istituzioni, sport, heritage | illeggibile da piccolo: serve una versione ridotta |
| Sistema dinamico | la variazione è il messaggio | senza una costante fissa non c'è marchio |

## 3. Tre ingressi: significato, forma, comportamento

Una frase come requisito preliminare favorisce le soluzioni facili da raccontare (metafore
letterali, iniziali nascoste, oggetti semplificati). Lo studio esplora da tre ingressi:
- **significato**: un'idea dal mondo del cliente ("il segno è X perché il brand Y");
- **forma**: relazioni tra lettere, masse, ritmi, contrasti, spazi che emergono disegnando;
- **comportamento**: come il segno si muove, si ripete, si adatta, si costruisce nel sistema.
Tutti si valutano rispetto al brief. Il razionale definitivo si scrive **dopo** il confronto,
descrivendo ciò che il segno fa davvero: non si inventano spiegazioni a posteriori.

**Quanto deve dire il segno da solo?** Decidilo con il brief: spesso l'identità comunica
attraverso immagini, parole, colore e movimento, e il simbolo deve soprattutto essere
distinguibile, appropriato e capace di caricarsi di significato con l'uso [B4][B11].

## 4. Esplorazione proporzionata al tipo di marchio

- [S] Esplora largo: abbastanza alternative perché la scelta sia una scelta (per un simbolo
  spesso venti o più; per un logotipo varianti di carattere, spaziatura e dettaglio; per un
  sistema dinamico le regole e i loro esiti). Non produrre varianti solo per raggiungere un numero.
- Formato e prova adatti al tipo: un simbolo si giudica anche in nero pieno e piccolo; un
  logotipo nella sua lunghezza reale; un emblema alla dimensione minima d'uso; un segno animato
  in movimento (EffectCraft) oltre che fermo.
- Foglio di selezione: `scripts/logo_proof.py sheet *.svg --out sheet.png --mono`.
  Guardalo. Ogni cella mostra il candidato grande e a 24 px.
- Elimina: illeggibili a 24 px, uguali a un cliché o a un concorrente, varianti che
  differiscono solo per dettagli. Tieni 3–5 candidati con la loro frase.

## 5. Costruzione

- Definisci un'unità `u` (di solito lo spessore principale) e deriva tutte le misure:
  raggi, aperture, spaziature, sbalzi. Pochi valori, rapporti semplici o motivati.
- Angoli da un insieme piccolo e coerente (0/90, 45, o un angolo che nasce dall'idea).
- Costruisci in **VectorCraft**: il master è il `.vectorcraft`. Il calcolo serve a trovare le
  coordinate, poi entra nel master con `vectorcraft-cli run --commands passi.json --export
  work/source/segno.vectorcraft` (o con `vectorcraft-cli convert calcolo.svg …`) e da lì si rifinisce.
  Un SVG scritto da uno script non è un master.
- Esporta sempre dal master: `.claude/scripts/py .claude/scripts/master.py export
  work/source/segno.vectorcraft work/exports/segno.svg`. Per le esplorazioni basta un master con più tavole.
- Scrivi `construction.md`: unità, regole, griglia, e ogni correzione ottica come
  deviazione nominata dalla costruzione ("O: +2% oltre la cap height").
- La griglia è uno strumento di coerenza; il risultato finale si giudica a vista.

## 6. Correzioni ottiche e curve

Dettagli e valori di partenza in [references/optics.md](references/optics.md). In sintesi:
- overshoot delle forme tonde e appuntite oltre le linee di riferimento;
- cerchi e triangoli più grandi dei quadrati per sembrare uguali;
- orizzontali più sottili delle verticali; giunzioni alleggerite;
- centratura sul baricentro visivo, non sulla bounding box;
- versione in negativo leggermente più sottile per compensare l'irradiazione;
- nodi agli estremi, tangenti continue, nessun nodo superfluo, nessun gomito
  tra retta e curva.

## 7. Logotipo e lettering

- Verifica la licenza del carattere per uso come logo e per modifiche dei glifi.
  Registra fonderia, licenza e versione.
- Spazia per area ottica, non per distanza tra bounding box: dritta-dritta più larga,
  dritta-tonda media, tonda-tonda più stretta; poi correggi le coppie difficili
  (diagonali, T, L, r, f) a vista.
- Modifica un glifo solo se esprime l'idea o risolve un problema (collisione,
  ambiguità come rn/m, ritmo spezzato).
- Maiuscolo con tracking largo e sans geometrica neutra sono la soluzione di default:
  usali solo con una ragione scritta.
- Deliverable in tracciati; conserva il master con testo vivo e il nome del font.

## 8. Test

Esegui e **guarda** i risultati prima della critica:

```sh
.claude/scripts/py .claude/skills/logo-design/scripts/svg_audit.py logo.svg
.claude/scripts/py .claude/skills/logo-design/scripts/logo_proof.py proof logo.svg --out proofs/ [--background foto.jpg]
```

| Test | Come | Superato se |
|---|---|---|
| Geometria | `svg_audit.py` | nessun quasi-allineamento, segmento minuscolo, tratto non espanso o transform residuo |
| Parità di rendering | `.claude/skills/visual-qa/scripts/svg_parity.py` | stesso aspetto in tutti i renderer (filtri, maschere e testo vivo sono la causa tipica delle differenze) |
| Riduzione | foglio di prova 16–64 px, ingrandimenti `_16px_x16`, `_32px_x16` | forma riconoscibile, contatori aperti; altrimenti versione ridotta dedicata |
| Silhouette | blur nel foglio di prova | la massa resta identificabile e diversa dai concorrenti |
| Monocromia | riga "mono" (forma dall'alpha) | funziona in un colore pieno; se parti spariscono, i vuoti erano disegnati in bianco: usa tracciati composti |
| Negativo | riga "neg" | stesso peso percepito del positivo |
| Ingrandimento | `_1024.png` e oltre | nessun difetto di curva, nodo o giunzione |
| Contesto | almeno 3 applicazioni del brief | il segno tiene accanto a testo, foto, interfaccia |
| Distintività | confronto affiancato con i concorrenti e con [anti-patterns](../../design-agency/references/anti-patterns.md) | non confondibile; nessun cliché non giustificato |
| Marchio nuovo: potenziale | differenziabilità, appropriatezza, potenziale di apprendimento (semplice da ricordare e ridisegnare, coerente con il sistema) | la riconoscibilità senza nome richiede esposizione: non si pretende da un marchio nuovo |
| Marchio esistente: equity | confronto prima/dopo con gli asset riconosciuti | gli asset forti restano riconoscibili |

La somiglianza con marchi esistenti va cercata e registrata, ma non è una verifica legale:
per la registrazione serve una ricerca di anteriorità professionale.

## 9. Sistema e lockup

- Solo le varianti che gli usi richiedono: primario, simbolo, logotipo, orizzontale o
  verticale, versione ridotta.
- Rapporto simbolo/logotipo calibrato otticamente e annotato.
- Area di rispetto in `u` o in altezze della x, non in pixel.
- Dimensione minima ricavata dai test, per schermo (px) e stampa (mm).

## 10. Deliverable

- master `.vectorcraft` con livelli: costruzione (nascosto), finale, varianti;
- SVG con `viewBox` corretto, testo in tracciati, nessun transform residuo; PDF vettoriale;
  PNG trasparenti @1x/@2x; favicon e app icon se richiesti;
- `construction.md` e foglio di prova;
- regole d'uso per `brand-guidelines`.

Prima della consegna: `/critique` sul logo e sul foglio di prova.
