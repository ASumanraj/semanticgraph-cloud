# Managed GraphRAG Extraction Pipeline Spec

## 1. Architecture Overview
This specification addresses the two core tensions in our Managed GraphRAG SaaS pipeline:
1. **Cost of Extraction**: Addressed via Lazy Extraction, Hybrid NLP filtering, and strict Schema-Guided LLM Extraction.
2. **Entity Resolution (ER)**: Addressed via an explicit Resolution Agent loop utilizing Golden Records and semantic deduplication.

## 2. Cost Optimization: `entity_extractor.py`

### 2.1 Chunking & Filtering Pipeline
Instead of eager all-at-once extraction, we implement a **Filter-then-Extract** pattern:
- **Semantic Chunking:** Break documents using semantic boundaries rather than rigid token counts to keep context intact.
- **FastEmbed Filtering:** Use local embedding models (e.g., `BAAI/bge-small-en-v1.5` via FastEmbed) to compute chunk embeddings. Prioritize chunks that semantically overlap with the active ontology or incoming user queries to enable "Lazy Extraction."
- **Hybrid Extraction (spaCy + LLM):** For standard entities (PERSON, ORG, LOC), use a lightweight NLP model like `spaCy` or GLiNER. Reserve the expensive LLM calls (e.g., GPT-4o) *only* for complex relationship extraction and implicit domain concepts.

### 2.2 Schema-Guided Extraction
To prevent LLM hallucination and reduce token generation overhead by ~90%, we inject a strict JSON Schema into the system prompt.

**Extractor System Prompt:**
```text
You are a top-tier schema-guided knowledge extraction system. 
Extract entities and relationships from the provided text using ONLY the ontology defined below.

ONTOLOGY:
- Entity Types: [Person, Organization, Technology, Contract]
- Relationship Types: [WORKS_FOR, OWNS, USES, SIGNED]

CONSTRAINTS:
1. Do not invent new Entity or Relationship types.
2. Return the output as a strict JSON array of objects conforming to this schema:
   { "entities": [{"id": "str", "type": "str", "name": "str"}], "relationships": [{"source_id": "str", "target_id": "str", "type": "str"}] }
3. If an entity doesn't fit the ontology, ignore it.
```

## 3. Entity Resolution: `resolution_agent.py`

Without ER, the graph fragments (e.g., "Microsoft", "MSFT", "Microsoft Corp" become separate disconnected nodes).

### 3.1 The Golden Record ER Loop
1. **Initial Ingestion (Local ER):** `entity_extractor.py` performs basic exact-match and alias resolution within the scope of a single document chunk.
2. **Global Disambiguation (Global ER):** Periodically (or synchronously per batch), the `resolution_agent.py` identifies potential duplicates across the entire graph.
   - **Candidate Generation:** Compute Cosine Similarity between the embeddings of Entity Names and Descriptions. Group entities with >0.85 similarity into "candidate clusters".
   - **LLM Adjudication:** Pass candidate clusters to the LLM to verify if they represent the same real-world entity and output a canonical record.

**Resolution Agent Prompt:**
```text
You are an Entity Resolution expert. Evaluate the following cluster of entities extracted from our GraphRAG pipeline.
Determine if they refer to the SAME real-world entity. 

Cluster:
1. ID: E1, Name: "Joe's Bldg Inc.", Desc: "Construction firm in NY"
2. ID: E2, Name: "Joe's Building Co.", Desc: "Contractor based in New York"
3. ID: E3, Name: "Joe's Burgers", Desc: "Restaurant in NY"

OUTPUT FORMAT (JSON):
{
  "merged_entities": [
    {
      "canonical_name": "Joe's Building Co.",
      "merged_ids": ["E1", "E2"],
      "combined_description": "Construction firm and contractor based in New York."
    }
  ],
  "distinct_entities": ["E3"]
}
```

### 3.2 Post-Processing & Graph Consolidation
Once the `resolution_agent.py` outputs the merged mapping:
- Run a graph traversal to remap all edges pointing to `E1` and `E2` to the new canonical node `E_Canonical`.
- Delete the orphaned `E1` and `E2` nodes.
- Update the canonical node's metadata array to link back to all original source text chunks for traceability and citations.
