# Accessibilità: criteri e ambito

WCAG riguarda contenuti web nel loro contesto: un'immagine da sola non certifica la
conformità di una pagina. Per stampa, segnaletica o video dichiara quali criteri adotti
volontariamente e quali requisiti del supporto restano da verificare [A0].

## Contrasto

- Testo web: almeno 4.5:1; testo grande almeno 3:1. Grande significa almeno 18 pt
  (24 CSS px) o 14 pt grassetto (circa 18.67 CSS px) [A1].
- I logotipi sono esenti dal requisito di contrasto [A1]; l'esenzione normativa non
  rende leggibile un marchio a basso contrasto: misuralo comunque.
- Parti di grafici necessarie alla comprensione e indicatori visivi di controlli e stati:
  almeno 3:1 rispetto ai colori adiacenti, con le eccezioni dello standard [A2].
- Misura i colori come appaiono davvero: trasparenze compositate, sfondi reali, zone
  peggiori di gradienti, foto e frame. Non arrotondare verso la soglia.
- APCA (`color.py`) guida la leggibilità per corpo e peso [K2]; la conformità WCAG 2.2
  si dichiara con il rapporto WCAG.

## Colore e significato

Nessuna informazione affidata solo al colore: aggiungi forma, etichetta o pattern [A3].

## Movimento

- Niente flash intenzionali. 2.3.1 considera più di tre flash in un secondo sopra le
  soglie generali e rosse [A4]. `motion_probe.py` è uno screening: con un rischio reale
  e senza analisi adeguata l'esito è `NOT_VERIFIED`.
- Pausa/stop/nascondi (2.2.2) per movimento automatico oltre 5 secondi in parallelo
  ad altro contenuto, salvo essenzialità [A5].
- Animazioni attivate dall'interazione disattivabili: criterio AAA 2.3.3 [A6]. Lo studio
  fornisce comunque una variante statica o ridotta per `prefers-reduced-motion`.

## Contenuti

Proponi testo alternativo per loghi e immagini informative, e un ordine di lettura per
le tavole quando saranno pubblicate come pagine.
