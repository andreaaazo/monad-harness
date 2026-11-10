"""The read slice behind the report and the dashboard (ADR-0019, ADR-0021).

It reads the registry (read-only), the SDK traces and the instance transcripts, and projects them into
`insights.sqlite`, which can be deleted and rebuilt. It imports neither the engine nor `Ledger`, and never
writes the registry: `import-linter` enforces this.

- `domain`: pure rules, no I/O.
- `ports`: the outer boundaries (registry, traces, transcripts, projection).
- `application`: the use cases: `rebuild` and `current`, then one per view.
- `views`: the project report, for `agency report` and the dashboard's run view.
- `flow`, `behaviour`, `quality`, `compare`, `replay`: the dashboard's phases, model, tools and QA, compare
  and replay views (Fasi, Modello, Strumenti e QA, Confronto and Replay on screen).
- `sums`: the sums on calls that those views share.
- `adapters`: read-only SQLite registry, JSONL traces, JSONL transcripts, SQLite projection.
"""
