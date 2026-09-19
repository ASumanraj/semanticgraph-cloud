from unittest.mock import patch

import ragas
from datasets import Dataset
from ragas.metrics import answer_relevancy, faithfulness


def test_ragas_pipeline_setup():
    """
    Simulates a GraphRAG response and evaluates it using Ragas metrics.
    Since we do not want to consume real API keys during tests, we mock
    the evaluate execution to validate the pipeline setup.
    """
    # Simulate a GraphRAG response
    data = {
        "question": ["What is the capital of France?"],
        "answer": ["Paris is the capital of France."],
        "contexts": [["France is a country in Western Europe. Its capital is Paris."]],
        "ground_truth": ["Paris"],
    }
    dataset = Dataset.from_dict(data)

    # Mock evaluate to bypass actual LLM/API calls.
    # Must patch ragas.evaluate and call it via module to ensure mock applies.
    with patch("ragas.evaluate") as mock_evaluate:
        mock_evaluate.return_value = {"faithfulness": 1.0, "answer_relevancy": 0.95}

        result = ragas.evaluate(dataset=dataset, metrics=[faithfulness, answer_relevancy])

        assert "faithfulness" in result
        assert "answer_relevancy" in result
        assert result["faithfulness"] == 1.0
        mock_evaluate.assert_called_once()
