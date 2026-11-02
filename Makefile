.PHONY: setup check test lint imports types web doctor
# pnpm alla versione scritta in web/package.json, senza installarlo sulla macchina.
PNPM = npx --yes pnpm@$(shell node -p "require('./web/package.json').packageManager.split('@')[1]")

setup:
	uv sync
	$(PNPM) --dir web install --frozen-lockfile
check: lint imports types test web
lint:
	uv run ruff check . && uv run ruff format --check .
imports:
	uv run lint-imports
types:
	uv run pyright
test:
	uv run pytest
web:
	@test -d web/node_modules || (echo "web/node_modules mancante: esegui make setup" && exit 1)
	$(PNPM) --dir web run api:check
	$(PNPM) --dir web run typecheck
doctor:
	uv run agency doctor
