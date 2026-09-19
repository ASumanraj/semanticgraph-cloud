class Orchestrator:
    def __init__(self, sqs_client, queue_url: str):
        self.sqs_client = sqs_client
        self.queue_url = queue_url
        
    def process_document(self, doc_id: str, text: str):
        # minimal logic to make test pass
        self.sqs_client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=text,
            MessageGroupId=f"group_{doc_id}"
        )
