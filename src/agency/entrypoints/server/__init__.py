"""The dashboard server: Django with Django Ninja, read-only, in a process of its own (ADR-0019, ADR-0020).

It reads through `agency.insights` and imports neither the engine nor `agency.config`, which reads `.env`;
`import-linter` enforces this. It has no models and no database: Django does not own the registry.
"""
