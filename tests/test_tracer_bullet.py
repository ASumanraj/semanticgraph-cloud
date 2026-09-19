import unittest
from unittest.mock import patch, MagicMock

from src.pipeline.agents.relationship_mapper import extract_knowledge_graph, KnowledgeGraph, Node, Edge
from src.semanticgraph.services.graph_database import GraphDatabase

class TestTracerBullet(unittest.TestCase):
    @patch('src.pipeline.agents.relationship_mapper.get_instructor_client')
    def test_extraction_and_save(self, mock_get_client):
        # Setup mock
        mock_client = MagicMock()
        
        # Create the mock returned KnowledgeGraph
        mock_graph = KnowledgeGraph(
            nodes=[
                Node(id="Steve Jobs", label="Person"),
                Node(id="Apple Inc.", label="Company")
            ],
            edges=[
                Edge(source="Steve Jobs", target="Apple Inc.", relation="FOUNDER_OF")
            ]
        )
        
        # Configure the mock to return our graph on create
        mock_client.chat.completions.create.return_value = mock_graph
        mock_get_client.return_value = mock_client

        text = "Apple Inc. was founded by Steve Jobs."
        tenant_id = "tenant-123"
        
        # Execute extraction
        graph = extract_knowledge_graph(text, tenant_id=tenant_id)
        
        # Assert Graph
        self.assertIsNotNone(graph)
        node_ids = [n.id for n in graph.nodes]
        self.assertIn("Steve Jobs", node_ids)
        self.assertIn("Apple Inc.", node_ids)
        
        edges = [(e.source, e.target, e.relation) for e in graph.edges]
        self.assertIn(("Steve Jobs", "Apple Inc.", "FOUNDER_OF"), edges)

        # Save to DB
        db = GraphDatabase()
        result = db.save_graph(graph, tenant_id=tenant_id)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
