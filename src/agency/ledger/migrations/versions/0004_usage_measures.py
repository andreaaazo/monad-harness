"""`usage` più ricca: esecuzione, fase, effort, durata, TTFT, ragionamento. Le righe vecchie restano vuote."""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"

STATEMENTS = (
    "ALTER TABLE usage ADD COLUMN run INTEGER",
    "ALTER TABLE usage ADD COLUMN phase VARCHAR",
    "ALTER TABLE usage ADD COLUMN effort VARCHAR",
    "ALTER TABLE usage ADD COLUMN duration_ms INTEGER",
    "ALTER TABLE usage ADD COLUMN ttft_ms INTEGER",
    "ALTER TABLE usage ADD COLUMN reasoning_tokens INTEGER",
    "CREATE INDEX ix_usage_run ON usage (run)",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("il registro non torna indietro: si ripristina dalla copia di agency migrate")
