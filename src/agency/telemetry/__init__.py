"""OpenTelemetry traces in a local file. The real costs are in the registry, not here."""

from agency.telemetry.setup import configure

__all__ = ["configure"]
