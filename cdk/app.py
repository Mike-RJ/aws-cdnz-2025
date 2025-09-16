#!/usr/bin/env python3

import aws_cdk as cdk
from time_management_app.time_management_app_stack import TimeManagementAppStack

app = cdk.App()
TimeManagementAppStack(
    app,
    "TimeManagementAppStack",
    env=cdk.Environment(account="000000000000", region="us-east-1"),
)

app.synth()
