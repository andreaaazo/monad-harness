"""Solo lettura, prima di ogni view: un metodo che non è GET non arriva a nessun codice dell'API."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

ALLOWED = ("GET",)


class ReadOnly:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Django controlla ALLOWED_HOSTS solo quando qualcuno chiede l'host: qui si chiede sempre, per primo.
        # Un host estraneo solleva DisallowedHost e Django risponde 400: è la difesa contro il DNS rebinding.
        request.get_host()
        if request.method in ALLOWED:
            response = self.get_response(request)
        else:
            response = HttpResponseNotAllowed(ALLOWED)
        response["Cache-Control"] = "no-store"  # i dati del cliente non restano nella cache del browser
        return response
