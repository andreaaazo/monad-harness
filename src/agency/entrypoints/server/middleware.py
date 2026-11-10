"""Read-only, before any view: a method other than GET never reaches the API code."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

ALLOWED = ("GET",)


class ReadOnly:
    """Checks the host first, answers 405 to every method but GET, and marks every response `no-store`."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Django checks ALLOWED_HOSTS only when something asks for the host: here it is always asked, first.
        # A foreign host raises DisallowedHost and Django answers 400: the defence against DNS rebinding.
        request.get_host()
        if request.method in ALLOWED:
            response = self.get_response(request)
        else:
            response = HttpResponseNotAllowed(ALLOWED)
        response["Cache-Control"] = "no-store"  # the client's data does not stay in the browser cache
        return response
