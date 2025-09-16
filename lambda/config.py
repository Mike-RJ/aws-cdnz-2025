#!/usr/bin/env python3

import json

import boto3

ssm = boto3.client("ssm")


def lambda_handler(event, context):
    """
    Returns the API endpoint from Parameter Store
    """
    try:
        # Get the API endpoint from Parameter Store
        parameter = ssm.get_parameter(Name="/time-management-app/api-endpoint")
        api_endpoint = parameter["Parameter"]["Value"]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "body": json.dumps({"apiEndpoint": api_endpoint}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "body": json.dumps({"error": str(e)}),
        }
