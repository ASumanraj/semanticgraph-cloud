from unittest.mock import MagicMock, patch

import pytest

from semanticgraph.application.use_cases.search_subgraph import SearchEngine

MODULE = "semanticgraph.application.use_cases.search_subgraph"


def test_global_search_uses_leiden_communities():
    reader = MagicMock()
    engine = SearchEngine(subgraph_reader=reader)

    with patch(f"{MODULE}.run_leiden_community_detection") as mock_leiden:
        mock_leiden.return_value = ["summary1", "summary2"]

        results = engine.global_search(query="What are the main themes?")

        mock_leiden.assert_called_once_with(reader)
        assert results == ["summary1", "summary2"]


def test_local_search_uses_semantic_pagerank():
    reader = MagicMock()
    engine = SearchEngine(subgraph_reader=reader)

    with patch(f"{MODULE}.run_semantic_pagerank") as mock_pagerank:
        mock_pagerank.return_value = ["node_A", "node_C"]

        results = engine.local_search(query="Tell me about Node A and C", entry_nodes=["node_A"])

        mock_pagerank.assert_called_once_with(reader, ["node_A"], "Tell me about Node A and C")
        assert results == ["node_A", "node_C"]


def test_search_engine_missing_dependency_raises_type_error():
    with pytest.raises(TypeError):
        SearchEngine()  # type: ignore[call-arg]
