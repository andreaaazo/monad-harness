---
name: design-handoff
description: Prepara la consegna del design digitale a chi sviluppa — file FigCraft ordinati e pronti per lo sviluppo, specifiche di layout, componenti, stati e interazioni, variabili e token, misure e annotazioni, asset esportati, comportamento responsive e ridotto. Lo studio non scrive codice; consegna tutto ciò che serve per realizzarlo fedelmente.
---

# Handoff del design

## Il file

- Pagine ordinate: copertina, fondamenti (colori, tipi, spazi, griglie, icone), componenti,
  pagine per breakpoint, flussi del prototipo, archivio delle esplorazioni separato.
- Nomi coerenti di frame, livelli, componenti e varianti; nessun livello nascosto o orfano
  nelle pagine consegnate.
- Frame e sezioni da sviluppare marcati come pronti per lo sviluppo (dev mode); dopo ogni
  modifica `dev.compare` mostra cosa è cambiato rispetto alla consegna.

## Specifiche

- **Variabili e token**: colori, spazi, raggi, tipi e durate come variabili con modi per i temi;
  esportali in DTCG (`design-tokens`) come fonte unica per lo sviluppo.
- **Componenti**: varianti, proprietà, stati, contenuti minimi e massimi, comportamento al
  ridimensionamento (auto layout, vincoli).
- **Interazioni**: trigger, transizione, durata, curva (dai token di movimento), stato ridotto.
- **Responsive**: cosa cambia tra i breakpoint e perché (ricomposizione, non solo scala).
- **Accessibilità**: ordine di lettura e di focus, etichette di icone e controlli, testi
  alternativi, contrasti misurati, target.
- Annotazioni e misure in FigCraft (annotation, measurement) sui punti non ovvi.

## Asset

Export dai layer con impostazioni di export (SVG per icone e illustrazioni, PNG/WebP/AVIF per le
immagini alle densità richieste), nomi coerenti, `image_check.py` e `svg_audit.py` sugli export.

## Verifica

`figcraft_audit.py` senza FAIL, render di tutti i frame guardati, prototipo provato, `delivery.md`
con elenco dei file e limiti. Cosa lo studio **non** consegna: codice di produzione.
