from unittest.mock import MagicMock, patch

from semanticgraph.application.use_cases.search_subgraph import SearchEngine

MODULE = "semanticgraph.application.use_cases.search_subgraph"


def test_global_search_uses_leiden_communities():
    graph_repo = MagicMock()
    engine = SearchEngine(graph_repo=graph_repo)

    with patch(f"{MODULE}.run_leiden_community_detection") as mock_leiden:
        mock_leiden.return_value = ["summary1", "summary2"]

        results = engine.global_search(query="What are the main themes?")

        mock_leiden.assert_called_once_with(graph_repo)
        assert results == ["summary1", "summary2"]


def test_local_search_uses_semantic_pagerank():
    graph_repo = MagicMock()
    engine = SearchEngine(graph_repo=graph_repo)

    with patch(f"{MODULE}.run_semantic_pagerank") as mock_pagerank:
        mock_pagerank.return_value = ["node_A", "node_C"]

        results = engine.local_search(query="Tell me about Node A and C", entry_nodes=["node_A"])

        mock_pagerank.assert_called_once_with(graph_repo, ["node_A"], "Tell me about Node A and C")
        assert results == ["node_A", "node_C"]
