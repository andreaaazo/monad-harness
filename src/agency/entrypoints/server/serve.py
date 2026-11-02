"""Il processo del cruscotto: `uv run agency-server`. Solo loopback, e senza chiave nell'ambiente.

Un server WSGI della libreria standard, con un thread per richiesta: basta per un solo operatore su questa
macchina (06-SECURITY.md). Come raggiungerlo da fuori lo decide un ADR in M6, non questo file.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from collections.abc import MutableMapping
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

SETTINGS = "agency.entrypoints.server.settings"
SECRETS = ("ANTHROPIC_API_KEY", "AGENCY_ANTHROPIC_API_KEY")
HOST, PORT = "127.0.0.1", 8000


class _Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class _Handler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def loopback(host: str) -> bool:
    """Solo indirizzi IPv4 di loopback, scritti come indirizzi: un nome si potrebbe risolvere altrove."""
    try:
        return ipaddress.IPv4Address(host).is_loopback
    except ValueError:
        return False


def scrub(environment: MutableMapping[str, str]) -> None:
    """La chiave API vive nel gateway: il processo del cruscotto non la eredita."""
    for name in SECRETS:
        environment.pop(name, None)


def build(host: str, port: int) -> WSGIServer:
    if not loopback(host):
        raise ValueError(f"{host} non è un indirizzo di loopback: il cruscotto resta su questa macchina")
    scrub(os.environ)
    os.environ["DJANGO_SETTINGS_MODULE"] = SETTINGS  # sempre queste: le difese stanno lì
    from django.core.wsgi import get_wsgi_application

    return make_server(host, port, get_wsgi_application(), server_class=_Server, handler_class=_Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agency-server", description=__doc__)
    parser.add_argument("--host", default=HOST, help="indirizzo di loopback, di solito 127.0.0.1")
    parser.add_argument("--port", type=int, default=PORT, help="0 sceglie una porta libera")
    args = parser.parse_args(argv)
    try:
        server = build(args.host, args.port)
    except ValueError as exc:
        print(f"SERVER: {exc}", file=sys.stderr)
        return 2
    host, port = server.server_address[:2]
    print(f"Cruscotto in sola lettura su http://{host}:{port}/api/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
