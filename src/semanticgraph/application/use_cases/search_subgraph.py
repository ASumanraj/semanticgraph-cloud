"""
Use Case: Subgraph Search.

Two retrieval modes, per ENTERPRISE_PLAN.md Part 3 (Stage 3, "Retrieve"):

- **local** — seed entities from vector search, expand the neighbourhood,
  rank by personalized PageRank, rerank, assemble context.
- **global** — Leiden communities with summaries generated on demand and
  cached, rather than eagerly for every community of every tenant.

Both are stubs. The shape is fixed here so the seam exists; Stage 3 fills them.
"""

from __future__ import annotations

from typing import Any

from semanticgraph.application.ports.outbound.graph_repository import GraphRepositoryPort
from semanticgraph.application.ports.outbound.subgraph_reader import SubgraphReader


def run_leiden_community_detection(graph_repo: SubgraphReader | GraphRepositoryPort) -> Any:
    """Global search: detect communities, then summarize the relevant ones lazily."""


def run_semantic_pagerank(
    graph_repo: SubgraphReader | GraphRepositoryPort, entry_nodes: list, query: str
) -> Any:
    """Local search: personalized PageRank outward from the seed entities."""


class SearchEngine:
    """Deep module: one entry point per retrieval mode, everything else hidden."""

    def __init__(
        self,
        graph_repo: SubgraphReader | GraphRepositoryPort | None = None,
        subgraph_reader: SubgraphReader | None = None,
    ) -> None:
        reader = subgraph_reader or graph_repo
        if reader is None:
            raise ValueError("Must provide either subgraph_reader or graph_repo")
        self.graph_repo = reader
        self.subgraph_reader = reader

    def global_search(self, query: str) -> Any:
        return run_leiden_community_detection(self.graph_repo)

    def local_search(self, query: str, entry_nodes: list) -> Any:
        return run_semantic_pagerank(self.graph_repo, entry_nodes, query)
