#!/usr/bin/env python3
import os

import aws_cdk as cdk

from lambda_datasci_perf.lambda_datasci_perf_stack import LambdaDatasciPerfStack


app = cdk.App()
LambdaDatasciPerfStack(app, "LambdaDatasciPerfStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)

app.synth()
