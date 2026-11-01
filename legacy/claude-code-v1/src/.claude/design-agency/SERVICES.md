# Catalogo dei servizi

Il router classifica ogni richiesta qui. **Ingresso** è il punto più basso che basta per la
dimensione tipica; se la richiesta è più grande, sali di un livello (ORG.md).
I livelli QA sono definiti in [QA.md](QA.md).

## Branding e identità

| Servizio | Richieste tipiche | Dim. | Ingresso | Team | Skill | QA |
|---|---|---|---|---|---|---|
| Strategia di marca | "posizioniamo il brand", "chi siamo per i clienti" | M | `strategy-director` | brand-strategist, researcher | brand-strategy, research | L3 |
| Naming | "trovami un nome", "rinominiamo il prodotto" | M | `strategy-director` | copywriter, researcher, legal-reviewer | verbal-identity, legal-ip | L3 |
| Voce e copy di marca | tagline, manifesto, tono, microcopy | S–M | `copywriter` | (strategy-director se manca la strategia) | verbal-identity | L2 |
| Logo | "fammi un logo", "rifinisci il marchio" | M | `design-director` | art-director, identity-designer, typographer, critic | concept-divergence, logo-design | L4 |
| Identità completa | "brand identity da zero" | L | `creative-director` | tutti i reparti design + strategia | tutte le skill di identità | L4 |
| Rebrand | "facciamo un rebranding", "rinfreschiamo il marchio" | L | `creative-director` | strategia, design, digitale, produzione | rebrand + identità | L4 |
| Sistema colore / tipografia | palette, scala, font | S–M | `identity-designer` / `typographer` | qa-inspector | color-system, type-system | L2 |
| Design system e token | "token per il sito", "temi chiaro/scuro" | M | `digital-director` | ui-designer, identity-designer | design-tokens | L3 |
| Brand book | "manuale del marchio" | M | `design-director` | editorial-designer, production-manager | brand-guidelines, editorial-layout | L4 |
| Motion identity | logo animato, sting, transizioni | M | `motion-designer` (S) / `design-director` (M) | critic | motion-identity | L3 |

## Comunicazione e prodotto

| Servizio | Richieste tipiche | Dim. | Ingresso | Team | Skill | QA |
|---|---|---|---|---|---|---|
| Mockup | "preparami un mockup per questo" | S | `mockup-artist` | qa-inspector | mockup | L2 |
| Packaging | etichetta, scatola, linea di prodotto | M | `design-director` | packaging-designer, copywriter, legal-reviewer, production-manager | packaging, print-production | L4 |
| Editoria e stampa | brochure, poster, report, libro, cancelleria | S–M | `editorial-designer` (S) / `design-director` (M) | typographer, production-manager | editorial-layout, print-production | L3 (L4 se va in stampa) |
| Campagna e key visual | lancio, affissione, adattamenti | M–L | `creative-director` | art-director, copywriter, editorial-designer, motion-designer | campaign-social | L3 |
| Kit social | template, formati, animazioni brevi | S–M | `design-director` | editorial-designer, motion-designer | campaign-social | L2 |
| Illustrazione e icone | set di icone, illustrazioni di marca | S–M | `illustrator` (S) / `design-director` (M) | critic | illustration-iconography | L3 |
| Direzione fotografica | moodboard, brief per shooting, trattamento immagini | S–M | `art-director` | researcher | image-direction | L2 |
| Presentazione | pitch deck, presentazione del progetto al cliente | S–M | `editorial-designer` | copywriter, art-director | presentation | L3 |

## Digitale

