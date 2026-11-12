# An alias of Taskfile.yml, the single entry point for commands (ADR-0039): `make check` is `task check`.
# mise exec provides the versions of mise.toml even when mise is not active in the shell.
TASKS := check lint imports types test web e2e schemas doctor dashboard
.PHONY: setup $(TASKS)

# Task comes from mise: the tools are installed first, then it can be called.
setup:
	mise install
	mise exec -- task setup

$(TASKS):
	mise exec -- task $@
