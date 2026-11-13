"""The dashboard's Django settings: read-only, loopback only, no database, no key.

They are read once, at startup, from two environment variables only: `AGENCY_DATA_DIR`, where the registry
lives, and `AGENCY_PROJECTION_DIR`, where the projection lives if not beside the registry. The server does not
read `.env`.
"""

from __future__ import annotations

import secrets

from agency.contracts.layout import data_root, projection_root

DEBUG = False
# No sessions, no users, nothing to sign: a new key at every start, never written down.
SECRET_KEY = secrets.token_urlsafe(50)
# Against DNS rebinding: an outside name that a web page points at 127.0.0.1 does not get through.
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
# No apps and no database: Django does not own the registry (ADR-0020).
INSTALLED_APPS: list[str] = []
DATABASES: dict[str, dict[str, str]] = {}
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "agency.entrypoints.server.middleware.ReadOnly",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "agency.entrypoints.server.urls"
X_FRAME_OPTIONS = "DENY"
USE_TZ = True
TIME_ZONE = "UTC"

# The engine's resolver: the same root, and the same refusal of a relative one (ADR-0045).
AGENCY_DATA_DIR = data_root()
# Without the variable the projection lives beside the registry, whichever that is when it is used: None, not
# a folder fixed at startup.
AGENCY_PROJECTION_DIR = projection_root()
