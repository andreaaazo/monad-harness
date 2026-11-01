.PHONY: setup check test lint types doctor
setup:
	uv sync
check: lint types test
lint:
	uv run ruff check . && uv run ruff format --check .
types:
	uv run pyright
test:
	uv run pytest
doctor:
	uv run agency doctor
