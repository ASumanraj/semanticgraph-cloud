import pytest
from unittest.mock import patch, MagicMock
import json

from pipeline.agents.entity_extractor import extract_entities
from pipeline.agents.relationship_mapper import map_relationships

@patch('pipeline.agents.entity_extractor.GLiNER')
def test_extract_entities(mock_gliner_class):
    mock_model = MagicMock()
    mock_model.predict_entities.return_value = [
        {"text": "Apple", "label": "Company"},
        {"text": "Steve Jobs", "label": "Person"}
    ]
    mock_gliner_class.from_pretrained.return_value = mock_model

    text = "Steve Jobs founded Apple."
    labels = ["Person", "Company"]
    
    entities = extract_entities(text, labels)
    
    assert entities == [
        {"text": "Apple", "label": "Company"},
        {"text": "Steve Jobs", "label": "Person"}
    ]
    mock_gliner_class.from_pretrained.assert_called_once_with("urchade/gliner_medium-v2.1")
    mock_model.predict_entities.assert_called_once_with(text, labels)

@patch('pipeline.agents.relationship_mapper.genai')
def test_map_relationships(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    mock_response = MagicMock()
    # Mocking parsed response for structured output
    class ParsedEdge:
        def __init__(self, source, target, relation):
            self.source = source
            self.target = target
            self.relation = relation
            
    class ParsedOutput:
        def __init__(self, edges):
            self.edges = edges
            
    mock_response.parsed = ParsedOutput([ParsedEdge("Steve Jobs", "Apple", "founded")])
    mock_client.models.generate_content.return_value = mock_response

    text = "Steve Jobs founded Apple."
    nodes = [{"text": "Apple", "label": "Company"}, {"text": "Steve Jobs", "label": "Person"}]
    
    relationships = map_relationships(text, nodes)
    
    assert len(relationships) == 1
    assert relationships[0]["source"] == "Steve Jobs"
    assert relationships[0]["target"] == "Apple"
    assert relationships[0]["relation"] == "founded"
    mock_client.models.generate_content.assert_called_once()
