"""
Extraction Contract for LLM Structured Outputs.

Enforces T-202 Acceptance Criterion 2:
The extraction contract requests claim + verbatim quote + chunk id, and NEVER an offset.
Language models cannot reliably count characters; asking for offsets produces hallucinations.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExtractedSpanEvidence(BaseModel):
    """An evidence citation requested from the language model.

    Notice: NEVER includes character offsets.
    """

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID = Field(
        description="The UUID of the semantic chunk containing the supporting quote"
    )
    verbatim_quote: str = Field(
        min_length=1,
        description="The exact, verbatim quote from the chunk supporting the claim",
    )


class ExtractedClaim(BaseModel):
    """An extracted factual claim with supporting evidence citations from the model."""

    model_config = ConfigDict(frozen=True)

    claim: str = Field(
        min_length=1,
        description="The factual claim, proposition, or relation asserted by the text",
    )
    evidence: list[ExtractedSpanEvidence] = Field(
        min_length=1,
        description="One or more verbatim quotes from the chunks supporting this claim",
    )
