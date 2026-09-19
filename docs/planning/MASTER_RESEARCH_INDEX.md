# GraphRAG Master Research Index

## 1. Core Research Papers
* **"From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (arXiv:2404.16130)**
  * **Authors:** Microsoft Research
  * **Summary:** The foundational paper for Microsoft GraphRAG. It introduces using LLMs to extract knowledge graphs from unstructured text and generating hierarchical community summaries to improve retrieval and multi-hop reasoning over global datasets.
* **Other Papers:** Various independent academic works and surveys exist (e.g., "Retrieval-Augmented Generation with Graphs"), covering the broader field of symbolic and graph-enhanced retrieval approaches.

## 2. GitHub Repositories
* **[microsoft/graphrag](https://github.com/microsoft/graphrag):** The official Microsoft implementation. Currently in maintenance mode. Provides the baseline pipeline for extracting entities/relationships and generating community summaries.
* **[neo4j/neo4j-graphrag-python](https://github.com/neo4j/neo4j-graphrag-python):** The official, first-party Python package by Neo4j for building GraphRAG applications. Replaces the deprecated `neo4j-genai`.
* **[LlamaIndex Property Graph (LlamaIndex Core)](https://docs.llamaindex.ai/):** LlamaIndex's `PropertyGraphIndex` supports hybrid retrieval and custom extraction (Schema-Guided Extraction) over property graphs, with integrations for Neo4j and Memgraph.
* **[neo4j-graphacademy/genai-workshop-graphrag](https://github.com/neo4j-graphacademy/genai-workshop-graphrag):** Hands-on examples and workflows from Neo4j.
* **[neo4j-field/ps-genai-agents](https://github.com/neo4j-field/ps-genai-agents):** Advanced agentic workflows and integrations with LangChain and LangGraph.

## 3. Graph Theory & Mechanics: Nodes & Edges Extraction
Best practices for parsing business documents and defining entities:
* **Explicit Ontology (Schema-Driven):** Do not let the LLM invent its own schema. Define a human-curated ontology (e.g., specific entity types like *Service, Person, Policy* and relationships like *depends_on*).
* **Canonical Identifiers:** Map variations (e.g., "PaymentService", "Payment Service") to a single canonical ID to avoid fragmented graphs.
* **Chunking Strategy:** Use 600-1,200 tokens with 10-15% overlap. Chunks need enough context to extract relationships but not so large that LLMs miss details.
* **Hybrid Extraction:** Combine LLM extraction with deterministic NLP (spaCy) for efficiency and to reduce hallucinations.
* **Community Detection:** Use algorithms like Leiden to group tightly connected nodes into communities. This enables answering broad, "global" thematic questions.
* **Node Granularity:** Balance between Document-level nodes (broad context), Chunk nodes (localized facts), and Entity-level nodes (multi-hop reasoning). Raw documents should be treated as evidence (metadata) rather than primary graph nodes.

## 4. Current Providers & Graph DBs for SaaS Backends
* **Neo4j:** 
  * *Pros:* The industry standard. Mature ecosystem, extensive tooling (APOC), official GraphRAG Python package, and robust support.
  * *Cons:* Can be resource-intensive and expensive at scale.
* **FalkorDB:**
  * *Pros:* Designed for AI/GraphRAG. Runs as a Redis module using sparse matrices. Ultra-low latency, making it ideal for real-time AI and agentic workflows.
  * *Cons:* Smaller ecosystem and community compared to Neo4j.
* **NebulaGraph:**
  * *Pros:* Built for massive scalability (hundreds of billions of edges). Best for web-scale knowledge graphs requiring horizontal distributed scaling.
  * *Cons:* High operational complexity. Overkill for smaller setups.
* **KùzuDB:**
  * *Pros:* Embedded graph database (like SQLite for graphs). Developer-friendly, uses SQL-like query patterns, great for local development and analytical workloads.
  * *Cons:* May not suit high-concurrency client-server enterprise workloads as well as Neo4j or FalkorDB.
* **Amazon Neptune / Memgraph:** Other notable mentions with strong LlamaIndex/LangChain integrations. Memgraph offers an in-memory, high-performance alternative to Neo4j with Cypher support.
