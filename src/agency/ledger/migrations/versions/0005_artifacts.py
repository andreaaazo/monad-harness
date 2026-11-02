"""La tabella `artifacts`: le versioni conservate per hash e da dove vengono, solo in aggiunta."""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"

STATEMENTS = (
    """
CREATE TABLE artifacts (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    path VARCHAR NOT NULL,
    ticket_id VARCHAR NOT NULL,
    origin VARCHAR NOT NULL,
    run INTEGER,
    media_type VARCHAR NOT NULL,
    size INTEGER NOT NULL,
    PRIMARY KEY (seq)
)
""",
    """
CREATE INDEX ix_artifacts_project ON artifacts (project)
""",
    """
CREATE UNIQUE INDEX ux_artifacts_kept ON artifacts (sha256, project, path, ticket_id, origin)
""",
    """
CREATE TRIGGER artifacts_no_delete BEFORE DELETE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts è solo in aggiunta');
END
""",
    """
CREATE TRIGGER artifacts_no_update BEFORE UPDATE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts è solo in aggiunta');
END
""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("il registro non torna indietro: si ripristina dalla copia di agency migrate")
