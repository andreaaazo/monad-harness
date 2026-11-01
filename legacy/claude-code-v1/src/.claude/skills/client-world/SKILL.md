---
name: client-world
description: Immersione nel mondo del cliente e costruzione del dossier del progetto — raccolta e inventario dei materiali (prodotto, materiali, linguaggio, documenti, fotografie, utenti, situazioni d'uso), palette e lessico misurati, fatti con provenienza (confermati dal cliente, da fonte, ipotesi) e copertura dei temi obbligatori. Da usare all'inizio di ogni progetto M o L e ogni volta che arrivano materiali nuovi.
---

# Mondo del cliente e dossier

Il lavoro personalizzato nasce dal materiale del cliente, non dalla categoria. Prima di
qualsiasi direzione lo studio deve sapere: pubblico, obiettivo, contesto d'uso, concorrenti,
contenuti reali, vincoli produttivi, criteri di successo — e da dove viene ogni informazione.

## 1. Raccogliere

Chiedi al cliente (tramite il router, `client.py ask`) i materiali, spiegando perché servono:
- **prodotto/servizio**: foto, schede, listini, come si usa davvero;
- **materiali**: superfici, campioni, packaging esistente, ambienti (foto del luogo);
- **linguaggio**: testi del sito, brochure, email, recensioni, come parlano i clienti;
- **documenti**: moduli, presentazioni, report, contratti tipo, segnaletica;
- **fotografie**: archivio, foto del team e dei luoghi, immagini usate oggi;
- **utenti e situazioni**: chi sono, dove e quando incontrano il brand, in che stato d'animo.

Mettili in `work/client/` (sottocartelle libere). Per i materiali pubblici (sito, social,
schede dei concorrenti) chiedi al `researcher` di raccoglierli con fonte e data.

## 2. Inventariare e guardare

```sh
.claude/scripts/py .claude/skills/client-world/scripts/world_ingest.py work/client
```

Produce in `work/context/world/`: inventario, testi estratti, palette misurate in OKLCH,
font usati nei PDF, lessico del cliente (parole, bigrammi, lunghezza delle frasi), fogli di
contatto di immagini e pagine. **Apri i fogli con Read e guardali**: la palette misurata
non dice come appare un ambulatorio, la foto sì.

## 3. Registrare i fatti con la provenienza

```sh
python3 .claude/scripts/facts.py add --topic audience --kind client --text "…" --ref A-0004
python3 .claude/scripts/facts.py add --topic materials --kind source --text "…" --ref work/client/foto/ingresso.jpg
python3 .claude/scripts/facts.py add --topic competitors --kind source --text "…" --ref https://… --date 2026-10-29
python3 .claude/scripts/facts.py add --topic users --kind hypothesis --text "…" --why "…" --test "chiedere a Marta"
```

- **client**: solo con l'id di una risposta, un feedback o un'approvazione di `client.py`.
- **source**: un file del cliente o una fonte con data. Un documento del cliente è una fonte,
  non una conferma: "il sito dice X" non significa "il cliente conferma X oggi".
- **hypothesis**: ragionamento e modo di verificarla. Le ipotesi importanti diventano domande
  al cliente; con la risposta: `facts.py confirm` o `facts.py reject`.

## 4. Copertura e dossier

```sh
python3 .claude/scripts/facts.py coverage     # temi obbligatori senza fatti → bloccante
python3 .claude/scripts/facts.py export       # work/context/dossier.md
```

Un tema coperto solo da ipotesi si dichiara al cliente prima di usarlo per decidere.
Strategia, brief pack e direzioni citano i fatti come [F-0007]: `facts.py check <file>`
segnala citazioni inesistenti o smentite e conta quante affermazioni poggiano su ipotesi.

## 5. Selezione pertinente

Da dossier e mondo del cliente, il `researcher` compone `work/references/selection.md`: 8–15
riferimenti (dalla storia del design, dalla categoria e **fuori** dalla categoria) scelti per
questo progetto, ognuno con il fatto del dossier a cui risponde, cosa insegna e cosa non
prendere. I riferimenti generici validi per qualsiasi cliente non entrano.

Inoltre `work/references/levels.md`: per ogni mezzo del progetto (tipografia, composizione,
fotografia, ritmo editoriale, interazione, motion) tre esempi reali con fonte — **ordinario**,
**buono**, **eccellente** — nelle stesse condizioni d'uso del progetto, e per ciascun passaggio
dove sta il salto concreto (es. "da buono a eccellente: la gerarchia nasce da un solo contrasto
di scala invece che da tre pesi"). Immagini in `work/references/img/` come materiale di analisi.
È lo strumento con cui il critico calibra il livello richiesto.
