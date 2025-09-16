from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class SimpleTimeManagementAppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB Table
        table = dynamodb.Table(
            self,
            "TimeEntriesTable",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Lambda Function
        lambda_function = _lambda.Function(
            self,
            "TimeManagementFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("../lambda"),
            handler="app.lambda_handler",
            environment={"TABLE_NAME": table.table_name},
            timeout=Duration.seconds(30),
        )

        # Grant permissions
        table.grant_read_write_data(lambda_function)

        # API Gateway - simple version
        api = apigateway.LambdaRestApi(
            self,
            "TimeManagementApi",
            handler=lambda_function,
            rest_api_name="time-management-api",
            description="API for Time Management Application",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                ],
            ),
        )

        # S3 Bucket for Frontend
        bucket = s3.Bucket(
            self,
            "TimeManagementFrontendBucket",
            website_index_document="index.html",
            public_read_access=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Deploy frontend to S3
        s3deploy.BucketDeployment(
            self,
            "DeployFrontend",
            sources=[s3deploy.Source.asset("../frontend")],
            destination_bucket=bucket,
        )

        # Outputs
        CfnOutput(
            self, "ApiEndpoint", value=api.url, description="API Gateway endpoint URL"
        )
        CfnOutput(
            self,
            "FrontendURL",
            value=f"http://{bucket.bucket_name}.s3-website-{self.region}.amazonaws.com",
            description="Frontend URL",
        )
