# Fonti

Consultazione e revisione: **2026-10-29**. Le skill sono una sintesi originale dello
studio. Gli ID tra parentesi quadre nelle skill rimandano a questa tabella. Distingui
sempre: **standard** (normativo), **evidenza** (ricerca), **pratica** (tradizione del
mestiere, euristica), **scelta dello studio**.

## Standard e specifiche

| ID | Fonte | Tipo | Uso e limite |
|---|---|---|---|
| A0 | [W3C, WCAG 2.2](https://www.w3.org/TR/WCAG22/) | standard | Ambito web e livelli. Un asset non certifica una pagina. |
| A1 | [Understanding 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | standard (informativo) | Soglie, testo grande, esenzione dei logotipi. |
| A2 | [Understanding 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) | standard (informativo) | Grafici e controlli, colori adiacenti. |
| A3 | [Understanding 1.4.1 Use of Color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) | standard (informativo) | Informazione non affidata solo al colore. |
| A4 | [Understanding 2.3.1 Three Flashes](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html) | standard (informativo) | Flash generali e rossi; lo screening non basta per certificare. |
| A5 | [Understanding 2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) | standard (informativo) | Movimento automatico oltre 5 s; livello A. |
| A6 | [Understanding 2.3.3 Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) | standard (informativo) | Livello AAA. |
| S1 | [W3C, SVG 2 Coordinate Systems](https://www.w3.org/TR/SVG2/coords.html) | standard | viewBox, viewport, trasformazioni. |
| K1 | [W3C, CSS Color Module Level 4](https://www.w3.org/TR/css-color-4/) | standard | `oklch()`, spazi colore, gamut mapping. |
| K2 | [Myndex, APCA-W3](https://github.com/Myndex/apca-w3) | metodo pubblicato | Contrasto percettivo; versione 0.0.98G-4g in `color.py`. Non è ancora normativo in WCAG 2.x. |
| K3 | [Björn Ottosson, A perceptual color space for image processing (2020)](https://bottosson.github.io/posts/oklab/) | metodo pubblicato | Matrici OKLab usate in `color.py`. |
| T1 | [DTCG, Design Tokens Format Module 2025.10](https://www.designtokens.org/tr/2025.10/) | Community Group Report | Formato dei token; non è una Recommendation W3C. |

Verifica locale di `color.py` (2026-10-29): APCA #888 su #FFF = 63.1, #FFF su #888 = −68.5,
#000 su #FFF = 106.0, in accordo con i valori di riferimento pubblicati per APCA-W3.

## Web, interfacce, produzione, proprietà intellettuale

| ID | Fonte | Tipo | Uso e limite |
|---|---|---|---|
| W1 | [web.dev, Web Vitals](https://web.dev/articles/vitals) | metrica pubblicata (Google) | LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 al 75° percentile; in laboratorio sono stime. |
| W2 | [Understanding 2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | standard (informativo) | Target ≥ 24×24 CSS px, con eccezioni; livello AA. |
| W3 | [Awwwards, About evaluation](https://www.awwwards.com/about-evaluation/) | criteri di una giuria | Design 40%, Usabilità 30%, Creatività 20%, Contenuto 10% (letto il 2026-10-29). |
| W5 | [Direttiva (UE) 2019/882, European Accessibility Act](https://eur-lex.europa.eu/eli/dir/2019/882/oj) | norma | Requisiti di accessibilità per prodotti e servizi digitali (tra cui e-commerce e servizi bancari) applicabili dal 28 giugno 2025; verificare ambito ed eccezioni (es. microimprese) per il cliente. |
| U1 | [NN/g, 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) | pratica consolidata | Revisione euristica; non sostituisce test con utenti. |
| U2 | [NN/g, The 3-Click Rule for Navigation Is False](https://www.nngroup.com/articles/3-click-rule/) | evidenza (analisi NN/g) | Nessuna soglia universale di clic: contano riuscita, comprensione, errori, fatica. |
| P1 | [Regolamento (UE) 1169/2011](https://eur-lex.europa.eu/eli/reg/2011/1169/oj) | norma | Informazioni sugli alimenti, altezza minima della x 1.2 mm (0.9 mm sotto 80 cm²). Verificare la versione consolidata vigente. |
| P2 | [GS1 General Specifications](https://www.gs1.org/standards/barcodes-epcrfid-id-keys/gs1-general-specifications) | standard | Dimensioni, ingrandimenti e zone di rispetto dei codici a barre. |
| L1 | [EUIPO eSearch](https://euipo.europa.eu/eSearch/), [TMview](https://www.tmdn.org/tmview/), [WIPO Global Brand Database](https://branddb.wipo.int/) | banche dati pubbliche | Ricerche preliminari di anteriorità; non sostituiscono una ricerca professionale. |

## Ricerca sul branding e sulla percezione

| ID | Fonte | Tipo | Uso |
|---|---|---|---|
| B10 | Wagemans J. et al., "A century of Gestalt psychology in visual perception", *Psychological Bulletin* 138(6), 2012 | evidenza | Raggruppamento percettivo, figura/sfondo. |
| B11 | Byron Sharp, *How Brands Grow*, Oxford University Press, 2010 | evidenza (Ehrenberg-Bass) | Distintività e asset distintivi più che differenziazione dichiarata. |
| B12 | Jenni Romaniuk, *Building Distinctive Brand Assets*, Oxford University Press, 2018 | evidenza (Ehrenberg-Bass) | Costruire e misurare asset distintivi; coerenza nel tempo. |

## Tradizione del mestiere

| ID | Fonte | Uso |
|---|---|---|
| B1 | Robert Bringhurst, *The Elements of Typographic Style* | Misura della riga, spaziatura, scala, dettagli tipografici. |
| B2 | Josef Müller-Brockmann, *Grid Systems in Graphic Design*, 1981 | Griglie come strumento di sistema. |
| B3 | Paul Rand, *Design, Form, and Chaos*, 1993 | Casi IBM e altri, processo del designer. |
| B4 | Paul Rand, "Logos, Flags, and Escutcheons", 1991 | Il logo acquista significato da ciò che rappresenta. |
| B5 | Chermayeff & Geismar & Haviv, *Identify*, 2011 | Un logo appropriato, distintivo e semplice; casi di marchi astratti. |
| B6 | Alina Wheeler, *Designing Brand Identity* | Processo completo d'identità e brand book. |
| B7 | Frank Thomas, Ollie Johnston, *The Illusion of Life*, 1981 | 12 principi dell'animazione come vocabolario. |
| B8 | Josef Albers, *Interaction of Color*, 1963 | Relatività del colore percepito. |
| B9 | Tim Brown, "More Meaningful Typography", *A List Apart*, 2011 | Scale modulari. |
| B13 | Ellen Lupton, *Thinking with Type* | Fondamenti di tipografia e gerarchia. |

## Metodi e sistemi

| ID | Fonte | Uso e limite |
|---|---|---|
| D1 | [Design Council, The Double Diamond](https://www.designcouncil.org.uk/resources/the-double-diamond/) | Alternanza divergenza/convergenza; non una sequenza rigida. |
| D2 | [NN/g, 5 Principles of Visual Design in UX](https://www.nngroup.com/articles/principles-visual-design/) | Scala, gerarchia, equilibrio, contrasto, Gestalt. |
| M1 | [IBM Carbon, Motion](https://www.carbondesignsystem.com/building-blocks/foundations/motion/overview) | Movimento productive/expressive in UI; timing non trasferibile a un brand film. |

## Contratti software

| ID | Fonte | Uso |
|---|---|---|
| C1 | [Claude Code, Subagents](https://code.claude.com/docs/en/sub-agents) | Frontmatter (`tools`, `disallowedTools`, `skills`…); delega annidata fino a 3 livelli sotto la sessione principale; 20 subagenti concorrenti di default (letto il 2026-10-29). |
| C7 | [Claude Code, Agent teams](https://code.claude.com/docs/en/agent-teams) | Sperimentali; non applicano `skills` ai teammate, niente team annidati: lo studio usa i subagenti annidati. |
| C2 | [Claude Code, Skills](https://code.claude.com/docs/en/skills) | Skill di progetto e comandi. |
| C3 | [Claude Code, Hooks](https://code.claude.com/docs/en/hooks) | SessionStart e iniezione di contesto. |
| C4 | [Claude Code, MCP](https://code.claude.com/docs/en/mcp) | `.mcp.json`, `--strict-mcp-config`. |
| C5 | [Claude Code, Settings](https://code.claude.com/docs/en/settings) | `settings.json` e precedenza. |
| C6 | [Claude Code, Memory](https://code.claude.com/docs/en/memory) | `.claude/CLAUDE.md` come istruzioni di progetto. |
| V1 | [VectorCraft, docs/mcp.md](https://github.com/storytold/vectorcraft/blob/main/docs/mcp.md) | MCP, headless, root di automazione. |
| V2 | [VectorCraft, control-protocol.md](https://github.com/storytold/vectorcraft/blob/main/docs/control-protocol.md) | Semantica dei comandi; fa fede la versione installata. |
| E1 | [EffectCraft, docs/agents.md](https://github.com/storytold/effectcraft/blob/main/docs/agents.md) | Sessione MCP, proprietà, salvataggio. |
| E2 | [EffectCraft, docs/mcp.md](https://github.com/storytold/effectcraft/blob/main/docs/mcp.md) | Root, restrizioni, batch. |
| E3 | [EffectCraft, control-protocol.md](https://github.com/storytold/effectcraft/blob/main/docs/control-protocol.md) | Base temporale e keyframe. |

Le pagine su `main` cambiano: per una chiamata concreta fanno fede gli schemi live.