| Servizio | Richieste tipiche | Dim. | Ingresso | Team | Skill | QA |
|---|---|---|---|---|---|---|
| Design di sito / landing (Awwwards) | "sito vetrina", "landing di lancio" | L | `digital-director` | ux-designer, ui-designer, copywriter, motion-designer, sprint delle direzioni | ux-design, web-design, direction-sprint, design-handoff | L4 |
| Design di app o prodotto | schermate, flussi, componenti, prototipi | M–L | `digital-director` | ux-designer, ui-designer | ux-design, web-design, design-tokens, design-handoff | L3 |
| Prototipo interattivo (FigCraft, EffectCraft) | "voglio vedere come si muove" | M | `ui-designer` | motion-designer | web-design, motion-identity | L3 |
| Handoff agli sviluppatori del cliente | "passateci i file per lo sviluppo" | S–M | `ui-designer` | production-manager | design-handoff | L3 |
| Audit di un sito esistente | "cosa non va nel nostro sito" | S–M | `digital-director` | qa-inspector, ux-designer | web-qa, ux-design (analisi del sito pubblicato; le correzioni si progettano, non si programmano) | L2 |

## Servizi trasversali

| Servizio | Richieste tipiche | Dim. | Ingresso | Skill | QA |
|---|---|---|---|---|---|
| Ricerca e audit di categoria | concorrenti, riferimenti, tendenze | S–M | `researcher` | research | L2 |
| Critica di un lavoro | "cosa ne pensi di questo logo/sito" | S | `critic` | critique | — |
| Preparazione file e consegna | "mandami i file per la stampa/il dev" | S | `production-manager` | print-production, visual-qa | L4 |
| Verifica legale preliminare | somiglianze, licenze di font e immagini | S | `legal-reviewer` | legal-ip | L2 |
| Domanda del cliente | "che font usereste?", "quanto costa stampare?" | S | router → consulenza allo specialista | — | — |

## Flussi standard

I passaggi segnati **[cliente: gate]** sono presentazioni con approvazione esplicita
(`CLIENT.md`); la fase successiva non parte senza.

**Identità completa / rebrand (L).**
intake **[cliente: brief]** → `creative-director` → strategy-director (mondo del cliente,
dossier, ricerca, strategia, verbale) **[cliente: strategy]** → contratto creativo → sprint delle direzioni
(`direction-a`, `-b`, `-c` isolati) → tavole anonime e critica → selezione del
creative-director con piano degli asset **[cliente: direction]** → carta della direzione →
design-director (logo, colore, tipo, icone, motion) **[cliente: design]** → digital-director
(token, applicazioni digitali) → prova di robustezza su un'applicazione nuova e sfavorevole → editorial-designer (brand book) → production-director
(pacchetto e verifiche) → critic → router **[cliente: final]**.

**Sito Awwwards (L).**
scoperta **[cliente: understanding]** → digital-director → ux-designer (obiettivi, compiti,
architettura, flussi) con copywriter (testi veri) **[cliente: strategy]** → sprint delle
direzioni digitali (frame desktop e touch, momento d'interazione, stato ridotto) con art
direction, copy, UI e motion insieme → **prototipi delle interazioni decisive** (FigCraft,
EffectCraft) provati su desktop e touch → tavole e critica → selezione **[cliente: direction]**
→ ui-designer (sistema, pagine, componenti, variabili) **[cliente: design]** → prototipo
completo → qa-inspector (`figcraft_audit`) e critic **[cliente: prototype]** → handoff
(`design-handoff`) **[cliente: final]**. Nessun codice.

**Mockup (S).**
mockup-artist (scena, superfici, composizione, prova a dimensione d'uso) → qa-inspector
(proporzioni, risoluzione, bordi) → router **[cliente: final]** → eventuali modifiche.

**Packaging (M).**
design-director → packaging-designer (concept e gerarchia sullo scaffale)
**[cliente: direction]** → packaging-designer (dieline) + copywriter (testi) + legal-reviewer
(diciture e licenze) → production-manager (preflight di stampa) → critic
**[cliente: final]** prima dell'invio allo stampatore.

## Richieste fuori catalogo

Se la richiesta non è in tabella, il router la scompone in servizi presenti. Se manca una
competenza o uno strumento, lo dice al cliente e propone come colmarlo. Non improvvisa
un ruolo che lo studio non ha.
