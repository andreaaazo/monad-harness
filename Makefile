# Alias di Taskfile.yml, l'ingresso unico dei comandi (ADR-0039): `make check` è `task check`.
# mise exec dà le versioni di mise.toml anche quando mise non è attivo nella shell.
TASKS := check lint imports types test web e2e schemas doctor dashboard
.PHONY: setup $(TASKS)

# Task viene da mise: prima si installano gli strumenti, poi si può chiamare.
setup:
	mise install
	mise exec -- task setup

$(TASKS):
	mise exec -- task $@
