"""Il server del cruscotto: Django con Django Ninja, in sola lettura, in un processo suo (ADR-0019, ADR-0020).

Legge attraverso `agency.insights` e non importa il motore né `agency.config`, che legge `.env`: lo impone
`import-linter`. Non ha modelli né database: Django non possiede il registro.
"""
