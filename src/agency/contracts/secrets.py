"""The environment variables that may hold the API key, in the order the engine reads them: first set wins.

The key lives in the gateway alone. The dashboard server removes every one of these names from its own
environment, so a name added here is both read by the engine and kept out of the dashboard.
"""

API_KEY_VARIABLES = ("ANTHROPIC_API_KEY", "AGENCY_ANTHROPIC_API_KEY")
