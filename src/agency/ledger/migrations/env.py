"""Alembic's environment: it works only on the connection that `agency.ledger.schema` opens."""

from __future__ import annotations

from alembic import context

context.configure(connection=context.config.attributes["connection"])
with context.begin_transaction():
    context.run_migrations()
