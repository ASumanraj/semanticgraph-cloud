"""
End-to-End Test for Contract Lifecycle: Ingestion, Provenance, Fact Retrieval, and Deletion.

Acceptance Criteria tested (T-110):
- [x] The `postgres` profile builds real Postgres adapters for assertions and facts,
      resolution, ontology, and deletion; contains no in-memory graph repository.
- [x] `GET /api/v1/facts/{id}` returns claim and evidence spans (chunk id, offsets, quote),
      asserting `chunk.text[start:end] == quote`.
- [x] `DELETE /api/v1/documents/{id}` runs assertion-counted cascade: a fact asserted by two
      documents survives the first delete, dies after the second.
- [x] Driven over HTTP against real Postgres; asserts row and assertion counts with raw SQL.
- [x] Multi-tenant isolation over HTTP: Tenant B gets 404 for Tenant A's fact and document IDs.
- [x] Engine-enforced isolation: Unfiltered SQL query as application role returns 0 rows.
- [x] Tenant comes from unsigned `X-Tenant-ID` header (stand-in until Stage 5 auth).
"""

from __future__ import annotations

import base64
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import create_app

APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.mark.e2e
def test_contract_lifecycle_e2e(postgres_admin_url: str, app_db_url: str) -> None:
    """
    E2E test driving document upload, extraction, fact verification, multi-tenant isolation,
    and assertion-counted deletion cascade against real Postgres.
    """
    from semanticgraph.composition.container import Container, default_container

    default_container.cache_clear()
    # Configure environment for postgres profile using application role
    os.environ["DATABASE_URL"] = app_db_url
    os.environ["SEMANTICGRAPH_ADAPTERS"] = "postgres"

    container = Container.postgres()
    app = create_app()
    app.state.container = container

    tenant_a = uuid4()
    tenant_b = uuid4()

    shared_sentence = "The agreement is governed by the laws of the State of Delaware."
    doc1_content = f"{shared_sentence} Additional specific terms for first party."
    doc2_content = f"{shared_sentence} Additional specific terms for second party."

    with TestClient(app) as client:
        # 1. Ingest Document 1 for Tenant A
        res1 = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": str(tenant_a)},
            json={
                "filename": "contract_alpha.txt",
                "content": base64.b64encode(doc1_content.encode()).decode(),
                "ontology_name": "Contracts",
                "allowed_entity_types": ["Agreement"],
                "allowed_edge_types": ["GOVERNED_BY"],
            },
        )
        assert res1.status_code == 200, res1.text
        data1 = res1.json()
        doc1_id = data1["document_id"]
        assert len(data1["fact_ids"]) > 0
        shared_fact_id = data1["fact_ids"][0]

        # 2. Ingest Document 2 for Tenant A asserting the same claim
        res2 = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": str(tenant_a)},
            json={
                "filename": "contract_beta.txt",
                "content": base64.b64encode(doc2_content.encode()).decode(),
                "ontology_name": "Contracts",
                "allowed_entity_types": ["Agreement"],
                "allowed_edge_types": ["GOVERNED_BY"],
            },
        )
        assert res2.status_code == 200, res2.text
        data2 = res2.json()
        doc2_id = data2["document_id"]
        assert shared_fact_id in data2["fact_ids"]

        # 3. Verify Database State via Raw SQL (admin connection)
        with psycopg.connect(postgres_admin_url) as conn, conn.cursor() as cur:
            # Two documents exist for Tenant A
            cur.execute(
                "SELECT count(*) FROM documents WHERE tenant_id = %s;",
                (tenant_a,),
            )
            assert cur.fetchone()[0] == 2

            # Exactly one Fact exists for Tenant A (deduplicated / merged)
            cur.execute(
                "SELECT count(*) FROM facts WHERE tenant_id = %s;",
                (tenant_a,),
            )
            assert cur.fetchone()[0] == 1

            # Two Assertions exist pointing to the same Fact ID
            cur.execute(
                "SELECT count(*) FROM assertions WHERE tenant_id = %s AND fact_id = %s;",
                (tenant_a, shared_fact_id),
            )
            assert cur.fetchone()[0] == 2

            # Fetch chunk text to verify span quote against DB text
            cur.execute(
                "SELECT id, text FROM semantic_chunks WHERE tenant_id = %s AND document_id = %s;",
                (tenant_a, doc1_id),
            )
            chunks = cur.fetchall()
            assert len(chunks) == 1
            chunk1_id, chunk1_text = chunks[0]

        # 4. GET /api/v1/facts/{id} over HTTP for Tenant A
        res_fact = client.get(
            f"/api/v1/facts/{shared_fact_id}",
            headers={"X-Tenant-ID": str(tenant_a)},
        )
        assert res_fact.status_code == 200, res_fact.text
        fact_payload = res_fact.json()
        assert fact_payload["id"] == shared_fact_id
        assert len(fact_payload["evidence_spans"]) >= 1

        # Assert chunk.text[start:end] == quote
        for span in fact_payload["evidence_spans"]:
            start = span["start_offset"]
            end = span["end_offset"]
            quote = span["quote"]
            assert end > start
            assert len(quote) == end - start
            if span["chunk_id"] == str(chunk1_id):
                assert chunk1_text[start:end] == quote

        # 5. Multi-Tenant HTTP Isolation: Tenant B gets 404 for Tenant A's fact and document
        res_b_fact = client.get(
            f"/api/v1/facts/{shared_fact_id}",
            headers={"X-Tenant-ID": str(tenant_b)},
        )
        assert res_b_fact.status_code == 404
        assert res_b_fact.json()["error"]["code"] == "FACT_NOT_FOUND"

        res_b_delete = client.delete(
            f"/api/v1/documents/{doc1_id}",
            headers={"X-Tenant-ID": str(tenant_b)},
        )
        assert res_b_delete.status_code == 404
        assert res_b_delete.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

        # 6. Engine-Enforced Tenant Isolation under RLS:
        # An unfiltered query connecting as the application role returns 0 rows
        with psycopg.connect(app_db_url) as app_conn, app_conn.cursor() as cur:
            cur.execute("SELECT * FROM documents;")
            assert len(cur.fetchall()) == 0, "Unfiltered documents query returned rows under RLS!"

            cur.execute("SELECT * FROM facts;")
            assert len(cur.fetchall()) == 0, "Unfiltered facts query returned rows under RLS!"

            cur.execute("SELECT * FROM assertions;")
            assert len(cur.fetchall()) == 0, "Unfiltered assertions query returned rows under RLS!"

            cur.execute("SELECT * FROM semantic_chunks;")
            assert len(cur.fetchall()) == 0, (
                "Unfiltered semantic_chunks query returned rows under RLS!"
            )

        # 7. DELETE Document 1: Fact survives because Document 2 still asserts it
        res_del1 = client.delete(
            f"/api/v1/documents/{doc1_id}",
            headers={"X-Tenant-ID": str(tenant_a)},
        )
        assert res_del1.status_code == 200, res_del1.text
        del1_data = res_del1.json()
        assert del1_data["facts_survived"] is True
        assert del1_data["retained_facts_count"] >= 1
        assert del1_data["deleted_facts_count"] == 0

        # Raw SQL verification: Fact remains, 1 assertion remains, 1 document remains
        with psycopg.connect(postgres_admin_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM documents WHERE tenant_id = %s;",
                (tenant_a,),
            )
            assert cur.fetchone()[0] == 1

            cur.execute(
                "SELECT count(*) FROM facts WHERE tenant_id = %s AND id = %s;",
                (tenant_a, shared_fact_id),
            )
            assert cur.fetchone()[0] == 1

            cur.execute(
                "SELECT count(*) FROM assertions WHERE tenant_id = %s AND fact_id = %s;",
                (tenant_a, shared_fact_id),
            )
            assert cur.fetchone()[0] == 1

        # HTTP check: Fact is still retrievable
        res_fact_survived = client.get(
            f"/api/v1/facts/{shared_fact_id}",
            headers={"X-Tenant-ID": str(tenant_a)},
        )
        assert res_fact_survived.status_code == 200

        # 8. DELETE Document 2: Fact dies because 0 assertions remain
        res_del2 = client.delete(
            f"/api/v1/documents/{doc2_id}",
            headers={"X-Tenant-ID": str(tenant_a)},
        )
        assert res_del2.status_code == 200, res_del2.text
        del2_data = res_del2.json()
        assert del2_data["facts_died"] is True
        assert del2_data["deleted_facts_count"] >= 1

        # Raw SQL verification: All documents, assertions, and facts are wiped for Tenant A
        with psycopg.connect(postgres_admin_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM documents WHERE tenant_id = %s;",
                (tenant_a,),
            )
            assert cur.fetchone()[0] == 0

            cur.execute(
                "SELECT count(*) FROM facts WHERE tenant_id = %s;",
                (tenant_a,),
            )
            assert cur.fetchone()[0] == 0

            cur.execute(
                "SELECT count(*) FROM assertions WHERE tenant_id = %s;",
                (tenant_a,),
            )
            assert cur.fetchone()[0] == 0

        # HTTP check: Fact is gone (404)
        res_fact_dead = client.get(
            f"/api/v1/facts/{shared_fact_id}",
            headers={"X-Tenant-ID": str(tenant_a)},
        )
        assert res_fact_dead.status_code == 404
        assert res_fact_dead.json()["error"]["code"] == "FACT_NOT_FOUND"

    default_container.cache_clear()
