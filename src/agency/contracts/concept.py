"""The idea card: what is judged before anything is drawn."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# The input of the `submit_concept` tool: the Field descriptions are model-facing, and a class docstring
# would join the tool schema.
class ConceptCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str = Field(description="L'idea in una frase")
    client_fact: str = Field(description="Il fatto specifico del cliente da cui nasce")
    why_not_obvious: str = Field(description="Quale idea ovvia evita, e perché questa non lo è")
    drawing: str = Field(description="Cosa si vede nello schizzo scelto, in parole semplici")
    substitution: str = Field(description="Perché non reggerebbe per un altro cliente dello stesso settore")
