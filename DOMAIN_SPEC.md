# Managed GraphRAG Domain Model (Ubiquitous Language)

This document defines the canonical glossary for the Managed GraphRAG domain. It is strictly a glossary of business and domain concepts, totally devoid of implementation details (no AWS, no Python, no Neo4j mentioned here). 

If a term is not in this document, it does not exist in our domain. If it is in this document, it must be used *exactly* as defined here in all code, documentation, and communication.

## Core Concepts

### Document
A raw, unstructured piece of text (e.g., a PDF contract, an email, a research paper) uploaded by a Tenant. This is the source material from which knowledge is extracted.

### Tenant
A distinct business or user account utilizing the SaaS platform. All domain data (Documents, Entities, Edges, Graphs) is strictly owned by and isolated to a single Tenant.

### Ontology
The strict, predefined schema of allowed `Entity Types` and `Edge Types`. The extraction process is entirely constrained by the Ontology.

### Semantic Chunk
A bounded, meaningful segment of a Document. Documents are broken down into Semantic Chunks to preserve context during the extraction process.

## The Knowledge Graph

### Entity (Node)
A distinct, identifiable real-world object, concept, or person extracted from a Semantic Chunk. Every Entity must conform to a type defined in the Ontology.
*   **Raw Entity:** An entity as it was initially extracted from a single text chunk, before resolution.
*   **Golden Record (Canonical Entity):** The authoritative, unified version of an Entity after the Resolution process has merged all duplicate or alias Raw Entities (e.g., merging "MSFT" and "Microsoft Corp." into a single Golden Record).

### Edge (Relationship)
A directional connection between two Entities, representing how they relate. Every Edge must conform to a type defined in the Ontology.

### Resolution
The domain process of identifying, adjudicating, and merging multiple Raw Entities into a single Golden Record to prevent graph fragmentation.

### Disambiguation
The domain process of explicitly declaring that two similar-sounding Raw Entities (e.g., "Apple" the fruit and "Apple" the company) are distinct and should *not* be merged into a single Golden Record.

### Subgraph
A constrained traversal or localized view of the wider Knowledge Graph, typically returned in response to a specific query.
