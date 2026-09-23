"""Category mapping between CUAD's 41 clause types and T-904's 12 questions (T-909).

Directly implements the mapping table from docs/research/t904-cuad-crosscheck.md §3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MappingFit(StrEnum):
    """Categorization of fit between our question and CUAD labels."""

    DIRECT = "direct"
    PARTIAL = "partial"
    NOT_COVERED = "not_covered"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class QuestionMapping:
    """Mapping entry for a single question in the T-904 benchmark set."""

    question_id: str
    description: str
    cuad_categories: tuple[str, ...]
    fit: MappingFit
    notes: str = ""

    @property
    def is_evaluable(self) -> bool:
        """True if CUAD contains signals that can be scored."""
        return self.fit in (MappingFit.DIRECT, MappingFit.PARTIAL)


QUESTION_MAPPINGS: tuple[QuestionMapping, ...] = (
    QuestionMapping(
        question_id="Q1",
        description="Parties to the agreement",
        cuad_categories=("Parties",),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on contracting parties.",
    ),
    QuestionMapping(
        question_id="Q2",
        description="Agreement execution date",
        cuad_categories=("Agreement Date",),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on date of agreement execution.",
    ),
    QuestionMapping(
        question_id="Q3",
        description="Effective date",
        cuad_categories=("Effective Date",),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on effective commencement date.",
    ),
    QuestionMapping(
        question_id="Q4",
        description="Contract term / expiration date",
        cuad_categories=("Expiration Date",),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on contract termination/expiration date.",
    ),
    QuestionMapping(
        question_id="Q5",
        description="Auto-renewal term and notice window",
        cuad_categories=("Renewal Term", "Notice Period To Terminate Renewal"),
        fit=MappingFit.PARTIAL,
        notes=(
            "Partial fit: CUAD frames this as renewal term length and notice period to "
            "terminate renewal, rather than a single boolean flag."
        ),
    ),
    QuestionMapping(
        question_id="Q6",
        description="Termination for convenience and notice period",
        cuad_categories=("Termination For Convenience",),
        fit=MappingFit.DIRECT,
        notes=(
            "Direct on right to terminate for convenience; notice period for convenience "
            "is not separately tagged in CUAD."
        ),
    ),
    QuestionMapping(
        question_id="Q7",
        description="Governing law / jurisdiction",
        cuad_categories=("Governing Law",),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on governing law clause.",
    ),
    QuestionMapping(
        question_id="Q8",
        description="Liability cap amount and uncapped liability terms",
        cuad_categories=("Cap On Liability", "Uncapped Liability"),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on liability limitations and uncapped obligations.",
    ),
    QuestionMapping(
        question_id="Q9",
        description="Exclusions and carve-outs from liability cap",
        cuad_categories=(),
        fit=MappingFit.NOT_COVERED,
        notes="Not covered: No CUAD category records carve-outs from a liability cap at all.",
    ),
    QuestionMapping(
        question_id="Q10",
        description="Indemnification obligations",
        cuad_categories=(),
        fit=MappingFit.NOT_COVERED,
        notes="Not covered: CUAD has no Indemnification category anywhere in its 41 categories.",
    ),
    QuestionMapping(
        question_id="Q11",
        description="Assignment restrictions and change of control",
        cuad_categories=("Anti-Assignment", "Change Of Control"),
        fit=MappingFit.DIRECT,
        notes="Direct alignment on anti-assignment and change of control provisions.",
    ),
    QuestionMapping(
        question_id="Q12",
        description="Exclusivity and non-compete covenants",
        cuad_categories=("Exclusivity", "Non-Compete"),
        fit=MappingFit.DIRECT,
        notes=(
            "Direct alignment on exclusivity and non-compete clauses. (CUAD separately tracks "
            "No-Solicit Of Customers/Employees)."
        ),
    ),
    QuestionMapping(
        question_id="Q13",
        description="Amendment diff — what changed between versions",
        cuad_categories=(),
        fit=MappingFit.NOT_APPLICABLE,
        notes=(
            "Not applicable: CUAD contracts are standalone documents and have no "
            "amendment/predecessor pairs to diff."
        ),
    ),
)


def get_supported_question_mappings() -> list[QuestionMapping]:
    """Returns question mappings that can be evaluated against CUAD (Q1–Q8, Q11, Q12)."""
    return [m for m in QUESTION_MAPPINGS if m.is_evaluable]


def get_unsupported_question_mappings() -> list[QuestionMapping]:
    """Returns question mappings with zero CUAD signal (Q9, Q10, Q13)."""
    return [m for m in QUESTION_MAPPINGS if not m.is_evaluable]


def get_all_cuad_target_categories() -> list[str]:
    """Returns sorted, deduplicated list of CUAD category names relevant to our questions."""
    categories: set[str] = set()
    for mapping in get_supported_question_mappings():
        categories.update(mapping.cuad_categories)
    return sorted(categories)
