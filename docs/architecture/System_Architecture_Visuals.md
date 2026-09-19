# SemanticGraph Cloud - System Architecture

## Goal Description
To provide a clear, visual understanding of the complete end-to-end system we are building. This document visualizes how the Enterprise SaaS Control Plane (PostgreSQL) routes traffic securely to the highly scalable AI Graph Engine (AWS Lambda + SQS + Neo4j).

## 1. High-Level Multi-Tenant Architecture

This diagram shows how a user request flows through the system. The **SaaS Control Plane** acts as the gatekeeper. Only if a user is authenticated and has quota remaining are they allowed to trigger the heavy AI graph extraction.

```mermaid
flowchart TD
    User["Corporate User / API Client"] -->|Uploads PDF / Queries| API["FastAPI Gateway"]
    
    subgraph SaaS_Control_Plane["SaaS Control Plane (PostgreSQL)"]
        IAM["IAM & Authentication"]
        Billing["Stripe Quotas & Billing"]
        Audit["Audit Logs & SOC2"]
    end
    
    API --> IAM
    IAM -->|Validates API Key / SSO| Billing
    Billing -->|Checks Rate Limits| Router["Tenant Router"]
    
    subgraph AI_Graph_Engine["AWS Serverless Graph Engine"]
        SQS["AWS SQS FIFO Queues"]
        Lambda["AWS Lambda (Extraction Agents)"]
        LLM["Google Gemini / GLiNER"]
    end
    
    Router -->|If valid| SQS
    SQS --> Lambda
    Lambda <--> LLM
    
    subgraph Silo_Isolation["Isolated Storage Layer"]
        DB1[("Neo4j DB (Tenant A)")]
        DB2[("Neo4j DB (Tenant B)")]
    end
    
    Lambda -->|Writes Edges/Nodes| DB1
    Lambda -->|Writes Edges/Nodes| DB2
    
    classDef control fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px;
    classDef engine fill:#fff3e0,stroke:#ff9800,stroke-width:2px;
    classDef silo fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;
    
    class SaaS_Control_Plane control;
    class AI_Graph_Engine engine;
    class Silo_Isolation silo;
```

## 2. The Core SaaS Relational Schema (Entity-Relationship)

This diagram visualizes the exact SQLAlchemy database we are currently building. Notice how **every** resource strictly points back to the `Tenant` to guarantee data isolation.

```mermaid
erDiagram
    SUPER_ADMIN ||--o{ TENANT : "manages"
    TENANT ||--|{ TENANT_MEMBER : "has"
    USER ||--o{ TENANT_MEMBER : "belongs to"
    
    TENANT ||--o{ API_KEY : "owns"
    TENANT ||--|| SUBSCRIPTION : "billed via"
    TENANT ||--o{ AUDIT_LOG : "generates"
    TENANT ||--o{ KNOWLEDGE_GRAPH_INSTANCE : "owns"
    
    KNOWLEDGE_GRAPH_INSTANCE ||--o{ DOCUMENT_JOB : "processes"
    
    TENANT {
        uuid id PK
        string slug "e.g. acme-corp"
    }
    USER {
        uuid id PK
        boolean is_super_admin
    }
    TENANT_MEMBER {
        string role "Admin, Member"
    }
    KNOWLEDGE_GRAPH_INSTANCE {
        string neo4j_uri "The Silo Connection"
    }
```

## 3. The Asynchronous Extraction Pipeline

When a document is uploaded, it does not process instantly (which would time out the API). Instead, we use our AWS CDK infrastructure to process the document safely.

```mermaid
sequenceDiagram
    participant C as Client (Tenant A)
    participant API as FastAPI Gateway
    participant DB as PostgreSQL (Control Plane)
    participant SQS as AWS SQS FIFO
    participant L as Lambda (Entity Extractor)
    participant N as Neo4j (Tenant A Instance)

    C->>API: POST /upload-document (PDF)
    API->>DB: Verify API Key & Quotas
    DB-->>API: Authorized. Quota remaining: 50.
    
    API->>DB: Create DocumentJob (Status: QUEUED)
    API->>SQS: Push message (MessageGroupId: tenantA_doc1)
    API-->>C: 202 Accepted (Job ID returned)
    
    Note over SQS, L: Async Processing Begins
    SQS->>L: Trigger Execution
    L->>L: Extract Nodes via local GLiNER
    L->>L: Extract Edges via Google Gemini API
    L->>N: MERGE (Node)-[Edge]->(Node)
    
    L->>DB: Update DocumentJob (Status: COMPLETE)
```

## User Review Required
Take a look at the three diagrams above. 
1. **The High-Level Architecture** shows how the system scales.
2. **The ER Diagram** shows how the data is isolated.
3. **The Sequence Diagram** shows the asynchronous event flow.

Does this visual breakdown clarify the massive enterprise system we are constructing?
