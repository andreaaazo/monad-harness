# Verifica tecnica

1. Dal ticket: file e controlli richiesti.
2. Esegui i controlli con `run_check`: i risultati li registra il sistema con la tua firma.
3. Guarda ciò che i numeri non vedono: `render` a dimensione d'uso, poi `view_image`.
4. Registra con `observe` ciò che hai visto, descrivendolo concretamente.
5. Ogni difetto: file, posizione o coordinate, misura, soglia, impatto.

## Controlli per i vettori

| Cosa | Controllo |
|---|---|
| Master apribile e non vuoto | `master_open` |
| Geometria dell'SVG | `svg_audit` |
| Stesso aspetto tra renderer | `svg_parity` |
| Foglio di prova: riduzione, mono, negativo, sfocatura | `logo_proof`, poi `observe` |
| Equilibrio e centro ottico su PNG | `optical_check` |

## Referto

Referto in `reviews/`: file e versioni ispezionate, controlli con esito, difetti con severità, verdetto.
Bloccante: inutilizzabile o errato. Maggiore: requisito fallito o difetto visibile all'uso. Minore:
difetto localizzato. Preferenza: alternativa senza violazione.
