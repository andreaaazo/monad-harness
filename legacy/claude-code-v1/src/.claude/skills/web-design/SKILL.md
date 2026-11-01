---
name: web-design
description: Design di siti, landing e prodotti digitali in FigCraft, giudicato sull'esperienza completa (design, usabilità, creatività, contenuto) — concept e narrazione dell'esperienza, sprint delle direzioni digitali, prototipi delle interazioni decisive, layout e griglie per breakpoint, componenti, variabili e temi, desktop e touch, comportamento ridotto, audit misurabile del design. Lo studio progetta e prototipa; non scrive codice.
---

# Design web e di interfacce

Awwwards valuta **Design 40%, Usabilità 30%, Creatività 20%, Contenuto 10%** [W3]: si giudica
l'esperienza completa, non la schermata iniziale. Lo studio consegna il design e i prototipi;
lo sviluppo è di chi riceve l'handoff (`design-handoff`).

Tipi di regola in questa skill: **[R]** requisito, **[E]** euristica da verificare sul progetto,
**[S]** scelta dello studio, **[X]** esperimento.

## 1. L'idea dell'esperienza

- [S] Dalla direzione del brand: qual è l'idea del sito in una frase e quale comportamento la
  rende viva (come si entra, come si scorre, come si passa tra le parti, cosa fa il contenuto)?
- [E] Un'esperienza forte ha spesso un'idea d'interazione decisa e un sistema sobrio attorno;
  il rischio va messo dove il progetto ne beneficia (memorabilità, racconto) e la familiarità dove
  serve (navigazione, compiti, form).

## 2. Direzioni digitali (progetti L)

Con `direction-sprint`: le applicazioni comuni sono **frame reali** — home desktop 1440, home
touch 390, una pagina di contenuto denso, un momento d'interazione chiave in sequenza (3–5
frame), lo stato ridotto (reduced motion) dello stesso momento. Contenuti veri del cliente.

## 3. Il tratto minimo dell'esperienza [X]

Non ogni progetto richiede un'interazione spettacolare: serve una scelta caratterizzante adeguata
al caso, che può vivere nella tipografia, nel montaggio delle immagini o nella narrazione. Quando il
comportamento è determinante, prima dell'approvazione prototipa in FigCraft il tratto minimo
necessario a giudicare l'idea: contenuto reale, una transizione significativa e un'azione
dell'utente, su desktop e touch. Valuta se il comportamento chiarisce il contenuto, produce
interesse e lascia l'utente in controllo. Lo studio prototipa, non programma.

## 3b. Prototipi delle interazioni decisive [X]

Prima di congelare la direzione, prototipa in FigCraft (interazioni, smart animate, curve di
easing e molle, variabili e condizioni) e, per il movimento fine, in EffectCraft con il
`motion-designer`. Ogni prototipo nasce da una domanda: *quale incertezza risolve?* Esempi:
l'esplorazione del prodotto comunica più delle fotografie o aggiunge fatica? Lo scorrimento
narrativo regge su touch? La transizione orienta o disorienta?
Prova ogni prototipo a passi, su desktop e touch, e con il comportamento ridotto; scrivi cosa è
successo. Si sceglie dopo aver visto cosa funziona davvero.

## 4. Layout e sistema

- Frame per breakpoint (es. 1440, 1024, 390), griglie di layout, auto layout: i contenuti si
  **ricompongono**, non si restringono.
- [R] Testo ≥ 12 px; contrasto testo/fondo WCAG 2.2 AA [A1]; focus visibile ≥ 3:1 [A2];
  target interattivi ≥ 24×24 px [W2]. [E] 44×44 px su touch; testo corrente ≥ 16 px su mobile.
- Variabili per colori, spazi, raggi, tipi, con modi per i temi; stili di testo dalla scala
  tipografica; componenti con varianti e stati (riposo, hover, focus, premuto, disabilitato,
  errore, caricamento, vuoto) e contenuti estremi.
- Movimento dalla specifica di `motion-identity`; lo scorrimento non toglie il controllo
  all'utente; ogni animazione ha uno stato ridotto progettato.

## 5. Verifica

```sh
.claude/scripts/py .claude/skills/web-design/scripts/figcraft_audit.py work/design/sito.figcraft --record-by ui-designer
.claude/scripts/py .claude/scripts/render.py work/design/sito.figcraft      # un PNG per frame: guardali tutti
```

L'audit misura font mancanti, testo minimo, contrasto sui fondi solidi, target interattivi,
coordinate non intere e quasi-allineamenti; segnala come NON VERIFICATO il testo su immagini o
sfumature (verifica a occhio nel punto peggiore). I prototipi si provano a passi e si registra
`prototype_review` con la descrizione del percorso. La qualità del design la giudica la critica.
