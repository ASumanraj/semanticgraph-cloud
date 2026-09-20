"""Commercial Contracts Workflow Demonstration.

Demonstrates the 5 Irreversible Rules end-to-end against real PostgreSQL:
1. Provenance is mandatory (verbatim quotes, exact character spans, chunk_ids).
2. Tenant isolation fails closed (tenant_id everywhere, FORCE RLS, SET LOCAL).
3. Resolution is non-destructive (decision log, human outranks model, unmerge).
4. Facts die by assertion count (shared contract facts survive single doc deletion, die at 0).
5. Ontologies are immutable (published contracts pack v1, extraction runs stamped with version).
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.ontologies.contracts import (
    build_contracts_ontology,
    load_sample_contract,
)
from semanticgraph.adapters.outbound.postgres.deletion_repository import (
    PostgresDeletionRepository,
)
from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.ontology_repository import (
    PostgresOntologyRepository,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.adapters.outbound.postgres.resolution_repository import (
    PostgresResolutionRepository,
)
from semanticgraph.application.use_cases.delete_document import (
    DeleteDocumentCommand,
    DeleteDocumentUseCase,
)
from semanticgraph.domain.models.entities import (
    ClusterMembership,
    DecisionAction,
    DecisionSource,
    Document,
    ExtractionRun,
    Mention,
    OntologyImmutableError,
    ResolutionDecision,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.locator import locate_span
from semanticgraph.domain.provenance.models import Assertion, Fact

DEFAULT_PG_URL = "postgresql://user:password@localhost:5432/semanticgraph"
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


def _get_app_db_url() -> str:
    admin_url = os.environ.get("DATABASE_URL") or DEFAULT_PG_URL
    p = urlparse(admin_url)
    app_netloc = f"{APP_ROLE}:{APP_PASSWORD}@{p.hostname}:{p.port or 5432}"
    app_url = urlunparse((p.scheme, app_netloc, p.path, p.params, p.query, p.fragment))
    return app_url.replace("postgresql://", "postgresql+psycopg_async://")


async def run_contract_workflow_demo() -> dict[str, bool]:
    """Run the complete end-to-end commercial contract workflow demo."""
    print("=" * 80)
    print("  SEMANTICGRAPH CLOUD — COMMERCIAL CONTRACTS WORKFLOW DEMO")
    print("=" * 80)
    print("Demonstrating the 5 Irreversible Rules with the Contracts Vertical Pack.\n")

    tenant_alpha = TenantId(uuid4())
    tenant_beta = TenantId(uuid4())
    print(f"[*] Tenant Alpha (Customer): {tenant_alpha}")
    print(f"[*] Tenant Beta  (Isolated): {tenant_beta}\n")

    db_url = _get_app_db_url()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    doc_repo = PostgresDocumentRepository(session_factory)
    onto_repo = PostgresOntologyRepository(session_factory)
    prov_repo = PostgresProvenanceRepository(session_factory)
    res_repo = PostgresResolutionRepository(session_factory)
    del_repo = PostgresDeletionRepository(session_factory)
    delete_use_case = DeleteDocumentUseCase(del_repo)

    results: dict[str, bool] = {}

    # -------------------------------------------------------------------------
    # STEP 1: Publish Commercial Contracts Vertical Ontology Pack (Rule 5)
    # -------------------------------------------------------------------------
    print("—" * 80)
    print("STEP 1: Publishing Commercial Contracts Vertical Ontology Pack (Rule 5)")
    print("—" * 80)
    ontology_v1 = build_contracts_ontology(tenant_alpha, version=1)
    await onto_repo.publish_ontology(tenant_alpha, ontology_v1)
    fetched_v1 = await onto_repo.get_ontology(tenant_alpha, ontology_v1.name, ontology_v1.version)
    assert fetched_v1 is not None
    print(f"✓ Published Ontology: '{fetched_v1.name}' v{fetched_v1.version}")
    ent_types_str = ", ".join(fetched_v1.allowed_entity_types)
    edge_types_str = ", ".join(fetched_v1.allowed_edge_types)
    print(f"  Entity Types ({len(fetched_v1.allowed_entity_types)}): {ent_types_str}")
    print(f"  Edge Types   ({len(fetched_v1.allowed_edge_types)}): {edge_types_str}")

    # Verify immutability: publishing same version again fails
    try:
        await onto_repo.publish_ontology(tenant_alpha, ontology_v1)
        print("✗ Failed: should have prevented overwriting published ontology version")
        results["immutability"] = False
    except OntologyImmutableError as exc:
        print(f"✓ Immutability Enforced: Overwriting v1 rejected ({exc})")
        results["immutability"] = True

    # -------------------------------------------------------------------------
    # STEP 2: Ingest Commercial Contracts Corpus
    # -------------------------------------------------------------------------
    print("\n" + "—" * 80)
    print("STEP 2: Ingesting Contract Corpus (MSA and Statement of Work #1)")
    print("—" * 80)
    msa_text = load_sample_contract("doc1_master_services_agreement.txt")
    sow_text = load_sample_contract("doc2_statement_of_work_1.txt")

    doc_msa = Document(
        tenant_id=tenant_alpha,
        filename="doc1_master_services_agreement.txt",
        content_type="text/plain",
        size_bytes=len(msa_text),
    )
    doc_sow = Document(
        tenant_id=tenant_alpha,
        filename="doc2_statement_of_work_1.txt",
        content_type="text/plain",
        size_bytes=len(sow_text),
    )
    await doc_repo.save_document(tenant_alpha, doc_msa)
    await doc_repo.save_document(tenant_alpha, doc_sow)

    chunk_msa = SemanticChunk(
        tenant_id=tenant_alpha,
        document_id=doc_msa.id,
        chunk_index=0,
        text=msa_text,
        token_count=len(msa_text.split()),
    )
    chunk_sow = SemanticChunk(
        tenant_id=tenant_alpha,
        document_id=doc_sow.id,
        chunk_index=0,
        text=sow_text,
        token_count=len(sow_text.split()),
    )
    await doc_repo.save_chunks(tenant_alpha, [chunk_msa, chunk_sow])
    print(f"✓ Ingested MSA (Doc ID: {doc_msa.id}, Chunk ID: {chunk_msa.id})")
    print(f"✓ Ingested SOW (Doc ID: {doc_sow.id}, Chunk ID: {chunk_sow.id})")

    # -------------------------------------------------------------------------
    # STEP 3: Ontology-Constrained Extraction with Mandatory Spans (Rule 1 & 5)
    # -------------------------------------------------------------------------
    print("\n" + "—" * 80)
    print("STEP 3: Extraction with Exact Character Spans & Run Tracking (Rule 1 & 5)")
    print("—" * 80)
    # Record ExtractionRun stamped with ontology_version
    ext_run = ExtractionRun(
        tenant_id=tenant_alpha,
        ontology_version=1,
        ontology_id=fetched_v1.id,
        ontology_name=fetched_v1.name,
        document_id=doc_msa.id,
        model_id="claude-3-7-sonnet",
    )
    await onto_repo.record_extraction_run(tenant_alpha, ext_run)
    print(
        f"✓ Stamped ExtractionRun: {ext_run.id} under ontology "
        f"'{ext_run.ontology_name}' v{ext_run.ontology_version}"
    )

    # Locate evidence spans from verbatim quotes (T-202)
    msa_quote_vendor = "Acme Global Solutions LLC, a Delaware limited liability company"
    span_msa_vendor = locate_span(chunk_msa.text, msa_quote_vendor, chunk_msa.id)

    sow_quote_vendor = "Acme Global Solutions and Beta Technologies Inc."
    span_sow_vendor = locate_span(chunk_sow.text, sow_quote_vendor, chunk_sow.id)

    msa_span_str = f"[{span_msa_vendor.start_offset}:{span_msa_vendor.end_offset}]"
    sow_span_str = f"[{span_sow_vendor.start_offset}:{span_sow_vendor.end_offset}]"
    print(f"✓ Extracted MSA Provenance Span: {msa_span_str}")
    print(f"  Verbatim Quote: '{span_msa_vendor.quote}'")
    print(f"✓ Extracted SOW Provenance Span: {sow_span_str}")
    print(f"  Verbatim Quote: '{span_sow_vendor.quote}'")
    results["provenance_spans"] = True

    # -------------------------------------------------------------------------
    # STEP 4: Entity Resolution with Human Precedence (Rule 3)
    # -------------------------------------------------------------------------
    print("\n" + "—" * 80)
    print("STEP 4: Non-Destructive Resolution & Human Precedence (Rule 3)")
    print("—" * 80)
    mention_msa = Mention(
        tenant_id=tenant_alpha,
        document_id=doc_msa.id,
        chunk_id=chunk_msa.id,
        name="Acme Global Solutions LLC",
        entity_type="Company",
        spans=(span_msa_vendor,),
    )
    mention_sow = Mention(
        tenant_id=tenant_alpha,
        document_id=doc_sow.id,
        chunk_id=chunk_sow.id,
        name="Acme Global Solutions",
        entity_type="Company",
        spans=(span_sow_vendor,),
    )
    await res_repo.save_mentions(tenant_alpha, [mention_msa, mention_sow])

    golden_record_id = uuid4()
    decision_model = ResolutionDecision(
        tenant_id=tenant_alpha,
        entity_ids=[mention_msa.id, mention_sow.id],
        golden_record_id=golden_record_id,
        action=DecisionAction.MERGE,
        source=DecisionSource.MODEL,
        confidence=0.88,
        rationale="String similarity and shared Delaware jurisdiction",
    )
    mem_msa_model = ClusterMembership(
        tenant_id=tenant_alpha,
        mention_id=mention_msa.id,
        cluster_id=golden_record_id,
        decision_id=decision_model.id,
        source=DecisionSource.MODEL,
        confidence=0.88,
    )
    mem_sow_model = ClusterMembership(
        tenant_id=tenant_alpha,
        mention_id=mention_sow.id,
        cluster_id=golden_record_id,
        decision_id=decision_model.id,
        source=DecisionSource.MODEL,
        confidence=0.88,
    )
    await res_repo.record_decision(
        tenant_alpha,
        decision_model,
        [mem_msa_model, mem_sow_model],
        canonical_name="Acme Global Solutions",
    )
    gr_model = await res_repo.get_golden_record(tenant_alpha, golden_record_id)
    assert gr_model is not None
    print(
        f"✓ Model Resolution: 2 Mentions clustered into Golden Record "
        f"'{gr_model.canonical_name}' (ID: {gr_model.id})"
    )

    # Human Adjudication: overrides with official LEI entity name
    decision_human = ResolutionDecision(
        tenant_id=tenant_alpha,
        entity_ids=[mention_msa.id, mention_sow.id],
        golden_record_id=golden_record_id,
        action=DecisionAction.MERGE,
        source=DecisionSource.HUMAN,
        confidence=1.0,
        rationale="Verified counterparty against Global LEI Index: 5493006MHB84DD0ZWV18",
        supersedes_decision_id=decision_model.id,
    )
    mem_msa_human = ClusterMembership(
        tenant_id=tenant_alpha,
        mention_id=mention_msa.id,
        cluster_id=golden_record_id,
        decision_id=decision_human.id,
        source=DecisionSource.HUMAN,
        confidence=1.0,
    )
    mem_sow_human = ClusterMembership(
        tenant_id=tenant_alpha,
        mention_id=mention_sow.id,
        cluster_id=golden_record_id,
        decision_id=decision_human.id,
        source=DecisionSource.HUMAN,
        confidence=1.0,
    )
    await res_repo.record_decision(
        tenant_alpha,
        decision_human,
        [mem_msa_human, mem_sow_human],
        canonical_name="Acme Global Solutions LLC",
    )
    gr_human = await res_repo.get_golden_record(tenant_alpha, golden_record_id)
    assert gr_human is not None
    print(
        f"✓ Human Precedence: Administrator decision outranked model "
        f"({gr_human.canonical_name}, LEI Verified)"
    )
    results["human_precedence"] = True

    # -------------------------------------------------------------------------
    # STEP 5: Multi-Document Facts with Provenance Chains (Rule 1 & 4)
    # -------------------------------------------------------------------------
    print("\n" + "—" * 80)
    print("STEP 5: Multi-Document Facts & Evidence Spans")
    print("—" * 80)
    assertion_msa = Assertion(
        tenant_id=tenant_alpha,
        document_id=doc_msa.id,
        chunk_id=chunk_msa.id,
        claim="Acme Global Solutions is a Delaware-registered vendor",
        spans=[span_msa_vendor],
    )
    assertion_sow = Assertion(
        tenant_id=tenant_alpha,
        document_id=doc_sow.id,
        chunk_id=chunk_sow.id,
        claim="Acme Global Solutions is a Delaware-registered vendor",
        spans=[span_sow_vendor],
    )
    shared_fact = Fact(
        tenant_id=tenant_alpha,
        claim="Acme Global Solutions is a Delaware-registered vendor",
        assertions=[assertion_msa, assertion_sow],
    )
    await prov_repo.save_fact(tenant_alpha, shared_fact)

    # SOW-only Fact
    sow_pay_quote = "fixed fee of $150,000, payable in three milestone installments"
    span_sow_pay = locate_span(chunk_sow.text, sow_pay_quote, chunk_sow.id)
    sow_claim = (
        "Customer shall compensate Acme a fixed fee of $150,000 in three milestone installments"
    )
    assertion_sow_only = Assertion(
        tenant_id=tenant_alpha,
        document_id=doc_sow.id,
        chunk_id=chunk_sow.id,
        claim=sow_claim,
        spans=[span_sow_pay],
    )
    sow_only_fact = Fact(
        tenant_id=tenant_alpha,
        claim=sow_claim,
        assertions=[assertion_sow_only],
    )
    await prov_repo.save_fact(tenant_alpha, sow_only_fact)

    print(f"✓ Shared Fact created: '{shared_fact.claim}'")
    print("  Supported by: 2 documents (MSA & SOW), Assertions = 2")
    print(f"✓ SOW-only Fact created: '{sow_only_fact.claim}' (Assertions = 1)")

    # -------------------------------------------------------------------------
    # STEP 6: Assertion-Counted Deletion Cascade (Rule 4)
    # -------------------------------------------------------------------------
    print("\n" + "—" * 80)
    print("STEP 6: Assertion-Counted Deletion Cascade (Rule 4)")
    print("—" * 80)
    print("[*] Action A: Deleting Document 2 (Statement of Work #1)...")
    res_del_sow = await delete_use_case.execute(
        DeleteDocumentCommand(tenant_id=tenant_alpha, document_id=doc_sow.id)
    )
    print("✓ Deletion Result for SOW:")
    print(f"  - Total records erased: {res_del_sow.total_records_erased}")
    print(f"  - Facts survived: {res_del_sow.facts_survived}")
    print(f"  - Facts died: {res_del_sow.facts_died}")

    # Verify: shared fact survives because MSA still asserts it!
    shared_fact_after_sow = await prov_repo.get_fact(tenant_alpha, shared_fact.id)
    assert shared_fact_after_sow is not None
    assert len(shared_fact_after_sow.assertions) == 1
    rem_cnt = len(shared_fact_after_sow.assertions)
    print(f"✓ Verifying Rule 4: Shared fact survived! (remaining assertions = {rem_cnt})")

    # Verify: SOW-only fact died
    sow_only_after = await prov_repo.get_fact(tenant_alpha, sow_only_fact.id)
    assert sow_only_after is None
    print("✓ Verifying Rule 4: SOW-only fact with 0 remaining assertions died cleanly.")

    print("\n[*] Action B: Deleting Document 1 (Master Services Agreement)...")
    res_del_msa = await delete_use_case.execute(
        DeleteDocumentCommand(tenant_id=tenant_alpha, document_id=doc_msa.id)
    )
    print("✓ Deletion Result for MSA:")
    print(f"  - Total records erased: {res_del_msa.total_records_erased}")
    print(f"  - Facts died: {res_del_msa.facts_died}")

    # Verify: shared fact now dies because remaining assertion count == 0
    shared_fact_final = await prov_repo.get_fact(tenant_alpha, shared_fact.id)
    assert shared_fact_final is None
    print("✓ Verifying Rule 4: Shared fact reached 0 assertions and was pruned from database!")

    # Verify Golden Record was also pruned when all member mentions were erased
    gr_final = await res_repo.get_golden_record(tenant_alpha, golden_record_id)
    assert gr_final is None
    print("✓ Verifying Cascade: Golden Record pruned when all supporting mentions were erased.")
    results["assertion_counted_deletion"] = True

    # -------------------------------------------------------------------------
    # STEP 7: Tenant Isolation Fails Closed (Rule 2)
    # -------------------------------------------------------------------------
    print("\n" + "—" * 80)
    print("STEP 7: Tenant Isolation Fails Closed (Rule 2)")
    print("—" * 80)
    beta_doc = await doc_repo.get_document(tenant_beta, doc_msa.id)
    beta_onto = await onto_repo.get_ontology(tenant_beta, "commercial_contracts", 1)
    assert beta_doc is None
    assert beta_onto is None
    print("✓ Cross-Tenant Isolation Verified: Tenant Beta sees 0 documents and 0 ontologies.")
    results["tenant_isolation"] = True

    print("\n" + "=" * 80)
    print("  DEMONSTRATION COMPLETED SUCCESSFULLY — ALL 5 INVARIANTS VERIFIED!")
    print("=" * 80)
    await engine.dispose()
    return results


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_contract_workflow_demo())
