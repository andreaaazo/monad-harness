"""Le impostazioni di Django per il cruscotto: solo lettura, solo loopback, nessun database, nessuna chiave.

Si leggono una volta, all'avvio, da due sole variabili d'ambiente: `AGENCY_DATA_DIR`, dove sta il registro, e
`AGENCY_PROJECTION_DIR`, dove sta la proiezione se non accanto al registro. Il server non legge `.env`.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

DEBUG = False
# Nessuna sessione, nessun utente, niente da firmare: una chiave nuova a ogni avvio, mai scritta.
SECRET_KEY = secrets.token_urlsafe(50)
# Contro il DNS rebinding: un nome esterno fatto puntare a 127.0.0.1 da una pagina web non passa.
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
# Nessuna app e nessun database: Django non possiede il registro (ADR-0020).
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

AGENCY_DATA_DIR = Path(os.environ.get("AGENCY_DATA_DIR", ".data")).resolve()
# Senza la variabile la proiezione sta accanto al registro, qualunque esso sia quando la si usa: None, non una
# cartella fissata all'avvio.
_PROJECTION = os.environ.get("AGENCY_PROJECTION_DIR")
AGENCY_PROJECTION_DIR = Path(_PROJECTION).resolve() if _PROJECTION else None
