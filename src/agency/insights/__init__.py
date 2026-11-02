"""Slice di lettura per report e cruscotto (ADR-0019, ADR-0021).

Legge il registro in sola lettura e le tracce, e le proietta in `.data/insights.sqlite`, che si può cancellare
e rigenerare. Non importa il motore né `Ledger`, e non scrive mai il registro: lo impone `import-linter`.

- `domain`: regole pure, senza I/O.
- `ports`: i confini esterni (registro, tracce, proiezione).
- `application`: il caso d'uso `rebuild`.
- `adapters`: SQLite in sola lettura, tracce JSONL, proiezione SQLite.
"""
