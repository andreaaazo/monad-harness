---
name: legal-ip
description: Verifica legale preliminare dello studio (non consulenza legale) — ricerca di anteriorità di nomi e marchi nelle banche dati pubbliche, somiglianze visive, licenze di font, immagini, icone e codice, diciture obbligatorie di packaging. Da usare prima di raccomandare un nome o un logo, prima di usare asset di terzi e prima di stampare un packaging.
---

# Verifica legale preliminare

**Due passaggi.** Prima della scelta del territorio o del nome: solo knock-out, 3–5 ricerche per
candidato, per escludere ciò che è già occupato. Dopo la scelta: la verifica completa qui sotto, una
volta, sul candidato scelto.

Ogni documento prodotto riporta: **"Verifica preliminare dello studio, non parere legale.
Per registrazione e uso commerciale serve un professionale in proprietà intellettuale."**

## Nomi e marchi

1. Definisci mercati (paesi/UE) e classi di Nice pertinenti a prodotti e servizi.
2. Cerca identità e somiglianze (grafiche, fonetiche, concettuali) nelle banche dati pubbliche:
   EUIPO eSearch e TMview per l'UE e i paesi membri, WIPO Global Brand Database per le
   registrazioni internazionali, l'ufficio nazionale del mercato (es. UIBM per l'Italia,
   USPTO per gli USA) [L1].
3. Per i loghi: ricerca per elementi figurativi (classificazione di Vienna dove disponibile)
   e confronto visivo con i concorrenti di categoria.
4. Verifica uso di fatto: ricerca web, domini, handle social (dato attuale, con data).
5. Esito per candidato: rischio basso / medio / alto con le anteriorità trovate (numero,
   titolare, classi, stato) e cosa serve per chiudere il rischio.

## Licenze

Per ogni font, immagine, icona, video, audio, libreria di codice:

| Asset | Fonte | Licenza | Uso consentito | Limiti | Prova |
|---|---|---|---|---|---|

- Font: licenza desktop, web, app, uso nel logo, modifiche, embedding nei PDF
  (`font_inspect.py` legge i campi dichiarati nel file; l'EULA della fonderia prevale).
- Stock: tipo di licenza, limiti (stampa oltre una tiratura, uso nel logo, merchandising).
- Codice: licenza open source e obblighi (attribuzione, copyleft).

## Diciture di packaging ed etichette

Elenco delle informazioni obbligatorie per categoria e mercato, con la norma di riferimento
(es. Reg. UE 1169/2011 per gli alimenti [P1]), e verifica di presenza, testo e altezza minima
sul file di stampa. Testi legali forniti o approvati dal cliente.

Registra `legal_text` e le verifiche di licenza in `evidence.py`.
