.PHONY: setup check test lint imports types doctor
setup:
	uv sync
check: lint imports types test
lint:
	uv run ruff check . && uv run ruff format --check .
imports:
	uv run lint-imports
types:
	uv run pyright
test:
	uv run pytest
doctor:
	uv run agency doctor
