from .llm import LLMError, call_agent


def process_message(sqs_client, queue_url: str, receipt_handle: str, attempt_number: int):
    try:
        call_agent()
    except LLMError as e:
        if e.status_code == 429:
            visibility_timeout = 2**attempt_number
            sqs_client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=visibility_timeout,
            )
