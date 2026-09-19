from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    Duration,
    RemovalPolicy
)
from constructs import Construct

class RagStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DLQs
        ingestion_dlq = sqs.Queue(self, "IngestionDLQ", fifo=True)
        extraction_dlq = sqs.Queue(self, "ExtractionDLQ", fifo=True)
        relationships_dlq = sqs.Queue(self, "RelationshipsDLQ", fifo=True)
        resolution_dlq = sqs.Queue(self, "ResolutionDLQ", fifo=True)

        # Queues
        ingestion_queue = sqs.Queue(
            self, "IngestionQueue",
            fifo=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=ingestion_dlq
            )
        )
        extraction_queue = sqs.Queue(
            self, "ExtractionQueue",
            fifo=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=extraction_dlq
            )
        )
        relationships_queue = sqs.Queue(
            self, "RelationshipsQueue",
            fifo=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=relationships_dlq
            )
        )
        resolution_queue = sqs.Queue(
            self, "ResolutionQueue",
            fifo=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=resolution_dlq
            )
        )

        # VPC for EFS
        vpc = ec2.Vpc(self, "RagVpc", max_azs=2)

        # EFS
        file_system = efs.FileSystem(self, "RagEfs",
            vpc=vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_14_DAYS,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            removal_policy=RemovalPolicy.DESTROY
        )

        # EFS Access Point
        access_point = file_system.add_access_point("ModelAccessPoint",
            path="/models",
            create_acl=efs.Acl(owner_uid="1001", owner_gid="1001", permissions="750"),
            posix_user=efs.PosixUser(uid="1001", gid="1001")
        )

        # Lambda Function
        extraction_lambda = _lambda.Function(self, "ExtractionLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline("def handler(event, context): pass"),
            vpc=vpc,
            filesystem=_lambda.FileSystem.from_efs_access_point(access_point, "/mnt/models")
        )
        
        # Provisioned Concurrency requires a Version or Alias
        # We create an alias for it
        version = extraction_lambda.current_version
        extraction_alias = _lambda.Alias(self, "ExtractionLambdaAlias",
            alias_name="prod",
            version=version,
            provisioned_concurrent_executions=1
        )
        
        # Subscribe lambda to extraction queue
        extraction_alias.add_event_source(
            lambda_event_sources.SqsEventSource(extraction_queue)
        )
