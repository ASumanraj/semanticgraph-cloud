from unittest.mock import MagicMock


def test_orchestrator_chunk_and_push():
    # Arrange
    from semanticgraph.orchestrator import Orchestrator

    mock_sqs = MagicMock()
    orchestrator = Orchestrator(
        sqs_client=mock_sqs, queue_url="https://sqs.us-east-1.amazonaws.com/123/fifo.fifo"
    )

    document = "This is a long document that needs to be chunked. " * 10
    doc_id = "doc_123"

    # Act
    orchestrator.process_document(doc_id=doc_id, text=document)

    # Assert
    # Assert SQS send_message is called at least once
    assert mock_sqs.send_message.call_count > 0

    # Check that MessageGroupId is deterministic
    # The expected deterministic MessageGroupId might be based on doc_id
    call_args = mock_sqs.send_message.call_args_list[0][1]
    assert call_args["MessageGroupId"] == f"group_{doc_id}"
