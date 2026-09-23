"""CUAD clause extraction evaluation harness (T-909).

Evaluates clause extraction models against CUAD ground-truth annotations:
- Uses GeminiLLMGateway via GeminiConfig.from_env() by default.
- Allows dependency-injecting any LLMGatewayPort for testability.
- Scores precision/recall per category (no blended score).
- Embeds mandatory citation, dataset checksum, and limitations.
"""

from __future__ import annotations

import argparse
from typing import Any
from uuid import uuid4

from evals.cuad.constants import (
    CUAD_CITATION,
    CUAD_LICENCE,
    DISCLAIMERS,
    MASTER_CLAUSES_CSV_SHA256,
)
from evals.cuad.loader import CUADContractAnnotation
from evals.cuad.mapping import (
    get_all_cuad_target_categories,
    get_supported_question_mappings,
    get_unsupported_question_mappings,
)
from evals.cuad.metrics import (
    CUADEvaluationReport,
    compute_category_metrics,
)

from semanticgraph.adapters.outbound.llm.gemini import (
    GeminiConfig,
    GeminiLLMGateway,
)
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.domain.models.entities import (
    Ontology,
    SemanticChunk,
    TenantId,
)

# Standard mapping between ontology entity type names and CUAD category names
ONTOLOGY_TYPE_TO_CUAD_CATEGORY: dict[str, str] = {
    "Party": "Parties",
    "Parties": "Parties",
    "AgreementDate": "Agreement Date",
    "Agreement Date": "Agreement Date",
    "EffectiveDate": "Effective Date",
    "Effective Date": "Effective Date",
    "ExpirationDate": "Expiration Date",
    "Expiration Date": "Expiration Date",
    "RenewalTerm": "Renewal Term",
    "Renewal Term": "Renewal Term",
    "NoticePeriodToTerminateRenewal": "Notice Period To Terminate Renewal",
    "Notice Period To Terminate Renewal": "Notice Period To Terminate Renewal",
    "TerminationForConvenience": "Termination For Convenience",
    "Termination For Convenience": "Termination For Convenience",
    "GoverningLaw": "Governing Law",
    "Governing Law": "Governing Law",
    "CapOnLiability": "Cap On Liability",
    "Cap On Liability": "Cap On Liability",
    "UncappedLiability": "Uncapped Liability",
    "Uncapped Liability": "Uncapped Liability",
    "AntiAssignment": "Anti-Assignment",
    "Anti-Assignment": "Anti-Assignment",
    "ChangeOfControl": "Change Of Control",
    "Change Of Control": "Change Of Control",
    "Exclusivity": "Exclusivity",
    "NonCompete": "Non-Compete",
    "Non-Compete": "Non-Compete",
}


def build_cuad_ontology(tenant_id: TenantId | None = None) -> Ontology:
    """Builds an ontology containing types for the evaluable CUAD categories."""
    allowed_types = list(ONTOLOGY_TYPE_TO_CUAD_CATEGORY.keys())
    t_id = tenant_id or TenantId(value=uuid4())
    return Ontology(
        tenant_id=t_id,
        name="cuad_evaluation_ontology",
        allowed_entity_types=allowed_types,
        allowed_edge_types=["APPLIES_TO", "MODIFIES", "GOVERNED_BY"],
    )


