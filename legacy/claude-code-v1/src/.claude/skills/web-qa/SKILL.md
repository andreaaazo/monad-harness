---
name: web-qa
description: Verifica di pagine web e prototipi — screenshot ai breakpoint, overflow, accessibilità automatica axe (WCAG 2.2 AA), target interattivi, testo minuscolo, immagini senza alt, font non caricati, errori console e richieste fallite, LCP e CLS di laboratorio, reduced-motion, Lighthouse, tastiera. Da usare su ogni pagina prima di consegnarla e per audit di siti esistenti.
---

# QA web

## Automatico

```sh
.claude/scripts/node .claude/skills/web-qa/scripts/web_audit.mjs <url|file.html> --out work/qa/web \
    [--widths 360,768,1280,1920] [--lighthouse]
```

Per ogni larghezza: screenshot a pagina intera e con `prefers-reduced-motion`; overflow
orizzontale con gli elementi colpevoli; violazioni axe con impatto; target interattivi sotto
24×24 px [W2]; testo sotto 12 px; immagini senza `alt`; famiglie di font dichiarate ma non
disponibili (misurate sul testo renderizzato); errori console; richieste fallite; LCP e CLS.
Report in `web_audit.json`. FAIL su overflow, axe serious/critical, errori console,
richieste fallite, font mancanti.

Lighthouse (`--lighthouse`) aggiunge prestazioni, accessibilità, best practice e SEO di
laboratorio. Sono misure di laboratorio, non dati di campo degli utenti.

## Manuale (non sostituibile da script)

- **Guarda** ogni screenshot: allineamenti, ritmo, tagli di testo, immagini deformate,
  sovrapposizioni, stati visibili.
- **Tastiera**: Tab e Shift+Tab su tutta la pagina; ordine logico, focus sempre visibile,
  nessuna trappola, menu e modali utilizzabili ed Esc che chiude.
- **Contenuti**: testi definitivi, link funzionanti, titoli di pagina, meta e immagini di
  condivisione.
- **Contrasto** delle coppie reali con `color.py matrix`, incluse le coppie su immagini e video
  nel punto peggiore.
- **Motion**: interazioni fluide, nessun flash, reduced-motion rispettato.

Registra `web_audit`, `lighthouse`, `keyboard_review`, `visual_review`, `copy_review` per
ogni pagina consegnata.
