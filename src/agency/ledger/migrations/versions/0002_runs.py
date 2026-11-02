"""La tabella `runs`: ogni esecuzione con la sua impronta, solo in aggiunta (M1.6, punto 4)."""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"

STATEMENTS = (
    """
CREATE TABLE runs (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    command VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    fingerprint_json VARCHAR NOT NULL,
    PRIMARY KEY (seq)
)
""",
    """
CREATE INDEX ix_runs_project ON runs (project)
""",
    """
CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs
BEGIN
    SELECT RAISE(ABORT, 'runs è solo in aggiunta');
END
""",
    """
CREATE TRIGGER runs_no_update BEFORE UPDATE ON runs
BEGIN
    SELECT RAISE(ABORT, 'runs è solo in aggiunta');
END
""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("il registro non torna indietro: si ripristina dalla copia di agency migrate")