class CUADEvalHarness:
    """Evaluation harness for testing LLM clause extraction against CUAD."""

    def __init__(
        self,
        extractor: LLMGatewayPort | None = None,
        config: GeminiConfig | None = None,
        ontology: Ontology | None = None,
    ) -> None:
        if extractor is not None:
            self.extractor = extractor
        else:
            cfg = config or GeminiConfig.from_env()
            self.extractor = GeminiLLMGateway(config=cfg)

        self.ontology = ontology or build_cuad_ontology()
        self.target_categories = get_all_cuad_target_categories()

    async def extract_contract_clauses(
        self,
        contract_text: str,
        chunk_size: int = 4000,
    ) -> dict[str, list[str]]:
        """Splits contract into chunks and runs extraction to collect predicted clauses."""
        predictions_by_category: dict[str, list[str]] = {cat: [] for cat in self.target_categories}
        tenant_id = TenantId(value=uuid4())

        # Simple sliding chunker for evaluation text
        chunks: list[str] = []
        for i in range(0, len(contract_text), chunk_size):
            chunks.append(contract_text[i : i + chunk_size])
        if not chunks:
            chunks = [""]

        for idx, chunk_text in enumerate(chunks):
            chunk = SemanticChunk(
                tenant_id=tenant_id,
                document_id=uuid4(),
                text=chunk_text,
                chunk_index=idx,
                token_count=len(chunk_text.split()),
            )
            raw_entities, _ = await self.extractor.extract_entities_and_edges(
                tenant_id=tenant_id,
                chunk=chunk,
                ontology=self.ontology,
            )

            for entity in raw_entities:
                cuad_category = ONTOLOGY_TYPE_TO_CUAD_CATEGORY.get(entity.entity_type)
                if cuad_category and cuad_category in predictions_by_category:
                    quote = ""
                    if entity.spans and entity.spans[0].quote:
                        quote = entity.spans[0].quote.strip()
                    elif entity.name:
                        quote = entity.name.strip()

                    if quote and quote not in predictions_by_category[cuad_category]:
                        predictions_by_category[cuad_category].append(quote)

        return predictions_by_category

    async def evaluate_contract(
        self,
        contract_text: str,
        annotation: CUADContractAnnotation,
    ) -> dict[str, Any]:
        """Runs extraction on a single contract and compares against annotation."""
        predictions = await self.extract_contract_clauses(contract_text)
        return {
            "filename": annotation.filename,
            "predictions": predictions,
            "ground_truth": annotation.annotations_by_category,
        }

    async def run_evaluation(
        self,
        contracts: list[tuple[str, CUADContractAnnotation]],
    ) -> CUADEvaluationReport:
        """Evaluates multiple contracts and produces a per-category evaluation report."""
        accumulated_predictions: dict[str, list[str]] = {cat: [] for cat in self.target_categories}
        accumulated_ground_truth: dict[str, list[str]] = {cat: [] for cat in self.target_categories}

        for contract_text, annotation in contracts:
            contract_preds = await self.extract_contract_clauses(contract_text)
            for cat in self.target_categories:
                accumulated_predictions[cat].extend(contract_preds.get(cat, []))
                accumulated_ground_truth[cat].extend(annotation.get_ground_truth(cat))

        # Score per category (no blended score)
        category_metrics = {}
        for cat in self.target_categories:
            metrics = compute_category_metrics(
                category=cat,
                predictions=accumulated_predictions[cat],
                ground_truth=accumulated_ground_truth[cat],
            )
            category_metrics[cat] = metrics

        supported_q = [m.question_id for m in get_supported_question_mappings()]
        unsupported_q = {m.question_id: m.notes for m in get_unsupported_question_mappings()}

        return CUADEvaluationReport(
            category_metrics=category_metrics,
            total_contracts=len(contracts),
            evaluated_questions=supported_q,
            unsupported_questions=unsupported_q,
            citation=CUAD_CITATION,
            licence=CUAD_LICENCE,
            dataset_checksum=MASTER_CLAUSES_CSV_SHA256,
            disclaimers=DISCLAIMERS,
        )


def main() -> None:
    """CLI entrypoint for CUAD evaluation harness."""
    parser = argparse.ArgumentParser(
        description="CUAD Clause Extraction Evaluation Harness (T-909)",
        epilog=f"Citation: {CUAD_CITATION}",
    )
    parser.add_argument(
        "--print-metadata",
        action="store_true",
        help="Print CUAD dataset metadata, citation, checksum, and disclaimers",
    )
    parser.add_argument(
        "--print-mappings",
        action="store_true",
        help="Print question-to-category mapping table",
    )

    args = parser.parse_args()

    if args.print_metadata:
        import json

        from evals.cuad.manifest import get_dataset_metadata

        print(json.dumps(get_dataset_metadata(), indent=2))
        return

    if args.print_mappings:
        print("T-904 Question to CUAD Category Mappings:")
        for m in get_supported_question_mappings():
            cats = ", ".join(m.cuad_categories)
            print(f"[{m.question_id}] {m.description} -> {cats} (Fit: {m.fit.value})")
        print("\nUnsupported / Out of Scope for CUAD:")
        for m in get_unsupported_question_mappings():
            print(f"[{m.question_id}] {m.description} -> Fit: {m.fit.value} ({m.notes})")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
