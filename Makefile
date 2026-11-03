.PHONY: setup check test lint imports types web e2e doctor
# Gli strumenti hanno le versioni di mise.toml: con mise attivo nella shell sono già nel PATH.
# setup passa da `mise exec`, così funziona anche prima di attivarlo.
setup:
	mise install
	mise exec -- uv sync
	mise exec -- pnpm --dir web install --frozen-lockfile
check: lint imports types test web e2e
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
	pnpm --dir web run api:check
	pnpm --dir web run typecheck
	pnpm --dir web run test
	pnpm --dir web run defenses
e2e:
	pnpm --dir web run build:e2e
	pnpm --dir web exec playwright test
doctor:
	uv run agency doctor
