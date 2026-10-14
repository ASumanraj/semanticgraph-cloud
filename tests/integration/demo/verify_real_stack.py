"""Verification script for T-228 Real Compose Stack End-to-End Checks.

Runs all 5 backend/database checks against the live running stack:
  API: http://localhost:8013
  DB:  postgresql://user:password@localhost:5433/semanticgraph
  Compose project: semanticgraph-real
"""

import base64
import subprocess
import time

import httpx
import psycopg

API_URL = "http://localhost:8013"
ADMIN_DB_URL = "postgresql://user:password@localhost:5433/semanticgraph"
APP_DB_URL = "postgresql://semanticgraph_app:semanticgraph_app@localhost:5433/semanticgraph"
DB_URL = ADMIN_DB_URL
TENANT_A = "10000000-0000-0000-0000-000000000001"
TENANT_B = "20000000-0000-0000-0000-000000000002"


def wait_for_api(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{API_URL}/health", timeout=2.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError("API did not become healthy in time")


def wait_for_document_processed(tenant_id: str, doc_id: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    with psycopg.connect(DB_URL) as conn:
        while time.time() < deadline:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM semantic_chunks "
                    "WHERE tenant_id = %s AND document_id = %s",
                    (tenant_id, doc_id),
                )
                count = cur.fetchone()[0]
                if count > 0:
                    return
            time.sleep(1.0)
    raise RuntimeError(f"Document {doc_id} was not processed by worker in {timeout}s")


def run_checks():
    wait_for_api()
    # Ensure fresh state for reproducible assertions
    with psycopg.connect(ADMIN_DB_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE edges, entities, evidence_spans, assertions, "
            "facts, semantic_chunks, documents CASCADE;"
        )
    print("=" * 70)
    print("T-228 REAL STACK END-TO-END CHECKS")
    print("=" * 70)

    # -------------------------------------------------------------
    # CHECK 1: Rows by SQL
    # -------------------------------------------------------------
    print("\n--- CHECK 1: Rows by SQL ---")
    doc1_text = (
        "Master Services Agreement between Alpha Technologies and Beta Solutions.\n\n"
        "Beta Solutions agrees to provide artificial intelligence research services."
    )
    b64_content = base64.b64encode(doc1_text.encode("utf-8")).decode("ascii")

    client = httpx.Client(base_url=API_URL, timeout=10.0)
    res = client.post(
        "/api/v1/documents/ingest",
        headers={"X-Tenant-ID": TENANT_A},
        json={
            "filename": "synthetic_alpha_beta_contract.txt",
            "content": b64_content,
            "ontology_name": "default",
            "allowed_entity_types": ["Organization", "Person", "Service"],
            "allowed_edge_types": ["AGREES_TO", "PROVIDES"],
        },
    )
    assert res.status_code == 200, f"Ingest failed: {res.text}"
    doc1_id = res.json()["document_id"]
    print(f"Ingested Document 1: {doc1_id} (Status: {res.json()['status']})")

    wait_for_document_processed(TENANT_A, doc1_id)

    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        # 1. Documents
        cur.execute(
            "SELECT id, tenant_id, filename, status FROM documents WHERE id = %s",
            (doc1_id,),
        )
        doc_row = cur.fetchone()
        print(
            f"\n[documents table]\n"
            f"  id: {doc_row[0]}\n"
            f"  tenant_id: {doc_row[1]}\n"
            f"  filename: {doc_row[2]}\n"
            f"  status: {doc_row[3]}"
        )
        assert str(doc_row[1]) == TENANT_A

        # 2. Semantic Chunks
        cur.execute(
            "SELECT id, tenant_id, document_id, chunk_index, length(text), left(text, 40) "
            "FROM semantic_chunks WHERE document_id = %s ORDER BY chunk_index",
            (doc1_id,),
        )
        chunk_rows = cur.fetchall()
        print(f"\n[semantic_chunks table] ({len(chunk_rows)} rows)")
        for c in chunk_rows:
            print(
                f"  chunk_id: {c[0]} | tenant: {c[1]} | index: {c[3]} | "
                f"len: {c[4]} | preview: '{c[5]}...'"
            )
            assert str(c[1]) == TENANT_A
            assert str(c[2]) == doc1_id
        assert len(chunk_rows) == 2, f"Expected 2 chunks, got {len(chunk_rows)}"

        # 3. Entities
        cur.execute(
            "SELECT id, tenant_id, name, entity_type FROM entities WHERE tenant_id = %s",
            (TENANT_A,),
        )
        entity_rows = cur.fetchall()
        print(f"\n[entities table] ({len(entity_rows)} rows)")
        for e in entity_rows:
            print(f"  entity_id: {e[0]} | tenant: {e[1]} | name: '{e[2]}' | type: {e[3]}")
            assert str(e[1]) == TENANT_A
        assert len(entity_rows) > 0, "Entities must be persisted"

        # 4. Edges
        cur.execute(
            "SELECT id, tenant_id, source_entity_id, target_entity_id, edge_type "
            "FROM edges WHERE tenant_id = %s",
            (TENANT_A,),
        )
        edge_rows = cur.fetchall()
        print(f"\n[edges table] ({len(edge_rows)} rows)")
        for ed in edge_rows:
            print(
                f"  edge_id: {ed[0]} | tenant: {ed[1]} | "
                f"source: {ed[2]} | target: {ed[3]} | type: {ed[4]}"
            )
            assert str(ed[1]) == TENANT_A
        assert len(edge_rows) > 0, "Edges must be persisted"

        # 5. Evidence Spans
        cur.execute(
            """
            SELECT s.id, s.tenant_id, s.chunk_id, s.start_offset, s.end_offset, s.quote, c.text
            FROM evidence_spans s
            JOIN semantic_chunks c ON s.chunk_id = c.id
            WHERE s.tenant_id = %s
            """,
            (TENANT_A,),
        )
        span_rows = cur.fetchall()
        print(f"\n[evidence_spans table] ({len(span_rows)} rows)")
        for s in span_rows:
            span_id, tid, cid, start_off, end_off, quote, chunk_text = s
            print(f"  span_id: {span_id}")
            print(f"    tenant_id: {tid} | chunk_id: {cid}")
            print(f"    offsets: [{start_off}:{end_off}]")
            print(f"    quote: '{quote}'")
            source_slice = chunk_text[start_off:end_off]
            assert str(tid) == TENANT_A
            assert cid is not None
            assert start_off is not None and end_off is not None
            assert quote == source_slice, f"Quote mismatch: {quote!r} != {source_slice!r}"
            print("    verified: quote matches chunk substring exactly -> TRUE")
        assert len(span_rows) > 0, "Evidence spans must exist"

    print("\n>>> CHECK 1 PASSED: All tables have rows with valid tenant_id, offsets and quotes.")

    # -------------------------------------------------------------
    # CHECK 2: Restart persistence
    # -------------------------------------------------------------
    print("\n--- CHECK 2: Restart Persistence ---")
    res_before = client.get("/api/v1/graph", headers={"X-Tenant-ID": TENANT_A})
    assert res_before.status_code == 200
    nodes_before = sorted([n["id"] for n in res_before.json().get("nodes", [])])
    print(f"Node IDs before restart ({len(nodes_before)} nodes): {nodes_before}")

    print("Restarting api and worker containers...")
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "semanticgraph-real",
            "-f",
            "docker-compose.real.yml",
            "restart",
            "api",
            "worker",
        ],
        check=True,
    )
    wait_for_api()

    res_after = client.get("/api/v1/graph", headers={"X-Tenant-ID": TENANT_A})
    assert res_after.status_code == 200
    nodes_after = sorted([n["id"] for n in res_after.json().get("nodes", [])])
    print(f"Node IDs after restart ({len(nodes_after)} nodes):  {nodes_after}")
    assert nodes_before == nodes_after, "Node IDs must be identical before and after restart!"
    print("\n>>> CHECK 2 PASSED: Graph survives api/worker restart with identical node IDs.")

    # -------------------------------------------------------------
    # CHECK 3: Isolation over HTTP and SQL RLS (Non-Owner Role)
    # -------------------------------------------------------------
    print("\n--- CHECK 3: Isolation over HTTP and SQL RLS (semanticgraph_app) ---")
    res_b_graph = client.get("/api/v1/graph", headers={"X-Tenant-ID": TENANT_B})
    assert res_b_graph.status_code == 200
    b_nodes = res_b_graph.json().get("nodes", [])
    b_edges = res_b_graph.json().get("edges", [])
    print(f"Tenant B HTTP graph: {len(b_nodes)} nodes, {len(b_edges)} edges")
    assert b_nodes == [] and b_edges == [], "Tenant B graph must be empty!"

    res_b_doc = client.delete(f"/api/v1/documents/{doc1_id}", headers={"X-Tenant-ID": TENANT_B})
    print(
        f"Tenant B HTTP access to Tenant A doc: Status {res_b_doc.status_code}, "
        f"Body: {res_b_doc.json()}"
    )
    assert res_b_doc.status_code == 404, "Tenant B must receive 404 for Tenant A's document!"

    # SQL RLS Check 3a: As semanticgraph_app with NO tenant context set, all queries return 0 rows
    print("\n[SQL RLS as semanticgraph_app without app.current_tenant_id context]")
    with psycopg.connect(APP_DB_URL) as app_conn, app_conn.cursor() as cur:
        # Check current user to confirm connected as semanticgraph_app
        cur.execute("SELECT current_user, session_user;")
        u_row = cur.fetchone()
        print(f"  Connected DB role: current_user={u_row[0]}, session_user={u_row[1]}")
        assert u_row[0] == "semanticgraph_app", f"Must be semanticgraph_app, got {u_row[0]}"

        # Query all tables without setting tenant context
        cur.execute("SELECT count(*) FROM documents;")
        doc_count_no_tenant = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM semantic_chunks;")
        chunk_count_no_tenant = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM entities;")
        entity_count_no_tenant = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM edges;")
        edge_count_no_tenant = cur.fetchone()[0]

        print(
            f"  SELECT count(*) FROM documents:       {doc_count_no_tenant} (expected 0)\n"
            f"  SELECT count(*) FROM semantic_chunks: {chunk_count_no_tenant} (expected 0)\n"
            f"  SELECT count(*) FROM entities:        {entity_count_no_tenant} (expected 0)\n"
            f"  SELECT count(*) FROM edges:           {edge_count_no_tenant} (expected 0)"
        )
        assert (
            doc_count_no_tenant == 0
            and chunk_count_no_tenant == 0
            and entity_count_no_tenant == 0
            and edge_count_no_tenant == 0
        ), "CRITICAL: RLS failed! Non-owner role semanticgraph_app saw rows without tenant context!"
        print("  -> Verified: zero rows visible when no tenant context is set.")

    # SQL RLS Check 3b: With SET LOCAL app.current_tenant_id = TENANT_B, returns 0 rows
    print("\n[SQL RLS as semanticgraph_app with SET LOCAL app.current_tenant_id = TENANT_B]")
    with psycopg.connect(APP_DB_URL) as app_conn, app_conn.cursor() as cur:
        cur.execute(f"SET LOCAL app.current_tenant_id = '{TENANT_B}';")
        cur.execute("SELECT count(*) FROM documents;")
        doc_count_tb = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM entities;")
        entity_count_tb = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM edges;")
        edge_count_tb = cur.fetchone()[0]
        print(
            f"  Tenant B SQL context:\n"
            f"    documents: {doc_count_tb} (expected 0)\n"
            f"    entities:  {entity_count_tb} (expected 0)\n"
            f"    edges:     {edge_count_tb} (expected 0)"
        )
        assert doc_count_tb == 0 and entity_count_tb == 0 and edge_count_tb == 0

    # SQL RLS Check 3c: With SET LOCAL app.current_tenant_id = TENANT_A, returns Tenant A rows
    print("\n[SQL RLS as semanticgraph_app with SET LOCAL app.current_tenant_id = TENANT_A]")
    with psycopg.connect(APP_DB_URL) as app_conn, app_conn.cursor() as cur:
        cur.execute(f"SET LOCAL app.current_tenant_id = '{TENANT_A}';")
        cur.execute("SELECT count(*) FROM documents;")
        doc_count_ta = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM semantic_chunks;")
        chunk_count_ta = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM entities;")
        entity_count_ta = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM edges;")
        edge_count_ta = cur.fetchone()[0]
        print(
            f"  Tenant A SQL context:\n"
            f"    documents:       {doc_count_ta} (expected 1)\n"
            f"    semantic_chunks: {chunk_count_ta} (expected 2)\n"
            f"    entities:        {entity_count_ta} (expected > 0)\n"
            f"    edges:           {edge_count_ta} (expected > 0)"
        )
        assert doc_count_ta == 1 and chunk_count_ta == 2 and entity_count_ta > 0

    print(
        "\n>>> CHECK 3 PASSED: Tenant B isolated via HTTP and SQL RLS "
        "(zero rows without tenant context)."
    )

    # -------------------------------------------------------------
    # CHECK 4: Deletion & Rule 4 assertion count cascade
    # -------------------------------------------------------------
    print("\n--- CHECK 4: Deletion & Rule 4 Cascade ---")
    doc2_text = (
        "Beta Solutions agrees to provide artificial intelligence research services.\n\n"
        "Beta Solutions delivers quarterly evaluation benchmarks."
    )
    b64_content_2 = base64.b64encode(doc2_text.encode("utf-8")).decode("ascii")
    res2 = client.post(
        "/api/v1/documents/ingest",
        headers={"X-Tenant-ID": TENANT_A},
        json={
            "filename": "synthetic_beta_deliverables.txt",
            "content": b64_content_2,
            "ontology_name": "default",
            "allowed_entity_types": ["Organization", "Person", "Service"],
            "allowed_edge_types": ["AGREES_TO", "PROVIDES"],
        },
    )
    assert res2.status_code == 200
    doc2_id = res2.json()["document_id"]
    print(f"Ingested Document 2: {doc2_id}")
    wait_for_document_processed(TENANT_A, doc2_id)

    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM assertions WHERE tenant_id = %s", (TENANT_A,))
        assertions_before_del = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM facts WHERE tenant_id = %s", (TENANT_A,))
        facts_before_del = cur.fetchone()[0]
        print(
            f"Before deleting Doc 1: {assertions_before_del} assertions, {facts_before_del} facts"
        )

    # Delete Document 1
    del_res = client.delete(f"/api/v1/documents/{doc1_id}", headers={"X-Tenant-ID": TENANT_A})
    assert del_res.status_code == 200
    print(f"Deleted Document 1: {del_res.json()}")

    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM semantic_chunks WHERE document_id = %s", (doc1_id,))
        doc1_chunks = cur.fetchone()[0]
        print(f"Doc 1 chunks remaining: {doc1_chunks}")
        assert doc1_chunks == 0, "Document 1 chunks must be deleted"

        cur.execute("SELECT count(*) FROM semantic_chunks WHERE document_id = %s", (doc2_id,))
        doc2_chunks = cur.fetchone()[0]
        print(f"Doc 2 chunks remaining: {doc2_chunks}")
        assert doc2_chunks > 0, "Document 2 chunks must remain"

        cur.execute("SELECT count(*) FROM assertions WHERE tenant_id = %s", (TENANT_A,))
        assertions_after_del = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM facts WHERE tenant_id = %s", (TENANT_A,))
        facts_after_del = cur.fetchone()[0]
        print(f"After deleting Doc 1: {assertions_after_del} assertions, {facts_after_del} facts")
        assert assertions_after_del < assertions_before_del, "Assertions count must decrease"
        assert facts_after_del > 0, "Facts asserted by Document 2 must survive"

    print("\n>>> CHECK 4 PASSED: Doc 1 chunks/assertions deleted while Doc 2 facts survived.")

    # -------------------------------------------------------------
    # CHECK 5: Idempotent retry
    # -------------------------------------------------------------
    print("\n--- CHECK 5: Idempotent Retry ---")
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM assertions WHERE tenant_id = %s", (TENANT_A,))
        assertions_pre_retry = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM facts WHERE tenant_id = %s", (TENANT_A,))
        facts_pre_retry = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM evidence_spans WHERE tenant_id = %s", (TENANT_A,))
        spans_pre_retry = cur.fetchone()[0]
        print(
            f"Pre-retry counts: facts={facts_pre_retry}, "
            f"assertions={assertions_pre_retry}, spans={spans_pre_retry}"
        )

    # Re-run process_document task via worker for doc2_id
    task_code = (
        "from semanticgraph.adapters.inbound.workers.tasks.ingestion_tasks "
        "import process_document_task; "
        f"res = process_document_task('{TENANT_A}', '{doc2_id}', "
        "{'name': 'default', 'allowed_entity_types': ['Organization', 'Person'], "
        "'allowed_edge_types': ['AGREES_TO']}); "
        "print('Worker retry result:', res)"
    )
    task_exec_cmd = [
        "docker",
        "exec",
        "semanticgraph-real-worker-1",
        "python",
        "-c",
        task_code,
    ]
    sub_res = subprocess.run(task_exec_cmd, capture_output=True, text=True, check=True)
    print(f"Celery worker re-processed doc2: {sub_res.stdout.strip()}")

    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM assertions WHERE tenant_id = %s", (TENANT_A,))
        assertions_post_retry = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM facts WHERE tenant_id = %s", (TENANT_A,))
        facts_post_retry = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM evidence_spans WHERE tenant_id = %s", (TENANT_A,))
        spans_post_retry = cur.fetchone()[0]
        print(
            f"Post-retry counts: facts={facts_post_retry}, "
            f"assertions={assertions_post_retry}, spans={spans_post_retry}"
        )
        assert (facts_pre_retry, assertions_pre_retry, spans_pre_retry) == (
            facts_post_retry,
            assertions_post_retry,
            spans_post_retry,
        ), (
            f"Counts changed on retry! Pre: "
            f"({facts_pre_retry}, {assertions_pre_retry}, {spans_pre_retry}) != Post: "
            f"({facts_post_retry}, {assertions_post_retry}, {spans_post_retry})"
        )

    print("\n>>> CHECK 5 PASSED: Re-running ingestion did not duplicate assertions or facts.")
    print("\n" + "=" * 70)
    print("ALL 5 END-TO-END CHECKS PASSED WITH REAL POSTGRES INFRASTRUCTURE!")
    print("=" * 70)


if __name__ == "__main__":
    run_checks()
