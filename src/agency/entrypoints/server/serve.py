"""The dashboard process: `uv run agency-server`. Loopback only, and no key in the environment.

A standard-library WSGI server with one thread per request: enough for a single operator on this machine
(06-SECURITY.md). How to reach it from outside is for an ADR in M6 to decide, not for this file.
"""

from __future__ import annotations

import argparse
import errno
import ipaddress
import os
import sys
from collections.abc import MutableMapping
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from agency.contracts.layout import RelativeDataRoot
from agency.contracts.text import plain

SETTINGS = "agency.entrypoints.server.settings"
SECRETS = ("ANTHROPIC_API_KEY", "AGENCY_ANTHROPIC_API_KEY")
# The help of the command is the operator's text (Italian, user-facing): it is written here, not taken
# from the docstring.
DESCRIPTION = (
    "Il processo del cruscotto: `uv run agency-server`. Solo loopback, e senza chiave nell'ambiente.\n"
    "\n"
    "Un server WSGI della libreria standard, con un thread per richiesta: basta per un solo "
    "operatore su questa\n"
    "macchina (06-SECURITY.md). Come raggiungerlo da fuori lo decide un ADR in M6, non questo file.\n"
)
HOST, PORT = "127.0.0.1", 8000


class _Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class _Handler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(plain(f"{self.address_string()} {format % args}") + "\n")


def loopback(host: str) -> bool:
    """Only IPv4 loopback addresses, written as addresses: a name could resolve elsewhere."""
    try:
        return ipaddress.IPv4Address(host).is_loopback
    except ValueError:
        return False


def scrub(environment: MutableMapping[str, str]) -> None:
    """The API key lives in the gateway: the dashboard process does not inherit it."""
    for name in SECRETS:
        environment.pop(name, None)


def build(host: str, port: int) -> WSGIServer:
    """The server on a loopback `host`, with the key scrubbed from the environment before Django loads."""
    if not loopback(host):
        raise ValueError(f"{host} non è un indirizzo di loopback: il cruscotto resta su questa macchina")
    scrub(os.environ)
    os.environ["DJANGO_SETTINGS_MODULE"] = SETTINGS  # always these settings: the defences live there
    # Imported here: Django reads the settings when it loads, and the key must already be gone.
    from django.core.wsgi import get_wsgi_application

    return make_server(host, port, get_wsgi_application(), server_class=_Server, handler_class=_Handler)


def main(argv: list[str] | None = None) -> int:
    """`agency-server`, until interrupted. Exits 2 for a host that is not loopback, 1 if it cannot start."""
    parser = argparse.ArgumentParser(prog="agency-server", description=DESCRIPTION)
    parser.add_argument("--host", default=HOST, help="indirizzo di loopback, di solito 127.0.0.1")
    parser.add_argument("--port", type=int, default=PORT, help="0 sceglie una porta libera")
    args = parser.parse_args(argv)
    try:
        server = build(args.host, args.port)
    except ValueError as exc:
        print(f"SERVER: {exc}", file=sys.stderr)
        return 2
    except RelativeDataRoot as exc:  # the settings load here; the engine prints the same line (ADR-0045)
        print(exc, file=sys.stderr)
        return 1
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise
        print(
            f"SERVER: la porta {args.port} di {args.host} è già occupata, forse da un altro cruscotto acceso."
            " Fermalo, o scegline un'altra con --port.",
            file=sys.stderr,
        )
        return 1
    host, port = server.server_address[:2]
    print(f"Cruscotto in sola lettura su http://{host}:{port}/api/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
