# ECC AWS Infrastructure Specifications: GraphRAG AGY Pipeline

This document details the architectural strategies for mitigating cold-start latencies in serverless environments for heavy NLP models, and guaranteeing exactly-once processing resiliency in the face of upstream LLM rate limits.

## 1. Serverless Cold Start Mitigation for NLP Extraction Agents

Running heavyweight NLP extraction models (e.g., GLiNER, large spaCy pipelines) on serverless compute (AWS Lambda or AWS Fargate) introduces significant cold-start latency due to both container image retrieval and the CPU/memory overhead of loading gigabytes of model weights into RAM.

### AWS Fargate Mitigation Strategies
*   **Seekable OCI (SOCI) Lazy Loading:** Fargate supports SOCI for images stored in Amazon ECR. Instead of downloading the full multi-gigabyte container image before task startup, SOCI creates a file-to-byte-range index (SOCI Index Manifest v2) stored as an OCI referrer artifact. Fargate detects this index and lazy-loads only the necessary binaries and dependencies required to reach the `ENTRYPOINT`, severely reducing the `PENDING` state duration.
*   **Amazon EFS Model Mounts:** Rather than baking the model weights into the Docker image (which inflates the image size), store the GLiNER/spaCy weights on an Amazon EFS filesystem provisioned with **Provisioned Throughput**. Mount the EFS volume to the Fargate tasks.
*   **Memory-mapped Loading (mmap):** When loading the model from EFS, utilize memory-mapped file I/O (`mmap`). This allows the OS to page model weights into memory on demand rather than blocking the CPU to load the entire multi-gigabyte file upfront.

### AWS Lambda Mitigation Strategies
*   **Container Image Streaming:** Lambda natively supports container images up to 10GB. Under the hood, Lambda uses a block-level caching and streaming mechanism similar to SOCI.
*   **Provisioned Concurrency:** To bypass the initialization penalty entirely, utilize **Provisioned Concurrency**. This keeps a specified number of execution environments fully initialized (including running the initialization code outside the handler where the NLP model is loaded into memory).
*   **Global Scope Initialization:** Ensure the model loading logic resides in the global scope (outside the `handler` function). During a cold start (or during Provisioned Concurrency initialization), the model is loaded into memory once and reused across all warm invocations.

## 2. SQS Resiliency, Deduplication, and Rate Limiting (HTTP 429)

When the Antigravity Relationship Mapper agent queries upstream LLMs (e.g., OpenAI, Anthropic) and receives HTTP 429 (Too Many Requests) rate limits, the queueing architecture must guarantee zero data loss and prevent duplicate node/edge generation in Neo4j.

### Queue Architecture: SQS FIFO
To guarantee exactly-once processing and strict ordering, use **SQS FIFO queues** (`.fifo`).
*   **MessageGroupId:** Set the `MessageGroupId` to the source document ID or entity ID. This ensures that SQS delivers messages belonging to the same document strictly in order and prevents parallel processing of the same entity, avoiding concurrent Neo4j write conflicts.
*   **MessageDeduplicationId:** Generate a deterministic SHA-256 hash of the extraction payload and use it as the `MessageDeduplicationId`. SQS FIFO will drop any duplicate messages sent within a 5-minute deduplication window.

### Handling HTTP 429 & Exponential Backoff
SQS does not natively implement exponential backoff for retries; it uses a static Visibility Timeout. If a Lambda consumer simply fails, the message reappears at a constant rate, potentially worsening the 429 rate limit.
*   **Dynamic Visibility Timeout Modulation:** When the agent catches an HTTP 429, it must read the `Retry-After` header. The consumer should immediately call the `ChangeMessageVisibility` SQS API to set the message's visibility timeout to match the backoff duration (with added jitter). If no header is present, compute an exponential backoff (`base_delay * 2^attempt + jitter`) and update the visibility. The function can then exit gracefully (returning success for that message in a partial batch response) to avoid triggering an immediate retry.
*   **Lambda Reserved Concurrency:** Actively prevent 429s by setting a strict `ReservedConcurrentExecutions` limit on the consumer Lambda, mathematically aligning it with the upstream LLM provider's Requests Per Minute (RPM) quota.

### DLQ Redrive Policies and Neo4j Idempotency
*   **Dead Letter Queue (DLQ):** Configure a `maxReceiveCount` (e.g., 5). If the model consistently fails to process the message (e.g., sustained LLM outage), SQS routes it to a FIFO DLQ.
*   **DLQ Redrive:** Use the native SQS DLQ redrive capability to move messages back to the source queue once the upstream API health is restored.
*   **Neo4j Cypher Idempotency:** Despite SQS FIFO exactly-once delivery semantics, network partitions can cause Lambda to successfully write to Neo4j but fail to delete the SQS message. Ensure all Cypher writes are idempotent using `MERGE` statements on uniquely constrained Node properties (e.g., `MERGE (n:Entity {id: $id})`), completely eliminating the risk of duplicate nodes or edges.
