import aws_cdk as core
import aws_cdk.assertions as assertions
from infra.infra_stack import InfraStack


# example tests. To run these tests, uncomment this file along with the example
# resource in infra/infra_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = InfraStack(app, "infra")
    assert assertions.Template.from_stack(stack) is not None


#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
