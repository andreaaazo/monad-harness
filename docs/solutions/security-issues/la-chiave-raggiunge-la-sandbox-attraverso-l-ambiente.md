---
title: La chiave raggiunge la sandbox attraverso l'ambiente, anche con --clearenv
date: 2026-11-13
category: security-issues
module: agency.tools.sandbox
problem_type: security_issue
component: infrastructure
symptoms:
  - "con ANTHROPIC_API_KEY esportata nella shell, il codice nella sandbox la legge da /proc/1/environ"
  - "la prova sull'ambiente del comando dice che la chiave non c'è, e l'audit lo ha scritto come verificato"
  - "con AGENCY_EXPLORERS=2 esportato, 33 prove di flusso falliscono; con anthropic_api_key minuscolo la chiave arriva alle prove"
root_cause: config_error
resolution_type: code_fix
severity: high
tags: [sandbox, bwrap, environment, secrets, proc-environ, test-isolation]
---

# La chiave raggiunge la sandbox attraverso l'ambiente, anche con --clearenv

## Problema

`Sandbox.run` avviava `systemd-run` e `bwrap` con l'ambiente intero dell'harness. `--clearenv` svuota solo
l'ambiente del **comando**: bwrap stesso è il processo 1 dentro la sandbox e conserva l'ambiente con cui è partito,
leggibile da qualunque processo della sandbox in `/proc/1/environ`. Con la chiave esportata nella shell, il codice
del modello poteva stamparla, e l'uscita tornava come risultato dello strumento nella conversazione, nelle
trascrizioni e nelle registrazioni. La regola di `CLAUDE.md` ("mai dentro una sandbox") era violata dal primo giorno,
e l'audit di sicurezza l'aveva data per verificata.

Lo stesso errore, ereditare l'ambiente senza volerlo, era nelle prove: il fixture che teneva lontano `.env` non
toglieva le variabili `AGENCY_*` né la chiave esportate nella shell dell'operatore.

## Sintomi

- La sonda della prova (`os.environ.get('ANTHROPIC_API_KEY')` dentro la sandbox) diceva `None`, e in
  `/proc/1/environ` c'era la chiave (R1, riprodotto al commit di partenza e alla testa del ramo).
- Lo spike `spikes/sandbox_craft.sh` eseguiva la stessa riga di bwrap da bash con tutto l'ambiente della shell (R8).
- Con `AGENCY_EXPLORERS=2 AGENCY_PROPOSAL_EFFORT=low` esportati, 33 prove fallivano; un `AGENCY_DATA_DIR` esportato
  avrebbe puntato una prova alle impostazioni predefinite verso un registro che la guardia di `conftest.py` non
  controlla (R3). Le impostazioni leggono i nomi in qualunque maiuscolo: `anthropic_api_key` passava (R6).

## Cosa non ha funzionato

- **Controllare l'ambiente del comando**: è quello che `--clearenv` pulisce davvero, quindi la prova passava
  sempre. Bisogna cercare la chiave in ogni `/proc/<pid>/environ`, pid 1 compreso.
- **Una sonda che non ha un controllo positivo**: se `/proc` non si legge, "nessuna chiave trovata" è vero e non
  dimostra nulla. La sonda dello spike ora pretende anche una riga `PATH=` in ciò che ha letto (R10).

## Soluzione

```python
# src/agency/tools/sandbox.py
HOST_VARIABLES = ("PATH", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")


def host_environment() -> dict[str, str]:
    return {name: os.environ[name] for name in HOST_VARIABLES if name in os.environ}


# Sandbox.run e scope_problem:
subprocess.Popen(self.argv(command), ..., env=host_environment())
```

`systemd-run --user` ha bisogno solo di `PATH` e di una tra `XDG_RUNTIME_DIR` e `DBUS_SESSION_BUS_ADDRESS` per
raggiungere il gestore utente (provato con `env -i`). Lo spike prende lo stesso elenco da `host_environment()` e
parte con `env -i`. Nelle prove, il fixture autouse `_no_operator_environment` toglie ogni variabile con il prefisso
di `Settings` e ogni nome della chiave, confrontati in qualunque maiuscolo (`tests/support/environment.py`).

## Perché funziona

Il blocco d'ambiente di pid 1 è quello passato a `execve` di bwrap: se l'harness non ce lo mette, nessun processo
della sandbox lo può leggere. Un elenco esplicito di ciò che serve è l'unico modo per non ereditare ciò che non si
conosce.

## Prevenzione

- Ogni processo figlio dell'harness riceve un `env=` esplicito, come già `src/agency/telemetry/fingerprint.py` per le CLI.
  Resta da decidere `CommandIndex.load` in `src/agency/tools/craft.py`, che lancia `vectorcraft-cli` sull'host con l'ambiente
  intero (`docs/audit/PLAN.md`, R1).
- Una prova di isolamento cerca il segreto dove un attaccante lo cercherebbe: `test_no_process_in_the_sandbox_holds_the_key`
  (in `tests/test_agent_flow.py`) legge ogni `/proc/<pid>/environ` e verifica di averne letto almeno due.
- Una prova che dipende dall'ambiente si verifica anche con l'ambiente sporco:
  `test_a_shell_with_the_operator_variables_changes_nothing` (in `tests/test_environment.py`) lancia pytest in un
  processo figlio con le variabili esportate.

## Problemi correlati

- `docs/06-SECURITY.md` (sezione "Sandbox"), ADR-0045 (`.env` solo per i segreti), ADR-0046 (i limiti della sandbox).
- `docs/audit/20-security.md` ("Checked, no finding", corretto dalla revisione finale) e `docs/audit/PLAN.md` (R1,
  R3, R6, R8, R10).
