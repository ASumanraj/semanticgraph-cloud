import pytest
from unittest.mock import MagicMock, patch

def test_sqs_resiliency_429_backoff():
    # Arrange
    mock_sqs = MagicMock()
    
    # We will assume a function `process_message` handles the LLM call and SQS logic
    from semanticgraph.resiliency import process_message
    from semanticgraph.llm import LLMError
    
    # Mock LLM to raise 429 Error
    with patch('semanticgraph.resiliency.call_agent') as mock_llm:
        mock_llm.side_effect = LLMError(status_code=429)
        
        # Act
        process_message(
            sqs_client=mock_sqs,
            queue_url="https://sqs.us-east-1.amazonaws.com/123/test",
            receipt_handle="dummy_handle",
            attempt_number=3
        )
        
        # Assert
        # Exponential backoff: e.g., 2^3 * base_delay (let's say base delay is 1, so 8 seconds)
        mock_sqs.change_message_visibility.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123/test",
            ReceiptHandle="dummy_handle",
            VisibilityTimeout=8
        )
