#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.rag_stack import RagStack

app = cdk.App()
RagStack(app, "RagStack")
app.synth()
