"""La tabella `judgments`: il giudizio alla cieca legato allo sha256 del file, solo in aggiunta."""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"

STATEMENTS = (
    """
CREATE TABLE judgments (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    comparison VARCHAR NOT NULL,
    judge VARCHAR NOT NULL,
    letter VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    file VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL,
    level VARCHAR NOT NULL,
    specific BOOLEAN NOT NULL,
    best BOOLEAN NOT NULL,
    why VARCHAR NOT NULL,
    PRIMARY KEY (seq)
)
""",
    """
CREATE INDEX ix_judgments_project ON judgments (project)
""",
    """
CREATE INDEX ix_judgments_comparison ON judgments (comparison)
""",
    """
CREATE TRIGGER judgments_no_delete BEFORE DELETE ON judgments
BEGIN
    SELECT RAISE(ABORT, 'judgments è solo in aggiunta');
END
""",
    """
CREATE TRIGGER judgments_no_update BEFORE UPDATE ON judgments
BEGIN
    SELECT RAISE(ABORT, 'judgments è solo in aggiunta');
END
""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("il registro non torna indietro: si ripristina dalla copia di agency migrate")
