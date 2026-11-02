"""Ambiente di Alembic: lavora solo sulla connessione aperta da `agency.ledger.schema`."""

from __future__ import annotations

from alembic import context

context.configure(connection=context.config.attributes["connection"])
with context.begin_transaction():
    context.run_migrations()
