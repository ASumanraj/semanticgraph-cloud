# Architectural Interrogation: Managed GraphRAG SaaS

This report addresses three critical architectural threats to our Managed GraphRAG SaaS platform, providing empirical and industry-standard solutions based on current research and best practices.

## 1. Concurrent Entity Resolution (Race Conditions)

**The Threat:** When multiple ingestion agents try to update the "Golden Record" graph simultaneously, race conditions can occur, leading to deadlocks or data corruption during entity merging.

**Industry Solutions:**
Managing concurrency during entity resolution on a live graph is challenging because read and write operations happen simultaneously. Graph databases employ different mechanisms to handle this:

*   **Neo4j (Transaction Locking):** Neo4j uses automatic write locks on nodes and relationships during transactions. While this ensures consistency, concurrent modification of the same entities by multiple agents can cause deadlocks. Best practices suggest treating entity resolution as a concurrent mutation process rather than batch edits. To minimize deadlock frequency, practitioners favor multiple smaller, atomic transactions over massive ones, and often perform initial fuzzy text-based entity resolution externally before committing the "golden records" to the graph.
*   **Memgraph (MVCC):** Memgraph leverages Multi-Version Concurrency Control (MVCC) and snapshot isolation, allowing writes and reads to occur simultaneously without blocking each other. This is highly advantageous for continuous ingestion.
*   **Queue-Based Single-Writer Ingestion:** The most robust architectural pattern for heavy write contention is the queue-based single-writer model. Incoming data is enqueued by a lightweight service, and a dedicated digestion worker (or a strict pool) reads from the queue to execute writes serially. This decoupling eliminates concurrent modification deadlocks and provides a predictable pipeline for applying entity resolution logic safely before committing to the graph.

*Citations: Neo4j Transaction Management documentation; Memgraph MVCC architecture guidelines; Bugsink architecture patterns for high-contention graph writes.*

## 2. Cross-Tenant Graph Isolation

**The Threat:** Strict isolation of tenants is required without the operational overhead of running entirely separate database instances for every single user.

**Industry Solutions:**
There are two primary approaches to multi-tenancy in graph databases, physical and logical:

*   **Database-Per-Tenant (Physical Isolation):** This is the industry standard for B2B SaaS where strict data isolation is non-negotiable. Each tenant is provisioned their own individual database within a larger cluster (e.g., a Neo4j Enterprise cluster). It provides the strongest isolation boundary and contains "noisy neighbor" issues. Modern Neo4j uses **Composite Databases** to aggregate data across these physical databases if cross-tenant analytics are required, without compromising the underlying isolation.
*   **Role-Based Access Control (RBAC) & Logical Separation:** If a single-database multi-tenant model must be used, standard property/label filtering (e.g., adding `tenantId` to queries) is **highly discouraged** as a security mechanism due to the risk of application-level bugs causing data leakage. Instead, true logical separation is achieved via Fine-Grained Access Control (FGAC) and RBAC. By creating tenant-specific roles with security rules that restrict access to specific subgraphs (labels/properties), the database engine itself enforces isolation, making it far more secure than application-level filtering.

*Recommendation:* For robust B2B SaaS, Database-Per-Tenant is the safest architectural bet for compliance.

*Citations: Neo4j Security and Multi-tenancy documentation; GraphAware multi-tenant architecture guides; Expero Inc. logical partitioning best practices.*

## 3. LLM Cost Economics in GraphRAG

**The Threat:** The sheer token volume required for extracting entities, relationships, and generating community summaries using foundational LLMs (like GPT-4) can bankrupt a GraphRAG project during the ingestion phase.

**Industry Solutions:**
The economics of GraphRAG have transitioned from monolithic, LLM-heavy indexing to efficient, hybrid architectures:

*   **Stripping the "LLM Tax" (GLiNER & spaCy):** Traditional pipelines spent ~75% of their token budget on extraction. Modern architectures replace expensive LLM calls with lightweight NLP models for the initial extraction. **GLiNER** (Generalist and Lightweight NER) is heavily adopted as a zero-shot, open-vocabulary entity extractor. By wrapping GLiNER in **spaCy** pipelines, developers achieve a highly accurate structure extraction locally and for free, reserving expensive LLMs strictly for query-time synthesis.
*   **Local Embedding Models:** Before hitting large commercial models, systems utilize small, local embedding models (like `all-MiniLM-L6-v2`) to cluster and organize the graph structure.
*   **Incremental Graph Updates:** Re-indexing an entire corpus when data changes is financially unviable. Modern frameworks (e.g., LightRAG, CocoIndex) employ incremental update architectures—similar to a Virtual DOM in React. They identify state changes in the document chunks and perform surgical additions, deletions, or updates to the graph. This eliminates full re-indexing costs and prevents context drift.

*Citations: Microsoft GraphRAG cost analysis reports; GLiNER/spaCy integration research; LightRAG incremental update methodology.*
