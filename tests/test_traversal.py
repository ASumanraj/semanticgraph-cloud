import pytest
from unittest.mock import MagicMock, patch

def test_global_search_leiden():
    from semanticgraph.traversal import SearchEngine
    mock_client = MagicMock()
    engine = SearchEngine(graph_client=mock_client)
    
    with patch('semanticgraph.traversal.run_leiden_community_detection') as mock_leiden:
        mock_leiden.return_value = ["summary1", "summary2"]
        
        results = engine.global_search(query="What are the main themes?")
        
        mock_leiden.assert_called_once_with(mock_client)
        assert results == ["summary1", "summary2"]

def test_local_search_semantic_pagerank():
    from semanticgraph.traversal import SearchEngine
    mock_client = MagicMock()
    engine = SearchEngine(graph_client=mock_client)
    
    with patch('semanticgraph.traversal.run_semantic_pagerank') as mock_pagerank:
        mock_pagerank.return_value = ["node_A", "node_C"]
        
        results = engine.local_search(query="Tell me about Node A and C", entry_nodes=["node_A"])
        
        mock_pagerank.assert_called_once_with(mock_client, ["node_A"], "Tell me about Node A and C")
        assert results == ["node_A", "node_C"]
